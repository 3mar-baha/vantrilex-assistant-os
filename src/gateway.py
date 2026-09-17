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
import re
import time
from collections.abc import AsyncIterator, Mapping, Sequence
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


def assert_zero_paid_model(model: str) -> None:
    """Unconditional free-tier proof for one model ID: `:free`-suffixed
    OpenRouter slugs pass, `groq/`-prefixed IDs pass (free tier by
    construction); everything else raises PaidModelBlockedError."""
    candidate = (model or "").strip()
    if candidate.startswith("groq/") or candidate.endswith(":free"):
        return
    raise PaidModelBlockedError(
        f"non-free model blocked before network: {candidate!r} "
        "(only ':free' slugs or groq/ free-tier IDs may dispatch)"
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
                    message = str(chunk["error"].get("message", chunk["error"]))
                    match = _EMBEDDED_STATUS.search(message)
                    status = int(match.group(1)) if match else 0
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
