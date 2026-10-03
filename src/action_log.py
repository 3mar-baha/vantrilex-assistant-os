"""N1 / D-2 — the durable action log: what the body DID, in the owner's vault.

THE GAP. `ToolRegistry.call` recorded FAILURES ONLY, and only to loguru: an
ephemeral stream that dies with the process, keeps nothing after a restart, and
is not part of the vault. The loguru lines stay — they are diagnostics, shaped
for a human watching stdout, and the action log does not replace them. What was
missing is a DURABLE record, which is a different thing with a different
lifetime, and whose absence made every safety claim about the body
(«it never acted without confirmation») unverifiable after the fact.

ONE HOOK, AT THE CHOKE POINT. `record` is called from `ToolRegistry.call` and
nowhere else. Not per handler: a per-handler hook is silently missed by every
tool registered later through `src.tool_overlay.register_tool`, which writes a
`_do_<name>` onto the class after the module was written.

STORAGE — WHY `append_section` AND NOT `upsert`. `upsert` OVERWRITES one path
(`src/vault.py:432`): it GETs the sha and PUTs the whole body back, so one
`upsert` per entry into a fixed filename would keep only the LAST entry and
silently discard every execution before it. `append_section`
(`src/vault.py:479`) is the append surface this vault already offers: a
read-modify-write under the client-wide write lock, with the 409 re-merge
re-reading the LATEST remote content so a racing writer's section survives. One
section per flush, one line per entry — one commit per flush, not one per entry.

The note lives at `04_Archives/Audit/action-log/YYYY/MM/YYYY-MM-DD.md`, beside
the PC audit ledger, in the vault's own audit directory.

DURABILITY STATEMENT — what is buffered, when it flushes, what a crash loses
------------------------------------------------------------------------------

* WHAT IS BUFFERED: every entry, in memory, from the instant `record` is called.
  `record` performs NO I/O and NO await (guarded structurally, not by
  benchmark), so a tool's own stack pays only microseconds of CPU.
* WHEN IT FLUSHES: `record` schedules ONE background `asyncio.Task` on the
  running loop, and that task runs at the loop's NEXT yield point — which in the
  live lane is while `FrontDoorDispatcher._tool_lane` is awaiting the narration
  stream, i.e. BEFORE the turn ends at `src/bot.py:788`. The loop is the flush
  point that sits inside this node's write-set: the natural one,
  `FrontDoorDispatcher.handle`'s exhaustion (`src/dispatcher.py:885`), is
  OUTSIDE it, and a flush strictly earlier than turn end has a strictly SMALLER
  loss window than the flush-at-turn-end it replaces.
* WHAT A CRASH LOSES: the buffered tail — every entry recorded since the last
  flush that had not completed when the process died. A hard kill, an OOM or a
  power cut can therefore lose the last few entries. That is the price of
  buffered append and it is stated rather than hidden: the alternative the owner
  rejected (a synchronous write per execution) would put a network round trip on
  the critical path of every tool call.
* WHAT A CRASH CANNOT LOSE: anything already flushed, because a flush is one
  `append_section` on the real vault — the same durability every other note in
  this vault has, no more and no less.

RETRY. A failed write keeps its entries buffered and counted (`failed`), and the
next flush re-attempts them in order — at-least-once. The buffer is bounded by
`MAX_PENDING_ENTRIES`; past it the OLDEST are dropped (they have had the longest
to be lost) and counted. Dropping anything is counted, never silent: the failure
mode this node exists to kill is a log that silently does not log.

ROTATION — the policy, in full
------------------------------

1. BY DAY, BY PATH. A day is closed when its date rolls over; nothing is ever
   written into yesterday's note. Read order is the path order.
2. BY SEGMENT, PAST A CAP. At most `MAX_SEGMENT_ENTRIES` entries land in one
   note; the next entries go to `...--02.md`, `--03.md`, and so on. A batch that
   would cross the cap rotates WHOLE, so a note never exceeds its cap.
3. THE CAP IS COUNTED FROM THE NOTE, not from process memory. On first touch of
   a note in a process, `read` counts what is already there — so a RESTART
   cannot forget a full segment and overfill the first one.
4. NOTHING IS DELETED, REWRITTEN OR COMPACTED BY THIS MODULE. Retention is the
   owner's vault policy; a compaction pass that rewrites history would break the
   append-only law that makes this an audit trail rather than a summary. What
   "rotation" means here is that the log STOPS GROWING A SINGLE NOTE, not that
   it discards.

REDACTION — the five classes, named
-----------------------------------

Never logged, each with its own guard in `tests/test_action_audit_log.py`:

1. ``api_key`` — provider key shapes (`AIza…`, `sk-…`, `github_pat_…`, `xox*`,
   `AKIA…`).
2. ``token`` — a LABELLED secret (the label survives, the value does not), a
   JWT, a `Bearer` header value.
3. ``credential`` — a `user:password@host` userinfo pair, which is what a
   URL-taking tool's arg is allowed to carry.
4. ``session_string`` — F-2's signed `cfm1.` confirmation id (a usable owner
   approval if it leaks), a labelled session value, and a bare Telethon
   session blob.
5. ``vault_personalization`` — `User_Info.md` content, in any of the three
   shapes this repo actually moves it in: the note itself (a
   `## معلومة` / `slot:` / `value:` stack, `src/memory.py:521`), the greeter's
   `[صاحبك باختصار …]` envelope (`src/bot.py:208`) and the outreach loop's
   `[ملف المالك]` envelope (`src/skills/proactive_outreach.py:138`). This class
   replaces the WHOLE arg — a partial profile excerpt is still private.

PLUS the process's OWN live shared secrets: `src.vault.redact_secret` screens
every secret registered by a `VaultClient` (`src/vault.py:353`), which no regex
can match because the value is whatever the owner pasted into `.env`.

WHERE THE LINE SITS — credentials, not meaning. The `arg` reaching `call` is
legitimately the OWNER'S OWN INSTRUCTION («سكّر كروم»), and a log that redacted
that would be unreadable and therefore useless. So the law is drawn at
CREDENTIAL SHAPE, not at "is this sensitive-looking": ordinary instruction text
passes through byte for byte, and every one of the five classes above is a
shape, not a topic.

THE HONEST LIMIT OF CLASS 5. A personalization excerpt is detected by its
STRUCTURE (the note's own markers, the two envelopes, the profile path). Free
text that happens to be about the owner and carries none of those markers cannot
be told apart from an instruction, and is not claimed to be: no comment here
says every private word is caught. What bounds the residue is `MAX_ARG_CHARS`
and the fact that no tool's arg is ever a profile excerpt today — this class is
depth for a future tool that might pass content through.
"""

from __future__ import annotations

import asyncio
import re
import weakref
from collections import deque
from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import perf_counter
from typing import Any, Final

from loguru import logger

#: The action log's home. A LITERAL, not `AUDIT_DIR` imported at module top —
#: `src/vault.py` drags httpx/pydantic/yaml into the import graph, and this
#: module is reached from `src/tools.py`, which deliberately does not import the
#: vault. `tests/test_action_audit_log.py` pins the literal against
#: `src.vault.AUDIT_DIR`, so the two cannot drift apart silently.
ACTION_LOG_DIR: Final[str] = "04_Archives/Audit/action-log"
COMMIT_PREFIX: Final[str] = "sara: action log"

#: Entry line grammar. `<at> | tool=<tool> | status=<status> | ms=<ms> | args=<arg>`
#: — five fields, pipe-separated, one line per entry, parsed back by
#: `parse_entry`. The order is fixed; a future field goes at the end.
_ENTRY_RE: re.Pattern[str] = re.compile(
    r"^(?P<at>\S+) \| tool=(?P<tool>\S*) \| status=(?P<status>\S+) "
    r"\| ms=(?P<ms>\d+(?:\.\d+)?) \| args=(?P<args>.*)$"
)

# ── the redaction law ─────────────────────────────────────────────────────────────

#: What never reaches the vault. Named, and one guard per name in
#: `tests/test_action_audit_log.py`. The order is the order the passes run in.
REDACTION_CLASSES: Final[tuple[str, ...]] = (
    "api_key",
    "token",
    "credential",
    "session_string",
    "vault_personalization",
)

#: The house marker, the one `src.vault.redact_secret` already uses.
REDACTED: Final[str] = "«redacted»"
#: Personalization is replaced WHOLE: a half-redacted profile is still a profile.
PROFILE_REDACTED: Final[str] = "«profile-redacted»"

#: Pass `api_key` — provider key shapes.
_API_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"\bAIza[0-9A-Za-z_-]{20,}"
    r"|\bsk-(?:ant-|or-v1-)?[A-Za-z0-9_-]{16,}"
    r"|\bgh[pousr]_[A-Za-z0-9]{20,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}"
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"
    r"|\bAKIA[0-9A-Z]{16}"
)

#: Pass `token` — the LABEL survives so a reader still sees THAT a secret was
#: present; the value never does — the `Bearer` scheme keyword excepted, which
#: is not a value at all (see `_LABELLED_RE` below). `REDACTED` is spliced in
#: as `\3`, so the labelled result reads `<label><separator>«redacted»`.
_SENSITIVE_KEYS: Final[str] = (
    r"api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|id[_-]?token"
    r"|token|secret|client[_-]?secret|password|passwd|passphrase|pwd"
    r"|auth|authorization|session|session[_-]?id|sess|confirmation[_-]?id|cfm"
)
#: `(?!\s*Bearer\b)` — A SCHEME KEYWORD IS NOT A VALUE. The value pattern stops
#: at whitespace, so for `Authorization: Bearer <secret>` this pass used to read
#: `Bearer` as the label's value, redact the scheme word, and leave the secret
#: dangling for `_BEARER_RE`, which had no `Bearer` left to key on: the
#: credential reached the vault, under a promise this module's own docstring made
#: and no guard tested. The lookahead makes this pass DECLINE the whole
#: `Bearer …` region and lets the bearer clause — which runs LATER in
#: `redact_arg` — take the shape whole, so the log keeps the label AND the word
#: `Bearer` and loses only the secret.
#:
#: The exemption is the STANDALONE keyword and nothing else. `BearerXYZ123…` has
#: no word boundary after `Bearer` and is still redacted here. Skipping is
#: LOCAL: a failed match resumes scanning at the next character, so a later
#: `password: …` in the same arg is still caught.
_LABELLED_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?i)\b({_SENSITIVE_KEYS})([\"']?\s*[:=]\s*[\"']?)(?!Bearer\b)[^\s\"',;]+"
)
_JWT_RE: Final[re.Pattern[str]] = re.compile(
    r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
)
_BEARER_RE: Final[re.Pattern[str]] = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}")

#: Pass `credential` — a userinfo pair in a URL.
_USERINFO_RE: Final[re.Pattern[str]] = re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@")

#: Pass `session_string` — F-2's signed approval id, and any long opaque
#: base64 blob, which is the shape `StringSession.save()` hands out
#: (`src/telegram_login.py` prints one into `.env`). The second clause is a
#: DELIBERATE over-approximation at 64 characters: the trade is that a very long
#: URL or path in an arg loses its tail to redaction. An over-redacted blob costs
#: one line of the log; an under-redacted session string costs the whole vault,
#: and no owner instruction is ever 64 unbroken base64 characters.
_SESSION_RE: Final[re.Pattern[str]] = re.compile(
    r"\bcfm1\.[A-Za-z0-9._-]+" r"|\b[A-Za-z0-9+/]{64,}={0,2}"
)

#: Pass `vault_personalization` — the three shapes this repo moves profile
#: content in, plus the note's own `slot:`/`value:` rows.
_PROFILE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?im)"
    r"\bUser_Info\b|02_Areas/Profile"
    r"|\[صاحبك باختصار[^\]]*\]|\[ملف المالك\]"
    r"|^#\s*User Info"
    r"|^##\s*معلومة\b|^\s*slot:\s|^\s*value:\s|^\s*superseded:\s"
)

#: Longest arg kept in a line. A log one enormous arg can fill is a log nobody
#: reads; the cut is marked with an ellipsis so a reader never mistakes a
#: truncated field for a whole one.
MAX_ARG_CHARS: Final[int] = 200

# ── the statuses an entry can carry ───────────────────────────────────────────────

#: The handler ran and returned a result that is not the failure line.
STATUS_OK: Final[str] = "ok"
#: The owner will be told `TOOL_FAIL_AR`: either the handler raised, or a handler
#: returned that line itself.
STATUS_TOOL_FAIL: Final[str] = "tool_fail"
#: No `_do_<tool>` exists. Nothing ran.
STATUS_UNKNOWN_TOOL: Final[str] = "unknown_tool"
#: F-1: a SHIPPED handler whose class attribute is no longer it. Nothing ran.
STATUS_REFUSED_HIJACKED: Final[str] = "refused_hijacked_handler"
#: F-1: an irreversible tool with no VERIFIED confirmation id. Nothing ran.
STATUS_REFUSED_UNCONFIRMED: Final[str] = "refused_unconfirmed"

# ── buffering bounds ──────────────────────────────────────────────────────────────

#: Entries per flush. One `append_section` (one vault commit) per batch, not one
#: per entry — a per-entry commit is a network round trip and a 409 waiting
#: to happen.
MAX_BATCH: Final[int] = 64
#: Hard ceiling on the in-memory buffer. Past it the oldest entries are dropped
#: and counted.
MAX_PENDING_ENTRIES: Final[int] = 512
#: Entries per note before the next segment is opened. At ~150 bytes an entry a
#: day would need ~2,400 executions to reach it; it is a bound, not an estimate
#: of a normal day.
MAX_SEGMENT_ENTRIES: Final[int] = 500


def _one_line(text: str, cap: int | None = None) -> str:
    """Collapse to ONE line and cap it. The collapse is not cosmetic:
    `append_section` writes each line verbatim, so an embedded newline would
    forge a second entry in a note nobody re-signs."""
    flat = " ".join(str(text or "").split()).replace("|", "/")
    if cap is not None and len(flat) > cap:
        return flat[: cap - 1] + "…"
    return flat


def redact_arg(arg: str) -> str:
    """Screen ONE tool argument. Returns what may be written to the vault.

    Six passes, in this order, each naming the class it enforces (see
    `REDACTION_CLASSES`): the process's live shared secrets, then
    `vault_personalization` (whole-arg, and it RETURNS — there is nothing left to
    screen), then `api_key`, `token`, `credential`, `session_string`, and finally
    the one-line collapse and cap.

    NOT a DLP product, and it does not claim to be: the five classes are shapes,
    and `src.action_log`'s module docstring states the limit in full. What this
    function guarantees is the narrower, testable law — every one of those five
    shapes is gone from the returned string, and the owner's ordinary
    instruction text is not.

    THE ONE PLACE THE ORDER IS LOAD-BEARING, and why it no longer is. Within
    `token`, `_LABELLED_RE` runs before `_BEARER_RE`, and it used to destroy the
    shape the bearer clause keys on: its value pattern stops at whitespace, so
    `Authorization: Bearer <secret>` gave it the word `Bearer` as the value, and
    the secret then survived a `_BEARER_RE` pass with no `Bearer` left to match.
    `_LABELLED_RE` now DECLINES a standalone `Bearer` (see its comment), so the
    bearer clause takes the shape whole and the label AND the scheme both stay
    readable — `Authorization: Bearer «redacted»`, not `«redacted» «redacted»`.
    The two passes are disjoint on this shape in either order, so the sequence
    is no longer what makes the class safe; the lookahead is.
    """
    text = str(arg or "")
    if not text.strip():
        return ""
    # 0. The live shared secrets this process already knows: the vault's own
    # token, registered at `VaultClient.__init__` (`src/vault.py:353`). Deferred,
    # like every `src.vault` reach in this repository.
    from src.vault import redact_secret

    text = redact_secret(text)
    # 5. vault_personalization — whole-arg, checked BEFORE the cap so a marker
    # past the cut point still triggers.
    if _PROFILE_RE.search(text):
        return PROFILE_REDACTED
    text = _API_KEY_RE.sub(REDACTED, text)
    text = _LABELLED_RE.sub(rf"\1\2{REDACTED}", text)
    text = _JWT_RE.sub(REDACTED, text)
    text = _BEARER_RE.sub(rf"\1{REDACTED}", text)
    text = _USERINFO_RE.sub(f"{REDACTED}@", text)
    text = _SESSION_RE.sub(REDACTED, text)
    return _one_line(text, MAX_ARG_CHARS)


def action_log_path(day: date, segment: int = 1) -> str:
    """Where a day's entries land. `segment` 1 is the canonical note; 2 and up
    are the rotation overflow, in path order so a reader sorts them correctly."""
    suffix = "" if segment < 2 else f"--{segment:02d}"
    return f"{ACTION_LOG_DIR}/{day:%Y/%m}/{day.isoformat()}{suffix}.md"


@dataclass(frozen=True, slots=True)
class ActionEntry:
    """One execution. `args` is ALREADY redacted — redaction happens at the
    record site, so an entry cannot exist unredacted in this process."""

    tool: str
    at: datetime
    args: str
    status: str
    duration_ms: float

    def line(self) -> str:
        return (
            f"{self.at.isoformat()} | tool={self.tool} | status={self.status} "
            f"| ms={self.duration_ms:.3f} | args={self.args}"
        )


def parse_entry(line: str) -> ActionEntry | None:
    """Read an entry line back. `None` for anything that is not one — including
    a section heading — so a note can be read with `parse_entry` alone."""
    match = _ENTRY_RE.match(line.strip())
    if match is None:
        return None
    try:
        at = datetime.fromisoformat(match.group("at"))
        duration = float(match.group("ms"))
    except ValueError:
        return None
    return ActionEntry(
        tool=match.group("tool"),
        at=at,
        args=match.group("args"),
        status=match.group("status"),
        duration_ms=duration,
    )


class ActionLog:
    """The buffer and the writer for ONE vault. Holds no reference to that vault
    (it is passed to `flush`), which is what lets the per-vault registry key on
    the vault weakly without keeping it alive itself."""

    def __init__(self, *, max_segment_entries: int = MAX_SEGMENT_ENTRIES, writable: bool = True):
        self.max_segment_entries = max_segment_entries
        self._writable = writable
        self._buffer: deque[ActionEntry] = deque()
        self._segment_by_day: dict[date, int] = {}
        self._counted: dict[str, int] = {}
        self._flushing = False
        self.written = 0
        self.failed = 0
        self.dropped = 0
        self.flushes = 0
        self.unscheduled = 0

    # -- accounting ----------------------------------------------------------------

    def counters(self) -> dict[str, int]:
        return {
            "pending": len(self._buffer),
            "written": self.written,
            "failed": self.failed,
            "dropped": self.dropped,
            "flushes": self.flushes,
            "unscheduled": self.unscheduled,
        }

    # -- the hot path: append, then hand the write to the loop ---------------------

    def append(self, entry: ActionEntry) -> bool:
        """Buffer one entry. No I/O, no await — this is the whole per-execution
        cost, and it is CPU only. Returns False when the entry was DROPPED
        because there is no writable sink, which is counted, never silent."""
        if not self._writable:
            self.dropped += 1
            return False
        self._buffer.append(entry)
        if len(self._buffer) >= MAX_BATCH:
            self.schedule()
        return True

    def schedule(self, vault: Any = None) -> bool:
        """Ask the running loop to flush at its NEXT yield point. Never awaited
        inline, so the tool's own stack pays nothing — the same shape as
        `src.memory_ledger.schedule_write_back`, which `src/bot.py` calls from
        its turn-end hook and deliberately does not await."""
        if not self._writable or not self._buffer or self._flushing:
            return False
        try:
            task = asyncio.create_task(self._flush_guarded(vault))
        except RuntimeError:  # no running loop (a sync caller): stay buffered
            self.unscheduled += 1
            return False
        _FLUSH_TASKS.add(task)
        task.add_done_callback(_FLUSH_TASKS.discard)
        return True

    # -- the write -----------------------------------------------------------------

    async def flush(self, vault: Any = None) -> int:
        """Drain the buffer into the vault, one `append_section` per batch.
        Returns how many entries were written. NEVER raises: a flush that fails
        is counted and its entries stay buffered for the next attempt."""
        if not self._writable or self._flushing or not self._buffer or vault is None:
            return 0
        self._flushing = True
        written = 0
        try:
            while self._buffer:
                batch: list[ActionEntry] = []
                while self._buffer and len(batch) < MAX_BATCH:
                    batch.append(self._buffer.popleft())
                try:
                    await self._write(vault, batch)
                except Exception as error:  # noqa: BLE001 — the log never raises
                    self.failed += len(batch)
                    self._requeue(batch)
                    logger.warning(
                        "action log flush failed ({} entries kept buffered): {}", len(batch), error
                    )
                    return written
                written += len(batch)
                self.written += len(batch)
        finally:
            self._flushing = False
            self.flushes += 1
        return written

    async def _flush_guarded(self, vault: Any) -> None:
        try:
            await self.flush(vault)
        except Exception as error:  # noqa: BLE001 — a task must never leak
            self.failed += len(self._buffer)
            logger.warning("action log flush task failed: {}", error)

    def _requeue(self, batch: list[ActionEntry]) -> None:
        """Put a failed batch back at the FRONT, order preserved. Bounded: past
        `MAX_PENDING_ENTRIES` the oldest go, and every drop is counted."""
        self._buffer.extendleft(reversed(batch))
        while len(self._buffer) > MAX_PENDING_ENTRIES:
            self._buffer.popleft()
            self.dropped += 1

    async def _write(self, vault: Any, batch: list[ActionEntry]) -> None:
        """One commit per day present in the batch. A batch that straddles local
        midnight is SPLIT by day rather than filed under one of them, so the
        one-note-per-day law is never bent."""
        by_day: dict[date, list[ActionEntry]] = {}
        for entry in batch:
            by_day.setdefault(entry.at.date(), []).append(entry)
        for day, entries in by_day.items():  # dict order = first-seen = earliest
            path, segment = await self._target(vault, day, len(entries))
            lines = [entry.line() for entry in entries]
            await vault.append_section(
                path,
                f"tool-executions {entries[0].at:%H:%M:%S}",
                lines,
                commit_prefix=COMMIT_PREFIX,
            )
            self._counted[path] = self._counted.get(path, 0) + len(lines)
            self._segment_by_day[day] = segment

    async def _target(self, vault: Any, day: date, incoming: int) -> tuple[str, int]:
        """The note this batch belongs in, rotating a segment rather than
        overfilling one. The entry count comes from the NOTE on first touch, so
        a restart cannot forget that a segment is full."""
        segment = self._segment_by_day.get(day, 1)
        path = action_log_path(day, segment)
        known = await self._count_in(vault, path)
        if known + incoming > self.max_segment_entries:
            segment += 1
            path = action_log_path(day, segment)
            known = await self._count_in(vault, path)
        return path, segment

    async def _count_in(self, vault: Any, path: str) -> int:
        cached = self._counted.get(path)
        if cached is not None:
            return cached
        try:
            text = await vault.read(path)
        except FileNotFoundError:
            text = ""
        count = sum(1 for line in text.splitlines() if _ENTRY_RE.match(line))
        self._counted[path] = count
        return count


#: Flush tasks in flight. Mirrors `src/bot.py`'s `_PERSIST_TASKS`: the set keeps
#: the task from being garbage-collected mid-write, and nothing else.
_FLUSH_TASKS: set[asyncio.Task] = set()

#: Entries with nowhere to go: no vault, or a vault with no append surface. They
#: are DROPPED and COUNTED here rather than being written somewhere that cannot
#: be read back.
_NO_SINK = ActionLog(writable=False)

#: One log per vault, keyed WEAKLY — the key is dropped as soon as the vault is
#: collected, and `ActionLog` holds no reference back, so nothing keeps a dead
#: vault (or a dead test's double) alive.
_LOGS: weakref.WeakKeyDictionary[Any, ActionLog] = weakref.WeakKeyDictionary()


def _can_host(vault: Any) -> bool:
    """Can this object carry a durable action log? Only a surface that offers
    `append_section` can, and that test is also what keeps the suite's
    single-purpose vault doubles untouched: a double without the append surface
    is counted as an unsupported sink and never written to."""
    return vault is not None and callable(getattr(vault, "append_section", None))


def action_log_for(vault: Any, *, max_segment_entries: int | None = None) -> ActionLog | None:
    """The log for this vault, or None when it cannot host one.

    Passing `max_segment_entries` CONSTRUCTS A NEW LOG over the same store,
    discarding any buffer and the in-memory entry count. That is the restart
    seam — a fresh process builds exactly this — and it is how the rotation
    guards prove the count comes from the note rather than from memory."""
    if not _can_host(vault):
        return None
    try:
        if max_segment_entries is not None:
            log = ActionLog(max_segment_entries=max_segment_entries)
            _LOGS[vault] = log
            return log
        log = _LOGS.get(vault)
        if log is None:
            log = ActionLog()
            _LOGS[vault] = log
        return log
    except TypeError:  # unhashable, or not weak-referenceable
        return None


def counters(vault: Any) -> dict[str, int]:
    """The observability surface: pending, written, failed, dropped, flushes,
    unscheduled. A silent log must be impossible to mistake for a working one."""
    log = action_log_for(vault)
    return (log or _NO_SINK).counters()


async def flush_action_log(vault: Any) -> int:
    """Flush now and return how many entries were written. The DETERMINISTIC
    seam: the buffered path is fire-and-forget, and a caller that must not lose
    an entry awaits this instead. Zero means there was nothing to write."""
    log = action_log_for(vault)
    if log is None:
        return 0
    return await log.flush(vault)


def record(
    vault: Any,
    *,
    tool: str,
    arg: str,
    status: str,
    started: float,
    tz: Any = None,
) -> ActionLog:
    """Append ONE entry for ONE tool execution. THE ONLY ENTRY POINT.

    Synchronous by law: no `await`, no vault call, no filesystem. It reads a
    clock, screens the argument, appends to memory and hands the write to the
    loop — that is all, and `tests/test_action_audit_log.py` asserts the shape
    off the AST rather than trusting this sentence.

    `confirmation_id` is deliberately ABSENT from this signature. F-2's signed
    `cfm1.` id is a usable owner approval: it is not merely redacted here, it is
    never read by the log at all.

    Raises only if the clock or the sink itself is broken, and the caller at
    `ToolRegistry.call` wraps this call precisely so a broken log cannot alter a
    tool's result. Returns the log it appended to, so a caller can inspect it.
    """
    log = action_log_for(vault) or _NO_SINK
    now = datetime.now(tz) if tz is not None else datetime.now(UTC)
    log.append(
        ActionEntry(
            tool=_one_line(tool, MAX_ARG_CHARS),
            at=now,
            args=redact_arg(arg),
            status=status,
            duration_ms=(perf_counter() - started) * 1000.0,
        )
    )
    log.schedule(vault)
    return log
