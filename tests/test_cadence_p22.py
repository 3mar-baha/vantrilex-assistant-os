"""P2.2 rotation policy gates (master transformation plan, Phase P2.2).

Pure cadence logic over hand-derived expectations: refresh triggers,
MOBILE derivation matrix, posture-conditioned rotation with no back-to-back
repeats.
"""

from src.cadence import CADENCE_TURNS, DOMAINS, derive_context, refresh_due, rotation_domain


def test_refresh_fires_every_tenth_turn():
    assert refresh_due(10) is True
    assert refresh_due(20) is True
    assert refresh_due(9) is False
    assert refresh_due(11) is False
    assert refresh_due(0) is False
    assert refresh_due(-3) is False


def test_starvation_guard_on_session_start():
    assert refresh_due(4, session_fresh=True) is True
    assert refresh_due(4, session_fresh=False) is False
    assert refresh_due(0, session_fresh=True) is False


def test_mobile_derivation_matrix():
    assert derive_context(bridge_posture="AWAY", telegram_active=True) == "MOBILE"
    assert derive_context(bridge_posture="AWAY", telegram_active=False) == "AWAY"
    assert derive_context(bridge_posture="FOCUS", telegram_active=True) == "FOCUS"
    assert derive_context(bridge_posture="NORMAL", telegram_active=True) == "NORMAL"
    assert derive_context(bridge_posture="FRAGMENTED", telegram_active=False) == "FRAGMENTED"


def test_unknown_posture_degrades_to_normal():
    assert derive_context(bridge_posture="ORB Franz", telegram_active=True) == "NORMAL"
    assert derive_context(bridge_posture="", telegram_active=False) == "NORMAL"


def test_focus_forces_technical_lane():
    for last in [None, "dialect", "humor", "grace", "spotlight"]:
        assert rotation_domain(context="FOCUS", last_domain=last) == "spotlight"


def test_mobile_and_fragmented_stay_concise():
    for context in ("MOBILE", "FRAGMENTED"):
        seen = {rotation_domain(context=context, last_domain=None, turn_index=i) for i in range(6)}
        assert seen <= {"spotlight", "dialect"}, (context, seen)


def test_normal_wheel_never_repeats_back_to_back():
    last: str | None = None
    for i in range(12):
        domain = rotation_domain(context="NORMAL", last_domain=last, turn_index=i)
        assert domain in DOMAINS
        assert domain != last
        last = domain


def test_cadence_constant_is_ten():
    assert CADENCE_TURNS == 10
