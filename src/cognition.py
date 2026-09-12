"""Principles-over-Rules cognition (Tier 3 paradigm).

Replaces brittle first-regex-wins keyword matching with a scored,
explainable intent-deduction pass:

1. Root Intent Deduction — every tool declares the human GOALS it serves
   (not trigger words). The text is scored against all goals; the winner
   must explain why it beat every alternative.
2. Contextual Horizon Expansion — when the winning path is blocked, adjacent
   tools that honor the same root goal are proposed (offline screenshot ->
   telemetry description, blocked launch -> whitelist guidance, ...).
3. Reflective Self-Correction — ReflectiveTrace records friction per turn and
   demotes repeatedly-failing tools on subsequent turns without new rules.

Pure heuristics, zero LLM calls, zero network. The LLM router stays primary;
this engine is the principled replacement for the deterministic _TOOL_NET as
the behind-router safety layer (the net remains as the final fallback).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

# Goal families per tool: human objectives, not trigger spellings. Each entry
# is a set of concept markers (Arabic stems + English). Scoring counts how
# many distinct goal concepts appear — a paraphrase scores, a coincidental
# single-word collision does not dominate.
_TOOL_GOALS: Final[dict[str, tuple[str, ...]]] = {
    "multi_task": ("و بعدين", "و ", "ثم", "كمان", "بعدها"),
    "gmail": ("جيميل", "بريد", "ايميل", "إيميل", "رسائل", "inbox", "mail"),
    "calendar": ("موعد", "مواعيد", "تقويم", "اجتماع", "calendar"),
    "tasks": ("مهام", "مهمة", "مستحق", "tasks", "todo"),
    "telemetry": ("جهاز", "رام", "معالج", "بطيء", "حالة", "telemetry", "cpu"),
    "launch": ("افتح", "شغل", "شغ", "launch", "open", "start"),
    "close": ("سكر", "اغلق", "أغلق", "اطف", "وقف", "قفل", "close", "kill"),
    "screenshot": ("شاشة", "لقطة", "سكرين", "صوري", "screenshot"),
    "screen_ocr": ("اقرأ", "استخرج", "كود", "نص الشاشة", "ocr"),
    "volume": ("صوت", "اكتم", "ارفع", "وطي", "volume"),
    "media": ("فيديو", "اغنية", "أغنية", "مقطع", "تشغيل", "media"),
    "schedule": ("ذكر", "نبه", "تذكير", "مهمة جديدة", "remind", "schedule"),
    "list_reminders": ("تذكيراتي", "قائمة التذكيرات", "reminders"),
    "cancel_reminder": ("الغي", "امسح", "شيلي التذكير", "cancel"),
    "weather": ("طقس", "حرارة", "weather"),
    "web_search": ("بالنت", "في النت", "ابحث", "دور", "search"),
    "youtube": ("يوتيوب", "youtube"),
    "read_page": ("رابط", "مقال", "صفحة", "لخص", "http"),
    "prayer_times": ("صلاة", "اذان", "أذان", "مواقيت", "prayer"),
    "crypto_price": ("بيتكوين", "اثيريوم", "كريبتو", "crypto"),
    "convert_currency": ("دولار", "يورو", "دينار", "حول", "currency"),
    "file_fetch": ("ملف", "ابعثيلي ملف", "ارسلي ملف", "file"),
    "create_folder": ("فولدر", "مجلد", "folder"),
    "knowledge_graph": ("شبكة المعرفة", "مين بيحكي", "روابط", "graph"),
    "running_apps": ("مفتوح", "شغال", "التطبيقات", "running"),
    "whitelist_apps": ("مسموح", "معتمد", "قائمة", "صلاحية", "whitelist"),
    "brief": ("إحاطة", "احاطة", "نشرة", "brief"),
    "app_sessions": ("استخدمت", "جلسات", "استخدام البرامج", "sessions"),
    "drive": ("درايف", "drive"),
    "contacts": ("جهات الاتصال", "معلوماتي", "contacts"),
    "create_event": ("سجلي موعد", "ضيفي اجتماع", "create event"),
    "create_task": ("ضيفي مهمة", "مهمة جديدة", "create task"),
    "places": ("كافيه", "مطعم", "اماكن", "places"),
    "deep_search": ("بجوجل", "بحث متقدم", "deep search"),
    "fitness": ("مشيت", "خطوات", "سعرات", "fitness"),
    "network_status": ("ايبي", "شبكة", "ip", "network"),
    "tech_trending": ("اخبار التقنية", "أخبار التكنولوجيا", "tech news"),
}

# Adjacent alternatives honoring the same root goal when the winner is blocked.
_HORIZON: Final[dict[str, tuple[str, ...]]] = {
    "screenshot": ("screen_ocr", "telemetry", "running_apps"),
    "screen_ocr": ("screenshot", "telemetry"),
    "launch": ("whitelist_apps", "running_apps"),
    "close": ("running_apps", "telemetry"),
    "telemetry": ("running_apps", "app_sessions", "network_status"),
    "gmail": ("brief", "tasks"),
    "calendar": ("create_event", "brief", "list_reminders"),
    "tasks": ("create_task", "schedule", "list_reminders"),
    "schedule": ("create_task", "list_reminders", "calendar"),
    "web_search": ("deep_search", "read_page", "tech_trending"),
    "read_page": ("web_search", "deep_search"),
    "weather": ("brief", "web_search"),
    "drive": ("file_fetch", "web_search"),
    "file_fetch": ("drive", "running_apps"),
}

_CONNECTORS: Final = re.compile(r"\s*(?:و|بعدين|بعدها|ثم|كمان)\s*")
_URL_RE: Final = re.compile(r"https?://\S+")
_NEGATION_RE: Final = re.compile(r"لا\s+(?:ترسلي|تبعتي|ترسل)|بدون\s+(?:صورة|ما)|بس\s+(?:صفي|احكي)")


@dataclass
class IntentHypothesis:
    tool: str
    arg: str
    confidence: float
    rationale: str
    root_goal: str
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ReflectiveTrace:
    """Per-conversation friction ledger: failures demote tools next turn."""

    failures: dict[str, int] = field(default_factory=dict)
    turns: list[dict[str, Any]] = field(default_factory=list)

    def record_outcome(self, tool: str, ok: bool, note: str = "") -> None:
        self.turns.append({"tool": tool, "ok": ok, "note": note})
        if ok:
            self.failures.pop(tool, None)
        else:
            self.failures[tool] = self.failures.get(tool, 0) + 1

    def penalty(self, tool: str) -> float:
        return min(0.30 * self.failures.get(tool, 0), 0.60)

    def friction_notes(self) -> list[str]:
        return [f"{t['tool']}: {t['note']}" for t in self.turns if not t["ok"]]


def _normalize(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _goal_markers(tool: str, goals: tuple[str, ...]) -> tuple[str, ...]:
    """Union the inline goal family with the first-class capability registry
    (`src/skills/capabilities.py`) — one vocabulary, two consumers, no drift."""
    try:
        from src.skills.capabilities import markers_for
    except Exception:  # noqa: BLE001 — registry unavailable: inline family stands alone
        return goals
    extra = markers_for(tool)
    return tuple(dict.fromkeys((*goals, *extra)))


def evaluate_candidates(
    text: str, *, trace: ReflectiveTrace | None = None
) -> list[IntentHypothesis]:
    """Score EVERY tool against the text; return ranked hypotheses (best first)."""
    clean = _normalize(text)
    ranked: list[IntentHypothesis] = []
    for tool, goals in _TOOL_GOALS.items():
        hits = [g for g in _goal_markers(tool, goals) if g and g in clean]
        # multi_task needs 2+ distinct action zones joined by a connector;
        # score it by connector-separated action density instead of raw hits.
        if tool == "multi_task":
            parts = [p for p in _CONNECTORS.split(clean) if p.strip()]
            score = 0.0
            if len(parts) >= 2:
                action_zones = sum(
                    1
                    for p in parts
                    if any(
                        g.strip() and g.strip() in p
                        for g in (
                            "فتح",
                            "شغل",
                            "سكر",
                            "ذكر",
                            "ابحث",
                            "ارفع",
                            "صوري",
                            "ابعث",
                            "افتحي",
                            "شغلي",
                            "سكري",
                        )
                    )
                )
                if action_zones >= 2:
                    score = 0.55 + 0.10 * min(action_zones - 2, 3)
            if trace is not None:
                score -= trace.penalty(tool)
            ranked.append(
                IntentHypothesis(
                    tool=tool,
                    arg=clean,
                    confidence=max(score, 0.0),
                    rationale=f"{action_zones if len(parts) >= 2 else 0} action zones across {len(parts)} clauses"
                    if len(parts) >= 2
                    else "single clause — not multi-task",
                    root_goal="execute several distinct actions in one turn",
                    scores={"zones": len(parts)},
                )
            )
            continue
        # Principle: an expressed goal concept IS intent evidence. Score by hit
        # count (not normalized by family size — large families must not be
        # punished). Imperative-action tools outrank topic mentions («ذكريني
        # ... الجيميل» is a reminder, not a mail read).
        if not hits:
            base = 0.0
        else:
            base = min(0.20 + 0.25 * (len(hits) - 1), 0.95)
            if any(len(h) >= 4 for h in hits):
                base += 0.10  # distinctive marker, not a coincidental substring
            if tool in (
                "schedule",
                "close",
                "cancel_reminder",
                "list_reminders",
                "launch",
                "create_event",
                "create_task",
            ):
                base += 0.12  # action imperative beats topic noun
        if trace is not None:
            base -= trace.penalty(tool)
        ranked.append(
            IntentHypothesis(
                tool=tool,
                arg=_extract_arg(tool, clean),
                confidence=max(base, 0.0),
                rationale=f"matched {len(hits)} goal concept(s): {hits[:3]}"
                if hits
                else "no goal concepts matched",
                root_goal=_root_goal_line(tool),
                scores={"hits": len(hits)},
            )
        )
    ranked.sort(key=lambda h: h.confidence, reverse=True)
    return ranked


def _root_goal_line(tool: str) -> str:
    goals = {
        "gmail": "know what arrived in my mail",
        "calendar": "know my upcoming commitments",
        "telemetry": "know my device state",
        "launch": "have an app opened on my PC",
        "close": "have an app stopped on my PC",
        "screenshot": "see what is on my screen now",
        "schedule": "never forget a future obligation",
        "weather": "know the weather where I am",
    }
    return goals.get(tool, f"satisfy the {tool} need")


def _extract_arg(tool: str, clean: str) -> str:
    if tool in ("multi_task", "schedule", "volume", "media"):
        return clean  # planners/parsers need the full phrasing
    url = _URL_RE.search(clean)
    if tool == "read_page" and url:
        return url.group(0)
    if tool == "screenshot" and _NEGATION_RE.search(clean):
        return "no-send"
    # Generic: trailing entity after the verb (best-effort, never empty-critical).
    parts = clean.split()
    if len(parts) >= 3:
        return " ".join(parts[-2:])
    return ""


def deduce(text: str, *, trace: ReflectiveTrace | None = None) -> IntentHypothesis:
    """Top-ranked hypothesis, or a confident 'none' when nothing matches."""
    ranked = evaluate_candidates(text, trace=trace)
    best = ranked[0]
    if best.confidence < 0.12:
        return IntentHypothesis(
            tool="none",
            arg="",
            confidence=1.0 - best.confidence,
            rationale=f"no tool earned trust (best={best.tool}@{best.confidence:.2f}) — plain chat",
            root_goal="talk, not act",
            scores={},
        )
    return best


def expand_horizon(tool: str, *, blocked_reason: str = "") -> list[str]:
    """Adjacent tools honoring the same root goal when `tool` is blocked."""
    alts = list(_HORIZON.get(tool, ()))
    if not alts and tool != "none":
        alts = ["web_search", "brief"]  # generic adjacent knowledge goal
    return alts


def explain_choice(ranked: list[IntentHypothesis], *, top_n: int = 4) -> str:
    lines = [f"winner={ranked[0].tool}@{ranked[0].confidence:.2f} — {ranked[0].rationale}"]
    for h in ranked[1:top_n]:
        lines.append(f"rejected {h.tool}@{h.confidence:.2f} — {h.rationale}")
    return " | ".join(lines)
