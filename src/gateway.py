"""OmniRoute brain adapter — the only module that speaks LLM wire format.

3-tier model chains (ADR-16) walked per request; free-pool survival: quota ->
immediate fallback, transient -> capped-backoff retries, fatal -> loud stop.
STT-3 (2026-09-04): a 429 that ANNOUNCES its recovery window («try again in
17m25s», Retry-After) skips the model for that window (capped) instead of
burning fast retries against a server-side wall — the rest of the chain still
serves the turn.
"""

import asyncio
import json
import math
import re
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal, Self

import httpx
from loguru import logger

from src.gender_pipeline import normalize_masculine_address

RETRY_ATTEMPTS: Final[int] = 3
BACKOFF_BASE_S: Final[float] = 0.5
BACKOFF_CAP_S: Final[float] = 8.0
REQUEST_TIMEOUT_S: Final[float] = 120.0
# STT-3: a model that announced a recovery window is skipped for
# min(window, cap) — the cap keeps a bogus giant window from retiring a model
# for hours.
COOLDOWN_CAP_S: Final[float] = 1200.0

_sleep: Final = asyncio.sleep  # test seam; monkeypatched to instant in backoff tests


class Tier(str, Enum):
    """Brain tier per ADR-16: FAST reflex/ack, MEDIUM tool execution, HEAVY planning."""

    FAST = "fast"
    MEDIUM = "medium"
    HEAVY = "heavy"


class GatewayError(RuntimeError):
    pass


class PaidModelBlockedError(GatewayError):
    """$0.00 hard circuit breaker: a non-free model ID reached the dispatch
    edge. Raised BEFORE any request is built or sent — the turn stops loud
    instead of billing the owner's account."""


#: Provider prefixes whose keys the owner holds on OmniRoute itself, with no
#: billing account attached to the gateway. Dispatch through them costs $0 and
#: CANNOT silently become paid: quota exhaustion returns 429, it never bills.
#: Owner decision 2026-10-03.
#:
#: This is a STATIC allow-list on purpose. A config-driven list would replace
#: "this provider is free by construction" with "the owner configured it", and
#: having a key is not the same claim as being free — that weakening is exactly
#: what the guard exists to prevent.
FREE_TIER_PREFIXES: Final[tuple[str, ...]] = ("groq/", "gemini/")


#: Hard per-provider DAILY call ceiling — the backstop behind `assert_zero_paid_model`.
#:
#: The prefix guard proves a model is FREE BY CONSTRUCTION. This proves the
#: volume stays inside what a free tier will serve, so a runaway loop cannot
#: turn "free" into a quota wall (and, on any provider where quota maps to a
#: bill, into a charge). Fail-safe: when the ceiling is reached the call is
#: REFUSED before the request is built, loudly, and the cascade moves to the
#: next model in the chain.
#:
#: Sourced from the free tiers' published daily allowances, deliberately
#: conservative so the guard fires BEFORE the provider's own limit rather than
#: after. Owner decision 2026-10-03.
FREE_TIER_DAILY_CALL_CEILING: Final[int] = 400

#: Calls claimed per provider per UTC day. Process-local and deliberately so:
#: a restart must not silently restore a budget that was already spent, and an
#: in-memory counter cannot be inflated by a second process.
_DAILY_CALLS: dict[str, int] = {}
_DAILY_DAY: Final[str] = ""


def _claim_daily_budget(model: str) -> None:
    """Count one call against its provider's daily ceiling, or refuse.

    Raises `PaidModelBlockedError` — the SAME type the free-tier guard raises —
    so a ceiling refusal is handled by exactly the code path that already
    handles "this model cannot be used", and the cascade falls through to the
    next chain entry instead of failing the turn.
    """
    global _DAILY_DAY
    from datetime import UTC, datetime

    provider = model.split("/", 1)[0] if "/" in model else model
    today = datetime.now(UTC).date().isoformat()
    if today != _DAILY_DAY:
        _DAILY_DAY = today
        _DAILY_CALLS.clear()
    used = _DAILY_CALLS.get(provider, 0)
    if used >= FREE_TIER_DAILY_CALL_CEILING:
        raise PaidModelBlockedError(
            f"daily free-tier ceiling reached for provider {provider!r} "
            f"({used}/{FREE_TIER_DAILY_CALL_CEILING} calls today, UTC) — refusing before "
            "the wire so a runaway loop cannot reach a quota wall"
        )
    _DAILY_CALLS[provider] = used + 1


def assert_zero_paid_model(model: str) -> None:
    """Unconditional free-tier proof for one model ID.

    Passes when the ID is `:free`-suffixed (an OpenRouter free slug), or carries
    a prefix in `FREE_TIER_PREFIXES` (a gateway-held key on a provider with no
    billing attached). Everything else raises `PaidModelBlockedError`.

    The guard is deliberately STRUCTURAL and unconditional: it runs before any
    request is built, so a paid model can never reach the network even once.
    Adding a prefix is a deliberate act with a stated reason, never a default.
    """
    candidate = (model or "").strip()
    if candidate.endswith(":free"):
        return
    # A prefix only counts when the whole ID sits under it: `gemini/` may not
    # become a back door for `gemini/<model>:paid`.
    tail = candidate.split("/", 1)[1] if "/" in candidate else ""
    if not tail.endswith(":paid") and any(
        candidate.startswith(prefix) for prefix in FREE_TIER_PREFIXES
    ):
        return
    raise PaidModelBlockedError(
        f"non-free model blocked before network: {candidate!r} "
        "(only ':free' slugs or gateway-held free-tier prefixes "
        f"{FREE_TIER_PREFIXES} may dispatch)"
    )


# Dynamic routing matrix (2026-09-12): the HEAVY lane escalates past the
# concurrency threshold (or on explicit DAG swarms) to the MoE orchestrator.
HEAVY_CONCURRENCY_THRESHOLD_DEFAULT: Final[int] = 3


def select_heavy_chain(
    base_chain: Sequence[str],
    escalated_chain: Sequence[str],
    n_tasks: int = 1,
    *,
    is_dag_swarm: bool = False,
    threshold: int = HEAVY_CONCURRENCY_THRESHOLD_DEFAULT,
) -> list[str]:
    """Pure concurrency-aware HEAVY selector (hermetic-test seam)."""
    if is_dag_swarm or n_tasks > threshold:
        return list(escalated_chain or base_chain)
    return list(base_chain)


class ConcurrencyTracker:
    """Live gauge of concurrent HEAVY operations; escalation is advisory and
    never blocks admission (degraded chains still serve the turn)."""

    def __init__(self, threshold: int = HEAVY_CONCURRENCY_THRESHOLD_DEFAULT) -> None:
        self.threshold = threshold
        self._active = 0
        self.escalations = 0

    @property
    def active(self) -> int:
        return self._active

    def acquire(self, n: int = 1) -> int:
        self._active += max(n, 0)
        return self._active

    def release(self, n: int = 1) -> int:
        self._active = max(0, self._active - max(n, 0))
        return self._active

    def should_escalate(self, *, is_dag_swarm: bool = False) -> bool:
        escalate = is_dag_swarm or self._active > self.threshold
        if escalate:
            self.escalations += 1
        return escalate


class _QuotaExhausted(RuntimeError):
    pass


class _EmptyReply(RuntimeError):
    """A model streamed [DONE] with zero content deltas (reasoning-only or
    blank turn) — serving blank would poison the reply; the next model in
    the chain serves instead (immediate fallback, no retry burn)."""


class _TransientFailure(RuntimeError):
    pass


class _ModelUnavailable(RuntimeError):
    """Model-level fatal (400/404/422: unknown slug, bad params) — the NEXT
    model may live on another provider, so fall back instead of aborting.
    Auth failures (401/403) still abort: the whole gateway is suspect."""


class _FirstTokenTimeout(RuntimeError):
    """FAST fail-fast (live 2026-09-14): the attempt streamed zero content
    deltas within FIRST_TOKEN_TIMEOUT_S — a throttled endpoint stalls instead
    of answering. Abort the attempt, quarantine the stall, cascade now."""


class _WindowRateLimit(RuntimeError):
    """429 whose body/header ANNOUNCES the recovery window — the model is hot
    for that window; the rest of the chain serves the turn."""

    def __init__(self, detail: str, window_s: float) -> None:
        super().__init__(detail)
        self.window_s = window_s


# STT-3: model -> epoch-s until it may be probed again (process-wide; the
# live groq TPD 429 burned 3 retries x N models EVERY turn for 17 minutes).
_MODEL_COOLDOWNS: dict[str, float] = {}

# Fail-fast (2026-09-13 tuning): consecutive UNANNOUNCED 429s mark the model
# hot without waiting for an announced window — sustained free-pool throttle
# episodes stop burning 3 attempts every turn. Success resets the streak.
# Live 2026-09-14: a throttled primary stalled a greeting ~3min. The
# quarantine is now 15 minutes (THROTTLE_QUARANTINE_S): one throttle episode
# parks the model for the whole episode and the stable candidate serves FAST
# turns at turn zero with zero network calls to the hot model.
BARE_429_SKIP_AFTER: Final[int] = 2
THROTTLE_QUARANTINE_S: Final[float] = 15 * 60.0
BARE_429_COOLDOWN_S: Final[float] = THROTTLE_QUARANTINE_S
# Empty streams ([DONE] with zero content deltas) park the model just as
# long — a blank-serving model must not eat a turn every time.
EMPTY_REPLY_COOLDOWN_S: Final[float] = THROTTLE_QUARANTINE_S
# FAST first-token guillotine (live 2026-09-14): a FAST attempt that streams
# no content delta within this window is aborted and cascaded — the owner
# never waits on a stalled endpoint. MEDIUM/HEAVY keep their patience.
FIRST_TOKEN_TIMEOUT_S: Final[float] = 4.0
FIRST_TOKEN_STALL_COOLDOWN_S: Final[float] = THROTTLE_QUARANTINE_S
# Streak entries evaporate: a 429 from long ago must not skip a healthy model.
BARE_429_STREAK_TTL_S: Final[float] = 300.0
_429_STREAK: dict[str, tuple[int, float]] = {}  # model -> (streak, last epoch)

_RETRY_WINDOW_RE: Final = re.compile(
    r"(?:try\s+again\s+in|retry\s+in|reset\s+(?:after|in))\s+"
    r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+(?:\.\d+)?)\s*s)?",
    re.IGNORECASE,
)


def parse_retry_window_s(body: str, *, retry_after: str | None = None) -> float | None:
    """Seconds until the provider says it will serve again: the
    «try again in Xh Ym Zs» / «retry in Xs» body forms, a numeric Retry-After
    header, or the proxy's «(reset after Xs)» / «reset in Xs» phrasing (live
    2026-09-14: the hop surfaces throttles exactly that way after holding the
    stream ~107s). None = nothing announced (fast transient retries stay)."""
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass  # HTTP-date form: providers we use send seconds; ignore the rest
    match = _RETRY_WINDOW_RE.search(body or "")
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    parts = [float(g or 0) for g in (hours, minutes, seconds)]
    window = parts[0] * 3600 + parts[1] * 60 + parts[2]
    return window or None


def _note_bare_429(model: str) -> bool:
    """Count one unannounced 429 for the fail-fast skip. Returns True when the
    streak trips: the model is marked hot and the caller must fall back now
    instead of burning another ~25s attempt. Stale streaks evaporate (TTL);
    success resets via pop at the _stream success path."""
    now = time.time()
    count, last = _429_STREAK.get(model, (0, 0.0))
    if now - last > BARE_429_STREAK_TTL_S:
        count = 0
    count += 1
    if count >= BARE_429_SKIP_AFTER:
        _429_STREAK[model] = (0, now)
        _MODEL_COOLDOWNS[model] = now + BARE_429_COOLDOWN_S
        return True
    _429_STREAK[model] = (count, now)
    return False


def _model_hot(model: str) -> float | None:
    """Remaining cooldown on a model, or None when it may be probed."""
    until = _MODEL_COOLDOWNS.get(model)
    if until is None or until <= time.time():
        _MODEL_COOLDOWNS.pop(model, None)
        return None
    return until - time.time()


def any_quarantined() -> bool:
    """True while any model sits in cooldown (P3 budget coupling reads this to
    halve the RAG block ceiling instead of feeding a throttled turn)."""
    now = time.time()
    return any(until > now for until in _MODEL_COOLDOWNS.values())


def _classify(
    status_code: int, body_snippet: str
) -> Literal["fatal", "quota", "transient", "window", "unavailable"]:
    if status_code in (401, 403):
        return "fatal"  # credential-level: the whole gateway is suspect, abort
    if status_code in (400, 404, 422):
        return "unavailable"  # model-level: next model may live elsewhere, fall back
    if status_code == 402:
        return "quota"
    if status_code == 429:
        if any(
            m in body_snippet.lower()
            for m in ("quota", "exhausted", "insufficient", "credit", "billing")
        ):
            return "quota"
        if parse_retry_window_s(body_snippet) is not None:
            return "window"
        return "transient"
    if status_code in (408, 409, 425) or status_code >= 500:
        return "transient"
    return "fatal"


_EMBEDDED_STATUS: Final = re.compile(r"\[(\d{3})\]")

#: Structured rate-limit vocabulary. Matched as SUBSTRINGS of a lower-cased
#: `type`/`code`, so a provider that namespaces its own values (`model_cooldown`,
#: `gemini_model_cooldown`, `rate_limit_exceeded`) still reads as what it is.
_SSE_RATE_LIMIT_TYPES: Final[tuple[str, ...]] = ("rate_limit", "insufficient_quota")
_SSE_RATE_LIMIT_CODES: Final[tuple[str, ...]] = ("cooldown", "rate_limit", "throttl")
#: Auth-shaped codes recover 401 so the loud stop keeps its honest status instead
#: of the invented `0`. BEHAVIOUR-PRESERVING, not a widening: `_classify(401)`
#: returns "fatal" (:313-314) exactly as `_classify(0)` does (:330), so every one
#: of these shapes stops just as loudly — only the number in the message is real.
_SSE_AUTH_CODES: Final[tuple[str, ...]] = (
    "auth",
    "forbidden",
    "permission",
    "invalid_api_key",
    "unauthorized",
    "invalid_token",
)


@dataclass(frozen=True, slots=True)
class _SseErrorSignal:
    """What one SSE ``error`` event actually said.

    ``status`` is the status the PROVIDER stated, recovered from its structured
    fields, falling back to the prose bracket. ``window_s`` is the recovery window
    it announced, already clamped; ``None`` means it announced none, which is a
    real distinction and not a failure to parse.
    """

    status: int
    window_s: float | None
    message: str


def _sse_seconds(value: object) -> float | None:
    """A number a server sent as a duration, or ``None`` when it sent nothing
    usable. ``nan``/``inf`` are rejected here rather than defended against at each
    call site: they parse as floats and would defeat every clamp downstream — a
    ``nan`` window parks a model for ``time.time() + nan``, which is never now.
    Zero is ``None`` too: it means «retry now», never a zero-length window.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0.0:
        return None
    return seconds


def _sse_error_signal(error: object) -> _SseErrorSignal:
    """Recover the status and the recovery window from ONE SSE error payload.

    PURE BY CONTRACT, and the contract is the point: a payload in, a verdict out.
    No client, no I/O, no sleeping, no clock. That is what lets the decision be
    read from the signature and the body rather than trusted from a docstring,
    and it keeps the whole classification in one place instead of scattered
    through the streaming loop.

    THE LADDER, and the order IS the argument. A structured field is something the
    provider SENT about this event; the prose bracket is something we GUESSED out
    of a sentence. A guess never overrides a field.

    1. A non-mapping payload is «no signal» — not an ``AttributeError``. The old
       inline ``.get("message", ...)`` raised out of the stream on a bare string.
    2. ``type`` naming a rate limit is 429, and nothing demotes it — a missing or
       malformed window does not make a declared throttle less of one.
    3. ``code`` naming a cooldown / rate limit is 429.
    4. ``type``/``code`` naming an AUTH condition is 401 (see _SSE_AUTH_CODES).
    5. The WINDOW, and only for a 429: ``reset_seconds`` when it is a finite
       positive number, else the prose parser. Clamped to COOLDOWN_CAP_S.
       ``THROTTLE_QUARANTINE_S`` is deliberately NOT the cap: it is the client's
       policy for evidence it does NOT have (the bare-429 streak, an empty
       stream, a first-token stall). An announced provider window is the opposite
       case — the client HAS the number — so padding 48 s up to 15 minutes would
       retire a model that recovers in under a minute.
    6. The prose bracket, DEMOTED to last.

    THE DEFAULT FAILS SAFE. With nothing recovered the status is 0, which
    classifies «fatal» and produces the loud stop with its ``[0]`` intact — the
    gateway honestly reporting that it could not find a status. This predicate
    therefore CANNOT invent a cascade out of an unrecognised error: the unknown
    case is exactly the case it leaves alone.
    """
    if not isinstance(error, Mapping):
        return _SseErrorSignal(0, None, str(error))

    message = str(error.get("message", error))
    kind = f"{error.get('type', '')} {error.get('code', '')}".lower()

    if any(marker in kind for marker in _SSE_RATE_LIMIT_TYPES + _SSE_RATE_LIMIT_CODES):
        status = 429
    elif any(marker in kind for marker in _SSE_AUTH_CODES):
        return _SseErrorSignal(401, None, message)
    else:
        match = _EMBEDDED_STATUS.search(message)
        status = int(match.group(1)) if match else 0

    window: float | None = None
    if status == 429:
        window = _sse_seconds(error.get("reset_seconds"))
        if window is None:
            window = parse_retry_window_s(message)
        if window is not None:
            window = min(window, COOLDOWN_CAP_S)
    return _SseErrorSignal(status, window, message)


def _http_declared_window(body: str, status_code: int) -> float | None:
    """The recovery window a NON-200 body declared about a rate limit, or None.

    PURE BY CONTRACT, like `_sse_error_signal`, and for the same reason: the
    decision is one readable site instead of a conditional inside the streaming
    loop. A payload in, a clamped number or None out.

    NARROWER THAN ITS SSE SIBLING, ON PURPOSE. Here the body is available as raw
    text, not as a parsed mapping, so a body's several shapes can disagree with
    each other and this function has no parsed field to arbitrate with. It
    therefore refuses to guess at all: it reads a status and a window that the
    SAME nested error object agrees on, and returns None whenever the body cannot
    be parsed or says nothing unambiguous. None is the safe answer twice over —
    it leaves the classification below this line exactly as it was.
    """
    if status_code != 429:
        return None
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return None
    kind = f"{error.get('type', '')} {error.get('code', '')}".lower()
    if not any(marker in kind for marker in _SSE_RATE_LIMIT_TYPES + _SSE_RATE_LIMIT_CODES):
        return None
    window = _sse_seconds(error.get("reset_seconds"))
    return None if window is None else min(window, COOLDOWN_CAP_S)


def _raise_for_gateway_error(
    model: str,
    kind: str,
    source: str,
    detail: str,
    *,
    retry_after: str | None = None,
) -> None:
    if kind == "quota":
        raise _QuotaExhausted(f"{source}: {detail}")
    if kind == "unavailable":
        raise _ModelUnavailable(f"{source}: {detail}")
    if kind == "window":
        window = parse_retry_window_s(detail, retry_after=retry_after)
        assert window is not None, "window classification without a parseable window"
        raise _WindowRateLimit(f"{source}: {detail}", window_s=min(window, COOLDOWN_CAP_S))
    if kind == "transient":
        raise _TransientFailure(f"{source}: {detail}")
    logger.error("gateway fatal | model={} {} :: {}", model, source, detail)
    raise GatewayError(f"fatal {source} on {model}: {detail}")


class OmniRouteClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        chains: Mapping[Tier, Sequence[str]],
        timeout_s: float = REQUEST_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        escalated_heavy_chain: Sequence[str] | None = None,
        concurrency_threshold: int = HEAVY_CONCURRENCY_THRESHOLD_DEFAULT,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
            transport=transport,
        )
        self._chains: dict[Tier, list[str]] = {
            tier: list(models) for tier, models in chains.items()
        }
        self._escalated_heavy: list[str] = list(escalated_heavy_chain or [])
        self.tracker = ConcurrencyTracker(threshold=concurrency_threshold)

    def heavy_chain_for(self, n_tasks: int = 1, *, is_dag_swarm: bool = False) -> list[str]:
        """Concurrency-aware HEAVY chain: base orchestrator at/below threshold,
        MoE escalation beyond (or on DAG swarms). Falls back to base when no
        escalation chain is configured."""
        return select_heavy_chain(
            self._chains.get(Tier.HEAVY, []),
            self._escalated_heavy or self._chains.get(Tier.HEAVY, []),
            n_tasks,
            is_dag_swarm=is_dag_swarm,
            threshold=self.tracker.threshold,
        )

    def stream_heavy(
        self,
        messages: list[dict[str, str]],
        *,
        n_tasks: int = 1,
        is_dag_swarm: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """HEAVY streaming through the escalation-selected chain (logged)."""
        chain = self.heavy_chain_for(n_tasks, is_dag_swarm=is_dag_swarm)
        escalated = bool(chain and self._escalated_heavy and chain[0] == self._escalated_heavy[0])
        logger.bind(n_tasks=n_tasks, dag=is_dag_swarm, escalated=escalated).info(
            "gateway heavy route (escalated={})", escalated
        )
        return self._stream(
            chain, messages, temperature=temperature, max_tokens=max_tokens, tier=Tier.HEAVY
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = Tier.FAST,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Stream through the tier's own fallback chain (ADR-16 order)."""
        return self._stream(
            self._chains[tier],
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tier=tier,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tier: Tier = Tier.FAST,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        parts: list[str] = []
        async for delta in self.stream_chat(
            messages, tier=tier, temperature=temperature, max_tokens=max_tokens
        ):
            parts.append(delta)
        # Gender shield (mission 2026-09-13): normalize 2nd-person address to
        # masculine (Omar) on the aggregated reply. JSON-safe by construction:
        # verdict keys are English and third-person nouns (أختي/أمي) match no
        # rule — only addressee-directed feminine verb forms rewrite.
        return normalize_masculine_address("".join(parts))

    @staticmethod
    async def _first_token_guarded(
        model: str, attempt: AsyncIterator[str], timeout_s: float
    ) -> AsyncIterator[str]:
        """FAST guillotine wrapper: the first content delta must arrive within
        timeout_s or the attempt dies here (caller quarantines + cascades).
        A generator that simply ENDS with zero deltas is an empty reply, not
        a success — it raises _EmptyReply instead of surfacing silence."""
        it = attempt.__aiter__()
        try:
            async with asyncio.timeout(timeout_s):
                first = await it.__anext__()
        except TimeoutError:
            await attempt.aclose()
            raise _FirstTokenTimeout(
                f"{model} streamed zero deltas in {timeout_s:.0f}s — cascade"
            ) from None
        except StopAsyncIteration:
            raise _EmptyReply(f"{model} closed stream with zero content deltas") from None
        yield first
        async for content in it:
            yield content

    async def _stream(
        self,
        chain: Sequence[str],
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        tier: Tier | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # FAST-only guillotine: stalled endpoints never hold a reflex turn.
        first_token_timeout = FIRST_TOKEN_TIMEOUT_S if tier is Tier.FAST else None
        last_cause = "unknown"
        hot_skips: list[str] = []
        for model in chain:
            remaining = _model_hot(model)
            if remaining is not None:
                logger.info("gateway skip hot model {} (cooldown {:.0f}s left)", model, remaining)
                hot_skips.append(model)
                continue
            delay = BACKOFF_BASE_S
            for attempt in range(1, RETRY_ATTEMPTS + 1):
                deltas = 0
                try:
                    attempt_gen = self._attempt(model, payload)
                    if first_token_timeout is not None:
                        attempt_gen = self._first_token_guarded(
                            model, attempt_gen, first_token_timeout
                        )
                    async for content in attempt_gen:
                        deltas += 1
                        yield content
                    _429_STREAK.pop(model, None)  # served: throttle streak resets
                    return
                except _QuotaExhausted as exc:
                    logger.info(
                        "gateway quota | model={} attempt={} -> immediate fallback", model, attempt
                    )
                    last_cause = str(exc)
                    break
                except _ModelUnavailable as exc:
                    # 2026-09-13 tuning: model-level fatal (unknown slug on this
                    # provider) — the next model may live elsewhere, fall back.
                    logger.warning(
                        "gateway model unavailable | model={} -> immediate fallback", model
                    )
                    last_cause = str(exc)
                    break
                except _EmptyReply as exc:
                    # 2026-09-13 audit: blank turns never retry blindly — the
                    # next model serves this turn immediately. 2026-09-14: the
                    # blank-serving model is also parked for the quarantine —
                    # it must not eat a turn every time.
                    _MODEL_COOLDOWNS[model] = time.time() + EMPTY_REPLY_COOLDOWN_S
                    logger.warning(
                        "gateway empty reply | model={} -> quarantine + immediate fallback",
                        model,
                    )
                    last_cause = str(exc)
                    break
                except _FirstTokenTimeout as exc:
                    # FAST guillotine tripped: no retry against a stalled
                    # endpoint — park it for the quarantine and cascade now.
                    _MODEL_COOLDOWNS[model] = time.time() + FIRST_TOKEN_STALL_COOLDOWN_S
                    logger.warning(
                        "gateway first-token timeout | model={} -> quarantine + cascade",
                        model,
                    )
                    last_cause = str(exc)
                    break
                except _WindowRateLimit as exc:
                    # STT-3: the provider announced its recovery window — retrying
                    # against a server-side wall is pure waste. Mark the model hot
                    # for the window and let the NEXT model serve this turn.
                    if deltas > 0:
                        raise GatewayError(
                            f"mid-stream rate limit on {model} after {deltas} deltas: {exc}"
                        ) from exc
                    _MODEL_COOLDOWNS[model] = time.time() + exc.window_s
                    last_cause = str(exc)
                    logger.warning(
                        "gateway rate-window | model={} window={:.0f}s -> model hot, "
                        "next model serves",
                        model,
                        exc.window_s,
                    )
                    break
                except _TransientFailure as exc:
                    if deltas > 0:
                        # A partial answer must never be restarted: on a voice turn
                        # the owner would hear the same reply twice. Same contract the
                        # transport branch below honours.
                        raise GatewayError(
                            f"mid-stream failure on {model} after {deltas} deltas: {exc}"
                        ) from exc
                    last_cause = str(exc)
                    if attempt < RETRY_ATTEMPTS:
                        logger.warning(
                            "gateway transient | model={} attempt={} retry in {:.1f}s: {}",
                            model,
                            attempt,
                            delay,
                            exc,
                        )
                        await _sleep(delay)
                        delay = min(delay * 2, BACKOFF_CAP_S)
                    else:
                        logger.warning(
                            "gateway transient exhausted | model={} attempts={} :: {}",
                            model,
                            RETRY_ATTEMPTS,
                            exc,
                        )
                except httpx.HTTPError as exc:
                    if deltas > 0:
                        # Never restart a partially-yielded reply — owner would see duplicates.
                        logger.error(
                            "gateway mid-stream failure | model={} deltas={} :: {}",
                            model,
                            deltas,
                            exc,
                        )
                        raise GatewayError(
                            f"mid-stream failure on {model} after {deltas} deltas: {exc}"
                        ) from exc
                    last_cause = f"transport: {exc}"
                    if attempt < RETRY_ATTEMPTS:
                        logger.warning(
                            "gateway transport error | model={} attempt={} retry in {:.1f}s: {}",
                            model,
                            attempt,
                            delay,
                            exc,
                        )
                        await _sleep(delay)
                        delay = min(delay * 2, BACKOFF_CAP_S)
                    else:
                        logger.warning(
                            "gateway transport exhausted | model={} attempts={} :: {}",
                            model,
                            RETRY_ATTEMPTS,
                            exc,
                        )
        if hot_skips and not any(
            model not in hot_skips for model in chain
        ):  # every model hot: the honest cooldown cause, not a vague exhaustion
            raise GatewayError(
                f"all models ({', '.join(chain)}) in rate-limit cooldown; last cause: {last_cause}"
            )
        raise GatewayError(f"all models exhausted ({', '.join(chain)}); last cause: {last_cause}")

    async def _attempt(self, model: str, payload: dict) -> AsyncIterator[str]:
        assert_zero_paid_model(model)  # $0.00 breaker: before build_request, before wire
        _claim_daily_budget(model)  # backstop: refuse before the wire, not after billing
        request = self._client.build_request(
            "POST", "/chat/completions", json=dict(payload, model=model)
        )
        try:
            response = await self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise _TransientFailure(f"transport: {exc}") from exc
        if response.status_code != 200:
            try:
                await response.aread()  # stream=True leaves error bodies unread
            finally:
                await response.aclose()
            snippet = response.text[:500]
            kind = _classify(response.status_code, snippet)
            # A-1, second site: the same field loss the SSE branch carried, on the
            # HTTP branch. `_classify` is handed a STRING here, so the structured
            # reset_seconds inside the body is invisible to it — and neither
            # _RETRY_WINDOW_RE nor the quota keywords match `"reset_seconds":48`,
            # so a declared cooldown classifies "transient" and only the bare-429
            # streak engages, on the SECOND occurrence. The symptom differs from
            # the SSE branch (slower mitigation, never a dead turn), which is why
            # this is its own change and not part of the SSE fix.
            declared = _http_declared_window(snippet, response.status_code)
            if declared is not None:
                raise _WindowRateLimit(
                    f"HTTP {response.status_code} declared cooldown {declared:.0f}s: {snippet[:200]}",
                    window_s=declared,
                )
            if response.status_code == 429 and kind == "transient" and _note_bare_429(model):
                raise _WindowRateLimit(
                    f"HTTP 429 (streak skip, {BARE_429_SKIP_AFTER} consecutive)",
                    window_s=BARE_429_COOLDOWN_S,
                )
            _raise_for_gateway_error(
                model,
                kind,
                f"HTTP {response.status_code}",
                snippet,
                retry_after=response.headers.get("retry-after"),
            )

        received = 0
        done_seen = False
        yielded = False
        try:
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    logger.warning("gateway unexpected SSE line skipped: {!r}", line[:120])
                    continue
                received += len(line.encode())
                data = line[5:].strip()
                if data == "[DONE]":
                    done_seen = True
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("gateway malformed SSE line skipped: {!r}", data[:120])
                    continue
                if chunk.get("error"):
                    # Gateways stream upstream failures as 200 + SSE error events; swallowing
                    # them would deliver silent-empty replies instead of fallback/loud stop.
                    signal = _sse_error_signal(chunk["error"])
                    message, status, window = signal.message, signal.status, signal.window_s
                    # A-1 (live 2026-10-03): the provider SENT a 429 and a recovery
                    # window, and the prose carried no [nnn] — so the status used to be
                    # inferred as 0, classified "fatal", and raised a loud stop that no
                    # cascade handler matched. Acted on the FIRST occurrence: the wall is
                    # declared, so retrying against it is pure waste. This raise sits
                    # BEFORE the bare-429 streak check on purpose, or a streak on a
                    # second occurrence would park the model for the 15-minute
                    # quarantine when the provider said 48 seconds.
                    if status == 429 and window is not None:
                        raise _WindowRateLimit(
                            f"SSE error [429] declared cooldown {window:.0f}s: {message[:200]}",
                            window_s=window,
                        )
                    kind = _classify(status, message)
                    if status == 429 and kind == "transient" and _note_bare_429(model):
                        raise _WindowRateLimit(
                            f"SSE error [429] (streak skip, {BARE_429_SKIP_AFTER} consecutive)",
                            window_s=BARE_429_COOLDOWN_S,
                        )
                    _raise_for_gateway_error(model, kind, f"SSE error [{status}]", message[:500])
                choices = chunk.get("choices") or [{}]
                content = (choices[0].get("delta") or {}).get("content")
                if content:
                    yielded = True
                    yield content
        finally:
            await response.aclose()
        if not done_seen:
            logger.warning(
                "gateway stream ended without [DONE] | bytes={} (deltas still delivered)", received
            )
        elif not yielded:
            # 2026-09-13 audit: reasoning-only/blank turns must never surface
            # as empty replies — the chain falls through to the next model.
            raise _EmptyReply(f"{model} streamed [DONE] with zero content deltas")
