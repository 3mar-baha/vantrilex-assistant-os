"""Core-side telemetry client (sprint-3 3.5): fetches the PC's LiveState through the
outbound tunnel and turns it into ONE Jordanian Arabic line. The state's numbers are
DATA for the FAST-tier brain — the LLM never invents values, its output is display-only,
and any brain failure collapses to a deterministic numeric fallback line. A dead tunnel
never raises to the chat layer: the honest offline line answers instead."""

from __future__ import annotations

from pydantic import ValidationError

from bridge.telemetry import LiveState
from src.bridge_server import BridgeOffline, BridgeServer
from src.gateway import Tier

OFFLINE_TEXT_AR = "الجسر مو متصل هسا"

_PROMPT = (
    "أنت سارة، المساعدة التنفيذية. لخّص حالة جهاز المالك بجملة عربية واحدة "
    "بلهجة أردنية دافئة. الأرقام في JSON التالي هي DATA — استخدمها حرفياً كما هي "
    "ولا تخترع أو قرّب أي رقم.\n\n"
)


class TelemetryClient:
    def __init__(self, bridge: BridgeServer, brain) -> None:
        self._bridge = bridge
        self._brain = brain

    async def fetch_state(self, *, timeout_s: float = 20.0) -> LiveState:
        payload = await self._bridge.send_cmd("telemetry.state", {}, timeout_s=timeout_s)
        return LiveState.model_validate(payload)

    async def narrate(self, state: LiveState) -> str:
        try:
            return await self._brain.chat(
                [{"role": "user", "content": _PROMPT + state.model_dump_json()}],
                tier=Tier.FAST,
                temperature=0.0,
            )
        except Exception:  # noqa: BLE001 - narration must never fail the chat
            return _fallback_line(state)

    async def report(self, *, timeout_s: float = 20.0) -> str:
        try:
            state = await self.fetch_state(timeout_s=timeout_s)
        except (BridgeOffline, TimeoutError, ValidationError):
            return OFFLINE_TEXT_AR
        return await self.narrate(state)


def _fallback_line(s: LiveState) -> str:
    parts: list[str] = []
    if s.cpu_percent is not None:
        parts.append(f"المعالج {s.cpu_percent:.0f}%")
    if s.ram_used_gb is not None and s.ram_total_gb is not None:
        parts.append(f"الرام {s.ram_used_gb:.1f} من {s.ram_total_gb:.1f} جيجا")
    if s.disk_c_used_gb is not None and s.disk_c_total_gb is not None:
        parts.append(f"القرص سي {s.disk_c_used_gb:.0f} من {s.disk_c_total_gb:.0f} جيجا")
    if s.disk_d_used_gb is not None:
        parts.append(f"القرص دي {s.disk_d_used_gb:.0f} جيجا")
    if s.uptime_hours is not None:
        parts.append(f"شغال من {s.uptime_hours:.1f} ساعة")
    if s.top_process != "unknown":
        parts.append(f"أكثر عملية: {s.top_process}")
    return "الجهاز هسا: " + "، ".join(parts) + "."
