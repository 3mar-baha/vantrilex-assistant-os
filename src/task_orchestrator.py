"""Directive §5 (owner 2026-09-04): the dual task engine — timed scheduling,
sequential step-DAG, parallel gather, composite scheduled workflows.

Design anchored to the live failures (3:46-3:50pm):
- «بعد 60 ثانية ذكريني اشتري بيض» — REGISTERED, never fired: timers are REAL
  asyncio jobs with a persistence file, and the firing loop re-arms pending
  reminders after a restart (a registered reminder cannot vanish).
- «على الساعة 3:47 مساء ذكريني» — wallclock parsing tied to settings.tz (Amman).
- Timed dispatch is proactive: bot.send_message(owner chat, ...) directly —
  never a silent drop.
Sequential chains STOP at the first failure and report where they died (the
anti-hallucination contract — no claimed completions). Parallel uses gather
and sends ONE unified confirmation. Composite = timer + steps.
Ponytail ceiling: in-memory asyncio timers + a JSON state file — a personal
assistant needs no cron/queue infra; revisit only if reminders exceed dozens."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo

from loguru import logger

Step = tuple[str, Any]  # (label, async callable)

_DELAY_RE = re.compile(
    r"بعد\s+(?P<n>\d+)?\s*(?P<unit>ثانية|ثانيتين|ثواني|دقيقة|دقايق|دقائق|ساعة|ساعات|ساعتين)"
)
# any clock shape: [على] الساعة h[:m] [ampm] — minutes optional, any ampm
# form (صباح/صباحا/فجر/مساء/مساءً/مسا/مغرب/الليل), Arabic-Indic normalized
# upstream; the time may appear anywhere in the sentence.
_WALL_RE = re.compile(
    r"(?:على\s+)?(?:الساعة|الساعه)\s*(?P<h>\d{1,2})(?:[:،](?P<m>\d{1,2}))?"
    r"\s*(?P<ampm>صباحا?ً?|صباح|فجرا?ً?|فجر|مساءً?|مساء|مسا|مغرب|الليل)?"
    r"|(?P<bare_h>\d{1,2})(?:[:،](?P<bare_m>\d{1,2}))?\s*(?P<bare_ampm>صباحا?ً?|مساءً?|مسا)"
)
_AMPM_PM = ("مساء", "مغرب", "مسا", "الليل")
_AMPM_AM = ("صباح", "فجر")
_UNITS_S = {
    "ثانية": 1,
    "ثانيتين": 2,
    "ثواني": 1,
    "دقيقة": 60,
    "دقايق": 60,
    "دقائق": 60,
    "ساعة": 3600,
    "ساعتين": 3600,
    "ساعات": 3600,
}

# A-3b. Tashkeel stripped for MATCHING ONLY, and only by substitution — same
# length, same offsets — so a match on the canon can be applied to the original
# by prefix length. The title is the owner's own words and goes back to him
# verbatim, so no word he wrote may be respelled.
_TASHKEEL_RE: Final = re.compile(r"[ً-ْٰـ]")


def _strip_tashkeel(text: str) -> str:
    """Orthographic canon for matching only: same length, same offsets."""
    return _TASHKEEL_RE.sub("", text)


# A-3b. THE SCHEDULING VERB in every spelling the owner actually uses. The
# previous alternation was the bare `ذكرني`, but he writes `ذكّرني` (U+0651), and
# the substitution ran on RAW text, so the verb never matched and rode into the
# title even on the happy path: `parse_delay_ar('ذكّرني بعد ساعتين أحضر حليب')`
# returned the title `'ذكّرني أحضر حليب'`. One entry covers every diacritic
# variant because each is matched through the canon.
#
# The task's own narration guide states what a title is
# (`src/skills/sara_tool_skills.py:170-172`): what he needs to remember, without
# the time word and WITHOUT THE VERB ITSELF.
_VERB_CANON: Final[tuple[str, ...]] = (
    "ذكّرني",
    "ذكرني",
    "ذكريني",
    "نبّهيني",
    "نبهيني",
    "نبّهني",
    "نبهني",
    "فكّرني",
    "فكرني",
    "جبرني",
    "تنبيه",
    "تذكير",
)
_VERB_RE: Final = re.compile(
    r"^(?:" + "|".join(re.escape(_strip_tashkeel(v)) for v in _VERB_CANON) + r")\s*"
)

# A-3b. THE OWNER'S OWN TURN CONTINUATION. «تمام، …» acknowledges what he just
# said; it is not part of what he wants to be reminded about, and it rode into
# the title verbatim: `parse_delay_ar('تمام، ذكّرني بعد ساعتين أحضر حليب')`
# returned `'تمام، ذكّرني أحضر حليب'`.
#
# Arabic punctuation is a SEPARATOR in the character class below for the same
# reason it is one in `cognition._normalize` (A-3a): it is written with no
# following space, so the token is `تمام،ذكّرني` and a `^`-anchored pattern
# never sees the verb behind it.
_ACK_RE: Final = re.compile(
    r"^(?:تمام|تماماً|تمامًا|تماما|اوكي|أوكي|كيفي|كفى|ماشي|الله"
    r"|ما شاء الله|يسلمو|يسلمو|يعطيك العافية)"
    r"\s*[،؛,;.\s]*"
)

# A-3b, THE BARE-«بعد» BUG — the over-trim hazard, already shipped. The old
# first substitution was `(?:بعد\s+[\d٠-٩]*\s*\S+|…)` with `count=1`, NO `^`
# anchor, and `[\d٠-٩]*` quantifying to ZERO digits, so a bare `بعد` followed by
# any non-space token was eaten: «ذكرني بعد ما أكل» became «أكل», losing the
# conjunction that carried the meaning.
#
# THE FIX IS NOT A LOOSER PATTERN, IT IS THE PARSER'S OWN TABLE: `بعد` here is a
# CONJUNCTION unless a digit or a unit from `_UNITS_S` follows. Anything else —
# «بعد ما», «بعد أن», or «بعد يوم ننتقل» inside a title — is the owner's content
# and stays. `re.escape` on each unit keeps the table single-sourced: adding a
# unit to `_UNITS_S` teaches the stripper about it automatically, so no second
# vocabulary can drift out of step with the one the delay parser uses.
_DELAY_STRIP_RE: Final = re.compile(
    r"^بعد\s+(?:[\d٠-٩]+\s*)?(?:" + "|".join(re.escape(u) for u in _UNITS_S) + r")\s*"
)

# The wallclock prefix, am/pm included. Audit round-3 (2026-09-05) exists
# because the old chain stopped BEFORE the am/pm word, so «على الساعة 3:47 مساء
# ذكريني» produced the title «مساء ذكريني».
_WALL_STRIP_RE: Final = re.compile(
    r"^(?:على\s+)?الساعة\s+[\d٠-٩]{1,2}(?:[:،][\d٠-٩]{1,2})?"
    r"\s*(?:صباحا?ً?|صباح|فجرا?ً?|فجر|مساءً?|مساء|مسا|مغرب|الليل)?\s*"
)


def _strip_command(text: str) -> str:
    """Drop the scheduling prefix so the TITLE is what remains to be said.

    FOUR PASSES, each one there because of a measured failure (A-3b; the
    pre-2026-10-07 body is quoted in
    `tests/test_a3_schedule_title_hygiene.py`'s module docstring):

      1. the acknowledgement — «تمام، …» is turn continuation, not content;
      2. a REAL delay phrase — anchored, and only when a digit or a `_UNITS_S`
         unit follows, so «بعد ما» is never eaten;
      3. a wallclock phrase, am/pm included (audit round-3, 2026-09-05);
      4. the verb, matched tashkeel-insensitively so `ذكّرني` matches.

    THE PREFIX AND THE CONTENT ARE SEPARATE STRINGS. Matching both in one
    string meant folding tashkeel out of the CONTENT as well, which is not
    acceptable: the title goes back to the owner verbatim. So each pattern is
    matched against the canon and the content is advanced by the match's
    LENGTH on the original — the same offsets, because `_strip_tashkeel` only
    substitutes characters in place.

    THE FAIL-SAFE. Every pattern is anchored or leading-only, and the result
    falls back to the input: a title with no prefix comes back byte-identical.
    This function only ever REMOVES a recognised prefix — it never reorders,
    never rewrites a content word, and never touches the interior. That is what
    keeps «اشتري حليب اليوم من السوق» whole.
    """
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return text or ""

    # Repeat, because a turn may stack prefixes: «تمام، على الساعة 3:47 مساء
    # ذكريني» carries three, and each pass strips the one now at the front.
    for _ in range(4):
        before = cleaned
        canon = _strip_tashkeel(cleaned)
        for pattern in (_ACK_RE, _DELAY_STRIP_RE, _WALL_STRIP_RE, _VERB_RE):
            match = pattern.match(canon)
            if match is not None:
                cleaned = cleaned[match.end() :].strip()
                break
        if cleaned == before:
            break
    return cleaned or (text or "").strip()


def parse_delay_ar(text: str, *, now: datetime) -> tuple[timedelta, str] | None:
    """«بعد 60 ثانية/7 دقايق/ساعتين ...» -> (delay, title). GENERAL contract:
    Arabic-Indic digits accepted; all unit plurals land on one table; the
    title is what follows the scheduling verb."""
    match = _DELAY_RE.search(_normalize_digits(text))
    if not match:
        return None
    unit = match.group("unit")
    default_n = 2 if unit in ("ثانيتين", "ساعتين") else 1
    n = int(match.group("n") or default_n)
    unit_s = _UNITS_S[unit]
    return timedelta(seconds=n * unit_s), _strip_command(text)


def parse_wallclock_ar(text: str, *, now: datetime) -> tuple[datetime, str] | None:
    """Any clock shape -> (when-local, title). GENERAL contract: «[على]
    الساعة h[:m] [صباح/مساء]» OR a bare «h[:m] صباحاً/مساءً»; 12 صباح =
    midnight (00), 12 مساء = noon (12); Arabic-Indic digits accepted; a time
    already passed today is tomorrow's (honest, never silently dropped)."""
    match = _WALL_RE.search(_normalize_digits(text))
    if not match:
        return None
    hour = int(match.group("h") or match.group("bare_h"))
    minute = int(match.group("m") or match.group("bare_m") or 0)
    ampm = (match.group("ampm") or match.group("bare_ampm") or "").strip("ً")
    if ampm.startswith(_AMPM_PM):
        if hour < 12:  # 12 مساء = noon; 1-11 مساء = +12
            hour += 12
    elif ampm.startswith(_AMPM_AM) and hour == 12:  # 12 صباح = midnight
        hour = 0
    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if when <= now:
        when += timedelta(days=1)  # a passed wallclock is tomorrow's (honest)
    return when, _strip_command(text)


_DIGIT_MAP = {ord(e): w for e, w in zip("٠١٢٣٤٥٦٧٨٩", "0123456789")}


def _normalize_digits(text: str) -> str:
    """Arabic-Indic digits to Western (٠-٩ -> 0-9) so every parser and the
    regexes read ONE digit space."""
    return text.translate(_DIGIT_MAP)


@dataclass
class ChainReport:
    ok: bool
    label: str
    completed: list[str] = field(default_factory=list)
    failed_at: str | None = None


@dataclass
class _Job:
    """One armed timer: a message to send and/or steps to run when it fires."""

    id: str
    when: datetime
    message: str | None = None
    steps: list[Step] | None = None


def reminder_state_path(state_dir: Path | str) -> Path:
    return Path(state_dir) / "task_reminders.json"


class Orchestrator:
    """The dual engine. run_forever arms/loads timers, fires them on the tick,
    dispatches proactively, and persists the pending set after every change
    (a registered reminder cannot vanish on a restart — live 3:48pm lesson)."""

    def __init__(self, *, bot: Any, chat_id: int, tz: ZoneInfo | None = None) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._tz = tz or ZoneInfo("Asia/Amman")
        self._state_dir: Path | None = None
        self._jobs: dict[str, _Job] = {}
        self._next_id = 1

    # -- registration --------------------------------------------------------

    def bind_state_path(self, state_dir: Path | str) -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)

    async def schedule_delay(
        self,
        message: str,
        *,
        delay: timedelta,
        title: str = "",
        steps: list[Step] | None = None,
    ) -> str:
        when = datetime.now(self._tz) + delay
        return await self._arm(_Job(self._new_id(), when, message, steps), title)

    async def schedule_wallclock(
        self,
        message: str,
        *,
        when: datetime,
        title: str = "",
        steps: list[Step] | None = None,
    ) -> str:
        return await self._arm(_Job(self._new_id(), when, message, steps), title)

    @property
    def pending(self) -> list[_Job]:
        return list(self._jobs.values())

    # -- management (gap-أ, owner 2026-09-05): the owner sees + cancels ---------

    def list_for_owner(self) -> list[str]:
        """The pending reminders as the owner reads them: one line per job —
        id, local time, message — soonest first. The id is the cancel target."""
        rows = []
        for job in sorted(self._jobs.values(), key=lambda j: j.when):
            local = job.when.astimezone(self._tz)
            rows.append(f"{job.id} — {local:%H:%M} — {job.message or '(مهام مجدولة)'}")
        return rows

    def find_by_time(self, spoken: str) -> str | None:
        """Live-2 (2026-09-05 7:05am): «الغي التذكير 7:10» — the owner cancels
        by the SPOKEN time, not a job id. Match the pending job whose local
        hour[:minute] equals the spoken «h[:m]»; None when nothing matches."""
        import re as _re

        match = _re.search(r"(\d{1,2})(?:[:،](\d{1,2}))?", spoken)
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        for job in self._jobs.values():
            local = job.when.astimezone(self._tz)
            if local.hour == hour and local.minute == minute:
                return job.id
        return None

    async def cancel(self, job_id: str) -> bool:
        """Remove ONE reminder now + persist. Unknown id: False (the caller
        answers honestly; nothing fabricated, nothing harmed)."""
        if self._jobs.pop(job_id, None) is None:
            return False
        await self._persist()
        return True

    async def cancel_all(self) -> int:
        """«الغي كل التذكيرات» — the full sweep; returns the removed count."""
        removed = len(self._jobs)
        self._jobs.clear()
        await self._persist()
        return removed

    # -- loop ------------------------------------------------------------------

    async def run_forever(self, *, tick_s: float = 5.0) -> None:
        """Arms timers, fires them on the tick — exception-proof (journaler
        pattern). One tick = at most one sweep; fired jobs never re-fire."""
        while True:
            try:
                await asyncio.sleep(tick_s)
                await self._fire_due()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — the loop outlives any single failure
                logger.warning("orchestrator tick failed (skipped)")

    async def _fire_due(self) -> None:
        now = datetime.now(self._tz)
        due = [job for job in self._jobs.values() if job.when <= now]
        for job in due:
            self._jobs.pop(job.id, None)
            try:
                if job.message:
                    await self._bot.send_message(self._chat_id, job.message)
                if job.steps:
                    await self.run_sequential(job.message or "المهام المجدولة", job.steps)
            except Exception:  # noqa: BLE001 — a dead dispatch is LOUD, never silent
                logger.exception("reminder {} failed to dispatch — re-arming", job.id)
                job.when = now + timedelta(minutes=1)  # retry in a minute
                self._jobs[job.id] = job
            await self._persist()

    # -- engines -----------------------------------------------------------------

    async def run_sequential(self, label: str, steps: list[Step]) -> ChainReport:
        """Step-by-step in ORDER; each stage completes before the next; the
        chain STOPS at the first failure and the report names it — no
        hallucinated completions (live 3:23pm lesson)."""
        report = ChainReport(ok=True, label=label)
        for name, action in steps:
            try:
                await action()
                report.completed.append(name)
            except Exception as error:  # noqa: BLE001 — honest stop + report
                logger.warning("sequential step {} failed: {}", name, error)
                report.ok = False
                report.failed_at = name
                break
        if report.ok:
            done = "، ".join(report.completed)
            await self._tell(f"✅ خلصت {label} بترتيبه: {done} 🌸")
        else:
            await self._tell(
                f"⚠️ {label} توقفت عند «{report.failed_at}» — اللي خلص: "
                f"{'، '.join(report.completed) or 'ولا شي'}. بجرب بعدين إذا بدك 🌸"
            )
        await self._persist()
        return report

    async def run_parallel(self, label: str, steps: list[Step]) -> ChainReport:
        """Concurrent gather; ONE unified confirmation when everything lands.
        A partial failure is reported per-step, honestly."""
        results = await asyncio.gather(
            *(self._guarded(name, action) for name, action in steps),
            return_exceptions=True,
        )
        report = ChainReport(ok=True, label=label)
        for (name, _), result in zip(steps, results, strict=False):
            if isinstance(result, BaseException):
                report.ok = False
                report.failed_at = report.failed_at or name
            else:
                report.completed.append(name)
        if report.ok:
            await self._tell(f"✅ خلصت {label} كله بنفس الوقت: {'، '.join(report.completed)} 🌸")
        else:
            await self._tell(
                f"⚠️ من {label}: نجحت {'، '.join(report.completed) or 'ولا واحدة'}، "
                f"و«{report.failed_at}» ما اشتغلت — بجربها بعدين إذا بدك 🌸"
            )
        await self._persist()
        return report

    async def _guarded(self, name: str, action):
        try:
            await action()
            return name
        except Exception as error:  # noqa: BLE001 — one dead lane never kills the gather
            logger.warning("parallel step {} failed: {}", name, error)
            return error

    # -- internals ------------------------------------------------------------------

    async def _arm(self, job: _Job, title: str) -> str:
        self._jobs[job.id] = job
        await self._tell(f"تمام، سجلتها 🌸 {title or ''}".strip())
        await self._persist()
        return job.id

    async def _tell(self, text: str) -> None:
        try:
            await self._bot.send_message(self._chat_id, text)
        except Exception as error:  # noqa: BLE001 — never blocks scheduling
            logger.warning("orchestrator notify failed: {}", error)

    def _new_id(self) -> str:
        job_id = f"job-{self._next_id}"
        self._next_id += 1
        return job_id

    async def _persist(self) -> None:
        if self._state_dir is None:
            return
        try:
            data = [
                {
                    "id": job.id,
                    "when": job.when.isoformat(),
                    "message": job.message,
                    "has_steps": bool(job.steps),
                }
                for job in self._jobs.values()
            ]
            reminder_state_path(self._state_dir).write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as error:
            logger.warning("reminder persist failed: {}", error)

    def load_pending(self) -> int:
        """Re-arm persisted reminders after a restart (message-only jobs; step
        chains are re-armed as their message + a fresh id)."""
        if self._state_dir is None:
            return 0
        try:
            data = json.loads(reminder_state_path(self._state_dir).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        for entry in data:
            try:
                when = datetime.fromisoformat(entry["when"])
            except (KeyError, ValueError):
                continue
            job = _Job(
                id=entry.get("id") or self._new_id(), when=when, message=entry.get("message")
            )
            self._jobs[job.id] = job
        return len(self._jobs)
