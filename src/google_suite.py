"""Typed Google service clients over the shared GoogleSession (sprint-2 §2.1).

Flat method bags returning pydantic models — no SDK hierarchy. Datetimes
normalize to tz-aware UTC.
"""

from datetime import UTC, datetime

from pydantic import AliasChoices, BaseModel, Field, field_validator

from src.google_auth import GoogleSession

CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
TASKS_URL = "https://tasks.googleapis.com/tasks/v1/lists/{tasklist}/tasks"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
CONTACTS_SEARCH_URL = "https://people.googleapis.com/v1/people:searchContacts"


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


class _UTCModel(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def _to_utc(cls, value):
        return _utc(value) if isinstance(value, datetime) else value


class CalendarEvent(_UTCModel):
    id: str
    summary: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def _unwrap(cls, value):
        if isinstance(value, dict):  # Calendar API: {"dateTime": ...} or all-day {"date": ...}
            return value.get("dateTime") or value.get("date")
        return value


class TaskItem(_UTCModel):
    id: str
    title: str
    due: datetime | None = None
    notes: str | None = None
    completed: bool = Field(False, validation_alias=AliasChoices("completed", "status"))

    @field_validator("completed", mode="before")
    @classmethod
    def _from_status(cls, value):
        if isinstance(value, str):  # wire sends status: needsAction | completed
            return value == "completed"
        return value


class DriveFile(_UTCModel):
    id: str
    name: str
    mime_type: str = Field(alias="mimeType")
    modified_time: datetime | None = Field(None, alias="modifiedTime")


class Contact(BaseModel):
    resource_name: str
    display_name: str
    email: str | None = None


class GoogleSuite:
    def __init__(self, session: GoogleSession, calendar_id: str = "primary") -> None:
        self._session = session
        self._calendar_id = calendar_id

    async def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        data = await self._session.request(
            "GET",
            CALENDAR_EVENTS_URL.format(calendar_id=self._calendar_id),
            params={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        return [CalendarEvent.model_validate(item) for item in data.get("items", [])]

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        *,
        location: str | None = None,
        description: str | None = None,
    ) -> CalendarEvent:
        body: dict = {
            "summary": summary,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        data = await self._session.request(
            "POST", CALENDAR_EVENTS_URL.format(calendar_id=self._calendar_id), json=body
        )
        return CalendarEvent.model_validate(data)

    async def list_tasks(self, tasklist: str = "@default") -> list[TaskItem]:
        data = await self._session.request("GET", TASKS_URL.format(tasklist=tasklist))
        return [TaskItem.model_validate(item) for item in data.get("items", [])]

    async def add_task(
        self,
        title: str,
        *,
        due: datetime | None = None,
        notes: str | None = None,
        tasklist: str = "@default",
    ) -> TaskItem:
        body: dict = {"title": title}
        if due:
            body["due"] = due.isoformat()
        if notes:
            body["notes"] = notes
        data = await self._session.request("POST", TASKS_URL.format(tasklist=tasklist), json=body)
        return TaskItem.model_validate(data)

    async def list_drive_files(
        self, query: str | None = None, page_size: int = 25
    ) -> list[DriveFile]:
        params: dict = {
            "pageSize": page_size,
            "fields": "files(id,name,mimeType,modifiedTime)",
        }
        if query:
            params["q"] = query
        data = await self._session.request("GET", DRIVE_FILES_URL, params=params)
        return [DriveFile.model_validate(item) for item in data.get("files", [])]

    async def search_contacts(self, query: str, page_size: int = 10) -> list[Contact]:
        data = await self._session.request(
            "GET",
            CONTACTS_SEARCH_URL,
            params={"query": query, "pageSize": page_size, "readMask": "names,emailAddresses"},
        )
        contacts: list[Contact] = []
        for result in data.get("results", []):
            person = result.get("person", {})
            names = person.get("names") or [{}]
            emails = person.get("emailAddresses") or [{}]
            contacts.append(
                Contact(
                    resource_name=person.get("resourceName", ""),
                    display_name=names[0].get("displayName", ""),
                    email=emails[0].get("value"),
                )
            )
        return contacts
