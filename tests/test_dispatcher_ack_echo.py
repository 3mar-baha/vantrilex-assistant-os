"""Node C1 — ack-echo dedupe guards (RED-first).

Composition seam (dispatcher.handle ~1003-1011, NOT the router): when the
narration / tool body already starts with the ack text yielded at A8, the
duplicate is dropped instead of stacking. Pure, never-blocking, prefix-only.
"""

import json

import httpx

from src.dispatcher import FrontDoorDispatcher, _strip_ack_echo
from src.gateway import OmniRouteClient
from tests.test_dispatcher import CHAINS
from tests.test_omniroute_gateway import _chunk, _collect, _Scripted, _sse


def _router_json(route: str, ack: str) -> str:
    return _chunk(json.dumps({"route": route, "ack": ack}, ensure_ascii=False))


def _gateway(script: _Scripted) -> OmniRouteClient:
    return OmniRouteClient(
        "http://gw.test/v1", "test-key", chains=CHAINS, transport=script.transport()
    )


def test_strip_ack_echo_unit_dup_prefix_dropped():
    ack = "من عيوني هسا"
    assert _strip_ack_echo(ack, "من عيوني هسا الجواب الحقيقي") == "الجواب الحقيقي"
    assert _strip_ack_echo(ack, "من عيوني هسا") == ""


def test_strip_ack_echo_unit_distinct_kept():
    ack = "من عيوني هسا"
    body = "الجواب الحقيقي تمام"
    assert _strip_ack_echo(ack, body) == body


def test_strip_ack_echo_unit_mid_reply_survives():
    ack = "من عيوني هسا"
    body = "الجواب من عيوني هسا مكمل"
    assert _strip_ack_echo(ack, body) == body


async def test_dup_ack_dropped_at_plain_seam(make_settings):
    ack = "من عيوني هسا"
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", ack))),
        httpx.Response(200, content=_sse(_chunk(f"{ack} الجواب الحقيقي"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("طلب عادي"))
    assert out[0] == ack
    assert "".join(out[1:]).strip() == "الجواب الحقيقي"
    assert "".join(out).count(ack) == 1


async def test_distinct_ack_kept_at_plain_seam(make_settings):
    ack = "من عيوني هسا"
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", ack))),
        httpx.Response(200, content=_sse(_chunk("الجواب الحقيقي"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("طلب عادي"))
    assert out == [ack, "الجواب الحقيقي"]


async def test_mid_reply_repetition_survives(make_settings):
    ack = "من عيوني هسا"
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", ack))),
        httpx.Response(200, content=_sse(_chunk("الجواب"), _chunk(" ومن عيوني هسا مكمل"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("طلب عادي"))
    assert out[0] == ack
    assert "ومن عيوني هسا مكمل" in "".join(out[1:])
