"""Sprint-3 §3.4: PC whitelist guardrail — the sacred floor.

Contract: docs/specs/sprint-3.md §3.4 — AC1-AC9 map 1:1 onto the test names below.
The daemon side is exercised in-process: a real Guard + real Executor whose process
spawn/open hooks are spied (the OS process boundary is the mock edge), wired to the
coordinator through a tunnel double that dispatches to that same executor.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
from helpers_vault import FakeGitHub
from loguru import logger

from bridge.executor import Executor, mint_confirmation_id
from bridge.guard import Guard
from src.pc_actions import LaunchStatus, PCActionCoordinator, RefusedOrigin
from src.vault import AUDIT_DIR, CONFIRMATIONS_DIR, VaultClient, split_frontmatter

TOKEN = "your-github-test-pat-abcdef0123456789"
# F-2: the shared signing secret this file's executor verifies against. The
# `your-` shape is the repo's secret-scanner allowlist shape.
AC5_KEY = "your-ac5-shared-confirmation-key"

WHITELIST = {
    "allowed_apps": [
        {"name": "calculator", "executable": "calc.exe", "auto_approve": True},
        {"name": "obsidian", "executable": "Obsidian.exe", "auto_approve": True},
    ],
    "restricted_actions": [
        {"action": "shutdown", "requires_confirmation": True},
        {"action": "restart", "requires_confirmation": True},
        {"action": "sleep", "requires_confirmation": True},
    ],
}

AUDIT_CODE_RE = re.compile(r"^PC-\d{8}-\d{6}-[0-9a-f]{4}$")


class SpawnSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, argv: list[str]) -> None:
        self.calls.append(argv)


class OpenSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, path: str) -> None:
        self.calls.append(path)


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def notify(self, text: str) -> None:
        self.sent.append(text)


class FakeBridge:
    """In-proc daemon double: send_cmd dispatches to the real (spied) executor."""

    def __init__(self, executor: Executor) -> None:
        self.commands: list[tuple[str, dict]] = []
        self._executor = executor
        self.offline = False

    async def send_cmd(self, cmd: str, args: dict, *, timeout_s: float = 20.0) -> dict:
        if self.offline:
            from src.bridge_server import BridgeOffline

            raise BridgeOffline("no bridge session")
        self.commands.append((cmd, dict(args)))
        if cmd == "exec.launch":
            result = await self._executor.launch(
                args["name"],
                confirmation_id=args.get("confirmation_id"),
                audit_code=args.get("audit_code"),
            )
        elif cmd == "power":
            result = await self._executor.power(
                args["action"],
                confirmation_id=args["confirmation_id"],
                audit_code=args.get("audit_code"),
            )
        else:
            raise AssertionError(f"unexpected cmd {cmd}")
        return result.model_dump()


def _write_whitelist(tmp_path: Path, data: dict) -> str:
    path = tmp_path / "whitelist.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _rig(tmp_path: Path, whitelist: dict):
    spy, open_spy, notifier = SpawnSpy(), OpenSpy(), FakeNotifier()
    executor = Executor(Guard(_write_whitelist(tmp_path, whitelist)))
    executor._spawn = spy
    executor._open = open_spy
    gh = FakeGitHub()
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    vault = VaultClient("owner/vault-repo", TOKEN, session=session)
    bridge = FakeBridge(executor)
    coordinator = PCActionCoordinator(bridge, vault, notifier)
    return coordinator, bridge, spy, open_spy, notifier, gh


async def test_whitelisted_app_executes(tmp_path: Path):
    """AC1 — whitelisted auto_approve launches immediately."""
    coordinator, bridge, spy, _, notifier, _gh = _rig(tmp_path, WHITELIST)
    status = await coordinator.request_launch("calculator", origin="owner_chat")
    assert status == LaunchStatus.EXECUTED
    assert spy.calls and spy.calls[0][0].lower().startswith("calc")
    assert bridge.commands[0][0] == "exec.launch"
    assert any("رمز التدقيق" in msg for msg in notifier.sent)


async def test_nonwhitelisted_blocked_pending_confirmation(tmp_path: Path):
    """AC2 — non-whitelisted: refusal, CONFIRMATION_REQUIRED + Arabic prompt sent."""
    coordinator, _bridge, spy, _, notifier, _gh = _rig(tmp_path, WHITELIST)
    status = await coordinator.request_launch("steam", origin="owner_chat")
    assert status == LaunchStatus.CONFIRMATION_REQUIRED
    assert spy.calls == []  # nothing executed
    assert any("مش بالقائمة المعتمدة" in msg for msg in notifier.sent)
    assert coordinator.pending_active()


async def test_bridge_refuses_unconfirmed_execution(tmp_path: Path):
    """AC3 — daemon side: non-whitelisted launch with confirmation_id=None refused."""
    spy = SpawnSpy()
    executor = Executor(Guard(_write_whitelist(tmp_path, WHITELIST)))
    executor._spawn = spy
    result = await executor.launch("steam", confirmation_id=None)
    assert result.status == "error"
    assert spy.calls == []  # refused even from a compromised core


async def test_confirmation_roundtrip_persists_and_executes(tmp_path: Path):
    """AC4 — block -> affirm -> confirmation note (same id + audit_code) -> executed."""
    coordinator, bridge, spy, _, _notifier, gh = _rig(tmp_path, WHITELIST)
    assert await coordinator.request_launch("steam", origin="owner_chat") == (
        LaunchStatus.CONFIRMATION_REQUIRED
    )
    reply = await coordinator.handle_owner_reply("ايه سوّيها")
    assert reply is not None
    notes = [p for p in gh.objects if p.startswith(CONFIRMATIONS_DIR)]
    assert len(notes) == 1
    meta, _body = split_frontmatter(gh.objects[notes[0]][1])
    second_cmd, second_args = bridge.commands[1]
    assert second_cmd == "exec.launch"
    assert second_args["confirmation_id"] == meta["confirmation_id"]
    assert second_args["audit_code"] == meta["audit_code"]
    assert AUDIT_CODE_RE.match(meta["audit_code"])
    assert spy.calls, "confirmed launch must execute"


async def test_restricted_power_always_requires_confirmation(tmp_path: Path):
    """AC5 — power refused without a VERIFIED confirmation id even if the
    whitelist wrongly allows it.

    F-2 CORRECTED this test, and the correction is the point: the pre-F-2 body
    asserted that `"cid-123"` was a "valid ID", so the sacred floor PINNED the
    forgery (report Part F §42, remediation-1.3 precedent — a test whose name
    and assertion disagree is the thing that moves, never the fix). The law
    AC5 actually states is "a live confirmation id proceeds"; after F-2 "live"
    means signed by the shared core<->daemon secret, unexpired, and unused.
    """
    wrong = {
        "allowed_apps": [],
        "restricted_actions": [{"action": "sleep", "requires_confirmation": False}],
    }
    spy = SpawnSpy()
    executor = Executor(Guard(_write_whitelist(tmp_path, wrong)), confirm_key=AC5_KEY)
    executor._spawn = spy
    refused = await executor.power("sleep", confirmation_id="")
    assert refused.status == "error" and spy.calls == []
    # F-2: a forged id is refused even when it is non-empty, and the refusal is
    # asserted — not merely "nothing was executed".
    forged = await executor.power("sleep", confirmation_id="cid-123")
    assert forged.status == "error", "a forged confirmation id must never execute"
    # the refusal must NAME the id as the reason. "cid-123" is refused as
    # `malformed` (it is not even a token); a well-formed token signed by nobody
    # is refused as `does not verify`. Either is a refusal; neither executes.
    assert "confirmation id" in forged.detail, forged.detail
    assert spy.calls == []
    genuine = mint_confirmation_id(secret=AC5_KEY)
    ok = await executor.power("sleep", confirmation_id=genuine)
    assert ok.status == "ok" and spy.calls  # a genuine, signed ID proceeds
    # ... and it is single-use: the same approval is not a second approval.
    # Replayed on the SAME action deliberately — this fixture's whitelist holds
    # only "sleep", so a replay of "shutdown" would be refused by the whitelist
    # first and would prove nothing about single-use.
    replayed = await executor.power("sleep", confirmation_id=genuine)
    assert replayed.status == "error" and "already used" in replayed.detail
    missing = await executor.power("format", confirmation_id=mint_confirmation_id(secret=AC5_KEY))
    assert missing.status == "error" and "not in whitelist" in missing.detail


async def test_open_path_confined_and_guarded(tmp_path: Path):
    """AC6 — safe doc inside a root opens; exe/double-click equivalents and
    traversal/UNC/absolute-outside-roots are refused. F-3 EXTENDED this test
    (it never weakened an assertion): the pre-F-3 version built the Executor
    with NO roots and called a tmp_path document "inside C:/", which is not a
    confinement — the root is now explicit and every refusal is asserted."""
    spy, open_spy = SpawnSpy(), OpenSpy()
    executor = Executor(Guard(_write_whitelist(tmp_path, WHITELIST)), open_roots=(tmp_path,))
    executor._spawn = spy
    executor._open = open_spy
    doc = tmp_path / "report.txt"
    doc.write_text("hello", encoding="utf-8")
    ok = await executor.open_path(str(doc))
    assert ok.status == "ok" and open_spy.calls == [str(doc)]
    exe = await executor.open_path("C:/Windows/notepad.exe")
    assert exe.status == "error" and spy.calls == []  # pending confirmation, not executed
    traversal = await executor.open_path("../../etc/passwd")
    assert traversal.status == "error" and "outside_allowed_roots" in traversal.detail
    unc = await executor.open_path(r"\\server\share\file.txt")
    assert unc.status == "error" and "outside_allowed_roots" in unc.detail
    # F-3: an absolute path on another drive reaches nothing without a root
    outside = await executor.open_path("C:/Windows/System32/drivers/etc/hosts")
    assert outside.status == "error" and "outside_allowed_roots" in outside.detail
    # F-3: the double-click equivalents the pre-F-3 set let through
    for suffix in (".lnk", ".url", ".jar", ".hta", ".html"):
        double = tmp_path / f"payload{suffix}"
        double.write_text("x", encoding="utf-8")
        refused = await executor.open_path(str(double))
        assert refused.status == "error", suffix
        assert "whitelist" in refused.detail, (suffix, refused.detail)
    assert open_spy.calls == [str(doc.resolve())]  # nothing above ever opened
    assert spy.calls == []


async def test_non_owner_origin_intent_refused(tmp_path: Path):
    """AC7 — origin != owner_chat raises RefusedOrigin (untrusted containment)."""
    coordinator, _bridge, _spy, _open, _notifier, _gh = _rig(tmp_path, WHITELIST)
    for origin in ("email_triage", "llm_output", "vault_parser", ""):
        with pytest.raises(RefusedOrigin):
            await coordinator.request_launch("calculator", origin=origin)
        with pytest.raises(RefusedOrigin):
            await coordinator.request_power("shutdown", origin=origin)


async def test_corrupt_whitelist_fails_closed(tmp_path: Path):
    """AC8 — corrupt whitelist flips the guard fail-closed + CRITICAL."""
    bad = tmp_path / "whitelist.json"
    bad.write_text("{not json", encoding="utf-8")
    guard = Guard(str(bad))
    records: list = []
    hid = logger.add(records.append, level="TRACE")
    try:
        verdict = guard.check_app("calculator")
        power = guard.check_power("shutdown")
    finally:
        logger.remove(hid)
    assert verdict.allowed_without_confirmation is False
    assert verdict.requires_confirmation is True
    assert power.requires_confirmation is True
    assert any(r.record["level"].name == "CRITICAL" for r in records)


async def test_audit_code_minted_and_ledger_appended(tmp_path: Path):
    """AC9 — every ExecResult carries a well-formed audit_code; refusals hit the ledger."""
    coordinator, _bridge, _spy, _open, _notifier, gh = _rig(tmp_path, WHITELIST)
    assert await coordinator.request_launch("steam", origin="owner_chat") == (
        LaunchStatus.CONFIRMATION_REQUIRED
    )
    ledger_path = f"{AUDIT_DIR}/pc-ledger.md"
    assert ledger_path in gh.objects
    lines = [ln for ln in gh.objects[ledger_path][1].splitlines() if ln.strip()]
    assert len(lines) == 1  # exactly one refusal event, one line
    assert AUDIT_CODE_RE.match(lines[0].split("|")[1].strip())


def test_productivity_six_pack_resolves_in_live_config():
    """Step-10 mission pin: the six canonical apps resolve in the shipped
    config/whitelist.json — five auto-approved, cmd.exe confirm-gated."""
    from pathlib import Path as _Path

    guard = Guard(str(_Path(__file__).resolve().parents[1] / "config" / "whitelist.json"))
    for name in ("Notepad", "Spotify", "Telegram Desktop", "WhatsApp", "File Explorer"):
        verdict = guard.check_app(name)
        assert verdict.allowed_without_confirmation is True, name
        assert verdict.requires_confirmation is False, name
    cmd = guard.check_app("Command Prompt")
    assert cmd.allowed_without_confirmation is False
    assert cmd.requires_confirmation is True


def test_confirm_gated_verdict_keeps_executable(tmp_path: Path):
    """A whitelisted-but-gated app still resolves its executable — otherwise
    the post-confirmation launch would spawn a bare name and fail."""
    wl = tmp_path / "whitelist.json"
    wl.write_text(
        json.dumps(
            {
                "allowed_apps": [
                    {
                        "name": "Command Prompt",
                        "executable": "C:\\Windows\\System32\\cmd.exe",
                        "auto_approve": False,
                    }
                ],
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )
    verdict = Guard(str(wl)).check_app("Command Prompt")
    assert verdict.requires_confirmation is True
    assert verdict.executable == "C:\\Windows\\System32\\cmd.exe"
