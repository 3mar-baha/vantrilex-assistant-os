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
