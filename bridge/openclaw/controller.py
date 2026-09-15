"""ExecutionController (Phase 2): op-by-op mechanical executor.

Owns NOTHING live: breaker + backends are injected. Every act mints an
audit code and returns an ActionTranscript; the daemon wraps it in the
ExecResult wire shape. Unconfigured backends answer honestly — Phase 3
binds the Win32/Playwright actuator and the UIA/DOM perception engines.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from loguru import logger

from bridge.executor import ExecResult, mint_audit_code
from bridge.openclaw import fetch_arm
from bridge.openclaw.breaker import ActionForbiddenError, SafetyCircuitBreaker
from bridge.openclaw.protocol import ActionTranscript, ElementHandle, Op

STAGED_ACT = "openclaw actuator not configured (Phase 3 binds Win32/Playwright)"
STAGED_PERCEIVE = "openclaw perception not configured (Phase 3 binds UIA/DOM)"
STAGED_INSPECT = "openclaw inspector not configured"
STAGED_BROWSE = "openclaw browser not configured (bind BrowserArm)"


class Actuator(Protocol):
    """Mechanical single-op execution (Phase-3 Win32/Playwright backend)."""

    async def act(self, op: Op) -> dict[str, Any]: ...


class OpenClawController:
    def __init__(
        self,
        *,
        breaker: SafetyCircuitBreaker | None = None,
        actuator: Actuator | None = None,
        perception: Any = None,
        fetcher: Any = None,
        inspector: Any = None,
        browser: Any = None,
    ) -> None:
        self._breaker = breaker or SafetyCircuitBreaker()
        self._actuator = actuator
        self._perception = perception
        self._fetcher = fetcher
        self._inspector = inspector
        self._browser = browser

    async def perceive(self, scope: str = "desktop") -> ExecResult:
        code = mint_audit_code()
        if self._perception is None:
            return ExecResult(status="error", detail=STAGED_PERCEIVE, audit_code=code)
        try:
            raw = await self._perception.snapshot(scope)
            handles = [
                h if isinstance(h, ElementHandle) else ElementHandle.model_validate(h) for h in raw
            ]
        except Exception as exc:  # noqa: BLE001 — a dead backend is honest, never a crash
            logger.warning("openclaw perceive failed: {}", exc)
            return ExecResult(status="error", detail=f"perceive failed: {exc}", audit_code=code)
        return ExecResult(
            status="ok",
            detail=json.dumps([h.model_dump() for h in handles], ensure_ascii=False),
            audit_code=code,
        )

    async def act(self, op_data: dict, confirmation_id: str | None = None) -> ExecResult:
        """Parse -> classify/authorize -> mechanical act -> transcript."""
        code = mint_audit_code()
        try:
            op = Op.model_validate(op_data)
        except Exception as exc:  # noqa: BLE001 — malformed ops refuse loudly
            return ExecResult(status="error", detail=f"malformed op: {exc}", audit_code=code)
        try:
            verdict = self._breaker.classify(op)
        except ActionForbiddenError as exc:
            return ExecResult(status="error", detail=f"forbidden: {exc}", audit_code=code)
        if verdict != op.reversibility:
            logger.warning(
                "openclaw wire-claim mismatch | op={} claimed={} computed={}",
                op.op.value,
                op.reversibility,
                verdict,
            )
        if not self._breaker.authorize(op, confirmation_id):
            return ExecResult(
                status="error",
                detail="irreversible op requires explicit owner confirmation",
                audit_code=code,
            )
        if self._actuator is None:
            return ExecResult(status="error", detail=STAGED_ACT, audit_code=code)
        try:
            observation = await self._actuator.act(op)
        except Exception as exc:  # noqa: BLE001
            logger.warning("openclaw act failed: {}", exc)
            observation = {"op": op.op.value, "ok": False, "evidence": str(exc)}
        transcript = ActionTranscript(
            plan_id=f"op-{code}",
            success=bool(observation.get("ok", False)),
            observations=[{"op": op.op.value, **observation}],
            audit_codes=[code],
        )
        return ExecResult(status="ok", detail=transcript.model_dump_json(), audit_code=code)

    async def inspect(self, scope: str = "desktop") -> ExecResult:
        """Full diagnostic transcript (3.1): screenshot + foreground + OCR."""
        code = mint_audit_code()
        if self._inspector is None:
            return ExecResult(status="error", detail=STAGED_INSPECT, audit_code=code)
        try:
            transcript = await self._inspector.inspect(scope)
        except Exception as exc:  # noqa: BLE001 — inspect() itself never raises, belt first
            logger.warning("openclaw inspect failed: {}", exc)
            return ExecResult(status="error", detail=f"inspect failed: {exc}", audit_code=code)
        return ExecResult(
            status="ok", detail=json.dumps(transcript, ensure_ascii=False), audit_code=code
        )

    async def browse(self, action: str, params: dict | None = None) -> ExecResult:
        """Interactive web lane: navigate/snapshot/click/type/scroll against
        the bound browser backend. Unknown actions and dead backends refuse
        loudly with audit codes — never a fake page."""
        code = mint_audit_code()
        params = params or {}
        if self._browser is None:
            return ExecResult(status="error", detail=STAGED_BROWSE, audit_code=code)
        try:
            starter = getattr(self._browser, "start", None)
            if callable(starter):
                await starter()
            kind = (action or "").strip().casefold()
            if kind == "navigate":
                observation = await self._browser.navigate(str(params.get("url", "")))
            elif kind == "snapshot":
                handles = await self._browser.snapshot()
                observation = {
                    "ok": True,
                    "handles": [h.model_dump() if hasattr(h, "model_dump") else h for h in handles],
                }
            elif kind == "click":
                observation = await self._browser.click_by_role(
                    str(params.get("role", "")), params.get("name")
                )
            elif kind == "type":
                observation = await self._browser.type_into(
                    str(params.get("role", "")),
                    params.get("name"),
                    str(params.get("text", "")),
                )
            elif kind == "scroll":
                observation = await self._browser.scroll(str(params.get("direction", "down")))
            else:
                return ExecResult(
                    status="error", detail=f"unknown browse action {action!r}", audit_code=code
                )
        except Exception as exc:  # noqa: BLE001 — dead browser is honest, never a crash
            logger.warning("openclaw browse failed: {}", exc)
            return ExecResult(status="error", detail=f"browse failed: {exc}", audit_code=code)
        return ExecResult(
            status="ok", detail=json.dumps(observation, ensure_ascii=False), audit_code=code
        )

    async def fetch(self, url: str) -> ExecResult:
        code = mint_audit_code()
        try:
            text = await fetch_arm.fetch(url, self._fetcher)
        except ValueError as exc:
            return ExecResult(status="error", detail=str(exc), audit_code=code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("openclaw fetch failed: {}", exc)
            return ExecResult(status="error", detail=f"fetch failed: {exc}", audit_code=code)
        if text == fetch_arm.NOT_CONFIGURED:
            return ExecResult(status="error", detail=text, audit_code=code)
        return ExecResult(status="ok", detail=text, audit_code=code)
