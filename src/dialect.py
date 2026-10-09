"""M1 adaptive Jordanian dialect engine.

Notes-driven pronunciation normalization before Fish Audio synthesis, an ingestion
loop for owner corrections/slang, and the system-prompt snapshot — per
`docs/specs/master-directive-2026-08-29.md` M1. Zero-cost, pure-python, no I/O:
the vault client (Sprint 3.1) persists the notes file around this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from loguru import logger


@dataclass(frozen=True)
class DialectNote:
    term: str
    phonetic: str
    context: str = ""
    date: str = ""


_TEACH_RE = re.compile(
    r"^تعلمي:\s*(?P<term>[^\n-]+?)\s*->\s*(?P<phonetic>[^(\n]+?)"
    r"(?:\s*\((?P<context>[^)]*)\))?\s*$",
    re.MULTILINE,
)
_FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
_ENTRY_RE = re.compile(
    r"- term:\s*(?P<term>[^\n]+)"
    r"(?:\n\s+phonetic:\s*(?P<phonetic>[^\n]*))?"
    r"(?:\n\s+context:\s*(?P<context>[^\n]*))?"
    r"(?:\n\s+date:\s*(?P<date>[^\n]*))?"
)


def parse_notes(notes_md: str) -> list[DialectNote]:
    """Read the `notes:` YAML list from the Dialect_Notes.md frontmatter."""
    match = _FRONTMATTER_RE.match(notes_md)
    if not match or "notes:" not in match.group("body"):
        return []
    block = match.group("body").split("notes:", 1)[1]
    return [
        DialectNote(
            term=e.group("term").strip(),
            phonetic=(e.group("phonetic") or e.group("term")).strip(),
            context=(e.group("context") or "").strip(),
            date=(e.group("date") or "").strip(),
        )
        for e in _ENTRY_RE.finditer(block)
    ]


def normalize(text: str, notes: list[DialectNote]) -> str:
    """Replace colloquial spellings with their TTS-friendly phonetic forms."""
    for note in sorted(notes, key=lambda n: len(n.term), reverse=True):
        text = text.replace(note.term, note.phonetic)
    return text


# --- TTS pre-synthesis shaper (owner directive 2026-09-02): Microsoft G2P reads
# --- unvocalized dialect text through MSA rules — forced tanween, mangled Jordanian
# --- words — so shape every synthesis input before it reaches the engine. -------

_EMOJI_RE: Final = re.compile(
    "["
    "\U0001f000-\U0001faff"  # pictographs + supplemental symbols (emoji planes)
    "\U00002600-\U000027bf"  # misc symbols + dingbats
    "\U0001f1e6-\U0001f1ff"  # regional indicators (flags)
    "\U00002b00-\U00002bff"  # misc symbols/arrows (⭐ …)
    "️‍⃣⁉‼ℹ←-⇿〰〽㊗㊙"
    "]+"
)
_ARABIC_CLASS: Final[str] = "ء-يً-ْ"
# تسكين الأواخر: strip tanween + final fatha/damma/kasra/sukun at word end only
_TRAILING_HARAKAT_RE: Final = re.compile(r"[ً-ِْ]+\Z")
# الضحك المسرحي (owner live-retest 2026-09-03): «هههه»/«خخخ»/«هاها»/«haha» كتوكن
# مستقل يُقروء ضحكاً مسموعاً خارج السياق — يُحذف كاملاً قبل محرك الصوت.
_LAUGHTER_TOKEN_RE: Final = re.compile(r"^[هخhHaA]{2,}[،.!؟?…]*$")
# علامات التنصيص (توجيه 2026-09-03): المحرك يقرأ الكلمات لا الترقيم — تُحذف كلها.
_QUOTE_RE: Final = re.compile("[\"«»“”„‟‹›'‘’]+")
_SEED_TTS_LEXICON: Final[dict[str, str]] = {
    # pass-3: the original ten + the frequent live-transcript words the MSA
    # G2P mangles. Deliberately NOT: شوف/مرحبا/كيف — the shaping contract
    # (tests/test_dialect.py) pins them plain; the owner's «تعلمي:» notes
    # remain the live override for any word, always.
    "هسا": "هسَّا",
    "هلق": "هَلَق",
    "هيك": "هَيك",
    "شو": "شُو",
    "ليش": "لِيش",
    "كتير": "كْتير",
    "بدي": "بِدِّي",
    "بدك": "بِدَّك",
    "ابعت": "إبْعَت",
    "شغلة": "شُغْلة",
    # greeting / acknowledgment family (she says these constantly)
    "هلا": "هَلا",
    "اهلا": "أهلاً",
    # pass-1 (v2.0 directive §3-أ/2): her own name + the daily greeting verbs,
    # the explicit phonetic pins the owner named.
    "سارة": "سارَا",
    "كيفك": "كِيفَك",
    # the daily verbs of her live replies
    "بعرف": "بَعْرِف",
    "بقدر": "بَقْدِر",
    "رح": "رَح",
    "شوي": "شْوَي",
    "هلأ": "هلَّأ",
    "وين": "وين",
    "حكي": "حَكي",
    # node-A additions (TTS shaping fixes): units/location/Latin initials
    # «كم/س» must surface as words (never letter-spelled); «بالعمان» Jordanian
    # short form; «CI» deliberate unrushed letter names.
    "كم/س": "كيلومتر بالساعة",
    "بالعمان": "بعمان",
    "CI": "سي آي",
}


# V2-COMPOSE (numerals→spoken words): digits must never reach Fish — spoken
# Arabic says numbers as words. Jordanian-flavored forms matching the voice
# RAG doctrine (vault/Knowledge/fish_voice_style.md): اتناشر، مية وخمسين.
_AR_INDIC_DIGITS: Final = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_NUM_ONES: Final[dict[int, str]] = {
    0: "صفر",
    1: "واحد",
    2: "تنين",
    3: "تلاتة",
    4: "أربعة",
    5: "خمسة",
    6: "ستة",
    7: "سبعة",
    8: "تمانية",
    9: "تسعة",
}
_NUM_TEENS: Final[dict[int, str]] = {
    10: "عشرة",
    11: "حداش",
    12: "اتناش",
    13: "تلتاش",
    14: "أربعتاش",
    15: "خمستاش",
    16: "ستاش",
    17: "سبعتاش",
    18: "تمنتاش",
    19: "تسعتاش",
}
_NUM_TENS: Final[dict[int, str]] = {
    20: "عشرين",
    30: "تلاتين",
    40: "أربعين",
    50: "خمسين",
    60: "ستين",
    70: "سبعين",
    80: "تمانين",
    90: "تسعين",
}
_NUM_HUNDREDS: Final[dict[int, str]] = {
    100: "مية",
    200: "ميتين",
    300: "تلاتمية",
    400: "أربعمية",
    500: "خمسمية",
    600: "ستمية",
    700: "سبعمية",
    800: "تمنمية",
    900: "تسعمية",
}
# Node-A symbol cleanup (owner TTS leak 2026): raw `= > < |` + backticks reach
# the engine and get read aloud / double the neighboring word — space them out
# before synthesis so «الكود = 404» never renders doubled.
_SYMBOL_RE: Final = re.compile(r"[=><|`]+")
_NUM_RE: Final = re.compile(r"\d+(?:[:.٫/]\d+)+|\d+")


def _spell_sub_hundred(n: int) -> str:
    """Spell 0..99 in spoken Jordanian Arabic (ones-first with و)."""
    if n < 10:
        return _NUM_ONES[n]
    if n < 20:
        return _NUM_TEENS[n]
    tens, ones = (n // 10) * 10, n % 10
    if not ones:
        return _NUM_TENS[tens]
    return f"{_NUM_ONES[ones]} و{_NUM_TENS[tens]}"


def _spell_integer(n: int) -> str:
    """Spell a non-negative integer; huge values fall back to digit words so
    no digit ever survives (the only contract this helper guarantees)."""
    if n < 100:
        return _spell_sub_hundred(n)
    if n < 1000:
        hundreds, rest = (n // 100) * 100, n % 100
        head = _NUM_HUNDREDS[hundreds]
        return head if not rest else f"{head} و{_spell_sub_hundred(rest)}"
    if n < 100000:
        thousands, rest = n // 1000, n % 1000
        if thousands == 1:
            head = "ألف"
        elif thousands == 2:
            head = "ألفين"
        elif thousands < 11:
            head = f"{_spell_sub_hundred(thousands)} آلاف"
        else:
            head = f"{_spell_sub_hundred(thousands)} ألف"
        if not rest:
            return head
        return f"{head} و{_spell_integer(rest)}" if rest < 100 else f"{head} {_spell_integer(rest)}"
    return " ".join(_NUM_ONES[int(d)] for d in str(n))


def _clock_period(hour24: int) -> str:
    """Jordanian day-period for a 24h hour."""
    if 5 <= hour24 <= 11:
        return "الصبح"
    if 12 <= hour24 <= 14:
        return "الظهر"
    if 15 <= hour24 <= 17:
        return "العصر"
    if 18 <= hour24 <= 21:
        return "المسا"
    return "بالليل"


def _spell_clock_minute(m: int) -> str:
    """Minute words via the file's Jordanian forms; ones-2 takes the joined
    «اتنين» shape («سبعة واتنين وتلاتين») after the hour connector."""
    words = _spell_sub_hundred(m)
    if m == 2 or (m > 20 and m % 10 == 2):
        words = "اتنين" + words[len("تنين") :]
    return words


def _spell_clock(token: str) -> str | None:
    """Spell clock-like HH:MM (24h → 12h Jordanian + period); None when the
    token is not a valid clock (hour 0–23, minute 00–59, minute 2 digits)."""
    if token.count(":") != 1:
        return None
    h_part, m_part = token.split(":")
    if not h_part.isdigit() or not m_part.isdigit() or len(m_part) != 2:
        return None
    hour, minute = int(h_part), int(m_part)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    hour12 = 12 if hour == 0 else (hour - 12 if hour > 12 else hour)
    hour_words = _spell_sub_hundred(hour12)
    period = _clock_period(hour)
    if minute == 0:
        return f"{hour_words} بالزبط {period}"
    if minute == 15:
        return f"{hour_words} وربع {period}"
    if minute == 30:
        return f"{hour_words} ونص {period}"
    if minute == 45:
        return f"{hour_words} إلا ربع {period}"
    return f"{hour_words} و{_spell_clock_minute(minute)} {period}"


def _spell_number_token(token: str) -> str:
    """Spell one digit-run: clock HH:MM via 12h Jordanian + period, decimals
    via فاصلة, clock/slash runs joined with و, plain integers via
    _spell_integer. Never returns a digit."""
    if ":" in token:
        clock = _spell_clock(token)
        if clock is not None:
            return clock
    for sep in (":", "/", "٫"):
        if sep in token:
            return " و".join(_spell_integer(int(p)) for p in token.split(sep))
    if "." in token:
        int_part, _, frac_part = token.partition(".")
        head = _spell_integer(int(int_part)) if int_part else "صفر"
        tail = " ".join(_NUM_ONES[int(d)] for d in frac_part) if frac_part else ""
        return f"{head} فاصلة {tail}" if tail else head
    return _spell_integer(int(token))


def spell_numerals(text: str) -> str:
    """Replace every digit run (Western + Arabic-Indic) with spoken Arabic
    words. Pure and never-blocking: any failure returns the input."""
    try:
        text = text.translate(_AR_INDIC_DIGITS)
        return _NUM_RE.sub(lambda m: _spell_number_token(m.group()), text)
    except Exception:  # noqa: BLE001 — shaping must never block synthesis
        return text


def shape_for_tts(text: str, notes: list[DialectNote] | None = None) -> str:
    """Emoji-strip + quote-strip + laughter-token drop + whole-word pronunciation
    lexicon (owner notes override the seed) + trailing-harakat skeleton, so the
    engine never forces MSA tanween on dialect endings and never renders «هههه»
    as an out-of-context laugh. Pure and never-blocking: any internal failure
    returns the input.
    V2-COMPOSE: numerals become spoken words here (digits never reach Fish)."""
    original = text
    try:
        text = _EMOJI_RE.sub(" ", text)
        text = _QUOTE_RE.sub("", text)
        text = _SYMBOL_RE.sub(" ", text)
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        if text:
            text = " ".join(w for w in text.split() if not _LAUGHTER_TOKEN_RE.match(w))
            text = spell_numerals(text)
            lex = dict(_SEED_TTS_LEXICON)
            for note in notes or []:
                lex[note.term] = note.phonetic
            pattern = re.compile(
                "(?<![" + _ARABIC_CLASS + "])"
                "(?:" + "|".join(re.escape(t) for t in sorted(lex, key=len, reverse=True)) + ")"
                "(?![" + _ARABIC_CLASS + "])"
            )
            text = pattern.sub(lambda m: lex[m.group()], text)
            text = " ".join(_TRAILING_HARAKAT_RE.sub("", word) for word in text.split())
        return text
    except Exception:  # noqa: BLE001 — shaping must never block synthesis
        return original


def parse_teachings(text: str, *, today: str) -> list[DialectNote]:
    """Extract owner teach-lines («تعلمي: term -> phonetic (context)») from chat."""
    return [
        DialectNote(
            term=m.group("term").strip(),
            phonetic=m.group("phonetic").strip(),
            context=(m.group("context") or "").strip(),
            date=today,
        )
        for m in _TEACH_RE.finditer(text)
    ]


def append_notes(notes_md: str, notes: list[DialectNote]) -> str:
    """Append new note entries to the Dialect_Notes.md content (dedupe by term)."""
    known = {n.term for n in parse_notes(notes_md)}
    fresh = [n for n in notes if n.term not in known]
    if not fresh:
        return notes_md
    entry = "\n".join(
        f"- term: {n.term}\n  phonetic: {n.phonetic}\n  context: {n.context}\n  date: {n.date}"
        for n in fresh
    )
    match = _FRONTMATTER_RE.match(notes_md)
    if match and "notes:" in match.group("body"):
        return re.sub(
            r"^notes:[^\n]*$", lambda _: f"notes:\n{entry}", notes_md, count=1, flags=re.MULTILINE
        )
    return f"---\nnotes:\n{entry}\n---\n{notes_md}"


def learn(text: str, *, notes_md: str, today: str) -> str | None:
    """Ingest owner teach-lines; returns updated notes content or None.

    Contract: NEVER raises — the reply must not block on dialect learning
    (master-directive M1). All failures are logged and swallowed here. Pure
    and synchronous: the vault client (Sprint 3.1) awaits its own append
    around these pure transforms.
    """
    try:
        notes = parse_teachings(text, today=today)
        if not notes:
            return None
        return append_notes(notes_md, notes)
    except Exception as exc:  # noqa: BLE001 — documented never-blocks contract; narrow when gateway/vault error taxonomy lands
        logger.warning("dialect ingestion failed (non-blocking): {}", exc)
        return None


def prompt_block(notes: list[DialectNote], *, max_entries: int = 40) -> str:
    """Compact dialect snapshot injected into the system prompt at session start."""
    if not notes:
        return ""
    lines = [f"- {n.term} → {n.phonetic}" for n in notes[:max_entries]]
    return "الدليل اللهجي (نطق مصطلحات المالك):\n" + "\n".join(lines)
