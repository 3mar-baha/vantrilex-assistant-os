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
    "screen_ocr": (
        "اقرأ",
        "اقرئيلي",
        "اقرأي",
        "استخرج",
        "استخرجيلي",
        "كود",
        "نص الشاشة",
        "النص الظاهر",
        "ocr",
    ),
    "volume": (
        "صوت",
        "اكتم",
        "كتم",
        "ارفع",
        "وطي",
        "علي الصوت",
        "نصي الصوت",
        "الصوت عالي",
        "الصوت واطي",
        "mute",
        "volume",
    ),
    "media": ("فيديو", "اغنية", "أغنية", "شغلي", "موسيقى", "سبوتيفاي", "مقطع", "تشغيل", "media"),
    "schedule": ("ذكر", "نبه", "تذكير", "مهمة جديدة", "سجلي مهمة", "remind", "schedule"),
    "list_reminders": (
        "تذكيراتي",
        "تذكيرات",
        "التذكيرات",
        "مسجلة",
        "المسجلة",
        "قائمة",
        "reminders",
    ),
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
    "volume": ("media", "telemetry"),
    "media": ("volume", "web_search"),
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

_ZONE_VERBS: Final[tuple[str, ...]] = (
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
    "شوف",
    "وقف",
    # Observer finding 2026-09-14 (weight 7/8): shadda-bearing verb stems
    # glued after و («وذكّريني») never split — the lookahead only knew bare
    # stems, so two-tool turns weighed as one. Diacritic forms occur only in
    # real verbs, never in «وضع/وقت/وين»-class nouns: zero fracture risk.
    "ذكّر",
    "سكّر",
    "فكّر",
    "نبّه",
    "شغّل",
)
# Clause splitter: explicit connectors, spaced + a + glued و ONLY before an
# action-verb stem («وذكريني» splits; «وضع/وقت/وين» never fracture).
_CONNECTORS: Final = re.compile(
    r"\s*(?:بعدين|بعدها|ثم|كمان)\s*|\s+و\s+|(?<=\s)و(?="
    + "|".join(_ZONE_VERBS)
    + r")|^و(?="
    + "|".join(_ZONE_VERBS)
    + r")"
)

# A proven multi-action request beats any single tool unless the single intent
# is decisively stronger — one tool can only ever satisfy PART of the turn.
_MULTI_PRECEDENCE_MARGIN: Final[float] = 0.30
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

    def render_ledger_block(self, day_iso: str) -> str:
        """Nightly append-only section for Daily_Logs; "" when frictionless."""
        notes = self.friction_notes()
        if not notes:
            return ""
        lines = [f"### تأمل {day_iso}", ""]
        for tool in sorted({note.split(":")[0] for note in notes}):
            count = self.failures.get(tool, 0)
            lines.append(f"- {tool} ×{count}")
        lines += [f"  - {note}" for note in notes]
        return "\n".join(lines) + "\n"


@dataclass
class CompositionCache:
    """Ephemeral session cache for read-only tool chains (P1 consensus).

    Keys normalize via _normalize; only chains composed EXCLUSIVELY of the
    caller-supplied read-only set are stored (a write tool poisons the
    whole chain). In-memory only — a restart is a full reset. Deriving the
    read-only set from safety_class metadata is P2 dispatcher wiring.
    """

    read_only_tools: frozenset[str] = frozenset()
    _chains: dict[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)
    _meta: dict[str, tuple] = field(default_factory=dict)

    def store(
        self, request: str, chain: tuple[tuple[str, str], ...], meta: tuple | None = None
    ) -> None:
        if not chain or any(tool not in self.read_only_tools for tool, _ in chain):
            return
        key = _normalize(request)
        self._chains[key] = chain
        if meta is not None:
            self._meta[key] = meta

    def lookup(self, request: str) -> tuple[tuple[str, str], ...] | None:
        return self._chains.get(_normalize(request))

    def lookup_meta(self, request: str) -> tuple | None:
        """Companion verdict data (ack/voice/domains) stored alongside a chain."""
        return self._meta.get(_normalize(request))

    def clear(self) -> None:
        self._chains.clear()
        self._meta.clear()


def _normalize(text: str) -> str:
    """Whitespace collapse + orthographic canon: tashkeel/shadda/tatweel carry
    no intent («شغّلي» == «شغلي») — the net scores letterforms, never diacritics."""
    import re as _re

    bare = _re.sub(r"[\u064b-\u0652\u0640]", "", text or "")
    return " ".join(bare.split()).strip()


# Drill-hardened (Stage-2 simulation 2026-09-12): short stems anchor at a
# token START on proclitic-stripped forms («شغ» fires on «شغلي/شغل/وافتحي»
# but never inside «مشغول/بشغلة/الشغل»; «اقفلي» still reaches «قفل»).
# Markers of 5+ chars stay substring matches (distinctive enough to be safe).
_SHORT_STEM_LEN: Final[int] = 5

# Conjunction/preposition/hamza proclitics plus the definite article stripped
# for matching. ال-derived forms carry a flag: a definite ARTICLE marks a noun
# («البريد» names the mail), so verb-family tools may never claim through it —
# the legacy (?<!ال) guard, principled («الشغل» = the work, never the command).
# 2026-09-13 audit: the 4-char remainder floor blinded every 3-letter root with
# ال («الصوت», «الكود» never stripped) and colloquial على→ع gluing («عالشاشة»)
# never stripped at all — both are legitimate article forms, so ال strips at
# remainder >= 3 and colloquial عال+ strips like ال. The floor still blocks
# sub-3-letter ghosts («وقفي» never becomes «قفي»).
_PROCLITICS: Final[tuple[str, ...]] = ("و", "ف", "ب", "ك", "ا", "أ")

_IMPERATIVE_TOOLS: Final[tuple[str, ...]] = (
    "schedule",
    "close",
    "cancel_reminder",
    "list_reminders",
    "launch",
    "create_event",
    "create_task",
)


def _strip_proclitics(token: str) -> list[tuple[str, bool]]:
    """(form, via_definite_article) candidates, raw first."""
    forms = [(token, False)]
    while True:
        current, definite = forms[-1]
        if current.startswith("عال") and len(current) - 3 >= 4:
            forms.append((current[3:], True))
        elif current.startswith("ال") and len(current) - 2 >= 3:
            forms.append((current[2:], True))
        elif len(current) > 4 and current[0] in _PROCLITICS:
            forms.append((current[1:], definite))
        else:
            break
    return forms


# Explicit do-not-disturb: with a weak signal these defer to silent logging
# instead of firing an action tool mid-focus.
_BUSY_MARKERS: Final[tuple[str, ...]] = ("مشغول", "لا تزعج", "busy")

# A leading action verb names the primary intent («ذكريني بشغلة» is a reminder
# even though it mentions a thing; the legacy net ruled the same way).
_LEAD_WINDOW: Final[int] = 12
_LEAD_BONUS: Final[float] = 0.30
_WEAK_SIGNAL_CAP: Final[float] = 0.50


def _hit_spans(
    marker: str,
    clean: str,
    token_offsets: list[tuple[str, int]],
    *,
    allow_definite: bool = True,
) -> list[tuple[int, int]]:
    """Character spans where `marker` fires. Short stems anchor at stripped
    token starts; long markers match anywhere. ال-derived forms are refused
    unless `allow_definite` (verb tools never claim through the article).
    Empty when no evidence."""
    if not marker:
        return []
    if len(marker) >= _SHORT_STEM_LEN:
        spans, i = [], clean.find(marker)
        while i >= 0:
            spans.append((i, i + len(marker)))
            i = clean.find(marker, i + 1)
        return spans
    spans = []
    for token, offset in token_offsets:
        for form, definite in _strip_proclitics(token):
            if definite and not allow_definite:
                continue
            if form.startswith(marker):
                start = offset + (len(token) - len(form))
                spans.append((start, start + len(marker)))
                break
    return spans


def _merge_spans(spans: list[tuple[int, int]]) -> int:
    """Overlapping evidence on one span counts ONCE («شغل»+«شغ» on «شغل»)."""
    count, end = 0, -1
    for start, stop in sorted(spans):
        if start >= end:
            count += 1
            end = stop
        else:
            end = max(end, stop)
    return count


def _lead_bonus(markers: tuple[str, ...], lead: str, lead_tokens: list[str]) -> bool:
    """A leading action verb names the primary intent. Single-word markers
    anchor conservatively on RAW lead tokens («بشغلة» never re-arms «شغ»);
    multi-word markers match the lead window directly («سجلي مهمة»).
    2026-09-13 audit: bare 2-3-letter prefixes («شغل» on «شغلي موسيقى»)
    over-committed ambiguous verbs to launch — the bonus now needs a whole
    token or a 4+ letter stem, so the object noun can outvote the verb."""
    for marker in markers:
        if not marker:
            continue
        if " " in marker:
            if marker in lead:
                return True
        elif any(
            tok == marker or (len(marker) >= 4 and tok.startswith(marker)) for tok in lead_tokens
        ):
            return True
    return False


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
    tokens = clean.split()
    offsets: list[tuple[str, int]] = []
    cursor = 0
    for token in tokens:
        cursor = clean.index(token, cursor)
        offsets.append((token, cursor))
        cursor += len(token)
    lead = clean[:_LEAD_WINDOW]
    ranked: list[IntentHypothesis] = []
    for tool, goals in _TOOL_GOALS.items():
        markers = _goal_markers(tool, goals)
        # multi_task needs 2+ distinct action zones joined by a connector;
        # score it by connector-separated action density instead of raw hits.
        if tool == "multi_task":
            parts = [p for p in _CONNECTORS.split(clean) if p.strip()]
            score = 0.0
            if len(parts) >= 2:
                action_zones = sum(
                    1 for p in parts if any(g.strip() and g.strip() in p for g in _ZONE_VERBS)
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
        # Principle: an expressed goal concept IS intent evidence. Overlapping
        # spans merge (one stem on one token = one vote, never double counts).
        # Imperative-action tools outrank topic mentions («ذكريني ... الجيميل»
        # is a reminder, not a mail read).
        allow_definite = tool not in _IMPERATIVE_TOOLS
        spans: list[tuple[int, int]] = []
        for marker in markers:
            spans.extend(_hit_spans(marker, clean, offsets, allow_definite=allow_definite))
        evidence = _merge_spans(spans)
        hits = sorted(
            {g for g in markers if _hit_spans(g, clean, offsets, allow_definite=allow_definite)}
        )
        if not evidence:
            base = 0.0
        else:
            base = min(0.20 + 0.25 * (evidence - 1), 0.95)
            if any(len(h) >= 4 for h in hits):
                base += 0.10  # distinctive marker, not a coincidental substring
            if tool in _IMPERATIVE_TOOLS:
                base += 0.12  # action imperative beats topic noun
                if _lead_bonus(markers, lead, lead.split()):
                    base += _LEAD_BONUS  # leading verb names the primary intent
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
    clean = _normalize(text)
    if any(b in clean for b in _BUSY_MARKERS) and best.confidence < _WEAK_SIGNAL_CAP:
        # Do-not-disturb with a weak signal: stay silent, log to the ledger.
        return IntentHypothesis(
            tool="none",
            arg="",
            confidence=1.0 - best.confidence,
            rationale=f"user busy, weak signal (best={best.tool}@{best.confidence:.2f}) — silent ledger",
            root_goal="do not interrupt",
            scores={},
        )
    multi = next((h for h in ranked if h.tool == "multi_task"), None)
    if (
        multi is not None
        and multi.confidence >= 0.55
        and best.tool != "multi_task"
        and best.confidence - multi.confidence < _MULTI_PRECEDENCE_MARGIN
    ):
        return multi
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
