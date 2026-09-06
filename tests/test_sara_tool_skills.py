"""M6 (owner's mediating-layer design, 2026-09-05): PER-TOOL SKILL GUIDES —
the layer BETWEEN the tool and its narration.

The owner's architecture: a request routes to a tool; the tool executes;
and the tool's OWN skill guide then rides the narration envelope so Sara's
brain knows — for THAT tool — the best usage, the output shape, the
benefit, and the honest failure lines. The guide is a MEDIATOR, not a
question surface: the owner never asks for skills; every tool turn carries
its guide automatically (progressive disclosure, skill-creator style).

Contract:
- Each guide: pushy trigger phrasings, usage, benefit, example, failure
  lines — synced into the LIVE vault under 02_Areas/Profile/Sara_Skills/.
- _tool_skill_note: a tool turn with a bound vault rides the guide in the
  system prompt (DATA, bounded); NO vault/NO guide -> today's plain
  narration (identical behavior — the layer is an enhancement, never a
  dependency).
- The capabilities manifest names the skills layer (the brain knows it).
"""

from __future__ import annotations

import json


class _Vault:
    def __init__(self, files: dict[str, str] | None = None):
        self.files = dict(files or {})
        self.upserts: list[str] = []

    async def read(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def upsert(self, path: str, content: str, *, message: str = "", merge=None) -> None:
        self.upserts.append(path)
        self.files[path] = content


def test_every_guide_carries_the_skill_creator_shape():
    """Each guide: the pushy trigger block, the usage, the benefit, and the
    failure/example contract — the four sections that make the narration
    use the tool in its best way."""
    from src.skills.sara_tool_skills import build_skill_guides

    guides = build_skill_guides()
    assert len(guides) >= 20, "every meaningful tool zone carries a guide"
    for name, content in guides.items():
        assert "متى" in content, f"{name}: no trigger block"
        assert "## الاستخدام" in content, f"{name}: no usage"
        assert "الفائدة" in content, f"{name}: no benefit"
        assert "الصادق" in content or "مثال" in content, f"{name}: no failure/example"


def test_guides_cover_the_real_tool_surface():
    """The guide filenames mirror the REAL ToolRegistry zones — no invented
    tools, none of the daily surface missing."""
    from src.dispatcher import _VALID_TOOLS
    from src.skills.sara_tool_skills import build_skill_guides

    guides = {name.removesuffix(".md") for name in build_skill_guides()}
    must_have = {
        "launch",
        "close",
        "telemetry",
        "screenshot",
        "running_apps",
        "whitelist_apps",
        "schedule",
        "list_reminders",
        "cancel_reminder",
        "gmail",
        "calendar",
        "weather",
        "web_search",
        "youtube",
        "read_page",
        "prayer_times",
        "convert_currency",
        "crypto_price",
        "tech_trending",
        "network_status",
        "volume",
        "media",
        "screen_ocr",
        "file_fetch",
        "create_folder",
        "knowledge_graph",
        "multi_task",
        # skill-creator application pass (2026-09-06): the daily-surface zones
        # that had no guide yet — the usage-report and the morning brief.
        "app_sessions",
        "brief",
    }
    missing = must_have - guides
    assert not missing, f"missing guides: {missing}"
    for guide_name in guides:
        assert guide_name in set(_VALID_TOOLS), guide_name


async def test_guides_sync_to_the_live_vault():
    """Boot sync: every guide lands under 02_Areas/Profile/Sara_Skills/."""
    from src.skills.sara_tool_skills import SARA_SKILLS_DIR, build_skill_guides, sync_skill_guides

    vault = _Vault()
    written = await sync_skill_guides(vault)
    assert written == len(build_skill_guides())
    assert all(path.startswith(SARA_SKILLS_DIR) for path in vault.upserts)
    assert "افتحي" in vault.files[f"{SARA_SKILLS_DIR}/launch.md"]


# -- the mediating layer: _tool_skill_note ---------------------------------------


async def _dispatcher_with_vault(vault, verdict_tool: str, deltas=("تمام",)):
    """A FrontDoorDispatcher wired to a scripted gateway + the vault."""
    from src.dispatcher import FrontDoorDispatcher

    verdict = json.dumps(
        {"route": "tier2", "tool": verdict_tool, "arg": "", "ack": "ثواني", "voice_reply": False},
        ensure_ascii=False,
    )

    class _Gateway:
        def __init__(self):
            self.systems: list[str | None] = []

        async def chat(self, messages, *, tier, **kw):
            return verdict

        async def stream_chat(self, messages, *, tier, **kw):
            self.systems.append(
                messages[0]["content"] if messages and messages[0]["role"] == "system" else None
            )
            for d in deltas:
                yield d

    class _Tools:
        async def call(self, tool, arg=""):
            return "المعالج 23% والرام 5.2 من 16 جيجا"

    gw = _Gateway()
    dp = FrontDoorDispatcher(gw, settings=None)
    dp.set_skill_vault(vault)
    return dp, gw, _Tools()


async def test_tool_turn_carries_its_own_guide():
    """THE mediating contract: a telemetry turn with a bound vault rides the
    TELEMETRY guide in the system prompt — the brain narrates THAT tool in
    its best way (usage shape, benefit, failure lines)."""
    from src.skills.sara_tool_skills import SARA_SKILLS_DIR

    vault = _Vault()
    vault.files[f"{SARA_SKILLS_DIR}/telemetry.md"] = (
        "---\nname: telemetry\n---\n\n# مهارة حالة الجهاز\n\n## الاستخدام\nالأرقام الحقيقية تنسخ كما هي.\n"
    )
    dp, gw, tools = await _dispatcher_with_vault(vault, "telemetry")
    out = []
    async for delta in dp.handle("شو وضع الجهاز", tools=tools):
        out.append(delta)
    assert any("تمام" in d for d in out)  # the narration happened
    system_used = gw.systems[0]
    assert system_used and "مهارة حالة الجهاز" in system_used  # the guide rode it
    assert "بيانات مرجعية للاستخدام الأمثل" in system_used  # as DATA
    assert "الأرقام الحقيقية" in system_used  # the guide's body, not frontmatter


async def test_no_vault_is_today_plain_narration():
    """The layer never degrades: no vault -> the narration still happens with
    the plain system prompt (identical to today's behavior)."""

    dp, gw, tools = await _dispatcher_with_vault(None, "telemetry")
    out = []
    async for delta in dp.handle("شو وضع الجهاز", tools=tools):
        out.append(delta)
    assert any("تمام" in d for d in out)
    system_used = gw.systems[0]
    assert "مهارة حالة الجهاز" not in (system_used or "")


async def test_unknown_tool_guide_skipped():
    """A tool with no guide (e.g. tasks) narrates plainly — no invented
    guide, no crash."""
    dp, _gw, tools = await _dispatcher_with_vault(_Vault(), "tasks")
    out = []
    async for delta in dp.handle("مهامي", tools=tools):
        out.append(delta)
    assert any("تمام" in d for d in out)


def test_manifest_mentions_the_skills_layer():
    """The capabilities manifest (the always-loaded level) names the skills
    layer so the brain knows the deeper guides exist on every tool turn."""
    from src.memory import build_capabilities_manifest

    manifest = build_capabilities_manifest()
    assert "Sara_Skills" in manifest
