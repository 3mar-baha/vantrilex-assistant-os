"""Sprint-2 §2.1 AC4: fixture responses parse into typed models with UTC normalization."""

import json
from datetime import UTC, datetime

import httpx

from src.google_auth import GoogleSession, GoogleTokens
from src.google_suite import Contact, GoogleSuite


def _suite(make_settings, handler) -> GoogleSuite:
    session = GoogleSession(
        make_settings(),
        GoogleTokens(access_token="a"),
        transport=httpx.MockTransport(handler),
    )
    return GoogleSuite(session)


async def test_calendar_list_parses_fixture(make_settings):
    """Calendar list fixture -> CalendarEvent, +03:00 start/end normalized to UTC."""
    payload = {
        "items": [
            {
                "id": "ev1",
                "summary": "اجتماع التخطيط",
                "start": {"dateTime": "2026-09-01T10:00:00+03:00"},
                "end": {"dateTime": "2026-09-01T11:00:00+03:00"},
                "location": "عمّان",
                "description": "مذكرة الاجتماع",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/calendar/v3/calendars/primary/events"
        assert request.url.params["timeMin"]
        return httpx.Response(200, json=payload)

    events = await _suite(make_settings, handler).list_events(
        datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC)
    )
    assert len(events) == 1
    event = events[0]
    assert event.id == "ev1" and event.summary == "اجتماع التخطيط"
    assert event.start == datetime(2026, 9, 1, 7, 0, tzinfo=UTC)
    assert event.end == datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    assert event.location == "عمّان" and event.description == "مذكرة الاجتماع"


async def test_tasks_crud_shapes(make_settings):
    """Tasks list parses (status -> completed); add_task posts the insert shape."""
    list_payload = {
        "items": [
            {"id": "t1", "title": "مراجعة العرض", "notes": "n", "status": "needsAction"},
            {
                "id": "t2",
                "title": "مؤجلة",
                "due": "2026-09-02T00:00:00.000Z",
                "status": "completed",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=list_payload)
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["title"] == "مهمة جديدة"
        assert body["due"] == "2026-09-03T00:00:00+00:00"
        assert body["notes"] == "x"
        return httpx.Response(
            200, json={"id": "t9", "title": "مهمة جديدة", "status": "needsAction"}
        )

    suite = _suite(make_settings, handler)
    tasks = await suite.list_tasks()
    assert tasks[0].completed is False
    assert tasks[1].completed is True
    assert tasks[1].due == datetime(2026, 9, 2, tzinfo=UTC)

    added = await suite.add_task("مهمة جديدة", due=datetime(2026, 9, 3, tzinfo=UTC), notes="x")
    assert added.id == "t9" and added.completed is False


async def test_drive_list_parses_fixture(make_settings):
    """Drive files fixture -> DriveFile with mimeType/modifiedTime aliased + UTC."""
    payload = {
        "files": [
            {
                "id": "f1",
                "name": "notes.md",
                "mimeType": "text/markdown",
                "modifiedTime": "2026-08-30T10:00:00Z",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/drive/v3/files"
        assert request.url.params["q"] == "name contains 'notes'"
        return httpx.Response(200, json=payload)

    files = await _suite(make_settings, handler).list_drive_files(
        query="name contains 'notes'", page_size=5
    )
    assert len(files) == 1
    assert files[0].mime_type == "text/markdown"
    assert files[0].modified_time == datetime(2026, 8, 30, 10, 0, tzinfo=UTC)


async def test_contacts_search_parses_fixture(make_settings):
    """People searchContacts fixture -> Contact flattening names/emails."""
    payload = {
        "results": [
            {
                "person": {
                    "resourceName": "people/1",
                    "names": [{"displayName": "أحمد"}],
                    "emailAddresses": [{"value": "a@b.c"}],
                }
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/people:searchContacts"
        assert request.url.params["query"] == "أحمد"
        return httpx.Response(200, json=payload)

    contacts = await _suite(make_settings, handler).search_contacts("أحمد")
    assert contacts == [Contact(resource_name="people/1", display_name="أحمد", email="a@b.c")]
