"""Whitelist guardrail (sprint-3 3.4, CLAUDE.md rule 4).

The whitelist file is RE-READ on every check (owner edits apply without restart).
Corrupt/unreadable whitelist -> fail CLOSED (confirm everything) with a CRITICAL log.
Power actions ALWAYS require owner confirmation regardless of any whitelist flag.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from pydantic import BaseModel


class Verdict(BaseModel):
    allowed_without_confirmation: bool
    executable: str | None = None
    requires_confirmation: bool = False
    reason: str


class Guard:
    def __init__(self, whitelist_path: str | Path):
        self._path = Path(whitelist_path)

    def _load(self) -> dict | None:
        """Re-read the whitelist; None = corrupt -> fail closed."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.critical(
                "whitelist {path} unreadable/corrupt — failing CLOSED (confirm everything)",
                path=self._path.name,
            )
            return None
        if not isinstance(data, dict):
            logger.critical("whitelist {path} malformed — failing CLOSED", path=self._path.name)
            return None
        return data

    def check_app(self, name: str) -> Verdict:
        data = self._load()
        if data is None:
            return Verdict(
                allowed_without_confirmation=False,
                requires_confirmation=True,
                reason="whitelist corrupt — confirmation required",
            )
        wanted = name.casefold()
        for entry in data.get("allowed_apps", []):
            if wanted in (
                str(entry.get("name", "")).casefold(),
                str(entry.get("executable", "")).casefold(),
            ):
                if entry.get("auto_approve"):
                    return Verdict(
                        allowed_without_confirmation=True,
                        executable=entry.get("executable"),
                        reason="whitelisted auto_approve",
                    )
                return Verdict(
                    allowed_without_confirmation=False,
                    requires_confirmation=True,
                    reason="whitelisted but requires confirmation",
                )
        return Verdict(
            allowed_without_confirmation=False,
            requires_confirmation=True,
            reason="not whitelisted",
        )

    def check_power(self, action: str) -> Verdict:
        """ALWAYS requires confirmation (fail-closed even if a flag says otherwise)."""
        data = self._load()
        if data is None:
            return Verdict(
                allowed_without_confirmation=False,
                requires_confirmation=True,
                reason="whitelist corrupt — confirmation required",
            )
        wanted = action.casefold()
        for entry in data.get("restricted_actions", []):
            if str(entry.get("action", "")).casefold() == wanted:
                # the entry's requires_confirmation flag is deliberately IGNORED:
                # power actions need an explicit confirmation ID, no exceptions
                return Verdict(
                    allowed_without_confirmation=False,
                    requires_confirmation=True,
                    reason="power action requires explicit owner confirmation",
                )
        return Verdict(
            allowed_without_confirmation=False,
            requires_confirmation=False,
            reason=f"power action {action!r} not in whitelist",
        )
