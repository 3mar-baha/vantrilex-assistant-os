"""Sprint-2 §2.2 AC1-AC8: Gmail sweep/incremental fetch, dedupe, dispatch-then-mark,
watch gating, corrupt-state recovery, lock serialization + parse_message catalog.

Red-test corrections against spec (spec is contract): first boot has no cursor ->
sweep per spec («no cursor → sweep»); the original draft routed only the history
endpoint there, which real Gmail rejects (history.list requires startHistoryId).
"""

import asyncio
import base64
import datetime
from pathlib import Path

import httpx

from src.gmail import GmailInbox
from src.google_auth import GoogleSession


def _settings(make_settings, tmp_path):
    from cryptography.fernet import Fernet

    return make_settings(
        VAULT_ENC_KEY=Fernet.generate_key().decode(), VAULT_LOCAL_PATH=str(tmp_path)
    )


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def message_payload(
    mid: str,
    *,
    subject: str | None = "مرحبا",
    body: str = "نص الرسالة",
    html: bool = False,
    labels: list[str] | None = None,
) -> dict:
    headers = [
        {"name": "From", "value": "مديري <boss@corp.com>"},
        {"name": "Date", "value": "Tue, 14 Nov 2023 10:00:00 +0300"},
        {"name": "List-Unsubscribe", "value": "<mailto:unsub@corp.com>"},
    ]
    if subject is not None:
        headers.append({"name": "Subject", "value": subject})
    if html:
        body_part = {"parts": [{"mimeType": "text/html", "body": {"data": _b64(body)}}]}
    else:
        body_part = {"body": {"data": _b64(body)}}
    return {
        "id": mid,
        "threadId": f"t-{mid}",
        "labelIds": labels or ["INBOX", "UNREAD"],
        "internalDate": "1700000000000",
        "payload": {"headers": headers, **body_part},
    }


class Routes:
    """httpx.MockTransport router on exact 'METHOD /path'; value or callable."""

    def __init__(self, **routes):
        self.routes = routes

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            key = f"{request.method} {request.url.path}"
            responder = self.routes.get(key)
            if responder is None:
                return httpx.Response(404, json={"error": {"message": f"unrouted {key}"}})
            return responder(request) if callable(responder) else responder

        return httpx.MockTransport(handler)


def _history(items: list[tuple[str, str]], history_id: str) -> httpx.Response:
    added = [{"message": {"id": mid, "labelIds": [label]}} for mid, label in items]
    return httpx.Response(
        200,
        json={"history": [{"id": "h1", "messagesAdded": added}], "historyId": history_id},
    )


HISTORY_URL = "GET /gmail/v1/users/me/history"
LIST_URL = "GET /gmail/v1/users/me/messages"
WATCH_URL = "POST /gmail/v1/users/me/watch"


def _msg_url(mid: str) -> str:
    return f"GET /gmail/v1/users/me/messages/{mid}"


def _list(ids: list[str], history_id: str) -> httpx.Response:
    return httpx.Response(
        200, json={"messages": [{"id": mid} for mid in ids], "historyId": history_id}
    )


NOT_FOUND_HISTORY = httpx.Response(
    404, json={"error": {"code": 404, "errors": [{"reason": "historyIdNotFound"}]}}
)


async def test_history_incremental_then_sweep_fallback(make_settings, tmp_path):
    """AC4: no cursor -> sweep (SENT excluded, cursor seeded); cursor -> history
    incremental; historyIdNotFound -> sweep fallback with new cursor persisted."""
    settings = _settings(make_settings, tmp_path)
    first_boot = Routes(
        **{
            LIST_URL: _list(["m1", "m2"], "100"),
            _msg_url("m1"): httpx.Response(200, json=message_payload("m1")),
            _msg_url("m2"): httpx.Response(200, json=message_payload("m2", labels=["SENT"])),
        }
    )
    inbox = GmailInbox(GoogleSession(settings, transport=first_boot.transport()), settings)
    batch = await inbox.fetch_new()
    assert [m.id for m in batch] == ["m1"]  # own SENT mail never delivered
    assert inbox.history_id == "100"  # sweep seeds the incremental cursor

    incremental = Routes(
        **{
            HISTORY_URL: _history([("m3", "INBOX"), ("m4", "SENT")], "300"),
            _msg_url("m3"): httpx.Response(200, json=message_payload("m3")),
        }
    )
    cursor_inbox = GmailInbox(GoogleSession(settings, transport=incremental.transport()), settings)
    cursor_inbox.state.history_id = "100"
    incremental_batch = await cursor_inbox.fetch_new()
    assert [m.id for m in incremental_batch] == ["m3"]
    assert cursor_inbox.history_id == "300"

    sweep = Routes(
        **{
            HISTORY_URL: NOT_FOUND_HISTORY,
            LIST_URL: _list(["m5"], "200"),
            _msg_url("m5"): httpx.Response(200, json=message_payload("m5")),
        }
    )
    stale = GmailInbox(GoogleSession(settings, transport=sweep.transport()), settings)
    stale.state.history_id = "999"  # a cursor the server no longer knows
    delivered = await stale.fetch_new()
    assert [m.id for m in delivered] == ["m5"]  # sweep fallback delivered
    assert stale.history_id == "200"


async def test_fetch_new_dedupes_on_message_id(make_settings, tmp_path):
    """AC3: overlapping fetches dedupe on message id — same mail never redelivered."""
    settings = _settings(make_settings, tmp_path)
    session = GoogleSession(
        settings,
        transport=Routes(
            **{
                LIST_URL: _list(["m1"], "100"),
                HISTORY_URL: _history([("m1", "INBOX")], "100"),
                _msg_url("m1"): httpx.Response(200, json=message_payload("m1")),
            }
        ).transport(),
    )
    inbox = GmailInbox(session, settings)
    first = await inbox.fetch_new()
    assert [m.id for m in first] == ["m1"]
    second = await inbox.fetch_new()  # server still lists m1 (cursor not advanced)
    assert second == []


async def test_dispatch_failure_redelivers_next_cycle(make_settings, tmp_path):
    """AC8: dispatch failure => seen state NOT persisted => next cycle re-delivers."""
    settings = _settings(make_settings, tmp_path)
    routes = Routes(
        **{
            LIST_URL: _list(["m1"], "100"),
            HISTORY_URL: _history([("m1", "INBOX")], "100"),
            _msg_url("m1"): httpx.Response(200, json=message_payload("m1")),
        }
    )
    session = GoogleSession(settings, transport=routes.transport())
    inbox = GmailInbox(session, settings)

    batch = await inbox.fetch_new()
    assert [m.id for m in batch] == ["m1"]
    # dispatch FAILED -> no mark_seen -> cursor/seen NOT persisted
    reloaded = GmailInbox(session, settings)
    redelivered = await reloaded.fetch_new()
    assert [m.id for m in redelivered] == ["m1"]  # crash-window redelivery

    # dispatch succeeds this time -> mark -> next cycle delivers nothing
    inbox.mark_seen(batch)
    assert await inbox.fetch_new() == []


async def test_parse_message_plain_text_fixture():
    """AC1: plain-text fixture parses fully into the typed model."""
    parsed = GmailInbox.parse_message(message_payload("m1"), max_chars=8000)
    assert parsed.id == "m1" and parsed.thread_id == "t-m1"
    assert parsed.from_email == "boss@corp.com"
    assert parsed.from_name == "مديري"
    assert parsed.subject == "مرحبا"
    assert parsed.body_text == "نص الرسالة"
    assert parsed.received_at == datetime.datetime.fromisoformat("2023-11-14T10:00:00+03:00")
    assert parsed.labels == ["INBOX", "UNREAD"]
    assert parsed.has_attachments is False
    assert parsed.list_unsubscribe is True


async def test_parse_message_defaults_and_html_fallback(make_settings, tmp_path):
    """AC2: From split, List-Unsubscribe flag, HTML strip fallback,
    missing-subject default, body truncation marker."""
    parsed = GmailInbox.parse_message(message_payload("m1"), max_chars=100)
    assert parsed.from_email == "boss@corp.com"
    assert parsed.from_name == "مديري"
    assert parsed.subject == "مرحبا"
    assert parsed.list_unsubscribe is True
    assert parsed.received_at == datetime.datetime.fromisoformat("2023-11-14T10:00:00+03:00")

    long = GmailInbox.parse_message(message_payload("m2", body="كلمة " * 200), max_chars=100)
    assert len(long.body_text) <= 110  # capped with truncation marker

    html_msg = GmailInbox.parse_message(
        message_payload("m3", body="<b>عريض</b> ونص عادي", html=True), max_chars=8000
    )
    assert "<b>" not in html_msg.body_text
    assert "عريض" in html_msg.body_text

    no_subject = GmailInbox.parse_message(message_payload("m4", subject=None), max_chars=100)
    assert no_subject.subject == "بدون عنوان"


async def test_watch_topic_gating(make_settings, tmp_path):
    """AC5: topic unset -> False with no wire call; topic set -> users.watch register."""
    from cryptography.fernet import Fernet

    settings_off = make_settings(
        VAULT_ENC_KEY=Fernet.generate_key().decode(), VAULT_LOCAL_PATH=str(tmp_path)
    )
    hits: list[str] = []

    def _record(request: httpx.Request) -> httpx.Response:
        hits.append(request.url.path)
        return httpx.Response(200, json={"historyId": "55"})

    routes = Routes(**{WATCH_URL: _record})
    off = GmailInbox(GoogleSession(settings_off, transport=routes.transport()), settings_off)
    assert await off.watch() is False
    assert hits == []  # no registration attempted without a topic

    settings_on = make_settings(
        VAULT_ENC_KEY=Fernet.generate_key().decode(),
        VAULT_LOCAL_PATH=str(tmp_path),
        GMAIL_PUBSUB_TOPIC="projects/p/topics/gmail-push",
    )
    on = GmailInbox(GoogleSession(settings_on, transport=routes.transport()), settings_on)
    assert await on.watch() is True
    assert hits == ["/gmail/v1/users/me/watch"]
    assert on.history_id == "55"  # watch response seeds the cursor


async def test_corrupt_state_recovers_fresh(make_settings, tmp_path):
    """AC6: corrupt state file -> *.corrupt rename + fresh state, fetch still works."""
    settings = _settings(make_settings, tmp_path)
    state_path = Path(settings.vault_local_path) / "State" / "gmail_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not json", encoding="utf-8")

    routes = Routes(
        **{
            LIST_URL: _list(["m1"], "100"),
            _msg_url("m1"): httpx.Response(200, json=message_payload("m1")),
        }
    )
    inbox = GmailInbox(GoogleSession(settings, transport=routes.transport()), settings)
    assert inbox.state.history_id is None and inbox.state.seen_ids == []
    assert state_path.with_name(state_path.name + ".corrupt").exists()

    batch = await inbox.fetch_new()
    assert [m.id for m in batch] == ["m1"]


async def test_fetch_serialized_under_lock(make_settings, tmp_path):
    """AC7: concurrent fetch_new calls are lock-serialized — m1 delivered exactly once."""
    settings = _settings(make_settings, tmp_path)
    session = GoogleSession(
        settings,
        transport=Routes(
            **{
                LIST_URL: _list(["m1"], "100"),
                _msg_url("m1"): httpx.Response(200, json=message_payload("m1")),
            }
        ).transport(),
    )
    real_request = session.request

    async def _yielding(method, url, **kwargs):
        await asyncio.sleep(0.01)  # force interleaving if the lock were absent
        return await real_request(method, url, **kwargs)

    session.request = _yielding
    inbox = GmailInbox(session, settings)
    first, second = await asyncio.gather(inbox.fetch_new(), inbox.fetch_new())
    assert [m.id for m in first + second].count("m1") == 1


async def test_peek_unread_caps_hydrations(make_settings, tmp_path):
    """Live incident 2026-09-18: peek hydrated 25 FULL messages per turn and blew
    the per-minute Gmail quota (HTTP 403). The snapshot caps per-message gets."""
    settings = _settings(make_settings, tmp_path)
    ids = [f"m{i}" for i in range(1, 13)]
    routes = {LIST_URL: _list(ids, "100")}
    routes.update(
        {_msg_url(mid): httpx.Response(200, json=message_payload(mid)) for mid in ids[:10]}
    )
    session = GoogleSession(settings, transport=Routes(**routes).transport())
    inbox = GmailInbox(session, settings)
    # m11/m12 have NO route: any hydration attempt raises -> proves the cap.
    assert [m.id for m in await inbox.peek_unread()] == ids[:10]


async def test_fetch_new_caps_sweep_burst_without_losing_overflow(make_settings, tmp_path):
    """Live incident 2026-09-18: unbounded sweeps multiply quota burn. Bursts are
    capped AND the cursor is held back so overflow redelivers next cycle."""
    settings = _settings(make_settings, tmp_path)
    ids = [f"m{i}" for i in range(1, 41)]
    routes = {LIST_URL: _list(ids, "100")}
    routes.update(
        {_msg_url(mid): httpx.Response(200, json=message_payload(mid)) for mid in ids[:25]}
    )
    session = GoogleSession(settings, transport=Routes(**routes).transport())
    inbox = GmailInbox(session, settings)
    first = await inbox.fetch_new()
    assert [m.id for m in first] == ids[:25]
    inbox.mark_seen(first)
    routes.update(
        {_msg_url(mid): httpx.Response(200, json=message_payload(mid)) for mid in ids[25:]}
    )
    session2 = GoogleSession(settings, transport=Routes(**routes).transport())
    second = await GmailInbox(session2, settings).fetch_new()
    assert [m.id for m in second] == ids[25:]
