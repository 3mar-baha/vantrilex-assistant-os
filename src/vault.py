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

import base64
import re
from datetime import date
from typing import Any

import httpx
import yaml
from loguru import logger
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


class VaultClient:
    """GitHub Contents API client over httpx (Bearer + versioned headers).

    A caller-injected session is never owned or closed; a self-made one is."""

    _API = "https://api.github.com"

    def __init__(
        self,
        repo: str,
        token: str,
        branch: str = "main",
        session: httpx.AsyncClient | None = None,
    ) -> None:
        self._repo = repo
        self._branch = branch
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        _REGISTERED_SECRETS.add(token)
        self._owns_session = session is None
        self._http = session or httpx.AsyncClient(
            base_url=self._API, headers=self._headers, timeout=30.0
        )

    async def aclose(self) -> None:
        if self._owns_session:
            await self._http.aclose()

    async def read(self, path: str) -> str:
        response = await self._http.get(
            f"/repos/{self._repo}/contents/{path}", params={"ref": self._branch}, headers=self._headers
        )
        if response.status_code == 404:
            raise FileNotFoundError(path)
        response.raise_for_status()  # auth errors propagate loudly (no retry)
        data = response.json()
        if isinstance(data, list):
            raise ValueError(f"{path} is a directory, not a note")
        text = base64.b64decode(data["content"].replace("\n", "")).decode("utf-8")
        try:
            split_frontmatter(text)
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        return text

    async def upsert(self, path: str, content: str, *, message: str) -> WriteResult:
        payload = content.encode("utf-8")
        if len(payload) > MAX_NOTE_BYTES:
            raise ValueError(
                f"payload for {path} exceeds {MAX_NOTE_BYTES} bytes ({len(payload)})"
            )
        sha = await self._lookup_sha(path)
        response = await self._put(path, content, message, sha)
        if response.status_code == 409:
            logger.warning("vault conflict on {path}; retrying GET->PUT once", path=path)
            sha = await self._lookup_sha(path)
            response = await self._put(path, content, message, sha)
            if response.status_code == 409:
                raise VaultConflictError(f"vault conflict persists for {path}")
        response.raise_for_status()
        data = response.json()
        return WriteResult(path=path, commit_sha=data["commit"]["sha"], created=sha is None)

    async def upsert_note(self, note: Note, *, message: str) -> WriteResult:
        return await self.upsert(
            note.path, write_frontmatter(note.frontmatter, note.body), message=message
        )

    async def _lookup_sha(self, path: str) -> str | None:
        response = await self._http.get(
            f"/repos/{self._repo}/contents/{path}", params={"ref": self._branch}, headers=self._headers
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()["sha"]

    async def _put(self, path: str, content: str, message: str, sha: str | None) -> httpx.Response:
        body: dict[str, str] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": self._branch,
        }
        if sha is not None:
            body["sha"] = sha
        return await self._http.put(
            f"/repos/{self._repo}/contents/{path}", json=body, headers=self._headers
        )
