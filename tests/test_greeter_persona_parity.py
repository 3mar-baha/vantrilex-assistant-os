"""F-6 follow-up (2026-10-01) — the reconnect greeter is the THIRD persona
surface, so "one assistant, one prompt" was not literally true yet.

MEASURED at d34d84a, not assumed: `src/bot.py:195` assigned `SARA_PERSONA_AR`
— the byte-locked identity CORE — straight into the greeter's system message,
while Telegram's chat lane (`src/bot.py:644`) and Terminal 1
(`src/bot_shell.py`'s `TERMINAL_SYSTEM_PROMPT`) both ran `build_persona_joda()`.
Those two line numbers are a HISTORICAL measurement of that commit, not a claim
about the tree this file now runs against — the greeter edit added 12 lines
above them. The defect was not a missing feature; it was that the greeter was
the LAST surface still speaking MSA.

Two things this file exists to protect:

  1. ONE BUILDER ON THE WIRE. Every owner-visible surface is driven for real —
     Telegram through the dispatcher, Terminal 1 through `Shell.turn`, the
     greeter through `make_bridge_greeter` — and the system message is read OFF
     THE GATEWAY DOUBLE, not recovered from the source. A builder that is called
     and then overwritten passes an AST guard and fails here.

  2. THE PROFILE GARNISH SURVIVED. The greeter reads the owner's
     `02_Areas/Profile/User_Info.md` and appends it as reference data, tolerating
     failure by design ("profile is garnish, not load-bearing"). Unifying the
     prompt must not delete the personalisation, and must not make a vault read
     failure fatal. Both directions are guarded: garnish present, and garnish
     absent with the greeting still delivered.

WHAT IS DELIBERATELY NOT TOUCHED
--------------------------------
The instruction the owner reads when the bridge comes back — «رجع الاتصال مع
جهاز عمر هسا بعد انقطاع…» — is pinned byte-for-byte below. The SYSTEM prompt
changed (that is the point, and the owner authorised it); the greeting's own
words did not, and a guard now says so out loud instead of leaving it to review
discipline.

The docstring guard at the bottom exists because `src/bot_shell.py`'s module
docstring carried FOUR `file:line` citations and every one of them was stale. A
`file:line` reference is a claim about the tree (CLAUDE.md §5.1 Directive 6), so
it is verified here by re-deriving it, not by re-reading it and agreeing.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from src.persona import JODA_EXEMPLARS_HEADER_AR, SARA_PERSONA_AR, build_persona_joda
from tests.conftest import OWNER_ID, FakeGateway, StreamProgram, drain, make_update

ROOT = Path(__file__).resolve().parents[1]
BOT_PY = ROOT / "src" / "bot.py"
SHELL_PY = ROOT / "src" / "bot_shell.py"

# The composed prompt every owner-visible surface must send. Byte-identical
# across surfaces; garnish (vault envelope, affect guide, profile excerpt) rides
# AFTER it, by design, and is asserted as a suffix rather than as part of it.
COMPOSED = build_persona_joda()

PROFILE_HEADER_AR = "[صاحبك باختصار — بيانات مرجعية]"

# The exact bytes the owner is asked for when his machine reconnects. Frozen by
# owner instruction (keep the greeting's wording): the prompt swap above may not
# drag this line with it.
GREETING_ASK_AR = (
    "رجع الاتصال مع جهاز عمر هسا بعد انقطاع — حيّيه بجملة أو جملتين "
    "بعاميتك الدافئة حسب وقت النهار، واذكر إنك رجعت."
)


def _router(route: str, ack: str) -> str:
    return json.dumps({"route": route, "ack": ack}, ensure_ascii=False)


async def _collect(turn: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in turn]


class VaultStub:
    """The one method `make_bridge_greeter` calls on the vault.

    Hand-rolled rather than a real `VaultClient`: this file guards the greeter's
    TOLERANCE of a failing profile read, so the failure has to be a property of
    the double, not something the real client might mask.
    """

    def __init__(self, body: str | None = None, *, error: Exception | None = None) -> None:
        self._body = body
        self._error = error
        self.reads: list[str] = []

    async def read(self, path: str) -> str:
        self.reads.append(path)
        if self._error is not None:
            raise self._error
        return self._body or ""


async def _greeted(gateway: FakeGateway, bot, vault=None) -> str:
    """Run the greeter once and return the system message it sent."""
    from src.bot import make_bridge_greeter

    await make_bridge_greeter(bot=bot, chat_id=OWNER_ID, gateway=gateway, vault=vault)()
    return gateway.router_calls[0][0]["content"]


# ===========================================================================
# 1. ONE BUILDER ON THE WIRE — all three surfaces, read off the double
# ===========================================================================


async def test_all_three_owner_surfaces_send_the_same_composed_prompt(
    make_shell, fake_bot, make_settings
):
    """The law, measured end to end on all three surfaces.

    RED before the fix: the greeter's system message was `SARA_PERSONA_AR` —
    the bare identity core, byte-for-byte a DIFFERENT prompt from the other two.
    The failure message printed the three prompts' first divergence so the
    implementer can see what moved rather than only that something did.
    """
    from src.bot import _STREAMS
    from src.bot_shell import build_shell

    # --- Telegram: the real dispatcher, the session gateway double ------------
    telegram = make_shell(
        router_replies=[_router("tier2", "تمام، ببدأ")],
        stream_programs=[StreamProgram(deltas=("سجّلت",))],
    )
    await telegram.dp.feed_update(fake_bot(), make_update(1, OWNER_ID, "حدّد موعد بكره"))
    await drain(_STREAMS)
    telegram_system = telegram.gateway.stream_calls[0][0][0]["content"]

    # --- Terminal 1: the real Shell over the real FrontDoorDispatcher --------
    shell_gateway = FakeGateway(
        router_replies=[_router("tier2", "من عيوني")],
        stream_programs=[StreamProgram(deltas=("هلق ببدأ",))],
    )
    shell = build_shell(shell_gateway, make_settings())
    # The shell yields the front door verbatim: the router's ack first, then the
    # streamed answer. Asserting only the TAIL keeps this guard about the prompt
    # it is named for and not about the ack/stream split.
    terminal_out = await _collect(shell.turn("شو رأيك"))
    assert terminal_out[-1] == "هلق ببدأ", f"the turn yielded {terminal_out}"
    terminal_system = shell_gateway.stream_calls[0][0][0]["content"]

    # --- The greeter: driven through its own factory, no vault, no garnish ---
    greeting_gateway = FakeGateway(router_replies=["أهلين عمر، رجعت معك!"])
    greeter_system = await _greeted(greeting_gateway, fake_bot())

    surfaces = {
        "telegram": telegram_system,
        "terminal": terminal_system,
        "greeter": greeter_system,
    }
    for name, system in surfaces.items():
        if not system.startswith(COMPOSED):
            which = (
                "the bare identity core (MSA)" if system == SARA_PERSONA_AR else "something else"
            )
            pytest.fail(
                f"the {name} surface does not send the composed ar-JO prompt — one "
                f"assistant, one prompt. It sends {system[:160]!r}…, which is {which}."
            )
        assert JODA_EXEMPLARS_HEADER_AR in system, (
            f"the {name} surface carries no JODA exemplars on the wire"
        )

    assert terminal_system == greeter_system == COMPOSED, (
        "Terminal 1 and the greeter carry no garnish, so their system prompts "
        "must be the composed prompt exactly — if they differ, one of them has "
        "grown its own second source of truth"
    )


async def test_the_greeter_does_not_send_the_identity_core(fake_bot):
    """The specific defect, named so a future regression cannot hide inside a
    general parity failure: the greeter must not speak MSA while the other two
    surfaces speak ar-JO.

    `build_persona_joda()` STARTS with the core, so `startswith` cannot tell the
    two apart — equality can.
    """
    gateway = FakeGateway(router_replies=["أهلين عمر، رجعت معك!"])
    system = await _greeted(gateway, fake_bot())

    assert system != SARA_PERSONA_AR, (
        "the greeter is still on the bare identity core — it is the last "
        "surface speaking MSA while Telegram and Terminal 1 speak ar-JO"
    )
    assert system.startswith(SARA_PERSONA_AR), (
        "the composed prompt must still OPEN with the byte-locked identity "
        "core; anything else means the persona laws moved"
    )


# ===========================================================================
# 2. THE GARNISH — present, and still optional
# ===========================================================================


async def test_the_profile_garnish_still_rides_the_greeting(fake_bot):
    """The personalisation is NOT collateral damage of the unification.

    RED before the fix, but for the WRONG reason if you read it alone: the old
    core-only prompt also carried the garnish, so the garnish assertions pass on
    both trees. What was red was `system.startswith(COMPOSED)` — the greeter had
    no composed prompt for the garnish to ride. The guard is here because the
    change sits exactly on top of this code: a guard that only exists for the
    behaviour being fixed is a guard that dies with the next edit.
    """
    vault = VaultStub("أ عمر — مهندس برمجيات، بيشتغل من البيت.\n\n.Supports Jordan.")
    gateway = FakeGateway(router_replies=["أهلين عمر، رجعت معك!"])
    system = await _greeted(gateway, fake_bot(), vault)

    assert vault.reads == ["02_Areas/Profile/User_Info.md"], (
        f"the greeter read {vault.reads} — the profile garnish reads exactly one path"
    )
    assert system.startswith(COMPOSED), "the garnish must ride AFTER the composed prompt"
    garnish = system[len(COMPOSED) :]
    assert garnish.startswith("\n\n"), f"garnish separator changed: {garnish[:40]!r}"
    assert PROFILE_HEADER_AR in garnish, "the profile header was dropped or renamed"
    # The excerpt is whitespace-collapsed before truncation, so a wrapped vault
    # note cannot smuggle a newline into the header block.
    assert "\n" not in garnish[len("\n\n") + len(PROFILE_HEADER_AR) + 1 :], (
        "the profile excerpt must be collapsed to one line"
    )
    assert ".Supports Jordan." in garnish, (
        f"the excerpt lost text: {garnish!r} — it must survive whitespace-collapse and truncation"
    )


async def test_the_profile_garnish_is_truncated_not_dropped(fake_bot):
    """The 500-character cap is a law about the owner's vault note, and a cap is
    the kind of number that rots.

    MEASURED, this is GREEN on both trees — the cap does not depend on which
    builder is called, and it is reported here as GREEN on purpose rather than
    dressed up as RED evidence. What it pins: a 2,589-character note must land
    exactly the first 500 characters of its whitespace-collapsed form, so a
    future "let's be generous, 2000" is a RED here and not a silent change to
    what Sara is told about her owner.
    """
    long_note = " ".join(f"عنده-{i}" for i in range(300))  # > 500 chars
    assert len(long_note) > 500, "the fixture must exceed the cap to mean anything"

    vault = VaultStub(long_note)
    gateway = FakeGateway(router_replies=["أهلين عمر، رجعت معك!"])
    system = await _greeted(gateway, fake_bot(), vault)

    excerpt = system.split(f"\n{PROFILE_HEADER_AR}\n", 1)[1]
    assert excerpt == long_note[:500], (
        f"excerpt is {len(excerpt)} chars, expected the collapsed first 500"
    )


async def test_a_failing_profile_read_still_degrades_to_a_greeting(fake_bot):
    """The other direction, and the one that matters operationally: a vault that
    cannot be reached must not cost the owner his reconnect greeting.

    The greeter's contract is that only a blank/failed GREETING raises (the
    watcher then does not stamp `last_greet`, so the next reconnect retries).
    The profile is garnish, not load-bearing — a failure there is logged and the
    greeting goes out on the bare composed prompt.
    """
    vault = VaultStub(error=OSError("vault unreachable"))
    gateway = FakeGateway(router_replies=["أهلين عمر، رجعت معك!"])
    bot = fake_bot()

    system = await _greeted(gateway, bot, vault)

    assert vault.reads == ["02_Areas/Profile/User_Info.md"], "the failing path was never touched"
    assert system == COMPOSED, (
        "a failing profile read must leave the composed prompt exactly as it was, "
        "not a truncated or partially-appended one"
    )
    sent = bot.session.sent("SendMessage")
    assert [call.method.text for call in sent] == ["أهلين عمر، رجعت معك!"], (
        f"the greeting did not survive the vault failure: {[call.method.text for call in sent]}"
    )


# ===========================================================================
# 3. THE OWNER-VISIBLE WORDING — frozen, so the next edit cannot change it
# ===========================================================================


async def test_the_greeting_instruction_bytes_are_unchanged(fake_bot):
    """The line the owner reads when his machine comes back. The owner authorised
    the SYSTEM prompt swap; he did not authorise a new greeting.

    Pinned byte-for-byte — wording, punctuation and the trailing full stop — so
    "I tidied the wording" is impossible to land silently. This guard is GREEN
    before the fix and GREEN after it; that is what a freeze has to do, and a
    freeze that could go red on the current tree would be pinning a bug.
    """
    gateway = FakeGateway(router_replies=["أهلين عمر، رجعت معك!"])
    await _greeted(gateway, fake_bot())

    messages = gateway.router_calls[0]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"] == GREETING_ASK_AR, (
        "the reconnect greeting's owner-visible wording changed — the owner "
        "authorised unifying the system prompt, NOT rewriting what Sara says "
        "to him. Flag it for approval instead of shipping it."
    )


# ===========================================================================
# 4. `src/bot_shell.py`'s docstring — every `file:line` claim, re-derived
# ===========================================================================

# Each anchor is the SYMBOL the docstring sentence names. A citation that points
# at a line without that symbol is a false claim about the tree, which is what
# CLAUDE.md §5.1 Directive 6 exists to prevent.
#
# Measured stale at d34d84a, all four of them; dispatcher symbols re-shifted by
# the C1 insertion 7bc4a33 (`_strip_ack_echo` at 264-290 plus the seam hunk):
#   `src/dispatcher.py:744`  -> the class is at 834
#   `:824`                   -> `handle` is at 914
#   `src/dispatcher.py:1076` -> `_plain_messages` is at 1200
#   `src/bot.py:615`         -> 615 is `acoustic: str = ""`; the call site is 644
CITATION_ANCHORS: dict[str, tuple[str, ...]] = {
    "src/dispatcher.py": (
        r"class\s+FrontDoorDispatcher\b",
        r"async\s+def\s+handle\b",
        r"def\s+_plain_messages\b",
    ),
    "src/bot.py": (r"build_persona_joda\(\)",),
}

# `build_persona_joda()` now has TWO call sites in `src/bot.py` — the Telegram
# lane and the greeter — and both match the anchor above. The docstring says
# "the Telegram route", so the citation is pinned to the Telegram lane's body and
# a citation that slid onto the greeter is caught rather than passing for luck.
TELEGRAM_LANE_FUNCTION = "_stream_answer"

_CITATION = re.compile(r"([\w./-]+\.(?:py|md)):(\d+)|:(\d+)(?![:\w])")


def _module_docstring(path: Path) -> str:
    return ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""


def _citations(doc: str) -> list[tuple[str, int]]:
    """Every `file:line` claim in the prose, with bare `:NNN` resolved against
    the last full path named (that is how the docstring writes its second
    citation of the same file: «(…:744, `handle` at :824)»)."""
    found: list[tuple[str, int]] = []
    last_path = ""
    for match in _CITATION.finditer(doc):
        if match.group(1):
            last_path = match.group(1)
            found.append((last_path, int(match.group(2))))
        elif match.group(3) and last_path:
            found.append((last_path, int(match.group(3))))
    return found


def _function_span(path: Path, name: str) -> tuple[int, int]:
    """Inclusive line span of a top-level `def`/`async def`, from the AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return (node.lineno, node.end_lineno or node.lineno)
    raise AssertionError(f"{path} has no top-level function named {name!r}")


def test_every_docstring_line_citation_points_at_the_symbol_it_names():
    """`src/bot_shell.py` cites four line numbers in its module docstring. A
    line number is a factual claim that rots the moment the file moves, and four
    stale ones had accumulated.

    The guard re-derives each one: the cited line must exist AND carry a symbol
    the sentence names. Delete the citation and the anchor is no longer cited
    either — so this cannot be satisfied by deleting the evidence.
    """
    citations = _citations(_module_docstring(SHELL_PY))
    assert citations, "the docstring cites no line numbers any more — re-derive this guard"

    claimed: set[tuple[str, str]] = set()
    for path, line_no in citations:
        anchors = CITATION_ANCHORS.get(path)
        assert anchors, (
            f"the docstring now cites {path}:{line_no}, but this guard anchors "
            f"no symbol in {path} — re-derive it from the tree"
        )
        lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
        assert 1 <= line_no <= len(lines), (
            f"{path} has {len(lines)} lines; the docstring cites :{line_no}"
        )
        cited = lines[line_no - 1]
        hit = [anchor for anchor in anchors if re.search(anchor, cited)]
        assert hit, (
            f"{path}:{line_no} is stale — it reads {cited.strip()!r} and carries "
            f"none of {list(anchors)}. Re-derive the number from the tree."
        )
        claimed |= {(path, anchor) for anchor in hit}

    orphaned = {
        (path, anchor)
        for path, anchors in CITATION_ANCHORS.items()
        for anchor in anchors
        if (path, anchor) not in claimed
    }
    assert not orphaned, (
        f"these docstring symbols are no longer cited by any line number: "
        f"{sorted(orphaned)} — delete them here, or restore the citation, but do "
        "not let the guard quietly shrink"
    )


def test_the_bot_py_citation_names_the_telegram_lane_not_the_greeter():
    """The sharper half of the citation guard.

    After this unification `src/bot.py` calls `build_persona_joda()` twice — the
    Telegram chat lane and the reconnect greeter. The docstring says «the
    Telegram route already used it», so the cited line must sit inside
    `_stream_answer`'s body. Without this, a citation that drifted onto the
    greeter's new call site would satisfy the anchor check by accident.
    """
    doc = _module_docstring(SHELL_PY)
    bot_citations = [line for path, line in _citations(doc) if path == "src/bot.py"]
    assert bot_citations, "the docstring no longer cites src/bot.py — re-derive this guard"

    start, end = _function_span(BOT_PY, TELEGRAM_LANE_FUNCTION)
    for line_no in bot_citations:
        assert start <= line_no <= end, (
            f"src/bot.py:{line_no} is outside `{TELEGRAM_LANE_FUNCTION}` "
            f"({start}-{end}) — the docstring claims the Telegram route, and "
            f"{TELEGRAM_LANE_FUNCTION} is where that route's prompt is built"
        )
    assert (
        "build_persona_joda()"
        in BOT_PY.read_text(encoding="utf-8").splitlines()[bot_citations[0] - 1]
    ), f"src/bot.py:{bot_citations[0]} no longer names the composed builder"
