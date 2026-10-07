r"""A-1 — a provider-credential cooldown arriving mid-SSE must CASCADE, not abort.

THE DEFECT THIS PINS. Live 2026-10-03, on the speaker lane:

    EXC GatewayError: fatal SSE error [0] on gemini/gemini-3.8-flash:
         All credentials for model gemini-3.8-flash are cooling down
    [64797 ms, 1 deltas]  |  لحظة بفحصلك

The owner heard the acknowledgement and then ~65 seconds of silence, because no
model after the primary was ever tried. The mechanism is in ``src/gateway.py``,
the SSE error branch. Gateways stream upstream failures as ``200 OK`` plus an SSE
``error`` event, so the real HTTP status is already gone by that branch and the
code substituted an INFERENCE scraped from the human-readable message with
``_EMBEDDED_STATUS`` (``r"\[(\d{3})\]"``). OmniRoute's body is STRUCTURED —
``type: rate_limit_error``, ``code: model_cooldown``, ``reset_seconds: 48`` — and
the branch read ``.get("message")`` and threw the rest away. The prose carries no
bracketed code, so ``status`` became ``0``; ``_classify(0, …)`` matches none of its
branches and returns ``"fatal"``; ``_raise_for_gateway_error`` has no ``fatal``
branch and raises ``GatewayError("fatal SSE error [0] on …")``. A plain
``GatewayError`` matches no cascade handler, so the chain fell through to a loud
stop. **The cascade machinery already existed and was never reached.**

THE LAW, in precedence order. The structured fields are what the provider SENT;
the prose bracket is what we GUESSED. A guess never overrides a field.

  P0  a non-mapping ``error`` payload is «no signal» — never an ``AttributeError``
  P1  ``type`` naming a rate limit is 429, and nothing demotes it
  P2  ``code`` naming a cooldown / rate limit is 429
  P3  ``type``/``code`` naming an AUTH condition is 401 — behaviour-preserving,
      because ``_classify(401)`` is ``"fatal"`` too, exactly like today's ``0``
  P4  the WINDOW, only when the status is 429: ``reset_seconds`` when it is a
      finite positive number, else the prose parser; clamped to COOLDOWN_CAP_S.
      ``THROTTLE_QUARANTINE_S`` is NOT the cap — it is the client's policy for
      evidence it does not have, and padding a provider's own number up to 15
      minutes would retire a model that recovers in 48 seconds
  P5  the prose bracket, DEMOTED to last. Absent everything else the status is 0
      and the outcome is byte-identical to today, ``fatal SSE error [0]`` included.
      **The default fails SAFE: it cannot invent a cascade.**

THE LATENCY DISTINCTION IS PRESERVED, not papered over. An announced window parks
the model on the FIRST occurrence; a window-less 429 stays on the bare-429 streak
and parks on the SECOND (``BARE_429_SKIP_AFTER``). Both end in a cascade, with
different latency to mitigation, and both are pinned below.

THE VOICE-LANE HAZARD. On a voice turn a partially-yielded answer must never be
restarted by the next model — the owner would hear the same answer twice. The
transport-failure branch already refuses to restart after content (``deltas > 0``);
the cascade handlers must refuse the same way, and guard 9 pins it.

NO TEST REACHES THE NETWORK. Every call is driven through ``httpx.MockTransport``
and the process-wide cooldown registries are cleared by the autouse fixture at
``tests/conftest.py``. ``tests/conftest.py`` also raises on any non-loopback
socket, so hermeticity is enforced outside these tests too.
"""

from __future__ import annotations

import ast
import inspect
import json
import math
from pathlib import Path

import httpx
import pytest

from src import gateway as gateway_mod
from src.gateway import COOLDOWN_CAP_S, GatewayError, OmniRouteClient, Tier, _model_hot
from tests.test_gateway_failfast import _chunk, _Scripted, _sse

GATEWAY_PY = Path(gateway_mod.__file__)

PRIMARY = "primary-x:free"
SECOND = "second-y:free"

#: The OmniRoute 429 body observed live 2026-10-03, verbatim. ``retry_after``'s
#: value was elided at observation time; every field this module's precedence
#: ladder reads is reproduced exactly as it was seen. The raw body was never
#: persisted to disk — this constant is the only surviving copy, which is why the
#: guard replays it rather than an idealized shape.
OBSERVED_COOLDOWN_BODY = {
    "error": {
        "message": "All credentials for model gemini-3.8-flash are cooling down",
        "type": "rate_limit_error",
        "code": "model_cooldown",
        "model": "gemini-3.8-flash",
        "reset_seconds": 48,
        "retry_after": "...",
        "credentials_cooling": 1,
    }
}

#: #forbidden_in_a_pure_function, minus the names this predicate legitimately
#: needs. ``error`` is absent on purpose — it is the parameter the contract
#: mandates. Every entry here is an I/O root: none may appear in a function whose
#: whole purpose is to be callable without a client.
_FORBIDDEN_IN_A_PURE_FUNCTION = frozenset(
    {
        "httpx",
        "socket",
        "ssl",
        "open",
        "urlopen",
        "urlretrieve",
        "requests",
        "aiohttp",
        "subprocess",
        "pathlib",
        "os",
        "shutil",
        "tempfile",
        "time",
        "sleep",
        "client",
        "session",
        "transport",
    }
)


def _error_line(error: dict) -> str:
    return "data: " + json.dumps({"error": error}) + "\n\n"


def _sse_open(*lines: str) -> bytes:
    """A stream that never reaches ``[DONE]``.

    The mid-stream guards need the error event to arrive *inside* an open stream.
    ``tests.test_gateway_failfast._sse`` always appends ``[DONE]``, so it cannot
    express that shape — and a guard written against the wrong seam would be
    testing the helper rather than the gateway.
    """
    return "".join(lines).encode()


def _client(script: _Scripted) -> OmniRouteClient:
    return OmniRouteClient(
        "http://gw.test/v1",
        "test-key",
        chains={
            Tier.FAST: [PRIMARY, SECOND],
            Tier.MEDIUM: ["medium-x:free"],
            Tier.HEAVY: ["heavy-x:free"],
        },
        transport=script.transport(),
    )


async def _collect(gen) -> list[str]:
    return [delta async for delta in gen]


async def _instant(_seconds):
    return None


# ── 1, 2: the live defect, replayed verbatim ──────────────────────────────────────


async def test_structured_cooldown_with_no_prose_code_cascades():
    """THE LIVE BUG. The observed body, verbatim, as the first SSE event of a 200
    stream. Its prose carries no ``[nnn]``, so before the fix the status was
    inferred as ``0`` → ``fatal`` → loud stop with no cascade at all.

    One occurrence is sufficient to reproduce (acceptance report §2, F-1 repro).
    """
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line(OBSERVED_COOLDOWN_BODY["error"]))),
        httpx.Response(200, content=_sse(_chunk("بديل"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["بديل"], "the next model must serve the turn"
    assert script.models() == [PRIMARY, SECOND], (
        "exactly ONE primary attempt — the announced window must not be retried against"
    )
    assert _model_hot(PRIMARY) is not None, "the cooling model must be parked"


async def test_structured_cooldown_parks_for_the_announced_window_not_the_quarantine():
    """The announced 48 s, not the client's 15-minute bare-429 quarantine.

    ``reset_seconds: 48`` is the provider's own number for its own pool. Padding
    it up to ``THROTTLE_QUARANTINE_S`` would retire a model that recovers in under
    a minute; ignoring it would burn retries against a wall we were told about.
    """
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line(OBSERVED_COOLDOWN_BODY["error"]))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    remaining = _model_hot(PRIMARY)
    assert remaining is not None
    assert 0 < remaining <= 48 + 1, f"parked {remaining:.1f}s — must be the announced 48s window"
    assert remaining < gateway_mod.BARE_429_COOLDOWN_S, (
        "an ANNOUNCED window must not be inflated to the 15-minute unannounced quarantine"
    )


# ── 3: the fix must not turn everything into a window ────────────────────────────


async def test_prose_five_hundred_without_structured_fields_still_retries_transient(monkeypatch):
    """A prose ``[500]`` and nothing else stays TRANSIENT: three bounded retries,
    then the cascade. Regression pin against a fix that over-reaches and parks
    every error it sees.
    """
    monkeypatch.setattr(gateway_mod, "_sleep", _instant)
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line({"message": "upstream exploded [500]"}))),
        httpx.Response(200, content=_sse(_error_line({"message": "upstream exploded [500]"}))),
        httpx.Response(200, content=_sse(_error_line({"message": "upstream exploded [500]"}))),
        httpx.Response(200, content=_sse(_chunk("خلاص"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["خلاص"]
    assert script.models() == [PRIMARY, PRIMARY, PRIMARY, SECOND], (
        "a 5xx keeps its bounded retries — it is not a rate limit and must not park the model"
    )
    assert _model_hot(PRIMARY) is None, "a transient failure must never park a model"


# ── 4, 5: precedence — the field beats the prose ──────────────────────────────────


async def test_structured_cooldown_outranks_a_prose_five_hundred():
    """``code: model_cooldown`` + prose ``[500]``. The bracketed code is a GUESS
    scraped out of prose; ``code`` is a field the provider emitted for this event.
    The field wins — under the guess, ``_classify(500)`` returns ``"transient"``
    and burns three retries against a wall we were already told about.
    """
    error = dict(
        OBSERVED_COOLDOWN_BODY["error"], message="upstream exploded [500]", reset_seconds=12
    )
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line(error))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["تم"]
    assert script.models() == [PRIMARY, SECOND], "a declared cooldown is never retried against"
    assert _model_hot(PRIMARY) is not None, "the declared cooldown must park the model"


async def test_structured_rate_limit_outranks_a_prose_four_oh_three():
    """The accepted-risk case, pinned by name so a reader is never surprised by it.

    ``type: rate_limit_error`` + prose ``[403]`` → 429 → cascade, not a loud stop.
    A provider stamping a bracket code from an upstream hop must not be able to
    promote its own rate limit into a credential abort. The bounded cost: the
    cascade parks THAT ONE model for at most ``COOLDOWN_CAP_S`` and moves on.
    """
    error = dict(OBSERVED_COOLDOWN_BODY["error"], message="[x] [403]: denied", reset_seconds=9)
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line(error))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["تم"], "a declared rate limit cascades rather than stopping loud"
    assert script.models() == [PRIMARY, SECOND]
    remaining = _model_hot(PRIMARY)
    assert remaining is not None and 0 < remaining <= 9 + 1


# ── 6: the fail-safe default, pinned byte-identical ──────────────────────────────


@pytest.mark.parametrize(
    ("label", "message"),
    [
        (
            "the observed message with its structure removed",
            OBSERVED_COOLDOWN_BODY["error"]["message"],
        ),
        ("a message with nothing to read at all", "boom"),
    ],
)
async def test_no_signal_at_all_stays_fatal_and_byte_identical(label, message):
    """THE DEFAULT MUST FAIL SAFE. With no structured field and no prose bracket
    the outcome is today's outcome, unchanged and un-invented: a loud stop whose
    ``[0]`` still says the gateway could not find a status.

    A fix that defaults to «assume a rate limit» would trade a loud stop for a
    cascade on every unrecognised provider error — the one direction this guard
    exists to forbid.
    """
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line({"message": message}))),
        httpx.Response(200, content=_sse(_chunk("يجب ألا يُستعمل"))),
    )
    async with _client(script) as client:
        with pytest.raises(GatewayError) as exc_info:
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert str(exc_info.value).startswith(f"fatal SSE error [0] on {PRIMARY}: "), (
        f"{label}: the no-signal outcome must stay byte-identical to today's, got: {exc_info.value}"
    )
    assert script.models() == [PRIMARY], f"{label}: no cascade may be invented"
    assert _model_hot(PRIMARY) is None, f"{label}: nothing may be parked"


# ── 7: hostile structured values ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "reset_seconds"),
    [
        ("a non-numeric string", "soon"),
        ("negative", -5),
        ("zero — meaning «retry now», never a zero-length window", 0),
        ("nan", float("nan")),
        ("infinity", float("inf")),
        ("a hostile giant, which the cap must bound", 1e12),
    ],
)
async def test_hostile_reset_seconds_is_rejected_and_the_window_stays_bounded(label, reset_seconds):
    """``gateway.py`` clamps every window with ``min(window, COOLDOWN_CAP_S)``, and
    ``tests/test_vulnerability_audit.py`` pins that law for the prose parser. The
    same law binds a structured number: a hostile or unusable ``reset_seconds``
    must never reach ``time.time() + window_s`` and park a model for ``nan``,
    forever, or for a duration the provider never asked for.

    The observable consequence is a BOUNDED, FINITE park — whatever the input.
    """
    error = dict(OBSERVED_COOLDOWN_BODY["error"], reset_seconds=reset_seconds)
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line(error))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["تم"], f"{label}: the turn must still be served"
    remaining = _model_hot(PRIMARY)
    if remaining is not None:
        assert math.isfinite(remaining), f"{label}: parked for a non-finite window ({remaining})"
        assert 0 < remaining <= COOLDOWN_CAP_S + 1, (
            f"{label}: parked {remaining}s — past the {COOLDOWN_CAP_S}s cap"
        )


# ── 8: one pure decision site ────────────────────────────────────────────────────


def _function(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """The named function, found by NAME. Raises if it is gone — a guard whose
    subject disappeared must FAIL, not pass vacuously.
    """
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{path.name}: `{name}` is gone — this guard has nothing left to check")


def test_the_signal_helper_is_pure_and_takes_only_the_error_payload():
    """ONE decision site, and it is PURE — the shape
    ``src.vault.classify_rate_limit`` already established for the vault lane.

    Read from the signature and the body rather than from prose, so a second
    required parameter cannot be slipped in behind a docstring that still says
    «the error payload». The body scan is what makes «callable without a client»
    a fact instead of a claim.
    """
    assert hasattr(gateway_mod, "_sse_error_signal"), (
        "src.gateway._sse_error_signal is absent — the SSE branch is still inferring the "
        "status from prose, which is the A-1 defect"
    )
    params = list(inspect.signature(gateway_mod._sse_error_signal).parameters.values())
    assert [p.name for p in params] == ["error"], (
        "must accept exactly (error) — it is handed the parsed SSE error payload and "
        f"nothing else, got {[p.name for p in params]}"
    )
    assert all(p.default is inspect.Parameter.empty for p in params), (
        "neither parameter may be optional: every caller passes the payload"
    )

    func = _function(GATEWAY_PY, "_sse_error_signal")
    referenced: set[str] = set()
    blocking: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Await):
            blocking.append("awaits")
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            blocking.append("yields")
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        if isinstance(node, ast.Attribute):
            referenced.add(node.attr)
    assert not blocking, f"_sse_error_signal {blocking} — it must be a pure mapping"
    leaked = referenced & _FORBIDDEN_IN_A_PURE_FUNCTION
    assert not leaked, f"_sse_error_signal references {sorted(leaked)} — it is not pure"


def test_a_non_mapping_error_payload_is_no_signal_and_never_raises():
    """P0. ``chunk["error"]`` is not guaranteed to be an object; a bare string
    made the old ``.get("message", …)`` line raise ``AttributeError`` from
    inside the stream, escaping every handler in the chain.
    """
    assert hasattr(gateway_mod, "_sse_error_signal"), "src.gateway._sse_error_signal is absent"
    for payload in ("boom", 7, None, ["a", "b"]):
        signal = gateway_mod._sse_error_signal(payload)
        assert signal.status == 0, f"{payload!r} carries no status"
        assert signal.window_s is None, f"{payload!r} announces no window"


# ── 9: the voice-lane partial-answer hazard ───────────────────────────────────────


async def test_mid_stream_cooldown_after_a_delta_never_restarts_the_answer():
    """A model that streamed part of an answer and then reported a cooldown must
    NOT be replaced by the next model — the owner would hear the same answer
    twice on a voice turn. This is the same contract the transport-failure
    branch already honours, and it applies to the cascade handlers too.
    """
    body = _sse_open(
        _chunk("نصف"),
        _error_line(OBSERVED_COOLDOWN_BODY["error"]),
    )
    script = _Scripted(
        httpx.Response(200, content=body),
        httpx.Response(200, content=_sse(_chunk("يجب ألا يُستعمل"))),
    )
    async with _client(script) as client:
        seen: list[str] = []
        with pytest.raises(GatewayError, match=r"after 1 deltas"):
            async for delta in client.stream_chat([{"role": "user", "content": "hi"}]):
                seen.append(delta)
    assert seen == ["نصف"], "the already-spoken half must not be retracted"
    assert script.models() == [PRIMARY], (
        "the fallback must NEVER be contacted — a partial answer must not be restarted"
    )


async def test_mid_stream_transient_after_a_delta_never_restarts_the_answer(monkeypatch):
    """The same hazard on the OTHER branch an SSE error can reach: a
    ``_TransientFailure`` after content would otherwise be retried three times
    and every retry would re-answer from the beginning.
    """
    monkeypatch.setattr(gateway_mod, "_sleep", _instant)
    body = _sse_open(
        _chunk("نصف"),
        _error_line({"message": "upstream exploded [500]"}),
    )
    script = _Scripted(
        httpx.Response(200, content=body),
        httpx.Response(200, content=_sse(_chunk("يجب ألا يُستعمل"))),
    )
    async with _client(script) as client:
        seen: list[str] = []
        with pytest.raises(GatewayError, match=r"after 1 deltas"):
            async for delta in client.stream_chat([{"role": "user", "content": "hi"}]):
                seen.append(delta)
    assert seen == ["نصف"]
    assert script.models() == [PRIMARY], "no retry, no restart, no fallback after a partial answer"


# ── 10: tier-independence, and the bare-vs-window latency distinction ─────────────


@pytest.mark.parametrize("tier", [Tier.FAST, Tier.MEDIUM, Tier.HEAVY])
async def test_the_sse_cooldown_path_is_tier_agnostic(monkeypatch, tier):
    """The SSE branch cannot see which tier invoked it — ``_attempt`` takes no
    ``tier`` — so the cooldown must cascade identically on all three. Pinning it
    makes that claim falsifiable rather than asserted, and it holds regardless of
    how the FAST first-token budget is later set.
    """
    monkeypatch.setattr(gateway_mod, "FIRST_TOKEN_TIMEOUT_S", 30.0)
    # Every tier gets a fallback: a chain of one can only end in a loud stop, so
    # a single-model chain would not be able to express «cascaded» at all.
    chains = {tier: [PRIMARY, SECOND] for tier in (Tier.FAST, Tier.MEDIUM, Tier.HEAVY)}
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line(OBSERVED_COOLDOWN_BODY["error"]))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    client = OmniRouteClient(
        "http://gw.test/v1", "test-key", chains=chains, transport=script.transport()
    )
    async with client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}], tier=tier))
    assert deltas == ["تم"], f"{tier}: the cooldown must cascade on every tier"
    assert _model_hot(PRIMARY) is not None, f"{tier}: the cooldown must park on every tier"


async def test_an_announced_window_parks_on_the_first_occurrence_and_a_bare_429_on_the_second(
    monkeypatch,
):
    """THE DISTINCTION, measured by request count rather than asserted in prose.

    An announced window is acted on immediately — the provider told us the wall is
    there, so retrying is pure waste. A window-less 429 keeps ONE fast retry for a
    seconds-scale blip, and only the SECOND consecutive occurrence parks the model
    (``BARE_429_SKIP_AFTER``). Collapsing the two would either re-burn retries
    against a known wall or stop retrying a blip that would have cleared.
    """
    monkeypatch.setattr(gateway_mod, "_sleep", _instant)
    cold = {"type": "rate_limit_error", "code": "model_cooldown", "message": "cooling down"}
    # A bare 429 is a 429 that announces NO window — the status still has to be
    # recoverable, so it carries the prose bracket the gateway has always emitted
    # for this shape (see test_coverage_gaps_p64b.py:169).
    bare = {"message": "[primary-x:free] [429]: too many requests"}
    script = _Scripted(
        httpx.Response(200, content=_sse(_error_line(dict(cold, reset_seconds=48)))),
        httpx.Response(200, content=_sse(_chunk("بعد النافذة"))),
        httpx.Response(200, content=_sse(_error_line(bare))),
        httpx.Response(200, content=_sse(_error_line(bare))),
        httpx.Response(200, content=_sse(_chunk("بعد التكرار"))),
    )
    async with _client(script) as client:
        first = await _collect(client.stream_chat([{"role": "user", "content": "a"}]))
        gateway_mod._MODEL_COOLDOWNS.clear()
        gateway_mod._429_STREAK.clear()
        second = await _collect(client.stream_chat([{"role": "user", "content": "b"}]))
    assert first == ["بعد النافذة"]
    assert script.models()[:2] == [PRIMARY, SECOND], (
        "an ANNOUNCED window is acted on the FIRST occurrence — no retry against a known wall"
    )
    assert second == ["بعد التكرار"]
    # Two primaries, not three: the streak trips on the SECOND consecutive 429
    # (BARE_429_SKIP_AFTER = 2), so the first keeps its one fast retry.
    assert script.models()[2:] == [PRIMARY, PRIMARY, SECOND], (
        "a window-LESS 429 keeps one fast retry, and only the SECOND parks the model"
    )
