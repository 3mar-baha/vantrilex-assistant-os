"""Tier 1 — open_path tool contracts (Step 10).

The orphaned exec.open tunnel verb gets a core caller: file-noun phrasing
routes here (BEFORE launch), the registry sends the typed envelope, and the
daemon's own shape walls (no UNC/traversal/executables) stay authoritative.
"""


class _FakeBridge:
    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc
        self.sent = []

    async def send_cmd(self, cmd, args, **kw):
        self.sent.append((cmd, args))
        if self.exc is not None:
            raise self.exc
        return self.payload


def _registry(bridge):
    from src.tools import ToolRegistry

    return ToolRegistry(bridge=bridge)


def test_net_routes_file_open_before_launch():
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net("افتحي ملف الميزانية")
    assert tool == "open_path" and "الميزانية" in arg
    tool, _ = _keyword_net("افتحي مجلد الصور")
    assert tool == "open_path"
    # launch owners untouched
    assert _keyword_net("افتحي المفكرة عندي")[0] == "launch"
    assert _keyword_net("افتحي كروم")[0] == "launch"
    assert _keyword_net("ابعثيلي ملف الميزانية")[0] == "file_fetch"


def test_dispatcher_names_and_allows_open_path():
    from src.dispatcher import _ROUTER_PROMPT_AR, _VALID_TOOLS

    assert "open_path" in _VALID_TOOLS
    assert "open_path" in _ROUTER_PROMPT_AR


async def test_handler_sends_typed_envelope():
    bridge = _FakeBridge({"status": "ok", "detail": "opened", "audit_code": "PC-1"})
    out = await _registry(bridge).call("open_path", "تقرير.pdf")
    assert bridge.sent == [("exec.open", {"path": "تقرير.pdf"})]
    assert out


async def test_handler_offline_and_error_honest():
    from src.bridge_server import BridgeOffline

    out = await _registry(None).call("open_path", "x.pdf")
    assert "الجسر" in out
    out = await _registry(_FakeBridge(exc=BridgeOffline("down"))).call("open_path", "x.pdf")
    assert "الجسر" in out
    out = await _registry(_FakeBridge({"status": "error", "detail": "nope"})).call(
        "open_path", "x.pdf"
    )
    assert out


async def test_handler_empty_arg_asks():
    bridge = _FakeBridge({"status": "ok", "detail": "opened", "audit_code": "PC-1"})
    out = await _registry(bridge).call("open_path", "   ")
    assert bridge.sent == []
    assert out


def test_capability_registered_reversible():
    from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES

    cap = TOOL_CAPABILITIES["open_path"]
    assert cap["reversible"] is True and cap["needs"] == "bridge"
    assert "open_path" not in IRREVERSIBLE_TOOLS


def test_audit_matrix_and_guide_cover_open_path():
    from src.skills.sara_tool_skills import _SKILLS
    from tests.suite.tier3_shadow_tracer.audit_harness import PROMPTS

    assert PROMPTS["open_path"]
    content = dict(_SKILLS)["open_path.md"]
    assert content.startswith("# ") and "open_path" in content
    assert "## الاستخدام" in content and "## الفشل الصادق" in content
