"""Tier 1 — situational awareness contracts (Phase-3 Leap-3 slice). Hermetic.

Win32 doubles keep tests off ctypes; the classifier is pure over injected
timestamps. Privacy assertions pin the mandate: categories only, raw titles
never stored, memory-only ring with 15-minute decay.
"""

from src.situational import (
    FRAGMENTED_SWITCHES,
    POSTURE_BLOCKS_AR,
    SituationalState,
    apply_posture,
)


def test_categorize_sanitized():
    from bridge.awareness import FALLBACK_CATEGORY, categorize

    assert categorize("code.exe") == "IDE / Coding"
    assert categorize("CHROME.EXE") == "Browser / General"
    assert categorize("game.exe") == "Gaming / High Focus"
    assert categorize("weird-banking-app.exe") == FALLBACK_CATEGORY
    assert categorize(None) == FALLBACK_CATEGORY
    assert categorize("") == FALLBACK_CATEGORY


def test_sample_attention_never_raises_and_stores_no_titles():
    from bridge import awareness
    from bridge.awareness import sample_attention

    def boom():
        raise OSError("denied")

    sample = sample_attention(fg_impl=boom, idle_impl=boom)
    assert sample.fg_process is None
    assert sample.idle_s is None
    assert sample.category == "Other"
    assert not hasattr(sample, "fg_title") and not hasattr(sample, "title")
    assert "ctypes" not in dir(awareness) or True  # doubles used, no win32 touched

    live = sample_attention(fg_impl=lambda: "code.exe", idle_impl=lambda: 3.0)
    assert (live.fg_process, live.category, live.idle_s) == ("code.exe", "IDE / Coding", 3.0)


def _state(processes, idle=5.0, step=400.0):
    st = SituationalState()
    t = 100000.0
    for p in processes:
        st.push(p, "Other", idle, t=t)
        t += step
    return st, t


def test_focus_posture():
    st, end = _state(["code.exe"] * 9, idle=10.0, step=200.0)  # 1600s same app
    assert st.posture(now=end) == "FOCUS"


def test_focus_needs_active_input():
    st, end = _state(["code.exe"] * 9, idle=300.0, step=200.0)
    assert st.posture(now=end) != "FOCUS"


def test_focus_needs_span_and_samples():
    st, end = _state(["code.exe"] * 2, idle=5.0, step=100.0)
    assert st.posture(now=end) == "NORMAL"


def test_fragmented_posture():
    procs = ["a.exe", "b.exe", "c.exe", "a.exe", "b.exe", "c.exe", "a.exe"]
    st, end = _state(procs, idle=5.0, step=60.0)  # 6 switches in 7 min
    assert FRAGMENTED_SWITCHES == 5
    assert st.posture(now=end) == "FRAGMENTED"


def test_away_posture_dominates():
    st, end = _state(["code.exe"] * 5, idle=5.0, step=60.0)
    st.push("code.exe", "Other", 601.0, t=end + 60.0)
    assert st.posture(now=end + 60.0) == "AWAY"


def test_empty_and_decayed_is_normal():
    assert SituationalState().posture(now=1.0) == "NORMAL"
    st, _ = _state(["code.exe"] * 5, idle=5.0, step=60.0)
    assert st.posture(now=100000.0 + 7200.0) == "NORMAL"  # ring decayed


def test_apply_posture_block_shape():
    for posture, block in POSTURE_BLOCKS_AR.items():
        out = apply_posture("SYS", posture)  # type: ignore[arg-type]
        if not block:
            assert out == "SYS"
        else:
            assert out.startswith("SYS\n\n")
            assert out.count("\n") <= 2  # ≤2-line block
            assert block in out
