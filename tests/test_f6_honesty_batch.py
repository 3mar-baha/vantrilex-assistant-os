"""F-6 (report Part F §46) — the P1 honesty batch, item by item.

Four defects, four guards, none of them a claim:

  1. PERSONA DIVERGENCE — Terminal 1 built its prompt with
     `build_persona_joda()` while Telegram built `build_persona([])`, so the
     two owner-facing surfaces of ONE assistant ran on two different prompts.
     Owner decision 2026-10-01: UNIFY. Both surfaces now name the same
     builder. This file asserts the parity from two sides — the AST (both
     modules call the same symbol, so a future divergence is a RED here, not
     a silent style drift) and the WIRE (the Telegram system message really
     carries the composed ar-JO prompt, exemplars included).

  2. THE MANIFEST PROMISED A VOICE ENGINE THAT DOES NOT EXIST — Sara's
     self-awareness manifest told her "if my primary engine breaks I use the
     local backup engine". `src/voice.py` says Fish-only, and
     `src/voice_policy.py` BANS a second engine outright. The false claim is
     the defect; building a fallback is a project F-4/F-6 deliberately did
     not do. The manifest now states what the code actually does.

  3. C-7 — ALIAS-MAP COVERAGE WAS A CLAIM. It is now a NUMBER, computed from
     the tree and pinned: how many of the Arabic colloquial aliases land on a
     key `config/whitelist.json` actually knows. An alias pointing at a key
     the whitelist lacks is a DEAD alias — the owner gets the honest
     «مش موجود بالقائمة» line instead of a launch. Silent shrinkage of the
     map is what the pin exists to catch.

  4. C-2 — PENDING-CONFIRMATION EXPIRY WAS UNVERIFIED. Affirming after the
     10-minute TTL used to fall through the coordinator in silence, so the
     owner believed he had approved something that had already lapsed. It is
     now refused AS EXPIRED, in honest ar-JO, with no path and no secret in
     the line — driven through an injected clock (`now_fn=`, the repo's
     seam) so no test dies at a midnight rollover.

WHAT THIS FILE DOES NOT CLAIM
-----------------------------
The `shutil.which` probe in §3 measures THIS box. Its hit count is reported,
not pinned: pinning a machine-dependent number would make the guard lie on any
other machine, and a guard that lies is worse than no guard. What IS pinned is
the deterministic half — the alias map's size and its whitelist coverage —
because that is the half a code change can silently shrink.
"""

from __future__ import annotations

import ast
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from helpers_vault import FakeGitHub

from src.persona import JODA_EXEMPLARS_HEADER_AR, build_persona_joda
from tests.conftest import OWNER_ID, StreamProgram, drain, make_update

ROOT = Path(__file__).resolve().parents[1]
WHITELIST_PATH = ROOT / "config" / "whitelist.json"
TOKEN = "your-github-test-pat-abcdef0123456789"

# The pinned shape of the alias map (src/pc_actions._APP_ALIASES). These are
# COUNTS, not examples: an entry deleted in either direction is a RED here.
ALIAS_ENTRIES = 45
ARABIC_ALIASES = 42
# Arabic aliases that resolve to a key the whitelist knows. The three that do
# NOT are named below — see `KNOWN_UNCOVERED_ALIASES`.
COVERED_ALIASES = 38

# The exact aliases whose resolved key `config/whitelist.json` does not carry.
# They are NOT defects in the map — the map is honest, the WHITELIST has not
# been extended to those programs on this box. The set is pinned BY NAME so
# the day the owner installs one of them the guard says exactly which line to
# drop, instead of the coverage silently drifting in either direction.
KNOWN_UNCOVERED_ALIASES = {
    "الضغط",  # -> 7-Zip
    "التيرمنال",  # -> Windows Terminal
    "تيرمنال",  # -> Windows Terminal
}

START = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


def _router(route: str, ack: str) -> str:
    return json.dumps({"route": route, "ack": ack}, ensure_ascii=False)


# ===========================================================================
# 1. PERSONA DIVERGENCE — one assistant, one prompt
# ===========================================================================


def _persona_builders(path: Path) -> set[str]:
    """Every `src.persona` builder this module CALLS.

    Parsed with `ast`, not grepped: the question is what the shipped code
    invokes, and a comment or a docstring naming a builder must not pass for
    a call.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"build_persona", "build_persona_joda"}
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in names:
                called.add(node.func.id)
    return called


def test_both_owner_surfaces_name_the_same_persona_builder():
    """The divergence guard. Terminal 1 and Telegram are the same assistant
    reaching the same owner; a split prompt is a split personality.

    RED before the fix: `src/bot.py` called `build_persona([])` (core only)
    while `src/bot_shell.py` called `build_persona_joda()` (core + the ar-JO
    few-shots). Both surfaces now name ONE builder.
    """
    shell = _persona_builders(ROOT / "src" / "bot_shell.py")
    telegram = _persona_builders(ROOT / "src" / "bot.py")

    assert shell == telegram, (
        f"the two owner-facing surfaces build different prompts: "
        f"terminal {sorted(shell)} vs Telegram {sorted(telegram)}. "
        "One assistant, one prompt — pick a builder and use it in both."
    )
    assert telegram == {"build_persona_joda"}, (
        f"Telegram must build the composed ar-JO prompt, not the core alone; "
        f"it calls {sorted(telegram)}"
    )


async def test_telegram_replies_carry_the_composed_ar_jo_prompt(make_shell, fake_bot):
    """The wire half of the same law: the system message Telegram actually
    sends carries the JODA exemplars, not just the identity core.

    The AST guard proves which builder is named; this proves it REACHED the
    gateway — a builder that is called and then overwritten would satisfy the
    first guard and fail this one.
    """
    from src.bot import _STREAMS

    shell = make_shell(
        router_replies=[_router("tier2", "تمام، ببدأ")],
        stream_programs=[StreamProgram(deltas=("سجّلت",))],
    )
    bot = fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "حدّد موعد بكره"))
    await drain(_STREAMS)

    messages, _tier = shell.gateway.stream_calls[0]
    system = messages[0]["content"]
    assert JODA_EXEMPLARS_HEADER_AR in system, (
        "Telegram's system prompt carries no JODA exemplars — the ar-JO "
        "few-shots that make Sara sound like Sara are not reaching the wire"
    )
    assert system.startswith(build_persona_joda()), (
        "Telegram's prompt must be the composed persona, byte-for-byte the "
        "one the terminal builds"
    )


# ===========================================================================
# 2. THE MANIFEST MUST NOT PROMISE AN ENGINE THAT DOES NOT EXIST
# ===========================================================================


def test_the_manifest_promises_no_backup_voice_engine():
    """`src/voice.py` states the law in its own docstring: Fish-only, no
    fallback voice, and a Fish failure lands the honest TEXT reply upstream
    (`_speak_demanded` returns False -> the text apology). The manifest told
    Sara the opposite — that she has a local backup engine.

    RED before the fix: the manifest contained «المحرك الاحتياطي المحلي».
    """
    from src.memory import build_capabilities_manifest

    manifest = build_capabilities_manifest()
    assert "المحرك الاحتياطي" not in manifest, (
        "the manifest promises a local backup voice engine that does not "
        "exist — src/voice_policy.py bans a second engine outright"
    )


def test_the_manifest_still_promises_the_voice_note_it_can_actually_send():
    """The fix must not gut the rule it was correcting. A voice request is
    still honoured — and when the ONE engine is down, the manifest now says
    the thing that really happens: the full text reply, stated plainly.
    """
    from src.memory import build_capabilities_manifest

    manifest = build_capabilities_manifest()
    assert "رسالة صوتية" in manifest, "the voice-demand law was deleted, not corrected"
    assert "نص" in manifest


def test_voice_module_still_declares_itself_fish_only():
    """Guard the guard's premise. The manifest was corrected BECAUSE the code
    is Fish-only; if a second engine ever ships, this file's claim changes and
    the manifest sentence above must be re-derived — not silently re-added.

    Whitespace is normalised first: the phrase wraps a newline in the source,
    and a guard that breaks on re-wrapping is a guard that will be "fixed" by
    deleting the claim instead of by fixing the code.
    """
    doc = " ".join((ROOT / "src" / "voice.py").read_text(encoding="utf-8")[:600].split())
    assert "no fallback voice" in doc, (
        "src/voice.py no longer declares Fish-only; the manifest's corrected "
        "wording must be re-derived from whatever the code now does"
    )


# ===========================================================================
# 3. C-7 — alias-map coverage is a NUMBER, and the number is pinned
# ===========================================================================


def _allowed_apps() -> list[dict]:
    return json.loads(WHITELIST_PATH.read_text(encoding="utf-8"))["allowed_apps"]


def _whitelist_keys() -> set[str]:
    """Every spelling `bridge.guard.Guard.check_app` will match on, rebuilt
    from the real file with the real rule (name / full executable / basename /
    stem, case-folded)."""
    keys: set[str] = set()
    for entry in _allowed_apps():
        executable = str(entry.get("executable", "")).casefold()
        base = executable.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        keys |= {
            str(entry.get("name", "")).casefold(),
            executable,
            base,
            base.removesuffix(".exe"),
        }
    return keys


def test_the_alias_map_has_not_silently_shrunk():
    """The pin. An alias deleted from `src/pc_actions._APP_ALIASES` is a
    colloquial phrase the owner can say that now lands the honest
    «مش موجود بالقائمة» line instead of launching — a regression nobody would
    notice in review, because deleting a line always looks like tidying."""
    from src.pc_actions import _APP_ALIASES

    assert len(_APP_ALIASES) == ALIAS_ENTRIES, (
        f"the alias map holds {len(_APP_ALIASES)} entries, pinned at "
        f"{ALIAS_ENTRIES} — entries were added or removed without re-deriving"
    )
    arabic = [k for k in _APP_ALIASES if _arabic(k)]
    assert len(arabic) == ARABIC_ALIASES, (
        f"{len(arabic)} Arabic aliases, pinned at {ARABIC_ALIASES}"
    )


def test_arabic_alias_coverage_is_measured_and_pinned():
    """C-7 coverage as a number: how many Arabic aliases resolve to a key the
    whitelist actually knows.

    The three uncovered ones are named in `KNOWN_UNCOVERED_ALIASES` and
    asserted by identity, so the day 7-Zip or Windows Terminal enters the
    whitelist this guard names the exact line to drop rather than the count
    quietly drifting.
    """
    from src.pc_actions import _APP_ALIASES, resolve_app_alias

    keys = _whitelist_keys()
    arabic = {k: v for k, v in _APP_ALIASES.items() if _arabic(k) and v is not None}

    covered: set[str] = set()
    uncovered: set[str] = set()
    for said, target in arabic.items():
        resolved = resolve_app_alias(said)
        assert resolved == target, (
            f"alias {said!r} does not survive its own resolver "
            f"(map says {target!r}, resolver says {resolved!r})"
        )
        (covered if resolved.casefold() in keys else uncovered).add(said)

    assert covered | uncovered == set(arabic), "an alias escaped the coverage walk"
    assert uncovered == KNOWN_UNCOVERED_ALIASES, (
        f"uncovered aliases are {sorted(uncovered)}, pinned at "
        f"{sorted(KNOWN_UNCOVERED_ALIASES)} — either the whitelist gained an "
        "app (drop the name here) or the map points somewhere new (fix the map)"
    )
    assert len(covered) == COVERED_ALIASES, (
        f"{len(covered)} of {len(arabic)} Arabic aliases reach a whitelist key, "
        f"pinned at {COVERED_ALIASES}"
    )


def test_the_on_box_executable_probe_actually_fires():
    """The `shutil.which` half is REPORTED, not pinned: it measures the box
    the suite runs on, and pinning a machine-dependent count would make this
    guard lie everywhere else.

    What this asserts is the only thing that is portable: the probe reaches
    real executables and finds some of them. A probe that silently matched
    nothing would make the reported coverage a fiction.
    """
    from src.pc_actions import _APP_ALIASES, resolve_app_alias

    keys = _whitelist_keys()
    hits = misses = 0
    for said, target in _APP_ALIASES.items():
        if target is None or not _arabic(said):
            continue
        resolved = resolve_app_alias(said)
        if resolved.casefold() not in keys:
            continue
        entry = next(
            (
                e
                for e in _allowed_apps()
                if str(e.get("name", "")).casefold() == resolved.casefold()
            ),
            None,
        )
        executable = str((entry or {}).get("executable", ""))
        if executable and shutil.which(executable):
            hits += 1
        else:
            misses += 1

    print(f"\n[C-7] on-box executable coverage: {hits} found, {misses} not found")
    assert hits + misses > 0, "the probe matched no alias at all — coverage is a fiction"
    assert hits > 0, "no whitelisted executable was found on this box; is the probe broken?"


# ===========================================================================
# 4. C-2 — a confirmation past its TTL is refused AS EXPIRED
# ===========================================================================


class Clock:
    """A movable `now_fn`. The repo's convention is `now_fn=`; a wall-clock
    read in an expiry guard is a test that dies at a midnight rollover."""

    def __init__(self, start: datetime = START) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class Notifier:
    _chat_id = 111  # mirrors _BotNotifier — the 2.4 memory hook keys off it

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def notify(self, text: str) -> None:
        self.sent.append(text)


class Bridge:
    """Answers every unconfirmed command with "not whitelisted", so a pending
    is minted and nothing ever executes without the coordinator's say-so."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, dict]] = []

    async def send_cmd(self, cmd: str, args: dict, *, timeout_s: float = 20.0) -> dict:
        self.commands.append((cmd, dict(args)))
        return {"status": "error", "detail": "not whitelisted", "audit_code": "PC-F6"}


def _vault_client() -> tuple:
    import httpx

    from src.vault import VaultClient

    gh = FakeGitHub()
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    return VaultClient("owner/vault-repo", TOKEN, session=session), gh


def _coordinator(clock: Clock) -> tuple:
    from src.pc_actions import PCActionCoordinator

    bridge, notifier = Bridge(), Notifier()
    vault, _gh = _vault_client()
    return PCActionCoordinator(bridge, vault, notifier, now_fn=clock), bridge, notifier


def test_the_coordinator_takes_an_injected_clock():
    """The seam exists at all. `pending_active` read `datetime.now(UTC)`
    directly, so the TTL could not be crossed in a test without sleeping ten
    minutes — which is why this behaviour was unverified in the first place."""
    from inspect import signature

    from src.pc_actions import PCActionCoordinator

    assert "now_fn" in signature(PCActionCoordinator.__init__).parameters, (
        "PCActionCoordinator must accept `now_fn=` — the repo's clock seam "
        "(CLAUDE.md §5.1 Directive 2: a guard you cannot drive is not a guard)"
    )


async def test_affirming_after_the_ttl_is_refused_as_expired():
    """The C-2 law. Inside the window «نعم» executes; one second past it,
    the affirmation is refused AS EXPIRED — no command on the wire, no
    confirmation note in the vault, and an honest ar-JO line that tells the
    owner the request lapsed instead of leaving him believing it ran."""
    from src.pc_actions import PENDING_TTL, LaunchStatus
    from src.vault import CONFIRMATIONS_DIR

    clock = Clock()
    coordinator, bridge, notifier = _coordinator(clock)
    _vault, gh = _vault_client()

    assert await coordinator.request_power("sleep", origin="owner_chat") == (
        LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert coordinator.pending_active()

    clock.advance(PENDING_TTL + timedelta(seconds=1))
    assert not coordinator.pending_active(), "the TTL must lapse"
    assert coordinator.pending_open(), (
        "an expired-but-unanswered prompt must still reach the coordinator, "
        "or the honest line below never lands"
    )

    assert await coordinator.handle_owner_reply("نعم") is None
    assert bridge.commands == [], "an expired approval must not reach the wire"
    assert not [p for p in gh.objects if p.startswith(CONFIRMATIONS_DIR)], (
        "an expired approval must not write a confirmation note"
    )

    assert [line for line in notifier.sent if "انتهت" in line], (
        f"the expiry was silent — the owner gets no line at all: {notifier.sent}"
    )


async def test_an_expired_refusal_is_not_repeatable():
    """One honest line, once. A lapsed prompt that keeps re-announcing on
    every subsequent message would nag the owner about a decision he already
    answered (or abandoned)."""
    from src.pc_actions import PENDING_TTL

    clock = Clock()
    coordinator, _bridge, notifier = _coordinator(clock)
    await coordinator.request_power("sleep", origin="owner_chat")
    clock.advance(PENDING_TTL + timedelta(seconds=1))

    await coordinator.handle_owner_reply("نعم")
    first = len(notifier.sent)
    await coordinator.handle_owner_reply("نعم")
    assert len(notifier.sent) == first, "the expiry line repeated"
    assert not coordinator.pending_open()


async def test_the_expiry_line_leaks_no_path_and_no_secret():
    """Sara's honest lines go to the owner's Telegram. A vault path, a
    confirmation token, or a signing key in that line is a disclosure."""
    from src.pc_actions import PENDING_TTL

    clock = Clock()
    coordinator, _bridge, notifier = _coordinator(clock)
    await coordinator.request_power("sleep", origin="owner_chat")
    clock.advance(PENDING_TTL + timedelta(seconds=1))
    await coordinator.handle_owner_reply("نعم")

    for line in notifier.sent:
        assert "\\" not in line and "/" not in line, f"a path leaked: {line!r}"
        assert "cfm1." not in line, f"a confirmation token leaked: {line!r}"
        assert TOKEN not in line and "your-" not in line, f"a secret leaked: {line!r}"


async def test_inside_the_window_a_confirmation_still_executes():
    """The negative control. Without it, "refuse and say nothing" would pass
    every guard above — a coordinator that never confirms anything is not an
    honest one, it is a broken one."""
    from src.pc_actions import PENDING_TTL

    clock = Clock()
    coordinator, _bridge, _notifier = _coordinator(clock)
    await coordinator.request_power("sleep", origin="owner_chat")
    clock.advance(PENDING_TTL - timedelta(seconds=1))
    assert await coordinator.handle_owner_reply("نعم") == "sleep", (
        "a confirmation one second inside the TTL must still execute"
    )


async def test_the_expired_turn_is_consumed_not_leaked_to_the_brain(
    make_shell, fake_bot, monkeypatch
):
    """The wiring half, driven through the REAL dispatcher.

    `src/bot.py` gates the coordinator on `pending_open()`, not
    `pending_active()`. Gating on the latter is what made C-2 unobservable:
    the moment the TTL lapsed, «نعم» stopped being a confirmation and became
    an ordinary chat message — the brain answered a yes to nothing, and the
    owner was never told the request had expired.

    Hermetic: `Settings` and the gateway are conftest doubles, so no `.env`
    is read and no socket is opened.
    """
    from src.bot import _STREAMS
    from src.pc_actions import PENDING_TTL

    monkeypatch.setenv("BRIDGE_TOKEN", "your-f6-shared-confirmation-key")
    clock = Clock()
    coordinator, bridge, notifier = _coordinator(clock)
    await coordinator.request_power("sleep", origin="owner_chat")
    clock.advance(PENDING_TTL + timedelta(seconds=1))

    shell = make_shell(coordinator=coordinator)
    bot = fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "نعم"))
    await drain(_STREAMS)

    assert bridge.commands == [], "the expired approval reached the wire"
    assert shell.gateway.router_calls == [], (
        "the expired «نعم» reached the brain as ordinary chat — the bot gates "
        "on pending_active() alone, so a lapsed confirmation is invisible"
    )
    assert shell.gateway.stream_calls == [], "a stream was spawned for a dead confirmation"
    assert [line for line in notifier.sent if "انتهت" in line], (
        f"the owner was told nothing: {notifier.sent}"
    )
    assert not coordinator.pending_open(), "the lapsed prompt must be consumed, not retried"