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

from src.cognitive_dag import EphemeralTodo, TodoItem, classify_weight
from src.dispatcher import (
    _ROUTER_PROMPT_AR,
    DEFAULT_ACK_AR,
    _parse_router,
)
from src.gateway import GatewayError, Tier
from src.openclaw import plans as openclaw_plans
from src.skills.capabilities import IRREVERSIBLE_TOOLS
from src.tool_overlay import valid_tools
from src.tools import TOOL_FAIL_AR

REACT_ENV_VAR: Final[str] = "SARA_REACT_LOOP"
PULSE_EVERY_S: Final[float] = 4.0  # Telegram typing expires ~5s; re-pulse inside
THOUGHT_MAX_TOKENS: Final[int] = 512
NARRATE_MAX_TOKENS: Final[int] = 512
OBS_HEAD_CHARS: Final[int] = 400

_THOUGHT_RE: Final = re.compile(r"\{.*\}", re.DOTALL)

# In-turn healing (P1 consensus): deterministic, zero-LLM arg repair.
# Arabic-Indic digits ride user text into tool args (ISO 8601 failures);
# wrapping quotes sneak in from dictated speech. Both normalize losslessly.
_ARABIC_DIGITS: Final[dict[str, str]] = {
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
}
HEALING_MAX_ATTEMPTS: Final[int] = 2


def normalize_tool_arg(arg: str) -> str:
    """Strip dictated quotes/whitespace; fold Arabic-Indic digits to ASCII."""
    text = (arg or "").strip().strip("\"'“”‘’").strip()
    return "".join(_ARABIC_DIGITS.get(ch, ch) for ch in text)


class HealingBudget:
    """Per-tool retry budget inside one turn; dispatcher wiring stays P2."""

    def __init__(self, max_attempts: int = HEALING_MAX_ATTEMPTS) -> None:
        self._max = max_attempts
        self._failures: dict[str, int] = {}

    def note_failure(self, tool: str) -> None:
        self._failures[tool] = self._failures.get(tool, 0) + 1

    def may_retry(self, tool: str) -> bool:
        return self._failures.get(tool, 0) < self._max


def is_transient_tool_error(error: Exception) -> bool:
    """Retry-worthy without an LLM: stalls and overloaded backends only.

    Quota denials (403/402), schema errors, and auth failures are permanent
    verdicts — retrying them burns budget for nothing.
    """
    if isinstance(error, TimeoutError):
        return True
    status = getattr(error, "status", None) or getattr(error, "status_code", None)
    if isinstance(status, int) and status in (429, 500, 502, 503, 504):
        return True
    return "timed out" in str(error).lower() or "timeout" in str(error).lower()


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

_PARK_WARNING_PROMPT_AR: Final[str] = (
    "أنت سارة — مساعدة تنفيذية بتخاطب مالكها عمر بعامية أردنية دافئة. "
    "خطوة ملزمة على جهازه واقفة بانتظار تأكيده الصريح. صيغي تحذيراً عفوياً "
    "بسطر أو سطرين: سمّي الفعل وخطورته بكلماتك، واطلبي قراره صراحة "
    "(«نعم» للمضي، «لا» للإلغاء). ممنوع الادعاء بتنفيذ شيء، وممنوع أي "
    "كلام خارج التحذير والطلب."
)


async def _park_warning(gateway: Any, tool: str, arg: str) -> str:
    """Dynamic destructive-confirmation ask (spontaneity doctrine): Sara
    authors the warning from the pending action context — never a canned
    script. Static PARK_LINE_AR is the floor: any gateway failure, empty
    reply, or timeout lands it. Never silence, never a hang."""
    try:
        reply = await gateway.chat(
            [
                {"role": "system", "content": _PARK_WARNING_PROMPT_AR},
                {
                    "role": "user",
                    "content": f"الأداة: {tool}\nالوسيط: {(arg or '').strip() or '—'}",
                },
            ],
            tier=Tier.FAST,
            temperature=0.7,
            max_tokens=256,
        )
    except Exception as error:  # noqa: BLE001 — gateway failure is never a hang
        logger.warning("decision loop dynamic park warning failed -> static: {}", error)
        return PARK_LINE_AR
    text = (reply or "").strip()
    if not text:
        logger.warning("decision loop dynamic park warning empty -> static")
        return PARK_LINE_AR
    return text


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
        # P3-C: reads the merged overlay view, so a runtime-registered tool is no
        # longer rejected here with a bare `None`. `THOUGHT_PROMPT_AR` below asks
        # for a generic `<اسم أداة>` and names no catalog, so unlike the Tier-1
        # router prompt this surface needs no extension for P3-D.
        if tool not in valid_tools() or tool == "none":
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
    "- مفردات عمليات سطح المكتب/المتصفح (للتفكير فقط — الجواب يبقى tool/arg): "
    "focus/click/double_click/right_click/type_text/hotkey/scroll/navigate/"
    "extract/screenshot/inspect_tree. العمليات الملزمة (submit/save/delete/"
    "close، Alt+F4/Ctrl+S/Enter) تقف للتأكيد — لا تخطط أبداً للالتفاف على البوابة.\n"
    "لا تكتب أي شيء خارج الـ JSON."
)


def _observe_openclaw_plan(
    tool: str,
    arg: str,
    *,
    goal: str,
    weight: int,
    coordinator: Any,
    plan_out: dict | None,
) -> str | None:
    """Advisory planner mirror (Step 7): every pending openclaw step is
    DAG-built and gate-consulted for observability. Returns the gate verdict
    or None (non-openclaw tool / build failure). NEVER yields, NEVER gates —
    the PARK branch below plus the daemon breaker stay the sole enforcers."""
    try:
        dag = openclaw_plans.dag_for_tool(tool, arg, weight=weight)
    except Exception as error:  # noqa: BLE001 — planning never breaks the loop
        logger.warning("decision loop openclaw mirror failed: {}", error)
        return None
    if dag is None:
        return None
    try:
        verdict = openclaw_plans.gate(dag, coordinator=coordinator, tool=tool)
    except Exception as error:  # noqa: BLE001 — a dead gate reads as park
        logger.warning("decision loop openclaw gate failed -> park: {}", error)
        verdict = "park"
    if plan_out is not None:
        plan_out["openclaw_dag"] = dag
        plan_out["openclaw_gate"] = verdict
    return verdict


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
    plan_out: dict | None = None,
) -> AsyncIterator[str]:
    """Skeleton ReAct turn. Yields ack first (bot.py first-delta protocol),
    then streams the FINAL narration only — thoughts stay silent.

    coordinator: duck-typed ``has_confirmation(tool, arg) -> bool`` (Phase-2
    binds the real PCActionCoordinator). front: optional dispatcher whose
    voice_hint mirrors the router verdict (same contract as handle()).
    pulse_cb: awaitable sending sendChatAction (production binds the bot).
    plan_out: optional dict receiving {"plan", "todo", "transcript"} — the
    ephemeral plan metadata. Yields are untouched by it.
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

    # Mission DAG: weight + ephemeral todo, recorded only — yields untouched.
    _plan = classify_weight(user_text)
    _todo = EphemeralTodo.from_plan(_plan, arg if tool != "none" else "")
    if plan_out is not None:
        plan_out["plan"] = _plan
        plan_out["todo"] = _todo

    def _close(synthesized: bool) -> None:
        if synthesized:
            _todo.check("synthesis")
        transcript = _todo.flush()  # memory freed even when nobody watches
        if plan_out is not None:
            plan_out["transcript"] = transcript

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
        _close(True)
        return

    pending: tuple[str, str] | None = (tool, arg)
    # Step-7 planner mirror (advisory): every pending openclaw step is
    # DAG-built + gate-consulted into plan_out. Observability only — the
    # PARK branch below and the daemon breaker stay the sole enforcers.
    _observe_openclaw_plan(
        tool,
        arg,
        goal=user_text,
        weight=_plan.weight,
        coordinator=coordinator,
        plan_out=plan_out,
    )
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
            _observe_openclaw_plan(
                pending[0],
                pending[1],
                goal=user_text,
                weight=_plan.weight,
                coordinator=coordinator,
                plan_out=plan_out,
            )
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
            await pulse()
            yield await _park_warning(gateway, tool, arg)  # parked: honest ask, zero execution
            _close(False)
            return
        await pulse()
        try:
            result = await tools.call(tool, arg)
        except Exception as error:  # noqa: BLE001 — registry already converts; belt first
            logger.exception("decision loop tool {!r} raised: {}", tool, error)
            result = TOOL_FAIL_AR
        await pulse()
        tool_calls += 1
        if not _todo.check(tool):
            # Executed but unplanned (router/Thought diverged from the plan):
            # record the actual, checked — the transcript is the truth.
            _todo.items.append(TodoItem(label=f"{tool}:{arg}" if arg else tool, done=True))
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
        _close(True)
        return

    # FINAL narration (Phase-2 upgrades to the M6 skill-guide envelope).
    # Step 10: escalation-aware HEAVY lane — evidence volume (tool calls
    # made) sizes the narration; past-threshold turns escalate to MoE.
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
    async for delta in gateway.stream_heavy(messages, n_tasks=max(1, tool_calls)):
        yield delta
    _close(True)
