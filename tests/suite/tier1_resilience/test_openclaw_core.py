"""Tier 1 — OpenClaw Phase-2 core seams. Hermetic.

Single-Brain policy: plans are built HERE (core); the PC only resolves and
executes. Tests cover intent definitions (compile + match, no collisions
with live routing — the dispatcher stays untouched until Phase 3), the DAG
builder + confirmation gate, registry handlers against a fake tunnel, and
the capability/audit/guide parity the sacred-floor tests enforce.
"""

import json
import re

from src.openclaw import intents, plans
from src.openclaw.protocol import ActionDAG, Op, OpKind
from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES


def test_valid_tools_are_the_four():
    assert set(intents.VALID_OPENCLAW_TOOLS) == {
        "openclaw_browse",
        "openclaw_desktop",
        "openclaw_fetch",
        "openclaw_inspect",
    }


def test_patterns_compile_and_match_their_samples():
    for tool, pattern, samples in intents.INTENT_PATTERNS:
        compiled = re.compile(pattern)
        assert samples, tool
        for sample in samples:
            assert compiled.search(sample), f"{tool} misses {sample!r}"


def test_patterns_do_not_steal_existing_tools_samples():
    """Collision guard for the Phase-3 insertion review: OpenClaw patterns
    must not swallow canonical samples of live tools."""
    existing = {
        "screenshot": "ارسلي لقطة الشاشة",
        "close": "سكري الآلة الحاسبة",
        "launch": "افتحي المفكرة عندي",
        "read_page": "لخصيلي محتوى هالصفحة https://example.com",
        "volume": "وطّي الصوت شوي",
    }
    for tool, pattern, _samples in intents.INTENT_PATTERNS:
        compiled = re.compile(pattern)
        for owner, sample in existing.items():
            assert not compiled.search(sample), f"{tool} steals {owner} sample {sample!r}"


def test_dispatcher_wiring_names_and_allows():
    """Phase-2 dispatcher seam: verdicts may name the tools and the prompt
    catalogs them (keyword-net entries wait for the Phase-3 review)."""
    from src.dispatcher import _ROUTER_PROMPT_AR, _VALID_TOOLS

    for tool in intents.VALID_OPENCLAW_TOOLS:
        assert tool in _VALID_TOOLS, tool
        assert tool in _ROUTER_PROMPT_AR, tool


def test_net_patterns_match_intents_single_source():
    """The live net IS the intents table: fetch inlined mid-net + the rest
    appended from INTENT_PATTERNS. Any edit in one place fails here until
    the other follows."""
    from src.dispatcher import _TOOL_NET

    by_tool = {}
    for tool, pattern in _TOOL_NET:
        by_tool.setdefault(tool, []).append(pattern.pattern)
    for tool, pattern, _samples in intents.INTENT_PATTERNS:
        assert tool in by_tool, f"{tool} missing from the live net"
        assert pattern in by_tool[tool], f"{tool} net regex drifted from intents.py"


def test_net_routes_openclaw_samples():
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net("حرّكي الماوس على زر الإرسال")
    assert tool == "openclaw_browse" and arg
    tool, arg = _keyword_net("اكتبي بالنافذة التقرير النهائي")
    assert tool == "openclaw_desktop" and arg
    tool, arg = _keyword_net("اجلبي محتوى الصفحة https://example.com/x")
    assert tool == "openclaw_fetch" and arg == "https://example.com/x"
    tool, arg = _keyword_net("افحصي عناصر النافذة")
    assert tool == "openclaw_inspect"


def test_net_existing_owners_keep_priority():
    """Zero colloquial hijacking: every pre-Phase-3 owner's canonical
    sample still resolves to its owner after the OpenClaw insertion."""
    from src.dispatcher import _keyword_net

    cases = {
        "ارسلي لقطة الشاشة": "screenshot",
        "سكري الآلة الحاسبة": "close",
        "افتحي المفكرة عندي": "launch",
        "لخصيلي محتوى هالصفحة https://example.com": "read_page",
        "https://adamlankamer.com/ai": "read_page",
        "وطّي الصوت شوي": "volume",
        "استخرجي الكود من الشاشة": "screen_ocr",
    }
    for text, expected in cases.items():
        assert _keyword_net(text)[0] == expected, text


def test_build_dag_stamps_plan_and_weight():
    dag = plans.build_dag(
        goal="افتحي المفكرة",
        ops=[Op(op=OpKind.HOTKEY, value="Win+R")],
        weight=2,
    )
    assert isinstance(dag, ActionDAG)
    assert dag.goal == "افتحي المفكرة" and dag.weight == 2
    assert dag.plan_id.startswith("oc-")


def test_needs_confirmation_flags_only_commit_dags():
    reversible = plans.build_dag(goal="x", ops=[Op(op=OpKind.SCREENSHOT)], weight=1)
    committing = plans.build_dag(goal="y", ops=[Op(op=OpKind.HOTKEY, value="Alt+F4")], weight=2)
    assert plans.needs_confirmation(reversible) is False
    assert plans.needs_confirmation(committing) is True
    assert plans.irreversible_ops(committing) == [committing.ops[0]]


class _Coordinator:
    def __init__(self, confirmed):
        self._confirmed = confirmed

    def has_confirmation(self, tool, arg):
        return (tool, arg) in self._confirmed


def test_gate_parks_commit_without_confirmation():
    dag = plans.build_dag(goal="y", ops=[Op(op=OpKind.HOTKEY, value="Alt+F4")], weight=2)
    assert plans.gate(dag, coordinator=None) == "park"
    assert plans.gate(dag, coordinator=_Coordinator(set())) == "park"


def test_gate_goes_when_clear_or_confirmed():
    clean = plans.build_dag(goal="x", ops=[Op(op=OpKind.SCREENSHOT)], weight=1)
    assert plans.gate(clean, coordinator=None) == "go"
    dag = plans.build_dag(goal="y", ops=[Op(op=OpKind.HOTKEY, value="Alt+F4")], weight=2)
    assert plans.gate(dag, coordinator=_Coordinator({("openclaw", "y")})) == "go"


class _FakeBridge:
    def __init__(self, payload):
        self.payload = payload
        self.sent = []

    async def send_cmd(self, cmd, args, **kw):
        self.sent.append((cmd, args))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _registry(bridge):
    from src.tools import ToolRegistry

    return ToolRegistry(bridge=bridge)


def test_dependency_isolation_wall():
    """No Container Bloat: PC-only wheels live strictly in
    requirements-bridge.txt — the Oracle container installs
    requirements.txt alone (Dockerfile) and must never see them."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    lines = (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
    core = "\n".join(line for line in lines if not line.strip().startswith("#"))
    bridge = (root / "requirements-bridge.txt").read_text(encoding="utf-8")
    for wheel in ("playwright", "scrapling"):
        assert wheel in bridge, f"{wheel} missing from requirements-bridge.txt"
        assert wheel not in core.casefold(), f"{wheel} leaked into requirements.txt"
    # UIA backend: pywinauto OR uiautomation (mission allows either)
    assert "pywinauto" in bridge or "uiautomation" in bridge
    for wheel in ("pywinauto", "uiautomation"):
        assert wheel not in core.casefold(), f"{wheel} leaked into requirements.txt"
    docker = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "requirements-bridge" not in docker


async def test_fetch_handler_returns_transcript_text():
    reg = _registry(_FakeBridge({"status": "ok", "detail": "# title\n\nbody text"}))
    out = await reg.call("openclaw_fetch", "https://example.com/x")
    assert "body text" in out


async def test_handlers_degrade_honestly_offline():
    from src.bridge_server import BridgeOffline

    offline_args = {
        "openclaw_browse": "https://example.com/x",  # URL path needs the tunnel
        "openclaw_desktop": "whatever",
        "openclaw_fetch": "https://example.com/x",
        "openclaw_inspect": "whatever",
    }
    reg = _registry(None)
    for tool in intents.VALID_OPENCLAW_TOOLS:
        out = await reg.call(tool, offline_args[tool])
        assert "الجسر" in out, tool
    reg = _registry(_FakeBridge(BridgeOffline("down")))
    for tool in intents.VALID_OPENCLAW_TOOLS:
        out = await reg.call(tool, offline_args[tool])
        assert "الجسر" in out, tool


async def test_handlers_surface_daemon_errors_honestly():
    reg = _registry(_FakeBridge({"status": "error", "detail": "not configured (Phase 3)"}))
    out = await reg.call("openclaw_inspect", "")
    assert "not configured" in out


async def test_act_handler_sends_typed_envelope():
    """Phase-2 desktop semantics: a safe read-only probe op rides
    openclaw.act (the breaker + transcript path gets exercised end to end;
    real DAGs arrive in Phase 3 via plans.build_dag)."""
    reg = _registry(_FakeBridge({"status": "ok", "detail": json.dumps({"ok": True})}))
    bridge = reg._bridge
    await reg.call("openclaw_desktop", "whatever")
    assert bridge.sent and bridge.sent[0][0] == "openclaw.act"
    probe = bridge.sent[0][1]["op"]
    assert Op.model_validate(probe).op == OpKind.SCREENSHOT


async def test_browse_url_uses_fetch_verb():
    reg = _registry(_FakeBridge({"status": "ok", "detail": "page text"}))
    bridge = reg._bridge
    out = await reg.call("openclaw_browse", "https://example.com/x")
    assert "page text" in out
    assert bridge.sent[0][0] == "openclaw.fetch"


async def test_browse_without_url_is_honest_no_tunnel_call():
    reg = _registry(_FakeBridge({"status": "ok", "detail": "unreached"}))
    bridge = reg._bridge
    out = await reg.call("openclaw_browse", "دوري على أسعار الذهب")
    assert bridge.sent == []  # interactive browsing is Phase 3 — no fake execution
    assert "المرحلة" in out or "Phase 3" in out


def test_capabilities_registered_with_reversibility():
    for tool in intents.VALID_OPENCLAW_TOOLS:
        cap = TOOL_CAPABILITIES[tool]
        assert cap["goals"] and cap["markers"] and cap["needs"] == "bridge"
        assert isinstance(cap["reversible"], bool)
        assert isinstance(cap["chains_with"], tuple)
    assert {"openclaw_browse", "openclaw_desktop"} <= set(IRREVERSIBLE_TOOLS)
    assert "openclaw_fetch" not in IRREVERSIBLE_TOOLS
    assert "openclaw_inspect" not in IRREVERSIBLE_TOOLS


def test_audit_matrix_covers_new_tools():
    from tests.suite.tier3_shadow_tracer.audit_harness import PROMPTS

    for tool in intents.VALID_OPENCLAW_TOOLS:
        assert PROMPTS[tool], tool


def test_guides_cover_new_tools():
    from src.skills.sara_tool_skills import _SKILLS

    guides = dict(_SKILLS)
    for tool in intents.VALID_OPENCLAW_TOOLS:
        content = guides[f"{tool}.md"]
        assert content.startswith("# ") and tool in content
        assert "## الاستخدام" in content and "## الفشل الصادق" in content
