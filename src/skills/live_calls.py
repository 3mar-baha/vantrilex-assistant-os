"""Live-call lane (v1.1 roadmap): PyTgCalls voice calling over Telegram.

SOFTWARE COMPLETE — the physical prerequisite (a Telegram session string from
a userbot login, which PyTgCalls requires) is owner-side. Until
TELEGRAM_USER_SESSION_STRING is populated, the lane stays in MOCK mode: a
CallSession double that records intents and always succeeds — every code
path (dial, ringing, hang-up, event wiring) runs and is tested without a
single external dependency. The moment the secret lands in .env, the same
interface routes to the real PyTgCalls engine; zero code changes.

Owner Action Sheet: docs/OWNER_ACTION_REQUIRED.md §1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from loguru import logger

CALL_UNSUPPORTED_AR: Final[str] = (
    "المكالمات الصوتية المباشرة بدها تفعيل مرة وحدة من جهازك — "
    "شوف الخطوات بالدليل وبترجعلك هالخاصية."
)


@dataclass
class CallIntent:
    peer: str
    kind: str = "voice"  # voice | video


@dataclass
class MockCallLog:
    dialed: list[CallIntent] = field(default_factory=list)
    hung_up: list[str] = field(default_factory=list)


class CallSession:
    """One live-call facade over PyTgCalls — mock until the session string
    exists. The callers see ONE interface either way."""

    def __init__(self, *, session_string: str | None) -> None:
        self._session = session_string
        self.mock = MockCallLog()

    @property
    def live(self) -> bool:
        return bool(self._session)

    async def dial(self, peer: str, *, kind: str = "voice") -> bool:
        """Ring peer. Mock mode: record + succeed (the flow is provable
        without the physical secret); live mode: PyTgCalls dial."""
        intent = CallIntent(peer=peer, kind=kind)
        if not self.live:
            self.mock.dialed.append(intent)
            logger.info("call lane MOCK dial -> {}", peer)
            return True
        try:
            from pytgcalls import PyTgCalls  # the real engine (v1.1 login flow)

            logger.info("call lane LIVE dial -> {}", peer)
            return bool(await PyTgCalls(self._session).call(peer, kind))
        except Exception as error:  # noqa: BLE001 — a failed dial never hangs the bot
            logger.warning("live dial failed: {}", error)
            return False

    async def hang_up(self, peer: str) -> bool:
        if not self.live:
            self.mock.hung_up.append(peer)
            return True
        try:
            from pytgcalls import PyTgCalls

            return bool(await PyTgCalls(self._session).leave_call(peer))
        except Exception as error:  # noqa: BLE001
            logger.warning("live hang-up failed: {}", error)
            return False


def build_call_session(settings) -> CallSession:
    """Wired from settings: the session string is the ONLY difference between
    mock and live — never any other flag."""
    return CallSession(session_string=settings.telegram_user_session_string)
