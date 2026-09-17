"""P3.1 fused rag_domains verdict + repair layer (master plan, Phase P3.1).

One FAST forward pass carries routing AND domain selection (+0ms, ~15 tokens).
Malformed model JSON (fences, trailing commas) is repaired non-throwing;
only total repair failure falls back to deduce/net — loudly.
"""

import json

import httpx

from src.dispatcher import (
    _ROUTER_PROMPT_AR,
    FrontDoorDispatcher,
    _parse_router,
    parse_rag_domains,
    repair_verdict,
)
from tests.test_dispatcher import _collect, _gateway
from tests.test_omniroute_gateway import _chunk, _Scripted, _sse


def _verdict_json(**over) -> str:
    base = {
        "route": "direct",
        "tool": "none",
        "arg": "",
        "ack": "من عيوني",
        "voice_reply": False,
        "rag_domains": ["dialect"],
    }
    base.update(over)
    return _chunk(json.dumps(base, ensure_ascii=False))


async def test_fused_verdict_parses_domains_single_call(make_settings):
    script = _Scripted(
        httpx.Response(200, content=_sse(_verdict_json())),
        httpx.Response(200, content=_sse(_chunk("الجواب"))),
    )
    async with _gateway(script) as client:
        front = FrontDoorDispatcher(client, make_settings())
        out = await _collect(front.handle("طلب عادي"))
    assert out[0] == "من عيوني"
    assert front.rag_domains == ("dialect",)


def test_fenced_json_repaired():
    raw = '```json\n{"route": "direct", "tool": "none", "ack": "تمام", "rag_domains": ["kb"]}\n```'
    verdict = repair_verdict(raw)
    assert verdict is not None and verdict["route"] == "direct"
    assert parse_rag_domains(raw) == ("kb",)


def test_trailing_comma_repaired():
    raw = '{"route": "direct", "tool": "none", "ack": "تمام", "rag_domains": ["humor",],}'
    verdict = repair_verdict(raw)
    assert verdict is not None
    assert parse_rag_domains(raw) == ("humor",)


def test_unknown_domains_dropped_to_none():
    assert parse_rag_domains('{"rag_domains": ["orca", "dialect"]}') == ("dialect",)
    assert parse_rag_domains('{"rag_domains": ["orca"]}') == ("none",)
    assert parse_rag_domains('{"route": "direct"}') == ("none",)


def test_garbage_repairs_to_none_and_parse_falls_back():
    assert repair_verdict("تمام يا عمر، أبشر") is None
    assert repair_verdict("") is None
    assert _parse_router("تمام يا عمر، أبشر") is None


def test_parse_router_contract_unchanged():
    """The 5-tuple shape is frozen — existing callers never break."""
    import json

    raw = json.dumps({"route": "tier2", "tool": "none", "ack": "تمام"}, ensure_ascii=False)
    verdict = _parse_router(raw)
    assert verdict is not None and len(verdict) == 5


def test_prompt_declares_domains_field():
    assert '"rag_domains"' in _ROUTER_PROMPT_AR
    for domain in ("dialect", "humor", "grace", "kb", "personal", "none"):
        assert domain in _ROUTER_PROMPT_AR


def test_multi_domain_order_preserved():
    assert parse_rag_domains('{"rag_domains": ["kb", "dialect"]}') == ("kb", "dialect")
