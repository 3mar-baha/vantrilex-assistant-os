"""Ops health probe: per-service TRUTH about gateway reachability, the Telegram
bot credential, ffmpeg, the vault PAT and the Google grant.

The node this module was rewritten for (N3 / F-8) exists because the old probe
answered with PRESENCE and called it a state: ``telegram_token: "set"`` for a
token that was set AND revoked, ``vault: "ok"`` for any non-empty
``str(SecretStr)`` — which is literally ``"**********"`` — and ``google: "ok"``
because a sealed file sat on disk. ``src/main.py``'s responder then answered
``200 {"status":"ok"}`` no matter what, so the body could not disagree with
reality and was therefore evidence of nothing.

THE THREE STATES, and no others. ``LANE_STATES`` is closed and asserted as
closed, because a fourth vague value ("ok", "found", "set") is what this module
used to emit:

``healthy``
    PROVEN working — a real call succeeded.
``misconfigured``
    Determinable and wrong: the credential was presented and REFUSED, or it is
    absent where it is required, or a local binary will not run.
``unreachable``
    COULD NOT BE DETERMINED. Never healthy. A transport error, a 5xx, a timeout,
    a probe that crashed, or a lane nobody has probed yet.

The last two are deliberately distinct. «your key is wrong» and «I could not
reach anything to find out» are different operator problems, and collapsing
them into one "not ok" is the vagueness this node deletes.

THE GOOGLE LANE DIVERGES FROM ``src.google_auth.probe_google`` ON PURPOSE.
F-4 built the boot probe, and this module does not replace or bypass it — it
reuses its session, its probe URL and its timeout, and its ``reason`` discipline
(class name only, never a response body). What it adds is the classification
``probe_google`` deliberately does not make: that probe collapses "the grant was
refused" and "nobody answered" into one ``healthy=False``, and this module's law
is that those two are different states. The 403 rate-limit-vs-scope ambiguity is
NOT solved here — it is N5's open work — so a GitHub 403 below reports
``misconfigured`` meaning precisely «the credential was refused», never «go and
rotate your token».

CACHING, and why the endpoint needs it. Every remote lane here costs one HTTP
call, and ``/health`` is POLLED — a Space probe, a keep-alive ping, ``sara.ps1``.
Probing per poll would be a self-inflicted rate limit against GitHub and Telegram,
and GitHub answers 403 for both a rate limit and bad scopes, so the probe would
manufacture the very ambiguity N5 has to resolve. ``PROBE_TTL_S`` bounds it at
30 s: short enough that a lapsed credential surfaces inside half a minute of an
operator looking, long enough that a 10 s poll loop costs at most one sweep every
third request. The ``/health`` responder reads the cache and never awaits a probe,
so it cannot block the bridge's event loop — which it shares with the
authenticated WSS tunnel — and a cold cache answers every lane ``unreachable``
rather than claiming health it has not measured.

THE HTTP STATUS. Report §48 step 1 offers 503 or «keep 200 with a
machine-readable body»; this is the second, and ``HTTP_STATUS_BY_STATE`` is the
decision, named and asserted rather than left implicit. A hosting platform treats
a non-200 as «the app is down» and may restart the container, so flapping the
whole process because one Google token lapsed would be worse than reporting the
truth in the body. The operator signal is ``--health``'s EXIT CODE, which is
non-zero for every non-healthy rollup.

Degraded components never crash the process — health reports, ops decide.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Final

import httpx
from loguru import logger

from src.config import Settings
from src.google_auth import (
    GOOGLE_PROBE_TIMEOUT_S,
    GOOGLE_PROBE_URL,
    GoogleAPIError,
    GoogleAuthError,
    GoogleSession,
    describe_probe_failure,
)

# ── the closed vocabulary ──────────────────────────────────────────────────────────

#: PROVEN working. A real call succeeded and said so.
STATE_HEALTHY: Final[str] = "healthy"
#: Determinable and wrong: present but REFUSED, absent where required, or a local
#: binary that will not run. The operator knows which knob to turn.
STATE_MISCONFIGURED: Final[str] = "misconfigured"
#: COULD NOT BE DETERMINED. Never healthy. A transport failure, a 5xx, a timeout,
#: a crashed probe, or a lane nobody has probed yet.
STATE_UNREACHABLE: Final[str] = "unreachable"

#: The whole vocabulary. Nothing outside this set may appear in a lane's state.
LANE_STATES: Final[frozenset[str]] = frozenset(
    {STATE_HEALTHY, STATE_MISCONFIGURED, STATE_UNREACHABLE}
)

#: The five lanes, in report order.
LANE_NAMES: Final[tuple[str, ...]] = (
    "gateway",
    "telegram_token",
    "ffmpeg",
    "vault",
    "google",
)

#: Lanes that gate ``overall``. Google is deliberately absent: a box with no OAuth
#: client secret is a SUPPORTED pure-local deployment (F-4), so its lane is
#: required only once credentials are present — decided per-probe, not here.
REQUIRED_LANES: Final[frozenset[str]] = frozenset({"gateway", "telegram_token", "ffmpeg", "vault"})

# ── the probe's own bounds ─────────────────────────────────────────────────────────

#: Every remote lane. A closed laptop lid must cost the probe a pause, never a
#: hang. The Google lane is bounded by F-4's own, longer boot bound instead.
PROBE_TIMEOUT_S: Final[float] = 5.0

#: How long one sweep stays answerable without re-probing. See the module
#: docstring: this is what keeps ``/health`` from being a rate-limit path.
PROBE_TTL_S: Final[float] = 30.0

#: ffmpeg's own version probe — the cheapest call that proves the binary RUNS
#: rather than merely resolves.
FFMPEG_PROBE_ARGS: Final[tuple[str, ...]] = ("-version",)
FFMPEG_PROBE_TIMEOUT_S: Final[float] = 5.0

#: Telegram's cheapest authenticated call: «is this token any good».
TELEGRAM_API_BASE: Final[str] = "https://api.telegram.org"
TELEGRAM_PROBE_PATH: Final[str] = "getMe"
#: GitHub's cheapest authenticated call: «whose token is this».
VAULT_PROBE_URL: Final[str] = "https://api.github.com/user"

# ── the status-code decision ───────────────────────────────────────────────────────

#: §48 step 1, resolved and named. EVERY lane state answers 200 at the public
#: port; the body carries the truth and ``--health``'s exit code carries the
#: alarm. A 503 here would tell a hosting platform the app is down, and a
#: container restarted because a Google token lapsed is a worse outcome than a
#: truthful body nobody reads. Changing a value in this table is a product
#: decision about restart policy, not a bug fix.
HTTP_STATUS_BY_STATE: Final[dict[str, int]] = {
    STATE_HEALTHY: 200,
    STATE_MISCONFIGURED: 200,
    STATE_UNREACHABLE: 200,
}


@dataclass(frozen=True, slots=True)
class Lane:
    """One lane's verdict. ``reason`` is populated only when ``state`` is not
    ``healthy`` — a reason on a healthy lane would be a claim the probe cannot
    support, and it is how a report grows a fourth vocabulary one string at a
    time.

    A reason is «a fault class or a one-clause explanation» (F-4): never a path,
    never a response body, never a header value, never token material.
    """

    state: str
    required: bool = True
    reason: str | None = None


def redact_reason(text: str) -> str:
    """Screen one reason on its way into the report.

    THE SECOND LINE OF DEFENCE ONLY. The probes below build reasons from fixed
    templates plus an exception's CLASS name, so a secret has no route to a
    reason at all — and no comment here claims otherwise. This screens a reason
    anyway, because the failure this guards against is a FUTURE probe
    interpolating the credential by mistake, and the cost of the screen is one
    pass over a string that is already a clause.

    It reuses the house marker and the process's own registered secrets via
    ``src.vault.redact_secret`` (deferred, like every ``src.vault`` reach in this
    repository). It cannot screen a secret that is not registered and matches no
    shape, and it is not claimed to.
    """
    from src.vault import redact_secret

    return redact_secret(str(text or ""))


def overall_state(lanes: Mapping[str, Mapping[str, Any]]) -> str:
    """The rollup: the worst state among the REQUIRED lanes.

    ``unreachable`` outranks ``misconfigured`` because «we could not find out» is
    the less actionable of the two and the more likely to be transient — an
    operator who reads ``unreachable`` checks the network, and that is the right
    first move when a lane never answered. A non-required lane cannot influence
    the rollup, which is how a supported pure-local box reads healthy with no
    Google at all.
    """
    states = [lane["state"] for lane in lanes.values() if lane["required"]]
    if any(state == STATE_UNREACHABLE for state in states):
        return STATE_UNREACHABLE
    if any(state == STATE_MISCONFIGURED for state in states):
        return STATE_MISCONFIGURED
    return STATE_HEALTHY


# ── the report ─────────────────────────────────────────────────────────────────────

#: ``_CACHED`` is the last completed sweep, and ``_CACHED_AT`` when it finished —
#: the module-level state behind ``/health``. Only ``_refresh`` writes them;
#: ``healthcheck`` deliberately does not, so a direct CLI probe is always fresh
#: and a test can never poison another test's snapshot.
_CACHED: dict[str, Any] | None = None
_CACHED_AT: float = 0.0
_TASK: asyncio.Task[None] | None = None


def _assemble(lanes: dict[str, dict[str, Any]], reasons: dict[str, str]) -> dict[str, Any]:
    return {
        "overall": overall_state(lanes),
        "lanes": lanes,
        "reasons": reasons,
        "probed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ttl_s": PROBE_TTL_S,
        "stale": False,
    }


def _unknown_report(reason: str) -> dict[str, Any]:
    """Every lane ``unreachable``. The fail-closed body: with no evidence at all,
    the honest answer is «I do not know», and «I do not know» is not healthy."""
    lanes = {
        name: {"state": STATE_UNREACHABLE, "required": name in REQUIRED_LANES}
        for name in LANE_NAMES
    }
    return _assemble(lanes, {name: reason for name in LANE_NAMES})


def encode_body(report: Mapping[str, Any]) -> bytes:
    """The `/health` wire body. Sorted keys so two sweeps of the same state diff
    cleanly in an operator's terminal."""
    return (json.dumps(report, sort_keys=True) + "\n").encode("utf-8")


def exit_code_for(report: Mapping[str, Any]) -> int:
    """`--health`'s contract, unchanged: 0 when the rollup is healthy, 1 otherwise.
    What changed is the WORD compared against, not the contract."""
    return 0 if report.get("overall") == STATE_HEALTHY else 1


async def healthcheck(
    settings: Settings,
    *,
    probe_gateway: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """One full sweep: every lane, every state, one report. Always fresh — the
    cache belongs to the endpoint, not here.

    ``probe_gateway=False`` declines one lane. A declined lane is an UNDETERMINED
    lane, so it reads ``unreachable``; it also does not gate ``overall``, because
    the caller said so explicitly rather than by accident.
    """
    if probe_gateway:

        async def _gateway(_settings, *, transport=None):
            return await _probe_gateway(_settings, transport=transport)

    else:

        async def _gateway(_settings, *, transport=None):
            return Lane(
                STATE_UNREACHABLE,
                required=False,
                reason="gateway probe declined by the caller",
            )

    probes = {
        "gateway": _gateway,
        "telegram_token": _probe_telegram,
        "ffmpeg": _probe_ffmpeg,
        "vault": _probe_vault,
        "google": _probe_google,
    }
    verdicts = await asyncio.gather(
        *(_safe_probe(probe, settings, transport=transport) for probe in probes.values())
    )
    lanes: dict[str, dict[str, Any]] = {}
    reasons: dict[str, str] = {}
    for name, verdict in zip(probes, verdicts, strict=True):
        lanes[name] = {"state": verdict.state, "required": verdict.required}
        if verdict.state != STATE_HEALTHY and verdict.reason:
            # The ONE place a reason enters a report, so this is the ONE place it
            # is screened — for the CLI body and the `/health` body alike.
            reason = redact_reason(verdict.reason)
            reasons[name] = reason
            # One WARNING per non-healthy lane per sweep, so an operator learns
            # without polling. Bounded by design: five lanes, one sweep per
            # PROBE_TTL_S, and a reason that is a clause rather than a payload.
            logger.warning("health: {} is {} — {}", name, verdict.state, reason)
    return _assemble(lanes, reasons)


async def _safe_probe(probe, settings, *, transport=None) -> Lane:
    """A probe crash degrades its own row loudly — never the whole report, and
    never to healthy."""
    try:
        return await probe(settings, transport=transport)
    except Exception as error:  # noqa: BLE001 — the report survives, the row degrades
        name = getattr(probe, "__name__", "probe")
        logger.warning("health: probe {} raised ({})", name, describe_probe_failure(error))
        return Lane(
            STATE_UNREACHABLE, reason=f"{name} probe raised ({describe_probe_failure(error)})"
        )


# ── the lanes ──────────────────────────────────────────────────────────────────────


async def _probe_gateway(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> Lane:
    """OmniRoute reachability. The URL is a config value, not a secret, but it is
    still never echoed: the operator has it in ``.env``."""
    base = str(settings.omniroute_base_url)
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S, transport=transport) as client:
            response = await client.get(f"{base.rstrip('/')}/models")
    except httpx.HTTPError as error:
        return Lane(
            STATE_UNREACHABLE, reason=f"gateway unreachable ({describe_probe_failure(error)})"
        )
    status = response.status_code
    if 200 <= status < 300:
        return Lane(STATE_HEALTHY)
    if status in (401, 403, 404, 422):
        # The gateway ANSWERED and refused us: determinable and wrong.
        return Lane(STATE_MISCONFIGURED, reason=f"gateway refused the probe (HTTP {status})")
    # 5xx and everything else: the answer says nothing about us. `unreachable`,
    # never `misconfigured` — a 503 must not send the operator to rotate a key.
    return Lane(STATE_UNREACHABLE, reason=f"gateway answered HTTP {status} — probe inconclusive")


async def _probe_telegram(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> Lane:
    """THE HEADLINE LANE. Telegram's ``getMe`` is the cheapest authenticated call
    the Bot API has, and it is the difference between «a token is set» and «a
    token works».

    TWO WAYS TELEGRAM SAYS NO, and the second one defeats a status-code-only
    probe: an unknown token answers HTTP 401, while a token for a deleted bot
    answers HTTP 200 with ``{"ok": false}`` in the envelope. Both are refusals.

    THE URL IS A SECRET. Telegram puts the credential in the PATH, so the request
    URL is itself the token — it is never logged, never put in a reason, and
    never in the report. Only the status code and the envelope flag leave here.
    """
    token = str(settings.telegram_bot_token or "").strip()
    if not token:
        return Lane(STATE_MISCONFIGURED, reason="telegram bot token absent")
    url = f"{TELEGRAM_API_BASE}/bot{token}/{TELEGRAM_PROBE_PATH}"
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S, transport=transport) as client:
            response = await client.get(url)
    except httpx.HTTPError as error:
        return Lane(
            STATE_UNREACHABLE, reason=f"telegram unreachable ({describe_probe_failure(error)})"
        )
    status = response.status_code
    if 200 <= status < 300:
        try:
            payload = response.json()
        except ValueError:
            return Lane(STATE_UNREACHABLE, reason="telegram probe answer unreadable")
        if isinstance(payload, dict) and payload.get("ok") is True:
            return Lane(STATE_HEALTHY)
        # HTTP 200 carrying ok=false is a REFUSAL, not a success.
        return Lane(STATE_MISCONFIGURED, reason="telegram refused the bot token (ok=false)")
    if status in (401, 403, 404):
        return Lane(STATE_MISCONFIGURED, reason=f"telegram refused the bot token (HTTP {status})")
    return Lane(STATE_UNREACHABLE, reason=f"telegram answered HTTP {status} — probe inconclusive")


async def _launch_ffmpeg(exe: str) -> tuple[int | None, BaseException | None]:
    """Run ``<exe> -version``. Returns ``(returncode, error)``; a launch that never
    produced a process returns ``(None, error)``.

    THE ONLY LANE THAT SPAWNS A PROCESS. It is cheap (~10 ms) and it is the only
    way to tell «ffmpeg is installed» from «ffmpeg runs», which on Windows are
    different facts whenever a DLL or a shim is broken. stdout and stderr go to
    DEVNULL: the version banner is not needed to answer the question, and a
    banner is one more string the probe does not have to keep.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            exe,
            *FFMPEG_PROBE_ARGS,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except (OSError, ValueError, NotImplementedError) as error:
        # No process: the platform refused to launch it at all.
        return None, error
    try:
        async with asyncio.timeout(FFMPEG_PROBE_TIMEOUT_S):
            return await process.wait(), None
    except TimeoutError:
        process.kill()
        await process.wait()
        return None, TimeoutError


async def _probe_ffmpeg(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> Lane:
    """ffmpeg: resolved on PATH AND it runs. ``shutil.which`` alone was presence."""
    del settings, transport  # a local lane: nothing is configured, nothing is remote
    exe = shutil.which("ffmpeg")
    if not exe:
        return Lane(STATE_MISCONFIGURED, reason="ffmpeg is not on PATH")
    code, error = await _launch_ffmpeg(exe)
    if isinstance(error, TimeoutError):
        # The binary hung: we could not determine whether it works.
        return Lane(STATE_UNREACHABLE, reason="ffmpeg -version timed out")
    if error is not None:
        return Lane(
            STATE_MISCONFIGURED,
            reason=f"ffmpeg is on PATH but will not launch ({describe_probe_failure(error)})",
        )
    if code == 0:
        return Lane(STATE_HEALTHY)
    return Lane(STATE_MISCONFIGURED, reason=f"ffmpeg -version exited {code}")


def _secret_text(value: Any) -> str:
    """Unwrap a ``SecretStr`` (or a plain string) for the CALL, and only for the
    call. The unwrapped value is never returned, logged, or placed in a reason."""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        return str(getter())
    return "" if value is None else str(value)


async def _probe_vault(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> Lane:
    """The vault PAT, proven by GitHub rather than by its own non-emptiness.

    ``GET /user`` is the cheapest authenticated call GitHub has: it reads the
    identity the token already belongs to and returns nothing new. THE 403
    AMBIGUITY IS NOT SOLVED HERE: GitHub answers 403 for a bad scope AND for a
    rate limit, and separating them is N5's open work. So ``misconfigured`` below
    means precisely «the credential was PRESENT and REFUSED» — the operator's
    next move is to check the rate limit first, and the reason does not pretend
    to know which cause it was.
    """
    token = _secret_text(settings.vault_github_token).strip()
    if not token:
        return Lane(STATE_MISCONFIGURED, reason="vault PAT absent")
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S, transport=transport) as client:
            response = await client.get(
                VAULT_PROBE_URL,
                headers={
                    "authorization": f"Bearer {token}",
                    "accept": "application/vnd.github+json",
                    "x-github-api-version": "2022-11-28",
                    "user-agent": "vantrilex-health",
                },
            )
    except httpx.HTTPError as error:
        return Lane(
            STATE_UNREACHABLE, reason=f"vault unreachable ({describe_probe_failure(error)})"
        )
    status = response.status_code
    if 200 <= status < 300:
        return Lane(STATE_HEALTHY)
    if status in (401, 403):
        return Lane(STATE_MISCONFIGURED, reason=f"vault PAT refused by GitHub (HTTP {status})")
    return Lane(
        STATE_UNREACHABLE, reason=f"github answered HTTP {status} — vault state undetermined"
    )


async def _probe_google(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> Lane:
    """The Google grant, proven by ``calendarList.list(maxResults=1)`` through the
    ordinary session — so a stale access token is refreshed first and a dead
    refresh token is found here rather than at the owner's first calendar read.

    F-4's pieces are reused, not reimplemented: ``GoogleSession`` (which rejects a
    BROKEN client secret at construction), ``GOOGLE_PROBE_URL``,
    ``GOOGLE_PROBE_TIMEOUT_S`` and ``describe_probe_failure``. What this adds is
    the split F-4's single ``healthy=False`` does not make:

    * no client secret  -> ``misconfigured``, and NOT required: a pure-local box
      is a supported deployment, so it cannot degrade the rollup.
    * secrets but no grant -> ``misconfigured``: nobody has run the bootstrap.
    * a grant Google REFUSES (401 that survived the refresh replay) ->
      ``misconfigured``: the credential was presented and declined.
    * a transport error, a 5xx, a timeout -> ``unreachable``: nobody answered.
    """
    try:
        session = GoogleSession(settings, transport=transport)
    except GoogleAuthError as error:
        return Lane(
            STATE_MISCONFIGURED,
            reason=f"google credentials unusable ({describe_probe_failure(error)})",
        )
    if not session.credentials_present:
        return Lane(
            STATE_MISCONFIGURED,
            required=False,
            reason="OAuth client secret absent — running without Google",
        )
    if not (session.tokens.access_token or session.tokens.refresh_token):
        return Lane(STATE_MISCONFIGURED, reason="no cached Google grant — run the OAuth bootstrap")
    try:
        async with asyncio.timeout(GOOGLE_PROBE_TIMEOUT_S):
            await session.request("GET", GOOGLE_PROBE_URL, params={"maxResults": 1})
    except TimeoutError:
        return Lane(STATE_UNREACHABLE, reason="google probe timed out")
    except GoogleAuthError as error:
        # A 401 that survived the refresh replay, or a refresh the grant could not
        # renew: the credential was PRESENT and REFUSED.
        return Lane(
            STATE_MISCONFIGURED, reason=f"google grant refused ({describe_probe_failure(error)})"
        )
    except (httpx.HTTPError, GoogleAPIError, ValueError) as error:
        return Lane(
            STATE_UNREACHABLE, reason=f"google probe failed ({describe_probe_failure(error)})"
        )
    finally:
        # Close the session's client. `GoogleSession` opens an `httpx.AsyncClient`
        # in `__init__` and exposes no close surface, and `src/google_auth.py` is
        # outside this node's write-set — so the private handle is used, through
        # `getattr` so a future refactor degrades to «nothing to close» instead of
        # raising. This is not cosmetic: this probe runs from a 30 s sweep for the
        # life of the process, and an unclosed client per sweep is a transport
        # leaked per sweep.
        client = getattr(session, "_http", None)
        if client is not None:
            await client.aclose()
    return Lane(STATE_HEALTHY)


# ── the endpoint's cache ───────────────────────────────────────────────────────────


def reset_cache() -> None:
    """Drop the sweep, and cancel one that is still running. Ops and tests only.

    The cancel matters: an in-flight sweep outlives the call that started it, and
    a caller that has reset its state should not have a task still writing into
    it. A sweep that is already past its last await simply finishes and finds
    nothing to publish."""
    global _CACHED, _CACHED_AT, _TASK
    task, _TASK = _TASK, None
    if task is not None and not task.done():
        task.cancel()
    _CACHED = None
    _CACHED_AT = 0.0


def snapshot_is_populated() -> bool:
    """Has a sweep ever completed in this process?"""
    return _CACHED is not None


def snapshot_is_stale() -> bool:
    """Has the cached sweep outlived ``PROBE_TTL_S``?"""
    return not snapshot_is_populated() or (monotonic() - _CACHED_AT) >= PROBE_TTL_S


def snapshot() -> dict[str, Any]:
    """What ``/health`` answers: the last completed sweep, or the fail-closed
    all-``unreachable`` body when there has never been one.

    SYNCHRONOUS AND NON-BLOCKING BY CONTRACT, because this is called from inside
    the bridge's event loop and the WebSocket tunnel shares it. It performs no
    I/O; ``schedule_refresh`` is the half that does."""
    if _CACHED is None:
        return _unknown_report("no probe has run yet")
    body = dict(_CACHED)
    body["stale"] = snapshot_is_stale()
    return body


def schedule_refresh(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """Start one background sweep, at most one in flight, and only when the cache
    needs it. The caller does NOT await this: a poll must answer immediately from
    whatever the last sweep found, and a sweep started by poll N is what poll
    N+1 (or a later one) reads.

    The single-flight guard matters as much as the TTL: a Space probe, a
    keep-alive ping and ``sara.ps1`` can all land inside one TTL, and without it
    three concurrent polls would mean three sweeps and three times the call rate.
    """
    global _TASK
    task = _TASK
    if task is not None and not task.done():
        return
    if snapshot_is_populated() and not snapshot_is_stale():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no loop: nothing can own the sweep, and the cache stays cold
    _TASK = loop.create_task(_refresh(settings, transport=transport))


async def _refresh(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """One sweep, published to the cache. Never raises: a background task that
    dies would leave every later poll reading a cache that never updates again,
    which is a quieter failure than reporting the truth."""
    global _CACHED, _CACHED_AT
    try:
        report = await healthcheck(settings, transport=transport)
    except Exception as error:  # noqa: BLE001 — the endpoint must survive anything
        report = _unknown_report("the probe sweep failed before it produced a report")
        logger.warning(
            "health: the refresh sweep failed ({}); every lane reads unknown",
            describe_probe_failure(error),
        )
    _CACHED = report
    _CACHED_AT = monotonic()
