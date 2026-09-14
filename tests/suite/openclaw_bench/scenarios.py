"""OpenClaw bench scenarios A–E (Phase 4): shared by pytest + the runner.

Each `run_*` coroutine is hermetic (doubles only), self-timing, and
returns a ScenarioResult — never raises on expected degradation (chaos
scenarios assert graceful recovery, not crashes). AssertionErrors signal
genuine contract breaks for both harnesses.
"""

from __future__ import annotations

import json as _json
import time
from dataclasses import dataclass

import pytest

from bridge.openclaw.actuator import DesktopActuator
from bridge.openclaw.breaker import ActionForbiddenError, SafetyCircuitBreaker
from bridge.openclaw.controller import OpenClawController
from bridge.openclaw.hotkeys import ACTION_HOTKEYS
from bridge.openclaw.inspect_arm import ScreenInspector
from bridge.openclaw.protocol import Op, OpKind
from bridge.openclaw.web_arm import BrowserArm
from src.openclaw.plans import build_dag, gate
from tests.suite.openclaw_bench.mock_desktop import (
    MockControl,
    MockUIA,
    MockWindow,
    mock_grab_factory,
    mock_ocr_factory,
    notepad_desktop,
)
from tests.suite.openclaw_bench.mock_web import (
    WebElementMissing,
    mock_browser_factory,
)


@dataclass
class ScenarioResult:
    name: str
    tier: str
    latency_ms: float = 0.0
    passed: bool = False
    detail: str = ""
    safety_violations: int = 0


async def _timed(coro):
    t0 = time.perf_counter()
    result = await coro
    result.latency_ms = (time.perf_counter() - t0) * 1000
    return result


# -- A: silent inspect + passive fetch (no UI interaction) ---------------------


async def _wrap(res: ScenarioResult, coro_fn):
    try:
        res.detail = await coro_fn()
        res.passed = True
    except AssertionError as exc:
        res.detail = f"ASSERT: {exc}"
    except Exception as exc:  # noqa: BLE001 — unexpected crash is a fail, not a hang
        res.detail = f"CRASH {type(exc).__name__}: {exc}"
    return res


async def run_a1_silent_inspect() -> ScenarioResult:
    res = ScenarioResult(name="A1-silent-inspect", tier="T3-vision")
    desktop = notepad_desktop()
    grab = mock_grab_factory()
    ocr = mock_ocr_factory("Error 404 on line 12")
    inspector = ScreenInspector(grab=grab, foreground=desktop.foreground, ocr=ocr)

    async def _run():
        transcript = await inspector.inspect()
        assert transcript["screenshot_ok"] is True
        assert transcript["foreground"] == "Notepad - report.txt"
        assert "Error 404" in (transcript["ocr_text"] or "")
        actuations = [c for c in desktop.calls if c[0] in ("focus", "click", "type")]
        assert actuations == [], f"silent inspect actuated: {actuations}"
        return f"fg={transcript['foreground']} ocr_head=Error 404"

    return await _timed(_wrap(res, _run))


async def run_a2_passive_fetch() -> ScenarioResult:
    res = ScenarioResult(name="A2-passive-fetch", tier="T2-fetch")

    async def _fetch(url: str) -> str:
        assert url == "https://shop.example/"
        return "# Shop\n\n- item one\n- item two"

    async def _run():
        controller = OpenClawController(fetcher=_fetch)
        result = await controller.fetch("https://shop.example/")
        assert result.status == "ok" and "item one" in result.detail
        assert result.audit_code.startswith("PC-")
        return "markdown served, audit coded"

    return await _timed(_wrap(res, _run))


# -- B: interactive web navigation (T1 tree) ------------------------------------


async def run_b1_web_fill_and_click() -> ScenarioResult:
    res = ScenarioResult(name="B1-web-fill-click", tier="T1-tree")

    async def _run():
        arm = BrowserArm(factory=mock_browser_factory())
        await arm.start()
        try:
            await arm.navigate("https://shop.example/")
            handles = await arm.snapshot()
            ids = {h.id for h in handles}
            assert {"e1", "e2", "e3"} <= ids
            await arm.type_into("textbox", "Search products", "منسف")
            await arm.click_by_role("button", "Search")
        finally:
            await arm.close()
        return f"{len(handles)} handles resolved, fill+click recorded"

    return await _timed(_wrap(res, _run))


async def run_b2_web_scroll() -> ScenarioResult:
    res = ScenarioResult(name="B2-web-scroll", tier="T1-tree")

    async def _run():
        arm = BrowserArm(factory=mock_browser_factory())
        await arm.start()
        try:
            obs = await arm.scroll("down")
            assert obs["ok"] is True and obs["dy"] == 500
        finally:
            await arm.close()
        return "signed wheel delta served"

    return await _timed(_wrap(res, _run))


# -- C: T0 hotkey acceleration ----------------------------------------------------


async def run_c1_hotkey_preferred_over_click() -> ScenarioResult:
    res = ScenarioResult(name="C1-hotkey-first", tier="T0-hotkey")

    async def _run():
        desktop = notepad_desktop()
        uia = MockUIA(desktop)
        sent: list[tuple] = []
        actuator = DesktopActuator(uia=uia, sender=lambda vk, down: sent.append((vk, down)))
        spec = ACTION_HOTKEYS["address_bar"]
        assert spec == "Ctrl+L"
        obs = await actuator.act(Op(op=OpKind.HOTKEY, value=spec))
        assert obs["ok"] is True
        assert sent, "hotkey never reached the sender"
        clicks = [c for c in desktop.calls if c[0] == "click"]
        assert clicks == [], "T0 violated: clicked instead of hotkey"
        return f"{spec} injected, zero clicks"

    return await _timed(_wrap(res, _run))


async def run_c2_run_dialog_flow() -> ScenarioResult:
    res = ScenarioResult(name="C2-run-dialog", tier="T0+T1")

    async def _run():
        desktop = notepad_desktop()
        uia = MockUIA(desktop)
        sent: list[tuple] = []
        actuator = DesktopActuator(uia=uia, sender=lambda vk, down: sent.append((vk, down)))
        await actuator.act(Op(op=OpKind.HOTKEY, value=ACTION_HOTKEYS["run_dialog"]))
        desktop.windows["Run"] = MockWindow(
            title="Run", controls={"input": MockControl(name="input", role="edit")}
        )
        obs = await actuator.act(Op(op=OpKind.TYPE_TEXT, target="Run>input", value="notepad"))
        assert obs["ok"] is True
        assert sent, "Win+R never injected"
        return "hotkey opened, text typed, no submit"

    return await _timed(_wrap(res, _run))


# -- D: safety gate battery ----------------------------------------------------------


COMMITTING_OPS: tuple[Op, ...] = (
    Op(op=OpKind.HOTKEY, value="Alt+F4"),
    Op(op=OpKind.HOTKEY, value="Ctrl+S"),
    Op(op=OpKind.HOTKEY, value="Enter"),
    Op(op=OpKind.TYPE_TEXT, target="Note>x", value="line\nsubmit"),
    Op(op=OpKind.CLICK, target="e9", verify="save"),
    Op(op=OpKind.CLICK, target="e9", verify="delete"),
    Op(op=OpKind.CLICK, target="e9", verify="send"),
)


class _ConfirmingCoordinator:
    def has_confirmation(self, tool, arg):
        return True


async def run_d1_commit_parks_without_confirmation() -> ScenarioResult:
    res = ScenarioResult(name="D1-park-without-confirmation", tier="safety")
    violations = 0

    async def _run():
        nonlocal violations
        desktop = notepad_desktop()
        uia = MockUIA(desktop)
        sent: list[tuple] = []
        controller = OpenClawController(
            actuator=DesktopActuator(uia=uia, sender=lambda vk, down: sent.append((vk, down)))
        )
        for op in COMMITTING_OPS:
            dag = build_dag(goal="do it", ops=[op], weight=2)
            assert gate(dag, coordinator=None) == "park", op
            assert SafetyCircuitBreaker.authorize(op, None) is False, op
            result = await controller.act(op.model_dump())
            assert result.status == "error", op
        # confirmed control case executes exactly once
        dag = build_dag(goal="focus bar", ops=[Op(op=OpKind.HOTKEY, value="Ctrl+L")], weight=1)
        assert gate(dag, coordinator=_ConfirmingCoordinator()) == "go"
        ok = await controller.act({"op": "hotkey", "value": "Ctrl+L"}, confirmation_id="c1")
        assert ok.status == "ok"
        executions = [c for c in desktop.calls if c[0] in ("focus", "click", "type")]
        assert executions == [], f"unconfirmed executions: {executions}"
        # one sanctioned Ctrl+L injection == 4 key events (down/down/up/up)
        assert len(sent) == 4, f"expected exactly one sanctioned hotkey, got {sent}"
        violations = 0  # asserts above prove zero unsanctioned backend effects
        return f"{len(COMMITTING_OPS)} committing ops parked, 0 unconfirmed executions"

    out = await _timed(_wrap(res, _run))
    out.safety_violations = violations if out.passed else -1
    return out


async def run_d2_forbidden_never_executes() -> ScenarioResult:
    res = ScenarioResult(name="D2-forbidden-rejected", tier="safety")

    async def _run():
        desktop = notepad_desktop()
        controller = OpenClawController(
            actuator=DesktopActuator(uia=MockUIA(desktop), sender=lambda vk, down: None)
        )
        shells = [
            Op(op=OpKind.TYPE_TEXT, value="powershell -c whoami"),
            Op(op=OpKind.TYPE_TEXT, value="reg add HKLM\\X /v a"),
        ]
        for op in shells:
            with pytest.raises(ActionForbiddenError):
                SafetyCircuitBreaker.classify(op)
            result = await controller.act(op.model_dump(), confirmation_id="c1")
            assert result.status == "error" and "forbidden" in result.detail, op
        assert desktop.calls == [], "forbidden op touched the desktop"
        return f"{len(shells)} shell shapes refused even WITH confirmation id"

    out = await _timed(_wrap(res, _run))
    out.safety_violations = 0 if out.passed else -1
    return out


# -- E: chaos + self-healing ------------------------------------------------------------


async def run_e1_popup_recovery() -> ScenarioResult:
    res = ScenarioResult(name="E1-popup-recovery", tier="chaos")

    async def _run():
        desktop = notepad_desktop()
        inspector = ScreenInspector(grab=lambda: b"JPEG", foreground=desktop.foreground, ocr=None)
        before = (await inspector.inspect())["foreground"]
        desktop.inject_popup("Update available", ["Later", "Now"])
        during = (await inspector.inspect())["foreground"]
        desktop.dismiss_popup("Update available")
        after = (await inspector.inspect())["foreground"]
        assert before == "Notepad - report.txt", before
        assert during == "Update available", during
        assert after == "Notepad - report.txt", after
        return "popup seen, dismissed, focus restored"

    return await _timed(_wrap(res, _run))


async def run_e2_focus_loss_degrades() -> ScenarioResult:
    res = ScenarioResult(name="E2-focus-loss", tier="chaos")

    async def _run():
        from bridge.openclaw.inspect_arm import ScreenInspector

        desktop = notepad_desktop()
        desktop.focus_lost = True
        inspector = ScreenInspector(grab=lambda: b"JPEG", foreground=desktop.foreground, ocr=None)
        transcript = await inspector.inspect()
        assert transcript["screenshot_ok"] is True
        assert transcript["foreground"] is None
        return "locked screen reads as None, transcript still ok"

    return await _timed(_wrap(res, _run))


async def run_e3_missing_element_graceful() -> ScenarioResult:
    res = ScenarioResult(name="E3-missing-element", tier="chaos")

    async def _run():
        desktop = notepad_desktop()
        controller = OpenClawController(
            actuator=DesktopActuator(uia=MockUIA(desktop), sender=lambda vk, down: None)
        )
        result = await controller.act({"op": "click", "target": "Ghost>nope"})
        assert result.status == "ok"  # transport ok; observation carries the failure
        transcript = _json.loads(result.detail)
        assert transcript["success"] is False
        assert result.audit_code.startswith("PC-")
        return "missing control -> failed observation, audit coded, no raise"

    return await _timed(_wrap(res, _run))


async def run_e4_stale_web_handle_recovers() -> ScenarioResult:
    res = ScenarioResult(name="E4-stale-handle", tier="chaos")

    async def _run():
        arm = BrowserArm(factory=mock_browser_factory())
        await arm.start()
        try:
            await arm.navigate("https://shop.example/")
            first = await arm.snapshot()
            assert any(h.name == "Search" for h in first)
            # page changes under us (popup overlay tree replaces content)
            arm._session.page.tree = {
                "role": "WebArea",
                "name": "Shop",
                "children": [{"role": "button", "name": "Dismiss"}],
            }
            try:
                await arm.click_by_role("button", "Search")
            except WebElementMissing:
                recovered = await arm.snapshot()
                assert any(h.name == "Dismiss" for h in recovered)
                await arm.click_by_role("button", "Dismiss")
            else:
                raise AssertionError("stale lookup should have missed")
        finally:
            await arm.close()
        return "stale id missed, re-snapshot recovered, dialog dismissed"

    return await _timed(_wrap(res, _run))


ALL_SCENARIOS = (
    run_a1_silent_inspect,
    run_a2_passive_fetch,
    run_b1_web_fill_and_click,
    run_b2_web_scroll,
    run_c1_hotkey_preferred_over_click,
    run_c2_run_dialog_flow,
    run_d1_commit_parks_without_confirmation,
    run_d2_forbidden_never_executes,
    run_e1_popup_recovery,
    run_e2_focus_loss_degrades,
    run_e3_missing_element_graceful,
    run_e4_stale_web_handle_recovers,
)
