"""A degrade message that names the way OUT.

RED-first for the owner's 2026-10-03 requirement: when a tool degrades because a
dependency is unreachable, the message must carry the exit path. A degrade line
that states a fact and stops is a dead end — the owner reads "Google isn't
connected", has no idea what to do, and the tool is useless to them.

THE EXIT PATH IS A LOCAL TERMINAL COMMAND, NOT A URL. This is the finding that
shapes the whole change, and it is worth stating plainly because the obvious
implementation is wrong:

Google's OAuth flow here binds a LOOPBACK listener (`src/google_auth.py`,
`authorize_interactive`), prints a consent URL, and captures the callback. The
authorization URL requires a `redirect_uri` pointing at that running listener
plus a fresh CSRF `state` — BOTH of which exist only inside the command that is
running. So there is no permanent link to print. Printing
`https://accounts.google.com/o/oauth2/v2/auth` would send the owner to a URL that
cannot complete the flow.

The correct entry point, already surfaced twice in `sara.ps1:218,220`:

    .venv\\Scripts\\python.exe -m src.google_auth

These tests therefore assert a COMMAND appears, not a hyperlink.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src import tools as T

GOOGLE_REAUTH_CMD = "python.exe -m src.google_auth"


def _msg(constant: str) -> str:
    return getattr(T, constant)


class TestNoDeadEnds:
    """Every REPAIRABLE degrade must name its exit path."""

    def test_google_degrade_names_the_reauth_command(self):
        m = _msg("GOOGLE_OFFLINE_AR")
        assert GOOGLE_REAUTH_CMD in m, (
            f"the Google degrade line is a dead end — it states the fact and stops. It "
            f"must also carry the re-auth command {GOOGLE_REAUTH_CMD!r}. Got: {m!r}"
        )

    def test_the_reauth_command_is_the_real_one(self):
        """Not a plausible-looking invention: it must be the module the repo
        actually runs (`src/google_auth.py:449 __main__ -> authorize_interactive`)."""
        m = _msg("GOOGLE_OFFLINE_AR")
        assert "src.google_auth" in m
        # the sara.ps1 renewal hint must agree with what we print
        ps1 = (Path(__file__).resolve().parents[1] / "sara.ps1").read_text(
            encoding="utf-8", errors="replace"
        )
        assert "python.exe -m src.google_auth" in ps1, (
            "the message names a command sara.ps1 does not tell the owner to run"
        )

    def test_no_hyperlink_is_printed(self):
        """The whole point: there IS no permanent URL. A degrade line that sends
        the owner to a bare accounts.google.com link is a dead end WITH A LINK."""
        for const in ("GOOGLE_OFFLINE_AR", "LAUNCH_OFFLINE_AR"):
            m = _msg(const)
            assert "accounts.google.com" not in m, (
                f"{const} prints an OAuth URL, but the flow needs a loopback "
                "redirect_uri and a live CSRF state — a bare URL cannot complete it"
            )

    def test_degrade_still_states_the_fact_first(self):
        """The explanation earns its place; it must not REPLACE the reason."""
        m = _msg("GOOGLE_OFFLINE_AR")
        assert "مو متصلين" in m or "ما قدرت" in m, (
            f"the degrade line lost its reason while gaining an exit path: {m!r}"
        )

    def test_bridge_degrade_names_its_recovery(self):
        """Same principle, different dependency: the bridge is local, so its exit
        path is starting the daemon — but it must NAME one."""
        m = _msg("LAUNCH_OFFLINE_AR")
        assert len(m) > len("الجسر مو متصل"), "bridge degrade is a bare dead end"

    def test_agents_cannot_be_told_to_click_a_link(self):
        """The voice lane reads these aloud. A URL spoken is useless; a command is
        still awkward but at least actionable. Guard the shape, not the exact text."""
        m = _msg("GOOGLE_OFFLINE_AR")
        assert "http" not in m.lower(), (
            "a spoken degrade line containing a URL cannot be acted on from Telegram"
        )


class TestExitPathIsNotASecret:
    """The exit path must never leak anything while fixing the dead end."""

    def test_command_carries_no_path_outside_the_repo_shape(self):
        m = _msg("GOOGLE_OFFLINE_AR")
        assert "C:\\" not in m and "/home/" not in m, (
            "the re-auth hint must be repo-relative; an absolute host path would leak "
            "the owner's directory layout into every chat"
        )


@pytest.mark.parametrize(
    "const",
    ["GOOGLE_OFFLINE_AR", "LAUNCH_OFFLINE_AR", "TOOL_FAIL_AR", "NO_EXTERNALS_AR"],
)
def test_constants_stay_non_empty_strings(const):
    assert isinstance(getattr(T, const), str) and getattr(T, const).strip()
