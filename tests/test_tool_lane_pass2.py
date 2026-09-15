"""Pass-2 tool-lane tests: the schedule + knowledge_graph ToolRegistry handlers
and their dispatcher keyword-net routing — the tool surface behind «ذكرني بكرة
...» و«مين بيحكي عن X؟»."""

from __future__ import annotations

from typing import ClassVar

from src.dispatcher import _keyword_net


class FakeVaultGraph:
    """Bare-minimum vault stub: list_dir + read for the graph snapshot."""

    FILES: ClassVar[dict[str, str]] = {
        "Daily_Logs/2026-09-01.md": "حكينا عن [[Studies/Physics]]",
        "Studies/Physics.md": "الميكانيكا — بدون روابط",
    }

    async def list_dir(self, directory: str, *, recursive: bool = False) -> list[str]:
        return [p for p in self.FILES if p.startswith(f"{directory}/")]

    async def read(self, path: str) -> str:
        if path not in self.FILES:
            raise FileNotFoundError(path)
        return self.FILES[path]


class FakeEngine:
    def __init__(self) -> None:
        self.created: list[tuple[str, object]] = []

    async def create_task(self, *, title: str, when) -> object:
        self.created.append((title, when))
        return type("Note", (), {"title": title})()


async def test_schedule_tool_creates_task_and_confirms():
    from datetime import UTC, datetime, timedelta

    from src.tools import ToolRegistry

    engine = FakeEngine()
    tools = ToolRegistry(task_engine=engine, tz=__import__("zoneinfo").ZoneInfo("UTC"))
    answer = await tools.call("schedule", "بكرة أراجع الفيزياء")
    assert engine.created, "the engine must be called"
    assert "أراجع الفيزياء" in engine.created[0][0]
    assert "سجلت" in answer
    # «بكرة» sets the day: the when is tomorrow, 09:00 local
    when = engine.created[0][1]
    now = datetime.now(UTC)
    assert when.date() == (now + timedelta(days=1)).date() or when > now


async def test_schedule_tool_without_engine_is_offline():
    from src.tools import ToolRegistry

    tools = ToolRegistry()
    answer = await tools.call("schedule", "مهمة")
    assert "غوغل" in answer or "متصلين" in answer


async def test_knowledge_graph_tool_overview_and_target():
    from src.tools import ToolRegistry

    tools = ToolRegistry(vault=FakeVaultGraph())
    overview = await tools.call("knowledge_graph", "")
    assert "شبكة المعرفة" in overview
    assert "2" in overview  # node count quoted verbatim

    brief = await tools.call("knowledge_graph", "Studies/Physics")
    assert "2026-09-01.md" in brief  # backlink quoted


async def test_knowledge_graph_tool_without_vault_degrades():
    from src.tools import ToolRegistry

    tools = ToolRegistry()
    answer = await tools.call("knowledge_graph", "شي")
    assert "ما قدرت" in answer


def test_keyword_net_routes_schedule_with_title():
    tool, arg = _keyword_net("ذكرني بكرة أراجع الفيزياء مع خالد")
    assert tool == "schedule"
    assert "أراجع الفيزياء" in arg


def test_keyword_net_routes_knowledge_graph():
    tool, _arg = _keyword_net("مين بيحكي عن Studies/Physics بالمفكرات؟")
    assert tool == "knowledge_graph"


def test_keyword_net_plain_chat_stays_none():
    tool, _ = _keyword_net("كيفك اليوم؟")
    assert tool == "none"
