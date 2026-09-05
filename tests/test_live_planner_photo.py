"""Live-4 findings 2026-09-05 (6:56-7:12am):

1. «خذي لقطة شاشة بعدها افتحي الآلة الحاسبة» -> «ما قدرت أنظم مهامك» —
   the planner died on its FIRST failure while the SAME request with «ثم»
   succeeded 30 seconds later: a transient planner round with ZERO retry
   kills the whole multi-task request.

2. «خذي لقطة شاشة واعرفي شو في تفاصيل لا ترسلي الصورة» -> the photo
   arrived anyway — the screenshot tool ALWAYS dispatches the JPEG when the
   sender is wired; the owner's explicit negation is ignored.

Contract:
- _plan retries ONCE on an unparseable planner reply (transient class);
  the second failure still lands the honest line.
- The planner prompt names the owner's connectors (و/ثم/بعدين/بعدها).
- The screenshot tool honors «لا ترسلي الصورة» — the description arrives,
  the photo does not (the negation is honored from BOTH routing surfaces
  because the check lives in _tool_lane where the full user text exists).
"""

from __future__ import annotations

import json

LINE_SCREENSHOT = "خذي لقطة شاشة وافتحي الآلة الحاسبة"


# -- finding 1: planner resilience ----------------------------------------------


async def test_planner_retries_once_on_unparseable():
    """A garbage first reply + a valid second plan: the run SUCCEEDS. One
    transient planner round never kills the request (live: بعدها died, ثم
    worked 30s later — same request class)."""
    from src.agent_manager import AgentManager

    replies = iter(["مو مشكلة رح أنظم كل شي!", "خطة نصية بدون جيسون"])
    plan = json.dumps(
        {
            "lines": [
                {"mode": "sequential", "text": "خذي لقطة شاشة"},
                {"mode": "sequential", "text": "افتحي الآلة الحاسبة"},
            ]
        },
        ensure_ascii=False,
    )
    calls = {"heavy": 0}

    class _Gateway:
        async def chat(self, messages, *, tier, **kw):
            if getattr(tier, "value", "") == "heavy":
                calls["heavy"] += 1
                if calls["heavy"] <= 2:
                    return next(replies)  # two garbage replies (retry covers one)
                return plan
            return json.dumps({"steps": [{"tool": "screenshot", "arg": ""}]})

    manager = AgentManager(gateway=_Gateway(), tools=_Tools())
    report = await manager.run(LINE_SCREENSHOT)
    assert calls["heavy"] == 2  # garbage + the one retry, then the honest stop
    # two unparseable rounds -> the honest line (retry covers ONE transient)
    assert "ما قدرت أنظم مهامك" in report


class _Tools:
    async def call(self, tool, arg=""):
        return "ok"


async def test_planner_retry_recovers():
    """Garbage once, valid plan on the retry: the run completes — one
    transient round is absorbed."""
    from src.agent_manager import AgentManager

    plan = json.dumps(
        {"lines": [{"mode": "parallel", "text": "افتحي الآلة الحاسبة"}]},
        ensure_ascii=False,
    )
    calls = {"heavy": 0}

    class _Gateway:
        async def chat(self, messages, *, tier, **kw):
            if getattr(tier, "value", "") == "heavy":
                calls["heavy"] += 1
                return "أكيد بدي أجهزلك خطة حلوة 😄" if calls["heavy"] == 1 else plan
            return json.dumps({"steps": [{"tool": "launch", "arg": "calculator"}]})

    manager = AgentManager(gateway=_Gateway(), tools=_Tools())
    report = await manager.run(LINE_SCREENSHOT)
    assert calls["heavy"] == 2  # garbage + retry -> the plan
    assert "ما قدرت أنظم مهامك" not in report
    assert "launch:calculator" in report


def test_planner_prompt_names_owner_connectors():
    """The planner vocabulary teaches و/ثم/بعدين/بعدها — the live بعدها round
    failed where ثم worked; the connectors belong in the prompt."""
    from src.agent_manager import _PLANNER_PROMPT_AR

    for connector in ("ثم", "بعدين", "بعدها", "و"):
        assert connector in _PLANNER_PROMPT_AR, connector


# -- finding 2: the screenshot no-send negation -----------------------------------


def test_no_send_pattern_detects_negation():
    """«لا ترسلي الصورة» and its colloquial siblings are recognized as a
    no-send instruction (pure detector, tested at the unit)."""
    from src.dispatcher import _NO_SEND_PHOTO_RE

    for phrase in (
        "خذي لقطة شاشة واعرفي شو في تفاصيل لا ترسلي الصورة",
        "خذي لقطة شو فيها بدون ما ترسلي الصورة",
        "شوفي الشاشة بس لا تبعتيلي الصورة",
        "صوري الشاشة بدون الصورة",
        "ما بدي الصورة بس صفيلي شو عالشاشة",
    ):
        assert _NO_SEND_PHOTO_RE.search(phrase), phrase
    # a normal send request is NOT a negation
    assert not _NO_SEND_PHOTO_RE.search("ارسلي لقطة الشاشة")


async def test_screenshot_negation_skips_photo_sends_description():
    """The full path: _tool_lane appends the no-send marker when the owner
    negated the photo; _do_screenshot skips the dispatch, keeps the vision
    description."""
    from src.tools import ToolRegistry

    sent_photos: list[bytes] = []

    class _PhotoSender:
        async def __call__(self, jpeg):
            sent_photos.append(jpeg)

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            import base64 as b64

            return {"status": "ok", "detail": b64.b64encode(b"jpegbytes").decode()}

    class _Vision:
        async def chat(self, messages):
            return "شاشة فيها تيليجرام وبرامج مفتوحة."

    registry = ToolRegistry(bridge=_Bridge(), vision=_Vision(), photo_sender=_PhotoSender())
    out = await registry.call("screenshot", "no-send")
    assert sent_photos == []  # the photo did NOT dispatch
    assert "شاشة" in out  # the description arrived

    # without the marker the photo still ships (the normal contract)
    await registry.call("screenshot", "")
    assert sent_photos == [b"jpegbytes"]
