"""STT-2 (owner 2026-09-04 evening): «افحصي التطبيقات التي كانت تعمل» got a
generic health answer (7:07pm) — Sara cannot NAME what's actually running.
New bridge wire cmd `exec.list_apps`: the daemon reports the REAL running
user-facing processes (psutil, deduped, whitelist-name aware); the
`running_apps` tool narrates the real list. Read-only — no confirmation gate
(same class as telemetry.state)."""

from __future__ import annotations

from bridge.guard import Guard


def _guard(tmp_path):
    import json

    wl = tmp_path / "whitelist.json"
    wl.write_text(
        json.dumps(
            {
                "allowed_apps": [
                    {"name": "calculator", "executable": "calc.exe", "auto_approve": True}
                ],
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )
    return Guard(wl)


async def test_daemon_list_apps_returns_real_processes(tmp_path, monkeypatch):
    """exec.list_apps: the daemon reports deduped running process names —
    REAL data from psutil, whitelist names preferred over raw images."""

    from bridge.app_sessions import running_apps_report

    monkeypatch.setattr(
        "bridge.app_sessions._running_processes",
        lambda: [
            ("CalculatorApp.exe", None),
            ("chrome.exe", None),
            ("chrome.exe", None),  # dedupe: one chrome row
            ("svchost.exe", None),  # system noise -> excluded
        ],
    )
    report = running_apps_report()
    names = [a["name"] for a in report["apps"]]
    assert len(names) == len(set(names)), "no duplicates"
    assert any("chrome" in n.casefold() for n in names)
    assert "svchost" not in " ".join(names).casefold()  # system noise stays out


async def test_running_apps_tool_narrates_real_list():
    """The `running_apps` tool: bridge payload -> honest Arabic list; bridge
    down -> the offline line; empty -> the honest none-line."""
    from src.tools import ToolRegistry

    class _Bridge:
        def __init__(self, payload):
            self.payload = payload

        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            assert cmd == "exec.list_apps"
            if self.payload is None:
                from src.bridge_server import BridgeOffline

                raise BridgeOffline("down")
            return self.payload

    ok = ToolRegistry(bridge=_Bridge({"apps": [{"name": "Chrome"}, {"name": "Calculator"}]}))
    answer = await ok.call("running_apps", "")
    assert "Chrome" in answer and "Calculator" in answer

    offline = ToolRegistry(bridge=_Bridge(None))
    assert "الجسر" in await offline.call("running_apps", "")

    empty = ToolRegistry(bridge=_Bridge({"apps": []}))
    answer = await empty.call("running_apps", "")
    assert "ما في" in answer or "ما شفت" in answer


def test_keyword_net_routes_running_apps():
    """«شو التطبيقات المفتوحة/الشغالة» routes to running_apps — the live
    7:07pm phrase fell to a generic telemetry answer."""
    from src.dispatcher import _keyword_net

    for phrase in (
        "افحصي التطبيقات التي كانت تعمل",
        "شو التطبيقات المفتوحة",
        "شو البرامج الشغالة هسا",
        "وين البرامج اللي شغالة",
        "شو التطبيقات النشطة",
    ):
        tool, _arg = _keyword_net(phrase)
        assert tool == "running_apps", phrase
