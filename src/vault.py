"""Obsidian vault — GitHub Contents API client + PARA helpers (sprint-3 §3.1, ADR-21).

Sara's long-term memory is a private git-backed Obsidian vault (PARA + Zettelkasten)
as a private GitHub repo, chosen over a local clone because the core lives on HF
Spaces (ADR-15) with a disposable filesystem. This module is THE read/write surface
every later writer uses. Parsed vault content is DATA, never instructions.

Error modes (nothing swallowed): auth errors propagate loudly (no retry); a 409 is
retried up to THREE times as a full re-merge — re-read the sha, re-run the caller's
`merge` callback, re-PUT — and a 409 that survives the third attempt raises
VaultConflictError (a merge callback must therefore assume it can be invoked more than
once); timeouts propagate; malformed frontmatter YAML raises ValueError naming the
path; missing reads raise FileNotFoundError; oversize payloads are refused pre-flight.
A 429/403 on a READ is retried at most once, honoring `Retry-After` (`_get_with_rate_limit`).
"""

from __future__ import annotations

import asyncio
import base64
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
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

# Local first-boot scaffold (drill finding 2026-09-12): the remote bootstrap
# (ensure_mandatory_dirs, GitHub API) never touches the disposable local root,
# so a fresh VAULT_LOCAL_PATH misses Contacts/Call_Transcripts/Studies (and
# the local-only State/ dir) until something crashes on them. This set is the
# complete local mkdir contract.
LOCAL_SCAFFOLD_DIRS = (*MANDATORY_DIRS, *CONTACTS_SUBDIRS, "State/")


def ensure_vault_scaffolding(root: str | Path) -> list[str]:
    """Create every mandatory local vault dir under `root` (idempotent).

    Returns the dirs actually created. Never raises: an unmakable dir degrades
    to a loud warning while the rest still land — boot must never die on
    scaffolding, and writers must never meet FileNotFoundError after it.
    """
    created: list[str] = []
    base = Path(root)
    for directory in LOCAL_SCAFFOLD_DIRS:
        try:
            path = base / directory.rstrip("/")
            if not path.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        except OSError as error:
            logger.warning("vault scaffold skipped {}: {}", directory, error)
    if created:
        logger.bind(created=created).info("vault scaffold created {} dirs", len(created))
    return created


def _default_resources_source() -> Path:
    """Repo-root 04_Resources/ resolved from this file's location (src/../)."""
    return Path(__file__).resolve().parent.parent / "04_Resources"


def ensure_resources_scaffolding(
    root: str | Path, *, source: str | Path | None = None
) -> list[str]:
    """Mirror 04_Resources/*.md into `<root>/04_Resources/` (idempotent).

    Strict copy-if-missing (ratified 2026-09-14, durability Solution A): a
    relpath lands ONLY when the vault side lacks it. An existing vault file
    is NEVER overwritten — not even on byte-difference — because the vault
    is the live layer where Sara's own write-backs land; the repo is merely
    the seed. A diverged file (same relpath, different bytes) is logged
    loudly as evidence of live Sara authorship, and skipped. Vault-side-only
    files are never deleted. Returns the mirrored relpaths.

    Never raises (boot must not die on RAG): a missing source degrades to one
    info line (normal inside the Oracle image until 04_Resources ships there);
    per-file failures log loudly and skip. This is what makes VaultIndex see
    the knowledge bases live — the index root is the vault, not the repo.
    """
    mirrored: list[str] = []
    src = Path(source) if source is not None else _default_resources_source()
    if not src.is_dir():
        logger.info("resources mirror skipped: source {} absent", src)
        return mirrored
    dest_root = Path(root) / "04_Resources"
    for path in sorted(src.rglob("*.md")):
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            rel = path.relative_to(src).as_posix()
            dest = dest_root / rel
            if dest.is_file():
                try:
                    if dest.read_bytes() != path.read_bytes():
                        logger.warning(
                            "resources mirror diverged (Sara-authored?) — keeping vault copy: {}",
                            rel,
                        )
                except OSError as error:
                    logger.warning("resources mirror reread skipped {}: {}", rel, error)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
            mirrored.append(rel)
        except OSError as error:
            logger.warning("resources mirror skipped {}: {}", path, error)
    if mirrored:
        logger.bind(mirrored=mirrored).info("resources mirror synced {} files", len(mirrored))
    return mirrored


MASTER_DIGEST_SEED = "Personal_Context/Omar_Core_Digest.md"
MASTER_DIGEST_DEST = "02_Areas/Profile/Omar_Master_Digest.md"


def ensure_master_digest(root: str | Path, *, source: str | Path | None = None) -> list[str]:
    """Plant the Tier-1 seed digest as the runtime source of truth.

    Copies `<source>/Personal_Context/Omar_Core_Digest.md` (default: the
    repo seed) to `<root>/02_Areas/Profile/Omar_Master_Digest.md` — but ONLY
    when the destination is missing. An existing live copy (Sara-refreshed
    by write-back) is never touched. Returns the planted relpath, else [].
    Never raises.
    """
    try:
        src = Path(source) if source is not None else _default_resources_source()
        seed = src / MASTER_DIGEST_SEED
        dest = Path(root) / MASTER_DIGEST_DEST
        if not seed.is_file():
            logger.info("master digest seed absent: {}", seed)
            return []
        if dest.is_file():
            return []
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(seed.read_bytes())
        logger.info("master digest planted: {}", MASTER_DIGEST_DEST)
        return [MASTER_DIGEST_DEST]
    except OSError as error:
        logger.warning("master digest plant skipped: {}", error)
        return []


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
    """Canonical ledger location (durability Solution B, 2026-09-14):
    nested `Daily_Logs/YYYY/MM/YYYY-MM-DD.md` so a decade of ledgers never
    chokes one flat directory. Writers always land here."""
    return f"Daily_Logs/{day:%Y/%m}/{day.isoformat()}.md"


def daily_log_candidates(day: date) -> list[str]:
    """Read order: nested canonical first, flat legacy fallback (pre-2026-09-14 notes)."""
    return [daily_log_path(day), f"Daily_Logs/{day.isoformat()}.md"]


async def read_daily_log(vault, day: date) -> tuple[str, str]:
    """Read a day's ledger as (hit_path, text), nested-first.

    Raises FileNotFoundError only when both shapes miss (existing callers'
    `except FileNotFoundError` clauses keep working); other vault errors
    propagate for the callers' loud-log paths.
    """
    for path in daily_log_candidates(day):
        try:
            return path, await vault.read(path)
        except FileNotFoundError:
            continue
    raise FileNotFoundError(daily_log_candidates(day)[0])


def daily_log_local_path(root: str | Path, day: date) -> Path:
    """Local-mirror twin of daily_log_path (evening journaler + hot index)."""
    return Path(root) / "Daily_Logs" / f"{day:%Y}" / f"{day:%m}" / f"{day.isoformat()}.md"


def iter_recent_daily_logs(root: str | Path, *, days: int = 90, today: date | None = None):
    """90-day hot rolling window over a local vault mirror, newest-first.

    Yields existing ledger Paths (nested canonical + flat legacy shapes);
    non-log files never match. Pure/local/total — backs batch summarizer
    passes; deep history stays in cold RAG (VaultIndex walks everything).
    """
    base = Path(root) / "Daily_Logs"
    anchor = today if today is not None else datetime.now(UTC).date()
    floor = anchor - timedelta(days=days)
    found: list[tuple[date, Path]] = []
    if not base.is_dir():
        return iter(())
    for path in sorted(base.rglob("*.md")):
        stem = path.stem
        try:
            stamp = date.fromisoformat(stem[-10:])
        except ValueError:
            continue
        if floor <= stamp <= anchor:
            found.append((stamp, path))

    def _gen():
        for _, path in sorted(found, reverse=True):
            yield path

    return _gen()


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


def zettel_link(
    title: str, *, alias: str | None = None, block: str | None = None, embed: bool = False
) -> str:
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
        # pass-1 (C-9): every write path serializes on this lock — concurrent
        # appends to the same note can no longer race past each other.
        self._write_lock = asyncio.Lock()
        self._http = session or httpx.AsyncClient(
            base_url=self._API, headers=self._headers, timeout=30.0
        )

    async def aclose(self) -> None:
        if self._owns_session:
            await self._http.aclose()

    async def read(self, path: str) -> str:
        response = await self._get_with_rate_limit(path)
        if response.status_code == 404:
            raise FileNotFoundError(path)
        response.raise_for_status()  # auth errors propagate loudly (no retry)
        data = response.json()
        if isinstance(data, list):
            raise TypeError(f"{path} is a directory, not a note")
        text = base64.b64decode(data["content"].replace("\n", "")).decode("utf-8")
        try:
            split_frontmatter(text)
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        return text

    async def list_dir(self, path: str, *, recursive: bool = False) -> list[str]:
        """List note paths under a vault directory (v2.0 pass-2: the knowledge
        graph + Scheduled_Tasks sync need directory scans). Returns
        `dir/file.md` paths; a missing directory is an empty list (an honest
        empty vault section, never an error). With recursive=True, descends
        into subdirectories (nested Daily_Logs archives) depth-first."""
        response = await self._get_with_rate_limit(path)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise TypeError(f"{path} is a note, not a directory")
        out: list[str] = []
        for entry in data:
            kind = entry.get("type")
            name = str(entry.get("name", ""))
            if kind == "file" and name.endswith(".md"):
                out.append(f"{path}/{name}")
            elif recursive and kind == "dir" and name and not name.startswith("."):
                out.extend(await self.list_dir(f"{path}/{name}", recursive=True))
        return out

    async def _get_with_rate_limit(self, path: str) -> httpx.Response:
        """2.10 (deferred queue): a 429/403 rate limit with Retry-After is
        honored ONCE — a momentary limit never fails a read; anything
        persistent surfaces loudly (no silent infinite retry loop)."""
        response = await self._http.get(
            f"/repos/{self._repo}/contents/{path}",
            params={"ref": self._branch},
            headers=self._headers,
        )
        if response.status_code not in (429, 403):
            return response
        retry_after = response.headers.get("Retry-After")
        if retry_after is None or getattr(self, "_rate_limit_used", False):
            return response  # no header, or we already retried once — surface it
        try:
            await asyncio.sleep(min(float(retry_after), 30.0))  # sane cap
        except ValueError:
            return response
        self._rate_limit_used = True
        try:
            return await self._http.get(
                f"/repos/{self._repo}/contents/{path}",
                params={"ref": self._branch},
                headers=self._headers,
            )
        finally:
            self._rate_limit_used = False

    async def upsert(self, path: str, content: str, *, message: str, merge=None) -> WriteResult:
        """Serialized + conflict-remerged (C-9/V-4 fix, pass-1): every write
        takes the client-wide lock (concurrent appends can no longer race to
        the same note), and a 409 re-runs the WHOLE merge (re-read + re-merge
        + re-PUT) via the caller's ``merge(path, content)`` callback when one
        is given — a stale re-PUT can never silently drop another writer's
        lines."""
        async with self._write_lock:
            return await self._upsert_locked(path, content, message=message, merge=merge)

    async def _upsert_locked(
        self, path: str, content: str, *, message: str, merge=None
    ) -> WriteResult:
        """The write body — caller holds ``_write_lock``."""
        payload = content.encode("utf-8")
        if len(payload) > MAX_NOTE_BYTES:
            raise ValueError(f"payload for {path} exceeds {MAX_NOTE_BYTES} bytes ({len(payload)})")
        sha = await self._lookup_sha(path)
        response = await self._put(path, content, message, sha)
        for attempt in (1, 2, 3):  # C-9: full re-merge, never a stale re-PUT
            if response.status_code != 409:
                break
            logger.warning(
                "vault conflict on {} (attempt {}); re-reading + re-merging",
                path,
                attempt,
            )
            sha = await self._lookup_sha(path)
            if merge is not None:
                content = await merge(path, content)
            response = await self._put(path, content, message, sha)
        if response.status_code == 409:
            raise VaultConflictError(f"vault conflict persists for {path}")
        response.raise_for_status()
        data = response.json()
        # C-10: a successful write invalidates the envelope cache — the next
        # turn reads fresh content, never a stale just-written note.
        from src.memory import invalidate_context_cache

        invalidate_context_cache()
        return WriteResult(path=path, commit_sha=data["commit"]["sha"], created=sha is None)

    async def upsert_note(self, note: Note, *, message: str) -> WriteResult:
        return await self.upsert(
            note.path, write_frontmatter(note.frontmatter, note.body), message=message
        )

    async def append_section(
        self, path: str, heading: str, lines: list[str], *, commit_prefix: str
    ) -> WriteResult:
        """Append a `## heading` section (append-only dossier/log discipline).
        Pass-1 (C-9): read-modify-write + the 409 re-merge both run under the
        client lock; a conflict re-appends onto the LATEST remote content — a
        racing writer's section survives and ours re-lands on top of it."""

        async def _merge(_path: str, _content: str) -> str:
            try:
                existing = (await self.read(_path)).rstrip("\n")
            except FileNotFoundError:
                existing = ""
            block = "\n".join([f"## {heading}", "", *lines])
            return f"{existing}\n\n{block}\n" if existing else f"{block}\n"

        async with self._write_lock:
            merged = await _merge(path, "")
            return await self._upsert_locked(
                path, merged, message=f"{commit_prefix}: {heading}", merge=_merge
            )

    async def commit_files(self, changes: dict[str, str | None], *, message: str) -> str:
        """Land many file changes as ONE structural commit (Git Data API):
        blobs -> tree -> commit -> ref update. None deletes a path."""
        ref = await self._http.get(
            f"/repos/{self._repo}/git/ref/heads/{self._branch}", headers=self._headers
        )
        ref.raise_for_status()
        base = ref.json()["object"]["sha"]
        head = await self._http.get(
            f"/repos/{self._repo}/git/commits/{base}", headers=self._headers
        )
        head.raise_for_status()
        base_tree = head.json()["tree"]["sha"]

        tree = []
        for path, content in changes.items():
            if content is None:
                tree.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                continue
            blob = await self._http.post(
                f"/repos/{self._repo}/git/blobs",
                json={"content": content, "encoding": "utf-8"},
                headers=self._headers,
            )
            blob.raise_for_status()
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob.json()["sha"]})

        tree_response = await self._http.post(
            f"/repos/{self._repo}/git/trees",
            json={"base_tree": base_tree, "tree": tree},
            headers=self._headers,
        )
        tree_response.raise_for_status()
        commit = await self._http.post(
            f"/repos/{self._repo}/git/commits",
            json={"message": message, "tree": tree_response.json()["sha"], "parents": [base]},
            headers=self._headers,
        )
        commit.raise_for_status()
        sha = commit.json()["sha"]
        update = await self._http.patch(
            f"/repos/{self._repo}/git/refs/heads/{self._branch}",
            json={"sha": sha},
            headers=self._headers,
        )
        update.raise_for_status()
        logger.info(
            "vault structural commit {sha}: {message}", sha=sha, message=redact_secret(message)
        )
        return sha

    async def ensure_mandatory_dirs(self) -> list[WriteResult]:
        """M6 first-boot bootstrap: one index note per missing dir + both profile
        files; idempotent (re-run = zero writes); migrates legacy Studies first."""
        results: list[WriteResult] = []
        await self._migrate_studies()
        targets: list[tuple[str, dict, str]] = []
        for directory in (*MANDATORY_DIRS, *CONTACTS_SUBDIRS):
            name = directory.rstrip("/")
            targets.append(
                (
                    f"{directory}{INDEX_NOTE_NAME}",
                    {"type": "vault-index", "dir": name},
                    f"# {name}\n\n{_PURPOSES[directory]}\n",
                )
            )
        targets.append(
            (
                PROFILE_USER_INFO,
                {"type": "profile", "name": "User_Info"},
                "# User Info\n\nOwner profile — identity, preferences, context. Sara keeps this current.\n",
            )
        )
        targets.append(
            (
                PROFILE_DIALECT,
                {"type": "profile", "name": "Dialect_Notes"},
                "# Dialect Notes\n\nJordanian (ar-JO) speech patterns feeding Sara's adaptive loop.\n",
            )
        )
        for path, frontmatter, body in targets:
            try:
                await self.read(path)
                continue  # exists — idempotent, zero writes
            except FileNotFoundError:
                results.append(
                    await self.upsert_note(
                        Note(path=path, frontmatter=frontmatter, body=body),
                        message=f"sara: bootstrap {path}",
                    )
                )
        return results

    async def _migrate_studies(self) -> None:
        """One-time legacy migration: 02_Areas/Studies/ notes MOVE to top-level
        Studies/ as ONE structural commit; absent legacy -> nothing."""
        response = await self._http.get(
            f"/repos/{self._repo}/contents/02_Areas/Studies/",
            params={"ref": self._branch},
            headers=self._headers,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return
        notes = [
            item for item in data if item.get("type") == "file" and item["name"].endswith(".md")
        ]
        if not notes:
            return
        changes: dict[str, str | None] = {}
        for item in notes:
            changes[f"Studies/{item['name']}"] = await self.read(item["path"])
            changes[item["path"]] = None
        await self.commit_files(changes, message="sara: migrate Studies to top-level")

    async def _lookup_sha(self, path: str) -> str | None:
        response = await self._http.get(
            f"/repos/{self._repo}/contents/{path}",
            params={"ref": self._branch},
            headers=self._headers,
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
