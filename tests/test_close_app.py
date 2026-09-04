"""Pass-1 close-app (v2.0 directive §3-د/1): «سكري البرنامج» closes a running app
by name through the guard — a close is a destructive action on the owner's session,
so it goes through the SAME whitelist gate as launching (a whitelisted app may close
without a round-trip; anything else demands confirmation), with taskkill argv on the
Windows side and an audit code every time."""

from __future__ import annotations

from pathlib import Path

from bridge.executor import Executor
from bridge.guard import Guard


def _guard(tmp_path: Path, *, auto: bool = False) -> Guard:
    import json

    wl = tmp_path / "whitelist.json"
    payload = {
        "allowed_apps": [{"name": "calculator", "executable": "calc.exe", "auto_approve": auto}],
        "restricted_actions": [],
    }
    wl.write_text(json.dumps(payload), encoding="utf-8")
    return Guard(wl)


class _SpawnSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, argv: list[str]) -> None:
        self.calls.append(argv)


async def test_close_whitelisted_app_executes_taskkill(tmp_path: Path):
    ex = Executor(_guard(tmp_path, auto=True))
    spy = _SpawnSpy()
    ex._spawn = spy
    result = await ex.close("calculator")
    assert result.status == "ok"
    # taskkill by image name, force, detached
    assert spy.calls and spy.calls[0][:3] == ["taskkill", "/IM", "calc.exe"]
    assert result.audit_code


async def test_close_requires_confirmation_when_not_auto(tmp_path: Path):
    """Whitelisted but requires confirmation -> refused without a live id."""
    ex = Executor(_guard(tmp_path, auto=False))
    spy = _SpawnSpy()
    ex._spawn = spy
    result = await ex.close("calculator")
    assert result.status == "error"
    assert "confirmation" in result.detail or "معتمدة" in result.detail
    assert spy.calls == []


async def test_close_unknown_app_refused_without_spawn(tmp_path: Path):
    ex = Executor(_guard(tmp_path))
    spy = _SpawnSpy()
    ex._spawn = spy
    result = await ex.close("SomeMalware")
    assert result.status == "error"
    assert spy.calls == []
