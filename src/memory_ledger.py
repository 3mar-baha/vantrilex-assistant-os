"""Async self-expanding memory write-back (Step 11, durability doctrine).

Dual-trigger, background-only ledger growth:
- AUTO: Cognitive Task Weight >= 4 (architectural decisions, milestones,
  strategic pivots) — measured, never vibes.
- EXPLICIT: owner intent shapes ("remember this", "we decided", ...).
Routine chitchat is strictly skipped — the ledger grows on signal alone.

Two surfaces per firing: a dated milestone bullet appended to the nested
daily ledger, plus a bounded refresh of the Tier-1 master digest (hard
800-word cap — overflow skips loudly instead of bloating hot context).
Everything here is total: skips and failures return None/False, never raise
(the reply path must never wait on — or die from — memory growth).
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

from loguru import logger

WRITEBACK_WEIGHT_THRESHOLD: Final[int] = 4
DIGEST_WORD_CAP: Final[int] = 800
MILESTONE_SECTION: Final[str] = "## Milestone log (auto)"
MASTER_DIGEST_PATH: Final[str] = "02_Areas/Profile/Omar_Master_Digest.md"

_EXPLICIT_RE: Final = re.compile(
    r"تذكّر|تذكر|افتكر|سجّل عندك|سجل عندك|احفظ (هالشي|هالشيء|هاد)|اتفقنا"
    r"|remember this|we decided|note (this|that) down|dont forget|don't forget",
    re.IGNORECASE,
)


def should_write_back(user_text: str, *, weight: int | None = None) -> bool:
    """Fire iff explicit owner intent OR task weight >= threshold."""
    text = user_text or ""
    if _EXPLICIT_RE.search(text):
        return True
    if weight is None:
        try:
            from src.cognitive_dag import classify_weight

            weight = classify_weight(text).weight
        except Exception as error:  # noqa: BLE001 — unmeasurable turns never write
            logger.debug("write-back weight probe failed: {}", error)
            return False
    try:
        return int(weight) >= WRITEBACK_WEIGHT_THRESHOLD
    except (TypeError, ValueError):
        return False


def render_milestone(user_text: str, *, day: date) -> str:
    """One dated bullet: date stamp + compacted turn essence (no newlines)."""
    essence = " ".join((user_text or "").split())[:200] or "—"
    return f"- {day.isoformat()}: {essence}"


async def append_milestone(vault, user_text: str, *, now: datetime) -> str | None:
    """Append the milestone bullet to the nested daily ledger. Returns the
    ledger path, or None when the vault write fails."""
    from src.vault import daily_log_path

    day = now.date()
    bullet = render_milestone(user_text, day=day)
    path = daily_log_path(day)
    try:
        await vault.append_section(
            path, MILESTONE_SECTION, [bullet], commit_prefix="sara: milestone"
        )
    except Exception as error:  # noqa: BLE001 — best-effort ledger growth
        logger.warning("write-back milestone append failed: {}", error)
        return None
    return path


async def refresh_digest(vault, bullet: str, *, max_words: int = DIGEST_WORD_CAP) -> bool:
    """Append the bullet to the master digest's trailing milestone section.

    Creates the section on first write. Refuses (False + loud log) when the
    digest is missing or the append would breach the word cap — hot context
    stays compact by construction; history lives in the dated archive.
    """
    try:
        current = await vault.read(MASTER_DIGEST_PATH)
    except FileNotFoundError:
        logger.warning("write-back digest refresh skipped: master digest absent")
        return False
    except Exception as error:  # noqa: BLE001
        logger.warning("write-back digest read failed: {}", error)
        return False
    if MILESTONE_SECTION not in current:
        updated = current.rstrip("\n") + f"\n\n{MILESTONE_SECTION}\n{bullet}\n"
    else:
        updated = current.rstrip("\n") + f"\n{bullet}\n"
    if len(updated.split()) > max_words:
        logger.warning("write-back digest refresh skipped: cap {} words would break", max_words)
        return False
    try:
        await vault.upsert(MASTER_DIGEST_PATH, updated, message="sara: digest milestone")
    except Exception as error:  # noqa: BLE001
        logger.warning("write-back digest upsert failed: {}", error)
        return False
    return True


async def maybe_write_back(
    vault, user_text: str, *, now: datetime | None = None, weight: int | None = None
) -> dict[str, Any] | None:
    """Full write-back pass: milestone ledger + digest refresh. Returns a
    summary dict, or None when skipped (no trigger / no vault / any failure).
    Never raises — call from background tasks only."""
    if vault is None:
        return None
    try:
        if not should_write_back(user_text, weight=weight):
            return None
    except Exception as error:  # noqa: BLE001 — belt first
        logger.debug("write-back gate failed closed: {}", error)
        return None
    moment = now or datetime.now(UTC)
    bullet = render_milestone(user_text, day=moment.date())
    ledger_path = await append_milestone(vault, user_text, now=moment)
    digest_ok = await refresh_digest(vault, bullet)
    return {"milestone_path": ledger_path, "digest_refreshed": digest_ok, "bullet": bullet}


def schedule_write_back(vault, user_text: str, *, tz=None) -> asyncio.Task | None:
    """Turn-end hook (bot.py _persist_exchange): pure trigger check first —
    returns None without touching the event loop on routine turns; otherwise
    spawns the background pass for the caller to track (never awaited inline,
    so live latency is untouched)."""
    if vault is None:
        return None
    try:
        if not should_write_back(user_text):
            return None
    except Exception as error:  # noqa: BLE001
        logger.debug("write-back schedule gate failed closed: {}", error)
        return None
    zone = tz or ZoneInfo("UTC")
    return asyncio.create_task(maybe_write_back(vault, user_text, now=datetime.now(zone)))
