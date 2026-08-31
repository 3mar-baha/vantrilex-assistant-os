"""One psutil snapshot of the PC (sprint-3 3.5): cpu / ram / disks / uptime / top
process. Degraded on failure — a metric that cannot be read becomes None (or
"unknown"), never a crash; the owner still gets real numbers for what IS measurable."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psutil
from pydantic import BaseModel, ConfigDict, Field

_SETTLE_S = 0.15  # window the per-process/cpu_percent deltas accumulate over


class LiveState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_percent: float | None = None
    ram_used_gb: float | None = None
    ram_total_gb: float | None = None
    disk_c_used_gb: float | None = None
    disk_c_total_gb: float | None = None
    disk_d_used_gb: float | None = None
    uptime_hours: float | None = None
    top_process: str = "unknown"
    top_process_cpu: float = 0.0
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_GIB = 1024**3


def _safe(read):
    try:
        return read()
    except (psutil.Error, OSError):  # OSError covers missing drives in psutil 7
        return None


def live_state() -> LiveState:
    state = LiveState()

    procs = _safe(lambda: list(psutil.process_iter(attrs=["name"]))) or []
    # prime the counters so the settle window yields real deltas (first call is 0)
    _safe(lambda: psutil.cpu_percent(interval=None))
    for proc in procs:
        try:
            proc.cpu_percent(None)
        except psutil.Error:
            pass
    time.sleep(_SETTLE_S)

    state.cpu_percent = _safe(lambda: psutil.cpu_percent(interval=None))
    mem = _safe(lambda: psutil.virtual_memory())
    if mem is not None:
        state.ram_used_gb = mem.used / _GIB
        state.ram_total_gb = mem.total / _GIB
    for drive, used_attr in (("C:/", "disk_c_used_gb"), ("D:/", "disk_d_used_gb")):
        disk = _safe(lambda d=drive: psutil.disk_usage(d))
        if disk is not None:
            setattr(state, used_attr, disk.used / _GIB)
            if used_attr == "disk_c_used_gb":
                state.disk_c_total_gb = disk.total / _GIB
    boot = _safe(lambda: psutil.boot_time())
    if boot is not None:
        state.uptime_hours = (time.time() - boot) / 3600

    top_name, top_cpu = "unknown", 0.0
    for proc in procs:
        try:
            cpu = proc.cpu_percent(None)
            if cpu > top_cpu:
                top_cpu = cpu
                top_name = proc.info.get("name") or "unknown"
        except psutil.Error:
            pass
    state.top_process, state.top_process_cpu = top_name, top_cpu
    return state
