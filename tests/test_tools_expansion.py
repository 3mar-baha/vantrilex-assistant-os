"""Phase B (2026-09-06): Tool Wiring & Operational Surface Completion.

Covers the B1–B8 backlog from AUDIT_AND_PLAN_40_FEATURES.md:

  B1 drive (Google Drive listing/search)      — GoogleSuite.list_drive_files
  B2 contacts (People directory lookup)        — GoogleSuite.search_contacts
  B3 create_event + create_task (write verbs)  — GoogleSuite.create_event/add_task
  B4 places (nearby venues, Amman)             — GoogleCloudClient.places
  B5 deep_search (Custom Search w/ DDG fallback)
  B6 fitness (daily readout)
  B7 cloud_backup + analytics (storage / SQL)
  B8 quota_safety (free-tier headroom)

Every handler must degrade to an honest offline line when its backend is
unconfigured or a call fails — never a fabricated number, never a hang
(ToolRegistry.call wraps all of this, but each handler still guards None deps).

Routing keywords live in src/dispatcher.py; per-tool skill guides in
src/skills/sara_tool_skills.py. All network is doubled (fakes / httpx doubles).
"""

from __future__ import annotations

from datetime import UTC

from src.dispatcher import _VALID_TOOLS, _keyword_net


def test_keyword_net_routes_prayer_adan_variants():
    """«شو اوقات الاذان للصلوات اليوم» — the live 2026-09-07 miss fell to plain
    chat («ما عندي أداة لأوقات الأذان»); the net now catches اذان/أذان/صلوات."""
    for phrase in (
        "شو اوقات الاذان للصلوات اليوم",
        "شو اوقات الأذان للصلوات",
        "وقت أذان الفجر اليوم",
        "مواقيت الصلاة اليوم",
        "شو أوقات الآذان اليوم",
    ):
        tool, _ = _keyword_net(phrase)
        assert tool == "prayer_times", phrase


# --------------------------------------------------------------------------- fakes


class _Suite:
    """A GoogleSuite-shaped fake for the B1-B3 handlers."""

    def __init__(
        self,
        drive=None,
        contacts=None,
        *,
        fail: str | None = None,
    ) -> None:
        self.drive = drive or []
        self.contacts = contacts or []
        self.fail = fail
        self.created_events: list[dict] = []
        self.created_tasks: list[dict] = []

    async def list_drive_files(self, query=None, page_size=25):
        if self.fail == "drive":
            raise RuntimeError("drive down")
        return self.drive

    async def search_contacts(self, query, page_size=10):
        if self.fail == "contacts":
            raise RuntimeError("people down")
        return [c for c in self.contacts if query in c.display_name]

    async def create_event(self, summary, start, end, *, location=None, description=None):
        if self.fail == "create_event":
            raise RuntimeError("calendar down")
        self.created_events.append({"summary": summary, "start": start, "end": end})
        return _Ev(summary=summary, start=start, end=end)

    async def add_task(self, title, *, due=None, notes=None, tasklist="@default"):
        if self.fail == "create_task":
            raise RuntimeError("tasks down")
        self.created_tasks.append({"title": title, "due": due})
        return _Task(title=title, due=due)


class _Ev:
    def __init__(self, *, summary, start, end):
        self.summary, self.start, self.end = summary, start, end


class _Task:
    def __init__(self, *, title, due=None):
        self.title, self.due = title, due


class _File:
    def __init__(self, name, id, mime="application/pdf"):
        self.name, self.id, self.mime_type = name, id, mime


class _Contact:
    def __init__(self, name, email=None, phones=()):
        self.display_name = name
        self.email = email
        self.phones = list(phones)


class _Cloud:
    """A GoogleCloudClient-shaped fake for the B4-B8 handlers."""

    def __init__(
        self,
        *,
        places=None,
        deep=None,
        fitness=None,
        quota=None,
        fail: str | None = None,
        raise_on: str | None = None,
    ) -> None:
        self.places_out = places or []
        self.deep_out = deep
        self.fitness_out = fitness
        self.quota_out = quota
        self.fail = fail
        self.raise_on = raise_on
        self.backed_up = 0
        self.analytics_called: list[str] = []

    async def places(self, query):
        if self.raise_on == "places":
            raise RuntimeError("places down")
        if self.fail == "places":
            return None
        return self.places_out

    async def deep_search(self, query):
        if self.raise_on == "deep_search":
            raise RuntimeError("cse down")
        if self.fail == "deep_search":
            return None
        return self.deep_out

    async def fitness(self):
        if self.raise_on == "fitness":
            raise RuntimeError("fitness down")
        if self.fail == "fitness":
            return None
        return self.fitness_out

    async def cloud_backup(self, payload: bytes):
        if self.raise_on == "cloud_backup":
            raise RuntimeError("storage down")
        if self.fail == "cloud_backup":
            return False
        self.backed_up += 1
        return True

    async def analytics(self, query):
        if self.raise_on == "analytics":
            raise RuntimeError("bq down")
        if self.fail == "analytics":
            return None
        self.analytics_called.append(query)
        return {"rows": [("الكروم", 210)]}

    async def quota_report(self):
        if self.raise_on == "quota_report":
            raise RuntimeError("usage down")
        if self.fail == "quota_report":
            return None
        return self.quota_out or {"services": [{"name": "calendar", "pct": 12}]}


# --------------------------------------------------------------------------- B1 drive


async def test_drive_lists_files_with_name_id_and_link():
    from src.tools import ToolRegistry

    suite = _Suite(drive=[_File("ملاحظات.md", "f1", "text/markdown")])
    out = await ToolRegistry(suite=suite).call("drive", "ملاحظات")
    assert "ملاحظات.md" in out and "f1" in out
    assert "drive.google.com" in out or "open?id=f1" in out


async def test_drive_empty_lists_recent_or_honest():
    from src.tools import ToolRegistry

    out = await ToolRegistry(suite=_Suite(drive=[])).call("drive", "ملاحظات")
    assert "ما لقيت" in out or "ما في" in out


async def test_drive_without_suite_is_offline():
    from src.tools import ToolRegistry

    assert "مو متصل" in await ToolRegistry().call("drive", "x")


# --------------------------------------------------------------------------- B2 contacts


async def test_contacts_returns_a_compact_card():
    from src.tools import ToolRegistry

    suite = _Suite(contacts=[_Contact("أحمد", email="a@b.c", phones=["0791234567"])])
    out = await ToolRegistry(suite=suite).call("contacts", "أحمد")
    assert "أحمد" in out and "a@b.c" in out and "0791234567" in out


async def test_contacts_not_found_is_honest():
    from src.tools import ToolRegistry

    out = await ToolRegistry(suite=_Suite(contacts=[])).call("contacts", "زيد")
    assert "ما لقيت" in out and "زيد" in out


async def test_contacts_without_suite_is_offline():
    from src.tools import ToolRegistry

    assert "مو متصل" in await ToolRegistry().call("contacts", "أحمد")


# --------------------------------------------------------------------------- B3 write verbs


async def test_create_event_parses_and_echoes():
    from src.tools import ToolRegistry

    suite = _Suite()
    out = await ToolRegistry(suite=suite, tz=UTC).call("create_event", "اجتماع التخطيط")
    assert suite.created_events, "the suite must have been called"
    assert "اجتماع التخطيط" in out


async def test_create_event_without_suite_is_offline():
    from src.tools import ToolRegistry

    assert "مو متصل" in await ToolRegistry().call("create_event", "اجتماع")


async def test_create_task_parses_and_echoes():
    from src.tools import ToolRegistry

    suite = _Suite()
    out = await ToolRegistry(suite=suite).call("create_task", "مراجعة العرض")
    assert suite.created_tasks and "مراجعة العرض" in out


async def test_create_task_without_suite_is_offline():
    from src.tools import ToolRegistry

    assert "مو متصل" in await ToolRegistry().call("create_task", "مهمة")


# --------------------------------------------------------------------------- B4 places


async def test_places_formats_venue_results():
    from src.tools import ToolRegistry

    cloud = _Cloud(places=[{"name": "مقهى كرك", "rating": 4.5, "address": "شارع الرينبو"}])
    out = await ToolRegistry(cloud=cloud).call("places", "كافيه")
    assert "مقهى كرك" in out and "4.5" in out and "شارع الرينبو" in out


async def test_places_honest_offline():
    from src.tools import ToolRegistry

    assert "ما قدرت" in await ToolRegistry().call("places", "كافيه")
    assert "ما قدرت" in await ToolRegistry(cloud=_Cloud(fail="places")).call("places", "كافيه")


# --------------------------------------------------------------------------- B5 deep_search


async def test_deep_search_returns_results():
    from src.tools import ToolRegistry

    cloud = _Cloud(deep={"items": [{"title": "عنوان", "link": "https://x", "snippet": "مقتطف"}]})
    out = await ToolRegistry(cloud=cloud).call("deep_search", "شرح الفيزياء")
    assert "عنوان" in out and "https://x" in out


async def test_deep_search_falls_back_to_web_when_cse_absent():
    from src.tools import ToolRegistry

    class _Web:
        async def search_block(self, q):
            return "نتايج داك-داك-غو: كروت شاشة — https://example.com"

    out = await ToolRegistry(cloud=None, web=_Web()).call("deep_search", "كروت شاشة")
    assert "داك-داك-غو" in out or "example.com" in out


async def test_deep_search_honest_offline():
    from src.tools import ToolRegistry

    assert "ما قدرت" in await ToolRegistry().call("deep_search", "x")


# --------------------------------------------------------------------------- B6 fitness


async def test_fitness_returns_readout():
    from src.tools import ToolRegistry

    cloud = _Cloud(fitness={"steps": 8200, "active_minutes": 35, "calories": 480})
    out = await ToolRegistry(cloud=cloud).call("fitness", "")
    assert "8200" in out and "35" in out and "480" in out


async def test_fitness_honest_offline():
    from src.tools import ToolRegistry

    assert "ما قدرت" in await ToolRegistry().call("fitness", "")


# --------------------------------------------------------------------------- B7 backup & analytics


async def test_cloud_backup_uses_vault_and_confirms():
    from src.tools import ToolRegistry

    class _Vault:
        async def list_dir(self, directory):
            return ["Daily_Logs/2026-09-06.md"]

        async def read(self, path):
            return "بيانات"

    cloud = _Cloud()
    out = await ToolRegistry(vault=_Vault(), cloud=cloud).call("cloud_backup", "")
    assert cloud.backed_up == 1 and "نسخة" in out


async def test_cloud_backup_without_vault_is_honest():
    from src.tools import ToolRegistry

    assert "ما قدرت" in await ToolRegistry().call("cloud_backup", "")


async def test_analytics_returns_rows():
    from src.tools import ToolRegistry

    cloud = _Cloud()
    out = await ToolRegistry(cloud=cloud).call("analytics", "وقت الشاشة")
    assert "الكروم" in out and "210" in out


async def test_analytics_honest_offline():
    from src.tools import ToolRegistry

    assert "ما قدرت" in await ToolRegistry().call("analytics", "وقت")


# --------------------------------------------------------------------------- B8 quota_safety


async def test_quota_safety_reports_headroom():
    from src.tools import ToolRegistry

    cloud = _Cloud(quota={"services": [{"name": "calendar", "pct": 12}]})
    out = await ToolRegistry(cloud=cloud).call("quota_safety", "")
    assert "12" in out and ("آمن" in out or "ضمن" in out or "حصة" in out)


async def test_quota_safety_honest_offline():
    from src.tools import ToolRegistry

    assert "ما قدرت" in await ToolRegistry().call("quota_safety", "")


# --------------------------------------------------------------------------- routing


def test_phase_b_tools_registered_in_valid_tools():
    for tool in (
        "drive",
        "contacts",
        "create_event",
        "create_task",
        "places",
        "deep_search",
        "fitness",
        "cloud_backup",
        "analytics",
        "quota_safety",
    ):
        assert tool in _VALID_TOOLS, tool


def test_keyword_net_routes_drive():
    tool, arg = _keyword_net("ابحثي بالدرايف عن تقارير")
    assert tool == "drive" and "تقارير" in arg


def test_keyword_net_routes_contacts():
    tool, _ = _keyword_net("مين هو أحمد بمعلوماتي")
    assert tool == "contacts"


def test_keyword_net_routes_create_event():
    tool, _ = _keyword_net("سجلي بالتقويم موعد اجتماع بكرة")
    assert tool == "create_event"


def test_keyword_net_routes_create_task():
    tool, _ = _keyword_net("ضيفي مهمة لمهامي مراجعة العرض")
    assert tool == "create_task"


def test_keyword_net_routes_places():
    tool, _ = _keyword_net("وين في كافيه بعمان")
    assert tool == "places"


def test_keyword_net_routes_deep_search():
    tool, _ = _keyword_net("ابحثي بجوجل عن أسعار الرام")
    assert tool == "deep_search"


def test_keyword_net_routes_fitness():
    tool, _ = _keyword_net("كم مشيت اليوم")
    assert tool == "fitness"


def test_keyword_net_routes_backup():
    tool, _ = _keyword_net("احفظي نسخة احتياطية بالسحابة")
    assert tool == "cloud_backup"


def test_keyword_net_routes_analytics():
    tool, _ = _keyword_net("تحليل استخدام جهازي")
    assert tool == "analytics"


def test_keyword_net_routes_quota():
    tool, _ = _keyword_net("شو حصة غوغل")
    assert tool == "quota_safety"


# --------------------------------------------------------------------------- skill guides


def test_phase_b_guides_present():
    from src.skills.sara_tool_skills import build_skill_guides

    guides = {n.removesuffix(".md") for n in build_skill_guides()}
    for tool in (
        "drive",
        "contacts",
        "create_event",
        "create_task",
        "places",
        "deep_search",
        "fitness",
        "cloud_backup",
        "analytics",
        "quota_safety",
    ):
        assert tool in guides, tool
