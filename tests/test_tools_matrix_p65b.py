"""P6 coverage, tools part B (master transformation plan, Phase P6).

Rich-backend legs for externals, cloud, vault-graph, scheduling, reminders,
web/media, and close handlers. Doubles sit at system boundaries; assertions
target user-visible Arabic outcomes.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from src.tools import TOOL_FAIL_AR, ToolRegistry

TZ = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def _aio(coro):
    import asyncio

    return asyncio.run(coro)


class FakeExternals:
    def __init__(self, error=None):
        self.error = error

    async def get_prayer_times(self):
        if self.error:
            raise self.error
        return {
            "Fajr": "05:10",
            "Dhuhr": "12:30",
            "Asr": "15:45",
            "Maghrib": "18:20",
            "Isha": "19:40",
        }

    async def convert_currency(self, amount, from_curr, to_curr):
        if self.error:
            raise self.error
        return {"total": amount * 0.71, "rate": 0.71}

    async def get_crypto_price(self, coin, fiat):
        if self.error:
            raise self.error
        return {coin: {"jod": 45000.0}}

    async def get_tech_trending(self, limit=5):
        if self.error:
            raise self.error
        return [{"title": f"Story {i}", "url": f"https://x/{i}"} for i in range(5)]

    async def check_network_status(self):
        if self.error:
            raise self.error
        return {"ip": "1.2.3.4", "isp": "Zain", "city": "Amman", "proxy": False}

    async def read_webpage_clean(self, url):
        if self.error:
            raise self.error
        return "مقال طويل " * 500


class FakeCloud:
    def __init__(self, error=None, empty=False):
        self.error = error
        self.empty = empty

    async def places(self, query):
        if self.error:
            raise self.error
        return [] if self.empty else [{"name": "مقهى", "address": "عمان", "rating": 4.5}]

    async def deep_search(self, query):
        if self.error:
            raise self.error
        return {} if self.empty else {"items": [{"title": "T", "link": "https://x"}]}

    async def fitness(self):
        if self.error:
            raise self.error
        return {} if self.empty else {"steps": 8000, "active_minutes": 40, "calories": 300}

    async def cloud_backup(self, snapshot):
        if self.error:
            raise self.error
        return True

    async def analytics(self, arg):
        if self.error:
            raise self.error
        return {} if self.empty else {"rows": [["screen", 120]]}

    async def quota_report(self):
        if self.error:
            raise self.error
        return (
            {}
            if self.empty
            else {"services": [{"name": "gmail", "pct": 12}, {"name": "maps", "pct": 95}]}
        )


class FakeVaultGraph:
    def __init__(self, notes=None, error=None):
        self.notes = notes or {}
        self.error = error
        self.upserts = []

    async def list_dir(self, directory, recursive=False):
        if self.error:
            raise self.error
        return [p for p in self.notes if p.startswith(directory)]

    async def read(self, path):
        if self.error:
            raise self.error
        return self.notes[path]

    async def upsert(self, path, text, message=""):
        self.upserts.append(path)
        self.notes[path] = text


class FakeTasksEngine:
    async def create_task(self, title, when):
        from types import SimpleNamespace

        return SimpleNamespace(title=title)


class FakeWeb:
    def __init__(self, text="نتايج", error=None):
        self.text = text
        self.error = error

    async def search_block(self, query):
        if self.error:
            raise self.error
        return self.text


class FakeWeather:
    def __init__(self, block="مشمس 25", unknown=False):
        self.block = block
        self.unknown = unknown

    async def current(self, place):
        return self.block

    def is_unknown_place(self, place):
        return self.unknown


class FakeYoutube:
    def __init__(self, results=None, error=None):
        self.results = results
        self.error = error

    async def search(self, query):
        if self.error:
            raise self.error
        return self.results


class FakeOrchestrator:
    def __init__(self, error=None):
        self.error = error
        self.scheduled = []
        self.rows = ["job-1 — 07:30 — دواء"]
        self.cancelled = []

    async def schedule_delay(self, text, delay, title):
        self.scheduled.append(("delay", title))

    async def schedule_wallclock(self, text, when, title):
        self.scheduled.append(("wallclock", title))

    def list_for_owner(self):
        if self.error:
            raise self.error
        return self.rows

    async def cancel_all(self):
        if self.error:
            raise self.error
        return 2

    async def cancel(self, job_id):
        if self.error:
            raise self.error
        self.cancelled.append(job_id)
        return job_id == "job-1"

    def find_by_time(self, text):
        if self.error:
            raise self.error
        return "job-1" if "7:10" in text else None


class FakeCoordinator:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def request_close(self, name, *, origin):
        self.calls.append(name)
        if self.error is not None:
            raise self.error


class FakeDocSender:
    def __init__(self, error=None):
        self.error = error
        self.sent = []

    async def __call__(self, data, name):
        if self.error is not None:
            raise self.error
        self.sent.append((name, data))


class FakeAgentManager:
    def __init__(self, error=None):
        self.error = error

    async def run(self, arg):
        if self.error is not None:
            raise self.error
        return "multi done"


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_externals_rich_and_dead():
    reg = ToolRegistry(externals=FakeExternals())
    assert "الفجر" in _run(reg.call("prayer_times", ""))
    assert "JOD" in _run(reg.call("convert_currency", "حولي 100 دولار"))
    assert "دينار" in _run(reg.call("crypto_price", "شو سعر البيتكوين"))
    assert "Story 1" in _run(reg.call("tech_trending", ""))
    assert "1.2.3.4" in _run(reg.call("network_status", ""))
    assert "example.com/x" in _run(reg.call("read_page", "https://example.com/x"))
    dead = ToolRegistry(externals=FakeExternals(error=RuntimeError("down")))
    assert "ما قدرت" in _run(dead.call("prayer_times", ""))
    assert "ما قدرت" in _run(dead.call("convert_currency", "x"))
    assert "ما قدرت" in _run(dead.call("crypto_price", "x"))
    assert "ما قدرت" in _run(dead.call("tech_trending", ""))
    assert "ما قدرت" in _run(dead.call("network_status", ""))
    assert "ما قدرت" in _run(dead.call("read_page", "https://x"))


def test_read_page_bad_url():
    reg = ToolRegistry(externals=FakeExternals())
    assert "https://" in _run(reg.call("read_page", "notaurl"))


def test_read_page_truncates_long():
    reg = ToolRegistry(externals=FakeExternals())
    out = _run(reg.call("read_page", "https://example.com/x"))
    assert out.endswith("…") and len(out) < 1400


def test_convert_defaults_and_arabic_digits():
    reg = ToolRegistry(externals=FakeExternals())
    assert "EUR" in _run(reg.call("convert_currency", "حولي ٥٠ يورو"))
    assert "EUR" in _run(reg.call("convert_currency", "حولي ٥٠ يورو"))


def test_crypto_unknown_and_missing_price():
    class _Priced(FakeExternals):
        async def get_crypto_price(self, coin, fiat):
            return {"bitcoin": {"jod": 45000.0}}

    reg = ToolRegistry(externals=_Priced())
    assert "البيتكوين" in _run(reg.call("crypto_price", "شو سعر الدوجكوين"))
    assert "45,000" in _run(reg.call("crypto_price", "شو سعر البيتكوين"))


def test_tech_empty_and_network_proxy():
    class _Empty(FakeExternals):
        async def get_tech_trending(self, limit=5):
            return []

    assert "ما قدرت" in _run(ToolRegistry(externals=_Empty()).call("tech_trending", ""))

    class _Proxy(FakeExternals):
        async def check_network_status(self):
            return {"ip": "9.9.9.9", "isp": "X", "city": "Y", "proxy": True}

    assert "بروكسي" in _run(ToolRegistry(externals=_Proxy()).call("network_status", ""))


def test_knowledge_graph_variants():
    notes = {
        "Studies/a.md": "---\ntitle: A\n---\nbody one",
        "Studies/b.md": "---\ntitle: B\n---\nbody two",
    }
    reg = ToolRegistry(vault=FakeVaultGraph(notes))
    out = _run(reg.call("knowledge_graph", ""))
    assert "مفكرة" in out
    out2 = _run(reg.call("knowledge_graph", "Studies/a"))
    assert isinstance(out2, str) and out2
    reg_dead = ToolRegistry(vault=FakeVaultGraph(error=RuntimeError("down")))
    out3 = _run(reg_dead.call("knowledge_graph", ""))
    assert isinstance(out3, str) and out3


def test_schedule_lanes():
    reg = ToolRegistry(orchestrator=FakeOrchestrator(), tz=TZ, now_fn=lambda: NOW)
    assert _run(reg.call("schedule", "")) != "" and "المهمة" in _run(reg.call("schedule", ""))
    assert _run(reg.call("schedule", "بعد 60 ثانية ذكريني")) is None
    assert _run(reg.call("schedule", "على الساعة 3:47 مساء ذكريني")) is None
    assert "سجلت المهمة" in _run(
        ToolRegistry(task_engine=FakeTasksEngine(), tz=TZ, now_fn=lambda: NOW).call(
            "schedule", "بكرة راجعي"
        )
    )
    assert "غوغل" in _run(ToolRegistry(tz=TZ).call("schedule", "بكرة راجعي"))


def test_reminders_list_and_cancel():
    reg = ToolRegistry(orchestrator=FakeOrchestrator())
    assert "job-1" in _run(reg.call("list_reminders", ""))
    assert "ألغيت" in _run(reg.call("cancel_reminder", "الكل"))
    assert "ألغيت" in _run(reg.call("cancel_reminder", "job-1"))
    assert "ما لقيت" in _run(reg.call("cancel_reminder", "job-9"))
    assert "رقمه" in _run(reg.call("cancel_reminder", "   "))
    assert "job-1" in _run(reg.call("cancel_reminder", "7:10"))
    assert "ما في" in _run(ToolRegistry().call("list_reminders", ""))
    assert (
        _run(
            ToolRegistry(orchestrator=FakeOrchestrator(error=RuntimeError("x"))).call(
                "cancel_reminder", "job-1"
            )
        )
        == TOOL_FAIL_AR
    )


def test_create_folder_asks_without_names():
    reg = ToolRegistry(vault=FakeVaultGraph({}))
    assert "الفولدر" in _run(reg.call("create_folder", "   "))


def test_create_folder_ok_and_mirror_fail():
    reg = ToolRegistry(vault=FakeVaultGraph({}))
    out = _aio(reg.call("create_folder", "RoutineTasks"))
    assert "أنشأت فولدر" in out

    class _FailMirror(FakeVaultGraph):
        async def upsert(self, path, text, message=""):
            raise RuntimeError("mirror down")

    reg2 = ToolRegistry(vault=_FailMirror({}))
    assert "ما قدرت" in _run(reg2.call("create_folder", "RoutineTasks"))


def test_web_weather_youtube_variants():
    assert "نتايج" in _aio(ToolRegistry(web=FakeWeb()).call("web_search", "عمان"))
    assert "الموضوع" in _aio(ToolRegistry(web=FakeWeb()).call("web_search", "   "))
    assert "جربها" in _aio(
        ToolRegistry(web=FakeWeb(error=RuntimeError("x"))).call("web_search", "عمان")
    )
    assert "مشمس" in _aio(ToolRegistry(weather=FakeWeather("مشمس 25")).call("weather", "عمان"))
    assert "ما لقيت" in _aio(
        ToolRegistry(weather=FakeWeather(block=None, unknown=True)).call("weather", "خريبة")
    )
    results = [{"title": "T", "channel": "C", "url": "https://y"}]
    assert "يوتيوب" in _aio(ToolRegistry(youtube=FakeYoutube(results)).call("youtube", "فيزياء"))
    assert "الموضوع" in _aio(ToolRegistry(youtube=FakeYoutube(results)).call("youtube", "   "))
    assert "المفتاح" in _aio(ToolRegistry(youtube=FakeYoutube([])).call("youtube", "فيزياء"))
    assert "المفتاح" in _aio(
        ToolRegistry(youtube=FakeYoutube(error=RuntimeError("x"))).call("youtube", "فيزياء")
    )


def test_close_variants():
    assert "أسكّره" in _aio(ToolRegistry().call("close", "   "))
    assert "الجسر" in _aio(ToolRegistry().call("close", "calc"))
    coord = FakeCoordinator()
    out = _aio(ToolRegistry(coordinator=coord).call("close", "calc"))
    assert out is None and coord.calls == ["calc"]
    coord2 = FakeCoordinator(error=RuntimeError("tunnel down"))
    assert _aio(ToolRegistry(coordinator=coord2).call("close", "calc")) == TOOL_FAIL_AR


def test_file_fetch_sender_legs():
    from tests.test_tools_matrix_p65a import FakeBridge as _FB

    ok_bridge = _FB({"file.download": {"status": "ok", "detail": "aGVsbG8="}})
    sent = []

    async def _doc(data, name):
        sent.append((name, data))

    reg = ToolRegistry(bridge=ok_bridge, document_sender=_doc)
    assert _aio(reg.call("file_fetch", "خطة.pdf")) is None
    assert sent and sent[0][0] == "خطة.pdf"

    async def _dead(data, name):
        raise RuntimeError("send down")

    reg2 = ToolRegistry(bridge=ok_bridge, document_sender=_dead)
    assert "جرب بعد" in _aio(reg2.call("file_fetch", "خطة.pdf"))
    reg3 = ToolRegistry(bridge=ok_bridge)
    assert "جرب بعد" in _aio(reg3.call("file_fetch", "خطة.pdf"))


def test_file_fetch_roots_and_sensitive():
    from tests.test_tools_matrix_p65a import FakeBridge as _FB

    bridge = _FB(
        {
            "file.download": {"status": "ok", "detail": ""},
        }
    )
    reg = ToolRegistry(bridge=bridge)
    out = _aio(reg.call("file_fetch", "../x.txt"))
    assert isinstance(out, str) and out

    bridge2 = _FB({"file.download": {"status": "error", "detail": "outside_allowed_roots: nope"}})
    assert "المجلدات" in _aio(ToolRegistry(bridge=bridge2).call("file_fetch", "x.pdf"))

    bridge3 = _FB({"file.download": {"status": "error", "detail": "sensitive file type"}})
    assert "حساس" in _aio(ToolRegistry(bridge=bridge3).call("file_fetch", "x.pdf"))

    bridge4 = _FB({"file.download": {"status": "error", "detail": "weird"}})
    assert _aio(ToolRegistry(bridge=bridge4).call("file_fetch", "x.pdf")) == TOOL_FAIL_AR


def test_multi_task_agent_ok_and_fail():
    class _Manager:
        def __init__(self, error=None):
            self.error = error

        async def run(self, arg):
            if self.error is not None:
                raise self.error
            return "multi:" + arg

    reg = ToolRegistry()
    reg.bind_agent_manager(_Manager())
    assert "multi:" in _aio(reg.call("multi_task", "أ وب"))
    reg2 = ToolRegistry()
    reg2.bind_agent_manager(_Manager(error=RuntimeError("x")))
    assert "مدير المهام" in _aio(reg2.call("multi_task", "أ"))
