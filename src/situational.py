"""Situational posture classifier (Leap 3, Phase-3) — core side.

Consumes ambient AttentionSamples into an in-memory ring (15-minute decay,
never vaulted) and derives a posture the persona envelope and initiative
loops consult. The classifier is a pure function of the sample window —
every threshold below is unit-tested, no heuristics hide in I/O.

Postures: FOCUS (deep single-app focus) / FRAGMENTED (rapid switching) /
AWAY (idle) / NORMAL. Heartbeat initiative gating (ProactiveOutreach etc.)
lands in Phase-6; this module only classifies + phrases the envelope block.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Final, Literal

Posture = Literal["FOCUS", "FRAGMENTED", "AWAY", "NORMAL"]

FOCUS_SAME_APP_S: Final[float] = 25 * 60  # one foreground app this long
FOCUS_IDLE_MAX_S: Final[float] = 60.0  # …while actively inputting
FOCUS_MIN_SAMPLES: Final[int] = 3
FRAGMENTED_WINDOW_S: Final[float] = 15 * 60
FRAGMENTED_SWITCHES: Final[int] = 5  # >4 switches inside the window
AWAY_IDLE_S: Final[float] = 10 * 60
# Ring decay 30min (not 15): a 25-min same-app FOCUS span must stay observable
# under 90s heartbeat cadence (24 slots cover 2160s). Still strictly in-memory,
# still zero vault leakage — persistence, not duration, is the privacy bound.
SAMPLE_TTL_S: Final[float] = 30 * 60
RING_MAX: Final[int] = 24

POSTURE_BLOCKS_AR: Final[dict[str, str]] = {
    "FOCUS": "[الوضع الحالي: تركيز عميق — اختصر للنصف ولا تبادر بشيء غير مطلوب.]",
    "FRAGMENTED": "[الوضع الحالي: انتباه مشتت — مسموح تذكير خفيف بسطر واحد.]",
    "AWAY": "[الوضع الحالي: بعيد عن الجهاز — وضع الملخصات.]",
    "NORMAL": "",
}


@dataclass
class SituationalSample:
    process: str | None
    category: str
    idle_s: float | None
    t: float = field(default_factory=time.monotonic)


class SituationalState:
    """In-memory ring of attention samples; posture() is pure."""

    def __init__(self) -> None:
        self.samples: deque[SituationalSample] = deque(maxlen=RING_MAX)

    def push(
        self,
        process: str | None,
        category: str,
        idle_s: float | None,
        *,
        t: float | None = None,
    ) -> None:
        self.samples.append(
            SituationalSample(process, category, idle_s, t=t if t is not None else time.monotonic())
        )

    def _fresh(self, now: float) -> list[SituationalSample]:
        return [s for s in self.samples if now - s.t <= SAMPLE_TTL_S]

    def posture(self, *, now: float | None = None) -> Posture:
        now = time.monotonic() if now is None else now
        fresh = self._fresh(now)
        if not fresh:
            return "NORMAL"
        latest = fresh[-1]
        if latest.idle_s is not None and latest.idle_s > AWAY_IDLE_S:
            return "AWAY"
        procs = [s.process for s in fresh if s.process]
        if (
            len(fresh) >= FOCUS_MIN_SAMPLES
            and procs
            and len(set(procs)) == 1
            and fresh[-1].t - fresh[0].t >= FOCUS_SAME_APP_S
            and (latest.idle_s or 0.0) < FOCUS_IDLE_MAX_S
        ):
            return "FOCUS"
        window = [s for s in fresh if now - s.t <= FRAGMENTED_WINDOW_S]
        switches = sum(
            1
            for prev, cur in pairwise(window)
            if prev.process and cur.process and prev.process != cur.process
        )
        if switches >= FRAGMENTED_SWITCHES:
            return "FRAGMENTED"
        return "NORMAL"


def apply_posture(system: str, posture: Posture) -> str:
    """Append the ≤2-line posture block; NORMAL returns the prompt untouched."""
    block = POSTURE_BLOCKS_AR[posture]
    if not block:
        return system
    return f"{system}\n\n{block}"
