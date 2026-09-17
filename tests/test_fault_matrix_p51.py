"""P5.1 fault-injection gap pins (master transformation plan, Phase P5.1).

A 30-seam audit found 27 seams covered in-suite; these 3 were genuine gaps.
Full registry (seam -> covering test): router-unparseable test_dispatcher;
FAST 429/empty/stall test_gateway_failfast + test_gateway_rate_windows;
non-free ID test_zero_paid_guard; Fish 429/unconfigured
test_fish_audio_pipeline; Whisper empty test_bot_shell; biometric miss/guest
test_guest_lockdown + test_voice_biometric_auth; whitelist miss/corrupt
test_whitelist_guardrail; breaker no-id (benchmark + guardrail suites);
Gmail 401/corrupt test_gmail_watch; calendar empty test_daily_brief; vault
missing digest test_memory; RAG short/routine test_associative_*; persona
test_persona_lines + benchmark; gender drift gender_pipeline suites;
triage invalid/timeout test_email_triage; brief disabled test_daily_brief;
journaler busy test_evening_journaler; voice-demand Fish-dead
test_bot_voice_demand; pending orphans test_bot_shell; OpenClaw daemon-down
openclaw_bench; unknown tool (TOOL_FAIL_AR) test_tools; memory write failure
test_memory + test_live_defects_2026_09_05; confirmation tamper
test_confirmation_separation_p41.
"""

import json

import httpx
import pytest

from src.gateway import OmniRouteClient, Tier


@pytest.fixture(autouse=True)
def _clear_cooldowns():
    from src.gateway import _429_STREAK, _MODEL_COOLDOWNS

    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()
    yield
    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()


def _chunk(text: str) -> str:
    return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"


def _sse(*lines: str) -> bytes:
    return ("".join([*lines, "data: [DONE]\n\n"])).encode()


class _Scripted:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def handler(self, request):
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def transport(self):
        return httpx.MockTransport(self.handler)

    def models(self):
        return [json.loads(r.content)["model"] for r in self.requests]


async def test_medium_429_cascades_to_fallback():
    """MEDIUM 429 announces a window — one attempt, then the fallback serves."""
    from src.gateway import _model_hot

    err = "data: " + json.dumps({"error": {"message": "[m1] [429]: reset after 3s"}}) + "\n\n"
    script = _Scripted(
        httpx.Response(200, content=_sse(err)),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    client = OmniRouteClient(
        "http://gw.test/v1",
        "test-key",
        chains={Tier.MEDIUM: ["m1:free", "m2:free"]},
        transport=script.transport(),
    )
    async with client:
        deltas = [
            d
            async for d in client.stream_chat([{"role": "user", "content": "hi"}], tier=Tier.MEDIUM)
        ]
    assert deltas == ["تم"]
    assert script.models() == ["m1:free", "m2:free"]
    assert _model_hot("m1:free") is not None


async def test_dead_coordinator_parks_committing_dag():
    """A coordinator that throws mid-verdict parks — never passes, never raises."""
    from src.openclaw.plans import build_dag, gate
    from src.openclaw.protocol import Op, OpKind

    class DeadCoordinator:
        def has_confirmation(self, tool, arg):
            raise RuntimeError("coordinator down")

    dag = build_dag(goal="close app", ops=[Op(op=OpKind.HOTKEY, value="Alt+F4")], weight=2)
    assert gate(dag, coordinator=DeadCoordinator()) == "park"


async def test_launch_missing_binary_arabic_line(tmp_path):
    """Spawn FileNotFoundError surfaces the honest Arabic line, not a traceback."""
    import json as _json

    from bridge.executor import Executor
    from bridge.guard import Guard

    wl = tmp_path / "whitelist.json"
    wl.write_text(
        _json.dumps(
            {
                "allowed_apps": [{"name": "calc", "executable": "calc.exe", "auto_approve": True}],
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )

    async def _missing(argv: list[str]) -> None:
        raise FileNotFoundError(argv[0])

    executor = Executor(Guard(wl))
    executor._spawn = _missing
    result = await executor.launch("calc.exe", confirmation_id="cid-1")
    assert result.status == "error"
    assert result.detail == "البرنامج مش موجود عالجهاز"
