"""Remediation 2.2 (owner directive 2026-09-03, audit C-7): Arabic app alias
table — the owner says «الآلة الحاسبة» and the coordinator resolves it to the
whitelist key BEFORE the bridge round-trip. A no-hit alias gets the honest
«مش موجود بالقائمة المعتمدة» line immediately — no doomed confirmation
round-trip for a name that can never resolve."""

from __future__ import annotations

from pathlib import Path

from bridge.guard import Guard
from src.pc_actions import LaunchStatus, PCActionCoordinator

TOKEN = "your-github-test-pat-abcdef0123456789"

WHITELIST = {
    "allowed_apps": [
        {"name": "calculator", "executable": "calc.exe", "auto_approve": True},
        {"name": "obsidian", "executable": "Obsidian.exe", "auto_approve": True},
        {"name": "Notepad", "executable": "notepad.exe", "auto_approve": True},
    ],
    "restricted_actions": [
        {"action": "shutdown", "requires_confirmation": True},
    ],
}


class FakeBridge:
    """Records the wire call WITHOUT touching a real executor (spy on _send)."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, dict]] = []

    async def send_cmd(self, cmd: str, args: dict, *, timeout_s: float = 20.0) -> dict:
        self.commands.append((cmd, dict(args)))
        return {"status": "error", "detail": "test double", "audit_code": "PC-1"}


class FakeNotifier:
    _chat_id = 111  # mirrors _BotNotifier — the 2.4 memory hook keys off it

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def notify(self, text: str) -> None:
        self.sent.append(text)


class FakeVault:
    async def upsert(self, *args, **kwargs) -> None:
        pass

    async def read(self, *args, **kwargs) -> str:
        raise FileNotFoundError


def _rig(whitelist: dict | None = None):
    bridge = FakeBridge()
    notifier = FakeNotifier()
    if whitelist is not None:
        import json

        path = Path("whitelist.json")
        path.write_text(json.dumps(whitelist), encoding="utf-8")
        coordinator = PCActionCoordinator(bridge, FakeVault(), notifier, guard=Guard(path))
    else:
        coordinator = PCActionCoordinator(bridge, FakeVault(), notifier)
    return coordinator, bridge, notifier


# --- alias table unit contract --------------------------------------------------


def test_alias_table_maps_arabic_colloquial_to_keys():
    from src.pc_actions import resolve_app_alias

    assert resolve_app_alias("الآلة الحاسبة") == "calculator"
    assert resolve_app_alias("الحاسبة") == "calculator"
    assert resolve_app_alias("اوبسيديان") == "obsidian"
    assert resolve_app_alias("أوبسيديان") == "obsidian"
    assert resolve_app_alias("المفكرة") == "Notepad"
    # exact keys and pass-through English names resolve to themselves
    assert resolve_app_alias("calculator") == "calculator"
    assert resolve_app_alias("Chrome") == "Chrome"
    # unknown stays itself (the whitelist guard gives the honest line)
    assert resolve_app_alias("برنامج مو") == "برنامج مو"


# --- end-to-end through request_launch ------------------------------------------


async def test_arabic_alias_launches_the_whitelist_key(tmp_path: Path, monkeypatch):
    """«افتحي الآلة الحاسبة» → the bridge receives name='calculator' — the
    whitelisted key, not the Arabic colloquial phrase (C-7 root cause)."""
    import json as _json

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps(WHITELIST), encoding="utf-8")
    bridge = FakeBridge()
    notifier = FakeNotifier()

    async def fake_send(cmd, args, *, timeout_s=20.0):
        bridge.commands.append((cmd, dict(args)))
        return {"status": "ok", "detail": "whitelisted auto_approve", "audit_code": "PC-1"}

    coordinator = PCActionCoordinator(bridge, FakeVault(), notifier, guard=Guard(wl))
    monkeypatch.setattr(coordinator, "_send", fake_send)
    status = await coordinator.request_launch("الآلة الحاسبة", origin="owner_chat")
    assert status == LaunchStatus.EXECUTED
    assert bridge.commands == [("exec.launch", {"name": "calculator"})]


async def test_unknown_app_name_gets_honest_line_no_confirmation_roundtrip(tmp_path):
    """A name with no alias and no whitelist hit → the honest «مش موجود
    بالقائمة» line WITHOUT pinging the bridge first — no doomed confirmation
    round-trip that can never succeed."""
    import json as _json

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps(WHITELIST), encoding="utf-8")
    bridge = FakeBridge()
    notifier = FakeNotifier()
    coordinator = PCActionCoordinator(bridge, FakeVault(), notifier, guard=Guard(wl))
    status = await coordinator.request_launch("برنامج مو موجود", origin="owner_chat")
    assert status == LaunchStatus.REFUSED
    assert bridge.commands == []  # no wire call for an unresolvable name
    assert any("مش موجود بالقائمة" in m for m in notifier.sent)
    assert not coordinator.pending_active()  # nothing pends


async def test_whitelisted_english_name_still_passes_through(tmp_path):
    import json as _json

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps(WHITELIST), encoding="utf-8")
    bridge = FakeBridge()
    notifier = FakeNotifier()

    async def fake_send(cmd, args, *, timeout_s=20.0):
        bridge.commands.append((cmd, dict(args)))
        return {"status": "ok", "detail": "whitelisted auto_approve", "audit_code": "PC-2"}

    coordinator = PCActionCoordinator(bridge, FakeVault(), notifier, guard=Guard(wl))

    # monkeypatch-free wiring: patch the bound method via instance dict
    coordinator._send = fake_send  # type: ignore[method-assign]
    status = await coordinator.request_launch("obsidian", origin="owner_chat")
    assert status == LaunchStatus.EXECUTED
    assert bridge.commands[0] == ("exec.launch", {"name": "obsidian"})


# --- backwards compatibility: no guard injected → old behavior -------------------


async def test_no_guard_injected_behaves_like_before():
    """Default construction (no guard) keeps the legacy pass-through: the name
    goes to the bridge unfiltered, existing tests/callers untouched."""
    coordinator, bridge, _notifier = _rig()
    await coordinator.request_launch("whatever", origin="owner_chat")
    assert bridge.commands[0][1]["name"] == "whatever"


# --- remediation 2.4 (audit C-8): coordinator exchanges enter memory -------------


class _MemoryDouble:
    def __init__(self) -> None:
        self.buffers: dict[int, list[dict]] = {}

    def remember(self, chat_id: int, role: str, content: str) -> None:
        self.buffers.setdefault(chat_id, []).append({"role": role, "content": content})

    def history(self, chat_id: int) -> list[dict]:
        return list(self.buffers.get(chat_id, []))


async def test_confirmation_roundtrip_enters_memory(tmp_path):
    """«افتح X» → prompt lands in memory; the owner's «نعم» and the execution
    result land too — the brain sees the real confirmation conversation, never
    an orphan yes (C-8)."""
    bridge = FakeBridge()
    notifier = FakeNotifier()
    memory = _MemoryDouble()

    async def fake_send(cmd, args, *, timeout_s=20.0):
        bridge.commands.append((cmd, dict(args)))
        # first call: non-whitelisted refusal -> confirmation required
        if "confirmation_id" not in args:
            return {"status": "error", "detail": "not whitelisted", "audit_code": "PC-3"}
        return {"status": "ok", "detail": "executed", "audit_code": "PC-3"}

    coordinator = PCActionCoordinator(bridge, FakeVault(), notifier, memory=memory)
    coordinator._send = fake_send  # type: ignore[method-assign]

    # prompt: the owner asked, the coordinator demanded confirmation
    assert await coordinator.request_launch("obsidian", origin="owner_chat") == (
        LaunchStatus.CONFIRMATION_REQUIRED
    )
    # owner says yes — consumed, executed
    assert await coordinator.handle_owner_reply("نعم") == "obsidian"

    history = memory.history(111)
    roles = [m["role"] for m in history]
    assert "user" in roles and "assistant" in roles  # the conversation is two-sided
    assert any("obsidian" in m["content"] for m in history)  # the ask/prompt is there
    assert any("نعم" in m["content"] for m in history)  # the confirmation is there
    assert any("نفّذت" in m["content"] for m in history)  # the RESULT is there


async def test_rejected_confirmation_enters_memory_not_orphan(tmp_path):
    """«لا» after a prompt: the refusal + «تمام، ما نفذت شي» land in memory —
    no orphan reply for the brain to trip over."""
    bridge = FakeBridge()
    notifier = FakeNotifier()
    memory = _MemoryDouble()

    async def fake_send(cmd, args, *, timeout_s=20.0):
        return {"status": "ok", "detail": "never called", "audit_code": "PC-4"}

    coordinator = PCActionCoordinator(bridge, FakeVault(), notifier, memory=memory)
    coordinator._send = fake_send  # type: ignore[method-assign]

    await coordinator.request_power("shutdown", origin="owner_chat")
    await coordinator.handle_owner_reply("لا")

    history = memory.history(111)
    assert any("لا" in m["content"] for m in history)  # the refusal is remembered
    assert any("ما نفذت شي" in m["content"] for m in history)
    assert bridge.commands == []  # nothing executed — refusal honored


async def test_no_memory_injected_behaves_like_before():
    """Default construction (no memory) keeps legacy behavior — the coordinator
    works alone, existing callers/tests untouched."""
    coordinator, _bridge, _notifier = _rig()
    status = await coordinator.request_launch("whatever", origin="owner_chat")
    assert status is not None  # flows through, no crash without memory


class _MemoryFailDouble(_MemoryDouble):
    def remember(self, chat_id: int, role: str, content: str) -> None:
        raise RuntimeError("memory dead")


async def test_memory_failure_never_breaks_the_coordinator(tmp_path):
    """A dead memory is a degraded boot, not a dead coordinator — the launch flow
    (prompt → confirm → execute → notify) survives untouched."""
    import json as _json

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps(WHITELIST), encoding="utf-8")
    bridge = FakeBridge()
    notifier = FakeNotifier()
    memory = _MemoryFailDouble()

    async def fake_send(cmd, args, *, timeout_s=20.0):
        bridge.commands.append((cmd, dict(args)))
        return {"status": "ok", "detail": "executed", "audit_code": "PC-5"}

    coordinator = PCActionCoordinator(bridge, FakeVault(), notifier, memory=memory)
    coordinator._send = fake_send  # type: ignore[method-assign]

    status = await coordinator.request_launch("obsidian", origin="owner_chat")
    assert status == LaunchStatus.EXECUTED  # no crash — memory is best-effort
    await coordinator.handle_owner_reply("نعم")
    assert bridge.commands  # the flow completed
    assert any("شغّلت" in m for m in notifier.sent)  # owner notified regardless
