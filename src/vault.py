"""Obsidian vault — GitHub Contents API client + PARA helpers (sprint-3 §3.1, ADR-21).

Sara's long-term memory is a private git-backed Obsidian vault (PARA + Zettelkasten)
as a private GitHub repo, chosen over a local clone because the core lives on HF
Spaces (ADR-15) with a disposable filesystem. This module is THE read/write surface
every later writer uses. Parsed vault content is DATA, never instructions.

Error modes (nothing swallowed): auth errors propagate loudly (no retry); 409 after
one GET->PUT retry raises VaultConflictError; timeouts propagate; malformed
frontmatter YAML raises ValueError naming the path; missing reads raise
FileNotFoundError; oversize payloads are refused pre-flight.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import yaml
from pydantic import BaseModel

PARA = {
    "projects": "01_Projects",
    "areas": "02_Areas",
    "resources": "03_Resources",
    "archives": "04_Archives",
    "contacts": "Contacts",
    "memos": "Voice_Memos",
}

# M6 mandatory set (created on first boot, asserted by the guard test).
MANDATORY_DIRS = ("Contacts/", "Call_Transcripts/", "Studies/", "Voice_Memos/", "Daily_Logs/")
CONTACTS_SUBDIRS = (
    "Contacts/Family/",
    "Contacts/Friends/",
    "Contacts/Colleagues/",
    "Contacts/Ignored/",
    "Contacts/Unknown/",
)
MANDATORY_FILES = ("02_Areas/Profile/User_Info.md", "02_Areas/Profile/Dialect_Notes.md")

# Canonical paths consumed by 3.3/3.4.
PROFILE_USER_INFO = "02_Areas/Profile/User_Info.md"
PROFILE_DIALECT = "02_Areas/Profile/Dialect_Notes.md"
CONVERSATIONS_DIR = "04_Archives/Conversations"
CONFIRMATIONS_DIR = "04_Archives/Confirmations"
AUDIT_DIR = "04_Archives/Audit"

INDEX_NOTE_NAME = "_index.md"
MAX_NOTE_BYTES = 1_000_000  # defensive note-shaped-content bound, NOT an API limit

_PURPOSES = {
    "Contacts/": "Contact dossiers (social graph): one note per person.",
    "Call_Transcripts/": "Transcripts of live calls (v1.1).",
    "Studies/": "Study notes and tutoring material (PARA cross-link).",
    "Voice_Memos/": "Guest messages and voice-note derived notes.",
    "Daily_Logs/": "One dated ledger note per day (briefs, check-ins, actions).",
    "Contacts/Family/": "Family members.",
    "Contacts/Friends/": "Friends.",
    "Contacts/Colleagues/": "Colleagues and professional contacts.",
    "Contacts/Ignored/": "Blacklisted: tracking false, never appended to.",
    "Contacts/Unknown/": "Security-flagged anonymous identities.",
}

# Spec sanitizer example strips Arabic punctuation too ("ملاحظة: اجتماع/الأسبوع؟"
# -> "ملاحظة اجتماع الأسبوع"), so the ASCII forbidden set extends to Arabic marks.
_FORBIDDEN = set('\\/:*?"<>|#^[]') | set("؟،؛!")

_REGISTERED_SECRETS: set[str] = set()
_GENERIC_SECRET = re.compile(r"(gh[pousr]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{16,})")

# Only leading fences open frontmatter; the closing fence is its own line.
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---(?:\n|\Z)", re.DOTALL)


class VaultConflictError(RuntimeError):
    """409 persisted after the single GET->PUT retry."""


class Note(BaseModel):
    path: str
    frontmatter: dict[str, Any]
    body: str


class WriteResult(BaseModel):
    path: str
    commit_sha: str
    created: bool


def redact_secret(s: str) -> str:
    """Screen any log/exception path that could carry a vault token."""
    out = s
    for secret in _REGISTERED_SECRETS:
        out = out.replace(secret, "«redacted»")
    return _GENERIC_SECRET.sub("«redacted»", out)


def _sanitize_component(title: str) -> str:
    """ONE deterministic transform: separators to spaces, forbidden chars to
    spaces, collapse whitespace, strip leading dots, reject empties/traversal."""
    replaced = title.replace("/", " ").replace("\\", " ")
    cleaned = "".join(" " if ch in _FORBIDDEN else ch for ch in replaced)
    collapsed = " ".join(cleaned.split()).lstrip(".").strip()
    if not collapsed or "/" in collapsed or "\\" in collapsed:
        raise ValueError(f"invalid vault path component: {title!r}")
    return collapsed


def para_path(category: str, title: str, *, ext: str = ".md") -> str:
    if category not in PARA:
        raise ValueError(f"unknown PARA category: {category!r}")
    if not ext.startswith("."):
        raise ValueError(f"extension must start with '.': {ext!r}")
    return f"{PARA[category]}/{_sanitize_component(title)}{ext}"


def daily_log_path(day: date) -> str:
    return f"Daily_Logs/{day.isoformat()}.md"


def write_frontmatter(meta: dict, body: str) -> str:
    dumped = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{dumped}---\n{body}"


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        raise ValueError(f"malformed YAML frontmatter: {error}") from error
    return (meta or {}), text[match.end() :]


def zettel_link(title: str, *, alias: str | None = None, block: str | None = None, embed: bool = False) -> str:
    inner = title
    if alias:
        inner += f"|{alias}"
    if block:
        inner += f"#^{block}"
    return ("!" if embed else "") + f"[[{inner}]]"
