"""Gmail watch + polled fetch (sprint-2 §2.2): typed, deduplicated inbox stream.

Polling-only in v1.0 (zero inbound ports): users.watch registered once when
GMAIL_PUBSUB_TOPIC is set (push option stays open for v1.1), delivery via
historyId incremental with query-sweep fallback. Dispatch-then-mark: seen
state persists only after dispatch, so a crash re-delivers instead of losing
mail. State is plaintext (no secrets) at {vault_local_path}/State/gmail_state.json.
"""

import asyncio
import base64
import json
import os
from datetime import UTC, datetime
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ValidationError

from src.google_auth import GoogleAPIError, GoogleSession

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
HISTORY_URL = f"{GMAIL_API}/history"
MESSAGES_URL = f"{GMAIL_API}/messages"
WATCH_URL = f"{GMAIL_API}/watch"

TRUNCATION_MARKER = "…[مقتطع]"
SEEN_IDS_CAP = 2000


class EmailMessage(BaseModel):
    id: str
    thread_id: str
    from_email: str = ""
    from_name: str = ""
    subject: str
    body_text: str = ""
    received_at: datetime
    labels: list[str] = []
    has_attachments: bool = False
    list_unsubscribe: bool = False  # set by parse_message from headers


class GmailState(BaseModel):
    seen_ids: list[str] = []
    history_id: str | None = None
    last_brief_date: str | None = None  # ISO local date of last daily brief (§2.4)


class StateStore:
    """Plaintext JSON state; corrupt file -> *.corrupt rename + fresh state."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> GmailState:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return GmailState()
        try:
            return GmailState.model_validate(json.loads(raw))
        except (ValueError, ValidationError):
            corrupt = self._path.with_name(self._path.name + ".corrupt")
            os.replace(self._path, corrupt)
            logger.warning("gmail state corrupt -> renamed to {}, starting fresh", corrupt)
            return GmailState()

    def save(self, state: GmailState) -> None:
        state.seen_ids = state.seen_ids[-SEEN_IDS_CAP:]  # newest kept
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(state.model_dump_json(), encoding="utf-8")
        tmp.replace(self._path)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.chunks.append(data)


def _strip_html(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return "".join(extractor.chunks)


def _decode_part(node: dict) -> str | None:
    data = (node.get("body") or {}).get("data")
    if not data:
        return None
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", "replace")
    except ValueError:  # binascii.Error subclasses ValueError; skip bad part
        return None


def _extract_body(part: dict, max_chars: int) -> str:
    plain: list[str] = []
    html: list[str] = []

    def walk(node: dict) -> None:
        if node.get("filename"):  # attachment — never body text
            return
        decoded = _decode_part(node)
        if decoded is not None:
            (html if node.get("mimeType") == "text/html" else plain).append(decoded)
        for child in node.get("parts", []):
            walk(child)

    walk(part)
    text = "\n".join(plain) if plain else _strip_html("\n".join(html))
    if len(text) > max_chars:
        text = text[:max_chars] + TRUNCATION_MARKER
    return text


def _has_attachments(part: dict) -> bool:
    stack = [part]
    while stack:
        node = stack.pop()
        if node.get("filename"):
            return True
        stack.extend(node.get("parts", []))
    return False


class GmailInbox:
    def __init__(self, session: GoogleSession, settings) -> None:
        self._session = session
        self._settings = settings
        self._lock = asyncio.Lock()
        self._store = StateStore(Path(settings.vault_local_path) / "State" / "gmail_state.json")
        self.state: GmailState = self._store.load()

    @property
    def history_id(self) -> str | None:
        return self.state.history_id

    async def watch(self) -> bool:
        """Register users.watch when a topic is configured; polling works regardless."""
        topic = self._settings.gmail_pubsub_topic
        if not topic:
            logger.info("GMAIL_PUBSUB_TOPIC unset -> polling only, watch not registered")
            return False
        try:
            data = await self._session.request(
                "POST",
                WATCH_URL,
                json={"topicName": topic, "labelIds": ["INBOX"], "labelFilterAction": "include"},
            )
        except GoogleAPIError as error:
            logger.warning("gmail watch registration failed (polling unaffected): {}", error)
            return False
        self.state.history_id = data.get("historyId", self.state.history_id)
        logger.info("gmail watch registered on {}", topic)
        return True

    async def fetch_new(self) -> list[EmailMessage]:
        async with self._lock:  # serialize concurrent fetches (AC7)
            return await self._fetch_locked()

    async def _fetch_locked(self) -> list[EmailMessage]:
        if self.state.history_id:
            try:
                candidates = await self._history_ids(self.state.history_id)
            except GoogleAPIError as error:  # historyIdNotFound/expiry -> sweep
                logger.warning("gmail history path failed -> sweep fallback: {}", error)
                candidates = await self._sweep_ids()
        else:
            candidates = await self._sweep_ids()
        candidates = [mid for mid in candidates if mid and mid not in self.state.seen_ids]
        messages: list[EmailMessage] = []
        for mid in candidates:
            parsed = await self._get_message(mid)
            if "SENT" in parsed.labels:  # sweep ids carry no labels until fetched
                continue
            self.state.seen_ids.append(parsed.id)  # in-memory now; persisted on mark
            messages.append(parsed)
        return messages

    async def _history_ids(self, start: str) -> list[str]:
        data = await self._session.request("GET", HISTORY_URL, params={"startHistoryId": start})
        self.state.history_id = data.get("historyId", self.state.history_id)
        ids: list[str] = []
        for entry in data.get("history", []):
            for added in entry.get("messagesAdded", []):
                message = added.get("message", {})
                if "SENT" in message.get("labelIds", []):  # own mail never delivered
                    continue
                ids.append(message.get("id"))
        return ids

    async def _sweep_ids(self) -> list[str]:
        days = self._settings.gmail_sweep_days
        data = await self._session.request(
            "GET", MESSAGES_URL, params={"q": f"is:unread newer_than:{days}d"}
        )
        if data.get("historyId"):  # sweep seeds/refreshes the incremental cursor
            self.state.history_id = data["historyId"]
        return [ref.get("id") for ref in data.get("messages", [])]

    async def _get_message(self, mid: str) -> EmailMessage:
        payload = await self._session.request(
            "GET", f"{MESSAGES_URL}/{mid}", params={"format": "full"}
        )
        return self.parse_message(payload, max_chars=self._settings.triage_body_max_chars)

    def save_state(self) -> None:
        """Persist state outside the dispatch-then-mark flow (daily brief date)."""
        self._store.save(self.state)

    def mark_seen(self, messages: list[EmailMessage]) -> None:
        """Persist cursor + seen ids — call ONLY after dispatch completed (AC8)."""
        self.save_state()
        logger.debug(
            "gmail state persisted: {} seen, cursor {}",
            len(self.state.seen_ids),
            self.state.history_id,
        )

    async def unread_digest(self) -> tuple[int, int]:
        data = await self._session.request("GET", MESSAGES_URL, params={"q": "is:unread"})
        ids = [ref.get("id") for ref in data.get("messages", [])]
        unseen = [mid for mid in ids if mid not in self.state.seen_ids]
        return len(ids), len(unseen)

    async def peek_unread(self, max_n: int = 25) -> list[EmailMessage]:
        """Read-only recent unread snapshot (daily brief) — never touches cursor/seen."""
        data = await self._session.request(
            "GET",
            MESSAGES_URL,
            params={"q": f"is:unread newer_than:{self._settings.gmail_sweep_days}d"},
        )
        refs = [ref.get("id", "") for ref in data.get("messages", [])[:max_n]]
        return [await self._get_message(mid) for mid in refs]

    @staticmethod
    def parse_message(payload: dict, max_chars: int) -> EmailMessage:
        headers = {
            h["name"].lower(): h.get("value", "")
            for h in payload.get("payload", {}).get("headers", [])
        }
        from_name, from_email = parseaddr(headers.get("from", ""))
        date_raw = headers.get("date")
        received: datetime | None = None
        if date_raw:
            try:
                received = parsedate_to_datetime(date_raw)
            except (TypeError, ValueError):
                received = None
        if received is None:  # safe default: wire epoch millis, else epoch
            internal = payload.get("internalDate")
            try:
                received = datetime.fromtimestamp(int(internal) / 1000, tz=UTC)
            except (TypeError, ValueError):
                received = datetime.fromtimestamp(0, tz=UTC)
        return EmailMessage(
            id=payload.get("id", ""),
            thread_id=payload.get("threadId", ""),
            from_email=from_email,
            from_name=from_name,
            subject=headers.get("subject") or "بدون عنوان",
            body_text=_extract_body(payload.get("payload", {}), max_chars),
            received_at=received,
            labels=payload.get("labelIds", []),
            has_attachments=_has_attachments(payload.get("payload", {})),
            list_unsubscribe="list-unsubscribe" in headers,
        )


async def run_gmail_poll(inbox: GmailInbox, dispatcher, classifier, settings) -> None:
    """Poll loop: fetch -> dispatch per message -> mark only after full batch."""
    await inbox.watch()
    while True:
        try:
            batch = await inbox.fetch_new()
            for message in batch:
                await dispatcher(message, classifier)
            if batch:
                inbox.mark_seen(batch)
        except GoogleAPIError as error:
            logger.warning("gmail poll cycle failed, continuing: {}", error)
        await asyncio.sleep(settings.gmail_poll_seconds)
