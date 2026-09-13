"""Tier 1 — skill-standard contracts: capabilities registry + SKILL.md shape.

Guards the Phase-4 rollout: every deduction tool has a first-class capability
(goals/markers/reversibility/backend needs/chains), and every shipped
SKILL.md file carries frontmatter + all six standard sections.
"""

from pathlib import Path

SKILLS_DIR = Path(__file__).parents[3] / "src" / "skills"
REQUIRED_SECTIONS = (
    "## Governing philosophy",
    "## Situational triggers",
    "## Execution workflow",
    "## Edge-case recovery",
    "## Safety boundaries",
)
REQUIRED_FRONTMATTER = ("name:", "version:", "owner:", "safety_class:", "needs:")


def test_capabilities_cover_deduction_tools():
    from src import cognition
    from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES

    missing = [t for t in cognition._TOOL_GOALS if t not in TOOL_CAPABILITIES]
    assert not missing, f"tools without capabilities: {missing}"
    for tool, cap in TOOL_CAPABILITIES.items():
        assert cap.get("goals"), tool
        assert cap.get("markers"), tool
        assert cap.get("needs") in ("bridge", "google", "network", "vault", "local", "none"), tool
        assert isinstance(cap.get("reversible"), bool), tool
        assert isinstance(cap.get("chains_with"), tuple), tool
    assert {"close", "cancel_reminder", "create_event", "create_task"} <= set(IRREVERSIBLE_TOOLS)


def test_skill_files_match_standard():
    files = sorted(SKILLS_DIR.glob("*.SKILL.md"))
    assert files, "no SKILL.md exemplar shipped"
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), path.name
        front = text.split("---\n")[1]
        for key in REQUIRED_FRONTMATTER:
            assert key in front, f"{path.name} frontmatter missing {key}"
        for section in REQUIRED_SECTIONS:
            assert section in text, f"{path.name} missing {section}"
        assert len(text) > 800, f"{path.name} is a stub, not an exhaustive skill"


def test_sara_tool_guides_cover_capabilities():
    """Every first-class capability ships a per-tool guide (superset allowed —
    cloud/Phase-B zones carry guides beyond the deduction set)."""
    from src.skills.capabilities import TOOL_CAPABILITIES
    from src.skills.sara_tool_skills import _SKILLS

    shipped = {name.removesuffix(".md") for name, _ in _SKILLS}
    missing = [t for t in TOOL_CAPABILITIES if t not in shipped]
    assert not missing, f"capabilities without guides: {missing}"


def test_sara_tool_guide_shape():
    """House shape: tool header + usage + honest-failure line (no stubs)."""
    from src.skills.sara_tool_skills import _SKILLS

    for name, content in _SKILLS:
        tool = name.removesuffix(".md")
        assert content.startswith("# "), f"{name} missing header"
        assert tool in content, f"{name} header does not name its tool"
        assert "## الاستخدام" in content, f"{name} missing usage section"
        assert "## الفشل الصادق" in content, f"{name} missing honest-failure line"


def test_vault_guides_exhaustive():
    """2026-09-13 mandate: the vault skill carries the full scaffolding doctrine
    (dynamic nesting, IA roles, frontmatter schema, idempotency) — not stubs."""
    from src.skills.sara_tool_skills import _SKILLS

    guides = dict(_SKILLS)
    for name in ("create_folder.md", "knowledge_graph.md"):
        content = guides[name]
        assert len(content) >= 1500, f"{name} too thin ({len(content)} chars)"
    folder = guides["create_folder.md"]
    for anchor in (
        "date",
        "tags",
        "type",
        "summary",
        "02_Areas",
        "03_Projects",
        "State/",
        "00_Inbox",
    ):
        assert anchor in folder, f"create_folder.md missing {anchor}"
    assert "موجود" in folder, "create_folder.md must state the exists-check (idempotency)"
