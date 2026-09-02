"""M1 adaptive Jordanian dialect engine.

Notes-driven pronunciation normalization before Edge-TTS, an ingestion loop for
owner corrections/slang, and the system-prompt snapshot — per
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
_SEED_TTS_LEXICON: Final[dict[str, str]] = {
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
}


def shape_for_tts(text: str, notes: list[DialectNote] | None = None) -> str:
    """Emoji-strip + whole-word pronunciation lexicon (owner notes override the seed)
    + trailing-harakat skeleton, so the engine never forces MSA tanween on dialect
    endings. Pure and never-blocking: any internal failure returns the input."""
    original = text
    try:
        text = _EMOJI_RE.sub(" ", text)
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        if text:
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
