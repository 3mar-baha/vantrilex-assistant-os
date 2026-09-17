"""P4.1 token/prose separation pins (master transformation plan, Phase P4.1).

Forensic result: the confirmation_id is minted server-side AFTER affirmation,
persisted to the vault BEFORE the command leaves, and travels machine to
machine — it never appears in user-visible prose and never passes through the
model. These tests pin that boundary: challenges carry no auth token, the
execution target always comes from pending state (never reply text), and the
dynamic park warning is single-pass with a static floor.
"""

import re

from src.decision_loop import PARK_LINE_AR, _park_warning
from src.pc_actions import LaunchStatus, PCActionCoordinator

TOKEN_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{12}(?![0-9a-f])")
AR_RE = re.compile(r"[\u0600-\u06FF]")


class FakeBridge:
    def __init__(self, detail="needs confirmation"):
        self.detail = detail
        self.commands = []

    async def send_cmd(self, cmd, args, **kw):
        self.commands.append((cmd, dict(args)))
        if "confirmation_id" in args:
            return {"status": "ok", "detail": "launched", "audit_code": "PC-9"}
        return {"status": "error", "detail": self.detail, "audit_code": "PC-9"}


class FakeNotifier:
    def __init__(self):
        self.sent = []

    async def notify(self, text):
        self.sent.append(text)


class FakeVault:
    def __init__(self):
        self.upserts = []

    async def upsert(self, *args, **kwargs):
        self.upserts.append((args, kwargs))

    async def read(self, *args, **kwargs):
        raise FileNotFoundError


def _rig(detail="needs confirmation"):
    bridge = FakeBridge(detail)
    notifier = FakeNotifier()
    vault = FakeVault()
    return (
        PCActionCoordinator(bridge, vault, notifier),
        bridge,
        notifier,
        vault,
    )


async def test_challenge_prompts_carry_no_auth_token():
    coord, _, notifier, _ = _rig()
    status = await coord.request_launch("somelauncher", origin="owner_chat")
    assert status == LaunchStatus.CONFIRMATION_REQUIRED
    assert notifier.sent, "challenge must surface exactly once"
    for prompt in notifier.sent:
        assert not TOKEN_RE.search(prompt), f"auth token leaked: {prompt!r}"
    assert any("PC-9" in prompt for prompt in notifier.sent)  # audit receipt stays


async def test_execution_target_comes_from_pending_state():
    """Reply names a DIFFERENT app — the pending target still executes."""
    coord, bridge, _, vault = _rig()
    await coord.request_launch("somelauncher", origin="owner_chat")
    assert coord.pending_active()
    result = await coord.handle_owner_reply("نعم وافتح الكروم")
    assert result == "somelauncher"
    launched = [args for cmd, args in bridge.commands if cmd == "exec.launch"]
    assert launched and launched[-1]["name"] == "somelauncher"
    assert launched[-1]["name"] != "الكروم"
    confirmation_id = launched[-1]["confirmation_id"]
    assert re.fullmatch(r"[0-9a-f]{12}", confirmation_id)  # server-minted
    assert vault.upserts, "audit note persists BEFORE the command leaves"


async def test_refusal_clears_without_execution():
    coord, bridge, _, _ = _rig()
    await coord.request_launch("somelauncher", origin="owner_chat")
    assert await coord.handle_owner_reply("لا") is None
    assert not coord.pending_active()
    assert not [c for c in bridge.commands if "confirmation_id" in c[1]]


async def test_park_warning_single_pass_shape():
    """Dynamic warning: exactly one FAST call, short Arabic, no identity drift."""

    class FakeGateway:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, **kwargs):
            self.calls += 1
            return "رح أسكّر البرنامج هسا — أكّدلي بـ«نعم» لو موافق."

    gateway = FakeGateway()
    warning = await _park_warning(gateway, "close", "calculator")
    assert gateway.calls == 1
    assert AR_RE.search(warning)
    assert 5 <= len(warning) <= 1200
    assert "بوابة" not in warning


async def test_park_warning_floor_on_failure():
    class DeadGateway:
        async def chat(self, messages, **kwargs):
            raise RuntimeError("pool down")

    assert await _park_warning(DeadGateway(), "close", "x") == PARK_LINE_AR
