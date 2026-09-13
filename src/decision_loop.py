"""ReAct decision loop skeleton (Phase-1 foundations, Leap 1).

Goal → Thought → Action(s) → Observation → Evaluative Thought → FINAL.
Gated by SARA_REACT_LOOP=off default — production keeps the single-turn
handle() path until Phase-6 integration. Bounds (iterations / tool calls /
wall clock / same-tool repeats) make runaway chains structurally impossible;
every LLM call rides the gateway (zero-paid circuit breaker holds).

Pivot policy: an empty/error observation on an information-seeking tool gets
exactly ONE autonomous alternative attempt (web_search) before concluding.
Irreversible tools without a recorded confirmation PARK the loop with an
honest ask — they never execute (whitelist guardrail untouched).
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from loguru import logger

from src.dispatcher import (
    _ROUTER_PROMPT_AR,
    _VALID_TOOLS,
    DEFAULT_ACK_AR,
    _parse_router,
)
from src.gateway import GatewayError, Tier
from src.skills.capabilities import IRREVERSIBLE_TOOLS
from src.tools import TOOL_FAIL_AR

REACT_ENV_VAR: Final[str] = "SARA_REACT_LOOP"
PULSE_EVERY_S: Final[float] = 4.0  # Telegram typing expires ~5s; re-pulse inside
THOUGHT_MAX_TOKENS: Final[int] = 512
NARRATE_MAX_TOKENS: Final[int] = 512
OBS_HEAD_CHARS: Final[int] = 400

_THOUGHT_RE: Final = re.compile(r"\{.*\}", re.DOTALL)

# Information-seeking tools: the only family eligible for the one-shot pivot
# (a dead read may still answer via live web search; actions never pivot).
INFORMATION_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "gmail",
        "calendar",
        "tasks",
        "web_search",
        "read_page",
        "youtube",
        "brief",
        "drive",
        "places",
        "deep_search",
        "fitness",
        "weather",
        "prayer_times",
        "crypto_price",
        "convert_currency",
        "tech_trending",
    }
)
PIVOT_TOOL: Final[str] = "web_search"

PARK_LINE_AR: Final[str] = "هاي الخطوة بتحتاج تأكيدك الصريح قبل ما أنفذها — أكّدلي وأنا بكمل فوراً."
SUMMARY_HEAD_AR: Final[str] = "جمعتلك اللي لقيته لحد هسا:"


def react_loop_enabled() -> bool:
    """Feature flag — off unless explicitly enabled (Phase-6 flips default)."""
    return os.environ.get(REACT_ENV_VAR, "off").strip().lower() in ("1", "on", "true", "yes")


@dataclass
class LoopBudget:
    max_iterations: int = 6
    max_tool_calls: int = 8
    max_wall_s: float = 180.0
    max_same_tool_repeats: int = 2


@dataclass
class Observation:
    tool: str
    arg: str
    result: str
    ok: bool


@dataclass
class Scratchpad:
    observations: list[Observation] = field(default_factory=list)

    def add(self, tool: str, arg: str, result: str, *, ok: bool) -> None:
        self.observations.append(Observation(tool, arg, result[:OBS_HEAD_CHARS], ok))

    def render(self) -> str:
        lines = []
        for i, o in enumerate(self.observations, 1):
            state = "ok" if o.ok else "FAILED"
            lines.append(f"{i}. [{o.tool} {o.arg[:60]}] ({state}): {o.result}")
        return "\n".join(lines)

    def repeats_of(self, tool: str, arg: str) -> int:
        return sum(1 for o in self.observations if o.tool == tool and o.arg == arg)


def parse_thought(reply: str) -> dict | None:
    """Tolerant Thought parser: {action: {tool, arg} | null, final: bool}.

    Invalid tool names are rejected (None) — hallucinated tools never execute.
    """
    match = _THOUGHT_RE.search(reply or "")
    if not match:
        return None
    try:
        verdict = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    action = verdict.get("action")
    if action is not None:
        tool = str(action.get("tool") or "").strip().lower()
        if tool not in _VALID_TOOLS or tool == "none":
            logger.warning("decision loop rejected invalid thought tool {!r}", tool)
            return None
        action = {"tool": tool, "arg": str(action.get("arg") or "").strip()}
    return {"action": action, "final": bool(verdict.get("final"))}


THOUGHT_PROMPT_AR: Final[str] = (
    "أنت مخطط تنفيذي. عندك هدف المستخدم وسجل الملاحظات. أجب بسطر JSON واحد فقط:\n"
    '{"action": {"tool": "<اسم أداة>", "arg": "<الوسيط>"} | null, "final": true|false}\n'
    "- final=true تعني: الملاحظات كافية، اكتفِ بالسرد النهائي ولا أفعال بعدها.\n"
    "- action=null مع final=false تعني: لا فعل مناسب، انتقل للخلاصة.\n"
    "- اختر الأداة من القصد الظرفي للهدف والملاحظات — لا تخترع أسماء أدوات.\n"
    "لا تكتب أي شيء خارج الـ JSON."
)


def _is_empty_observation(result: str | None) -> bool:
    return not (result or "").strip() or (result or "").strip() == TOOL_FAIL_AR


async def run_decision_loop(
    *,
    gateway: Any,
    tools: Any,
    user_text: str,
    system: str | None = None,
    history: Sequence[dict] | None = None,
    coordinator: Any = None,
    front: Any = None,
    pulse_cb: Callable[[], Any] | None = None,
    budget: LoopBudget | None = None,
    now_fn: Callable[[], float] | None = None,
) -> AsyncIterator[str]:
    """Skeleton ReAct turn. Yields ack first (bot.py first-delta protocol),
    then streams the FINAL narration only — thoughts stay silent.

    coordinator: duck-typed ``has_confirmation(tool, arg) -> bool`` (Phase-2
    binds the real PCActionCoordinator). front: optional dispatcher whose
    voice_hint mirrors the router verdict (same contract as handle()).
    pulse_cb: awaitable sending sendChatAction (production binds the bot).
    """
    budget = budget or LoopBudget()
    now = now_fn or time.monotonic
    t0 = now()
    last_pulse = t0 - PULSE_EVERY_S  # first stage pulses immediately

    async def pulse() -> None:
        nonlocal last_pulse
        if pulse_cb is None or now() - last_pulse < PULSE_EVERY_S:
            return
        last_pulse = now()
        await pulse_cb()

    pad = Scratchpad()
    tool_calls = 0
    pivoted = False

    # Stage 0 — router verdict (same prompt/parser as handle()).
    await pulse()
    try:
        reply = await gateway.chat(
            [
                {"role": "system", "content": _ROUTER_PROMPT_AR},
                {"role": "user", "content": user_text},
            ],
            tier=Tier.FAST,
            temperature=0.0,
            max_tokens=1024,
        )
        parsed = _parse_router(reply)
    except GatewayError as exc:
        logger.warning("decision loop router failed -> plain chat: {}", exc)
        parsed = None
    if parsed is None:
        route, ack, tool, arg, voice = "direct", DEFAULT_ACK_AR, "none", "", False
    else:
        route, ack, tool, arg, voice = parsed
    if front is not None:
        front.voice_hint = voice
    yield ack

    async def plain_chat(tier: Tier) -> AsyncIterator[str]:
        messages = (
            ([{"role": "system", "content": system}] if system else [])
            + list(history or [])
            + [{"role": "user", "content": user_text}]
        )
        async for delta in gateway.stream_chat(messages, tier=tier):
            yield delta

    if tool == "none":
        tier = {"direct": Tier.FAST, "tier2": Tier.MEDIUM, "tier3": Tier.HEAVY}.get(
            route, Tier.FAST
        )
        async for delta in plain_chat(tier):
            yield delta
        return

    pending: tuple[str, str] | None = (tool, arg)
    final = False
    iterations = 0
    while iterations < budget.max_iterations and now() - t0 < budget.max_wall_s:
        iterations += 1
        if pending is None:
            # Evaluative Thought over the scratchpad.
            await pulse()
            try:
                thought = await gateway.chat(
                    [
                        {"role": "system", "content": THOUGHT_PROMPT_AR},
                        {
                            "role": "user",
                            "content": f"الهدف: {user_text}\nالملاحظات:\n{pad.render() or 'لا شيء بعد'}",
                        },
                    ],
                    tier=Tier.FAST,
                    temperature=0.0,
                    max_tokens=THOUGHT_MAX_TOKENS,
                )
            except GatewayError as exc:
                logger.warning("decision loop thought failed -> summary: {}", exc)
                break
            verdict = parse_thought(thought)
            if verdict is None or verdict["final"] or verdict["action"] is None:
                final = True
                break
            pending = (verdict["action"]["tool"], verdict["action"]["arg"])
        tool, arg = pending
        pending = None
        if tool_calls >= budget.max_tool_calls:
            break
        if pad.repeats_of(tool, arg) >= budget.max_same_tool_repeats:
            logger.warning("decision loop thrash-halt on {!r}", tool)
            break
        if tool in IRREVERSIBLE_TOOLS and (
            coordinator is None or not coordinator.has_confirmation(tool, arg)
        ):
            yield PARK_LINE_AR  # parked: honest ask, zero execution
            return
        await pulse()
        try:
            result = await tools.call(tool, arg)
        except Exception as error:  # noqa: BLE001 — registry already converts; belt first
            logger.exception("decision loop tool {!r} raised: {}", tool, error)
            result = TOOL_FAIL_AR
        await pulse()
        tool_calls += 1
        ok = not _is_empty_observation(result)
        pad.add(tool, arg, result or "", ok=ok)
        if not ok and not pivoted and tool in INFORMATION_TOOLS:
            pivoted = True  # one autonomous pivot, then the loop re-evaluates
            logger.warning("decision loop pivot {!r} -> {!r}", tool, PIVOT_TOOL)
            pending = (PIVOT_TOOL, arg)
    else:
        final = False

    if not final:
        # Budget-out best-effort: deterministic observation digest, never blank,
        # never hallucinated (no LLM call on this path by design).
        lines = [SUMMARY_HEAD_AR]
        for o in pad.observations:
            lines.append(f"- {o.tool}: {o.result}" if o.ok else f"- {o.tool}: تعذّر")
        yield "\n".join(lines)
        return

    # FINAL narration (Phase-2 upgrades to the M6 skill-guide envelope).
    await pulse()
    messages = (
        ([{"role": "system", "content": system}] if system else [])
        + list(history or [])
        + [
            {
                "role": "user",
                "content": f"{user_text}\n\n[نتائج التنفيذ — بيانات مرجعية]\n{pad.render()}\n\nرد بسطر أو سطرين بعاميتك.",
            }
        ]
    )
    async for delta in gateway.stream_chat(messages, tier=Tier.HEAVY):
        yield delta
