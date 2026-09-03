"""Live-call lane contract (v1.1 scaffold): mock until the physical
secret lands, live the moment it does — one interface, zero code changes."""

from __future__ import annotations

from src.skills.live_calls import CALL_UNSUPPORTED_AR, CallSession, build_call_session


async def test_mock_mode_dials_and_records():
    """No session string -> MOCK: dial records the intent and succeeds (the
    whole flow is provable without the physical asset)."""
    session = CallSession(session_string=None)
    assert session.live is False
    assert await session.dial("@omar") is True
    assert await session.hang_up("@omar") is True
    assert [i.peer for i in session.mock.dialed] == ["@omar"]
    assert session.mock.hung_up == ["@omar"]


async def test_live_mode_routes_to_engine(monkeypatch):
    """With a session string the same interface routes to PyTgCalls —
    injected double proves the delegation."""

    class FakePyTgCalls:
        def __init__(self, session_string):
            self.session_string = session_string

        async def call(self, peer, kind):
            return kind == "voice" and self.session_string == "sess"

    import sys

    fake_module = type(sys)("pytgcalls")
    fake_module.PyTgCalls = FakePyTgCalls
    monkeypatch.setitem(sys.modules, "pytgcalls", fake_module)

    session = CallSession(session_string="sess")
    assert session.live is True
    assert await session.dial("@omar") is True
    assert session.mock.dialed == []  # nothing recorded in live mode


async def test_live_failure_never_hangs_the_bot():
    """A dead dial returns False — never an exception into the chat flow."""
    session = CallSession(session_string="sess")  # pytgcalls not installed -> ImportError path
    assert await session.dial("@omar") is False


def test_build_from_settings(make_settings):
    """The ONLY difference between mock and live is the env secret."""
    settings = make_settings(TELEGRAM_USER_SESSION_STRING="")
    assert build_call_session(settings).live is False
    settings = make_settings(TELEGRAM_USER_SESSION_STRING="real-session")
    assert build_call_session(settings).live is True


def test_honest_line_names_the_owner_action():
    """The degraded line tells the OWNER what to do — never «ما بقدر»."""
    assert "تفعيل" in CALL_UNSUPPORTED_AR or "الخطوات" in CALL_UNSUPPORTED_AR
    assert "ما بقدر" not in CALL_UNSUPPORTED_AR
