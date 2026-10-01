"""F-2 (report Part F §42) — a forged confirmation id is refused, site by site.

F-2's problem statement, measured: the daemon treated ANY non-empty
`confirmation_id` as a live approval — `bridge/executor.py` (close, launch,
power) and `bridge/openclaw/breaker.py` all asked only "is this string
non-empty?", and `tests/test_whitelist_guardrail.py::test_restricted_power_
always_requires_confirmation` PINNED the forgery by calling `"cid-123"` a
"valid ID". The core minted a real id, wrote it to the vault
(`04_Archives/Confirmations/`) and nobody ever read that note back.

§42's first move is "if the daemon cannot reach the vault, verification must
move to the core side". MEASURED: the daemon has no vault client at all — the
note lives in a GitHub-backed Obsidian vault and the executor process cannot
see it, so a vault-reading verifier is not shippable in this work order (it
would be §42's named failure mode: "don't ship a verifier that can't reach its
store"). F-2 therefore SIGNS the id: the core (which holds the shared
core<->daemon `BRIDGE_TOKEN`) signs it, the daemon verifies the MAC
statelessly, and `issued_at` is checked against the TTL. The vault note is
UNTOUCHED — it stays the audit trail; it is simply not the enforcement point.

WHAT THIS FILE CLAIMS, AND WHAT IT DOES NOT
------------------------------------------
Delivered, and guarded here:
  * FORGERY  — a token without a valid MAC over the shared secret is refused,
    whatever its shape (this includes the old `uuid4().hex[:12]` shape).
  * EXPIRY   — `issued_at` older than `CONFIRMATION_TTL` (== the core's
    `PENDING_TTL`, one number now) is refused. Driven through an injected
    clock (`now_fn=`, the repo's seam) so no test dies at a midnight rollover.
  * FAIL-CLOSED — a verifier with no reachable shared secret refuses EVERY
    confirmation instead of accepting an unverified one.
  * SINGLE-USE — a verified token is refused on second use *within one daemon
    process*. NOT across a daemon restart (the replay set is in memory), and
    the token is not bound to a target, so a captured live token can still be
    replayed against a different app inside the TTL window. Both residuals are
    stated in `verify_confirmation_id`'s own docstring; the guard below
    documents the same limit rather than claiming more than the code keeps.
"""

from __future__ import annotations

import ast
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from helpers_vault import FakeGitHub

from bridge.executor import (
    CONFIRMATION_TTL,
    CONFIRMATION_VERSION,
    Executor,
    confirmation_secret,
    mint_confirmation_id,
    verify_confirmation_id,
)
from bridge.guard import Guard
from bridge.openclaw.breaker import SafetyCircuitBreaker
from bridge.openclaw.protocol import Op, OpKind
from src.pc_actions import PENDING_TTL, LaunchStatus, PCActionCoordinator
from src.vault import CONFIRMATIONS_DIR, VaultClient, split_frontmatter

ROOT = Path(__file__).resolve().parents[1]
VAULT_TOKEN = "your-github-test-pat-abcdef0123456789"
# Test fixture secrets. The `your-` shape is the repo's secret-scanner
# allowlist (tests/conftest.py's ENV_EXAMPLE uses it for the same reason).
KEY = "your-f2-shared-confirmation-key"
OTHER_KEY = "your-f2-other-key"

WHITELIST = {
    "allowed_apps": [
        {"name": "calculator", "executable": "calc.exe", "auto_approve": True},
    ],
    "restricted_actions": [
        {"action": "shutdown", "requires_confirmation": True},
        {"action": "sleep", "requires_confirmation": True},
    ],
}
# An app the whitelist GATES: `auto_approve: false` is the only state in which
# the confirmation id is consulted at all, so the forgery guards must use it.
GATED_APP = [{"name": "steam", "executable": "steam.exe", "auto_approve": False}]

# The forged shapes F-2 must refuse, and the DoD names: a bare token, a
# 12-hex uuid (the pre-F-2 mint shape), a full uuid4 hex, whitespace, and a
# token that is grammatically perfect but signed by nobody.
FORGED_IDS = [
    "cid-123",
    "x",
    "1234567890ab",  # the pre-F-2 `uuid4().hex[:12]` shape
    "",
    "   ",
    "cfm1.1759320000.a3f19c2b.0000000000000000",  # right grammar, zero MAC
]

START = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


class Clock:
    """A movable `now_fn`. The repo's convention is `now_fn=`; a wall-clock read
    in an expiry guard is a test that dies at a midnight rollover."""

    def __init__(self, start: datetime = START) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class SpawnSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, argv: list[str]) -> None:
        self.calls.append(argv)


class Notifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def notify(self, text: str) -> None:
        self.sent.append(text)


class TunnelDouble:
    """The in-process daemon edge: the coordinator's `send_cmd` dispatches to the
    REAL executor (spawn edge spied), so the wire shape is exercised, not
    assumed."""

    def __init__(self, executor: Executor) -> None:
        self.executor = executor
        self.commands: list[tuple[str, dict]] = []

    async def send_cmd(self, cmd, args, *, timeout_s=20.0):
        self.commands.append((cmd, dict(args)))
        if cmd == "exec.launch":
            out = await self.executor.launch(
                args["name"],
                confirmation_id=args.get("confirmation_id"),
                audit_code=args.get("audit_code"),
            )
        elif cmd == "exec.close":
            out = await self.executor.close(
                args["name"],
                confirmation_id=args.get("confirmation_id"),
                audit_code=args.get("audit_code"),
            )
        else:
            out = await self.executor.power(
                args["action"],
                confirmation_id=args["confirmation_id"],
                audit_code=args.get("audit_code"),
            )
        return out.model_dump()


def _vault() -> tuple[VaultClient, FakeGitHub]:
    gh = FakeGitHub()
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    return VaultClient("owner/vault-repo", VAULT_TOKEN, session=session), gh


def _whitelist(tmp_path: Path, apps: list[dict]) -> str:
    data = dict(WHITELIST, allowed_apps=apps)
    path = tmp_path / "whitelist.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _executor(
    tmp_path: Path,
    *,
    apps: list[dict] | None = None,
    confirm_key: str | None = KEY,
    now_fn=None,
) -> tuple[Executor, SpawnSpy]:
    """An executor whose only secret is the test key — no ambient authority."""
    executor = Executor(
        Guard(_whitelist(tmp_path, apps if apps is not None else GATED_APP)),
        confirm_key=confirm_key,
        now_fn=now_fn,
    )
    spy = SpawnSpy()
    executor._spawn = spy
    return executor, spy


# -- 1. forgery: the four sites ------------------------------------------------------


@pytest.mark.parametrize("forged", FORGED_IDS)
async def test_executor_power_refuses_a_forged_confirmation_id(tmp_path: Path, forged: str):
    """Site 1 — `power`. The pre-F-2 gate was `if not (confirmation_id or
    "").strip()`, so every shape above executed a real power argv."""
    executor, spy = _executor(tmp_path)
    result = await executor.power("sleep", confirmation_id=forged)
    assert result.status == "error", (forged, result.detail)
    assert spy.calls == [], f"forged id {forged!r} reached the spawn edge"


@pytest.mark.parametrize("forged", FORGED_IDS)
async def test_executor_launch_refuses_a_forged_confirmation_id(tmp_path: Path, forged: str):
    """Site 2 — `launch`, on a gated app (the only state that consults the id)."""
    executor, spy = _executor(tmp_path)
    result = await executor.launch("steam", confirmation_id=forged)
    assert result.status == "error", (forged, result.detail)
    assert spy.calls == []


@pytest.mark.parametrize("forged", FORGED_IDS)
async def test_executor_close_refuses_a_forged_confirmation_id(tmp_path: Path, forged: str):
    """Site 3 — `close`."""
    executor, spy = _executor(tmp_path)
    result = await executor.close("steam", confirmation_id=forged)
    assert result.status == "error", (forged, result.detail)
    assert spy.calls == []


@pytest.mark.parametrize("forged", FORGED_IDS)
def test_breaker_refuses_a_forged_confirmation_id(forged: str):
    """Site 4 — the OpenClaw circuit breaker's irreversible branch. The
    pre-F-2 body was `return bool((confirmation_id or "").strip())`."""
    op = Op(op=OpKind.HOTKEY, value="Alt+F4")
    assert SafetyCircuitBreaker.authorize(op, forged, confirm_key=KEY) is False


async def test_a_random_uuid4_is_refused_however_it_is_shaped(tmp_path: Path):
    """The DoD's third forged shape, generated fresh: no length rule and no
    prefix rule saves an unsigned id."""
    executor, spy = _executor(tmp_path)
    result = await executor.power("sleep", confirmation_id=uuid.uuid4().hex)
    assert result.status == "error"
    assert "does not verify" in result.detail or "malformed" in result.detail, result.detail
    assert spy.calls == []


async def test_a_token_signed_with_another_secret_is_refused(tmp_path: Path):
    """Same grammar, same shape, different key — the MAC is the whole law."""
    executor, spy = _executor(tmp_path)
    stolen = mint_confirmation_id(secret=OTHER_KEY)
    assert stolen.startswith(f"{CONFIRMATION_VERSION}.")
    result = await executor.power("sleep", confirmation_id=stolen)
    assert result.status == "error" and "does not verify" in result.detail
    assert spy.calls == []


@pytest.mark.parametrize("field", ["issued", "nonce", "mac"])
def test_tampering_with_any_field_of_a_genuine_token_is_refused(field: str):
    """A token is not a bearer string: every field is inside the MAC."""
    parts = mint_confirmation_id(secret=KEY).split(".")
    assert len(parts) == 4
    if field == "issued":
        parts[1] = str(int(parts[1]) + 1)
    elif field == "nonce":
        parts[2] = "deadbeef"
    else:
        parts[3] = "f" * 16
    assert verify_confirmation_id(".".join(parts), secret=KEY).ok is False


# -- 2. the genuine path -------------------------------------------------------------


def test_a_genuine_token_verifies_and_one_from_another_secret_does_not():
    genuine = verify_confirmation_id(mint_confirmation_id(secret=KEY), secret=KEY)
    assert genuine.ok is True and genuine.reason == ""
    wrong = verify_confirmation_id(mint_confirmation_id(secret=KEY), secret=OTHER_KEY)
    assert wrong.ok is False and "does not verify" in wrong.reason


async def test_a_genuine_token_is_accepted_by_all_three_executor_sites(tmp_path: Path):
    """The positive control, and the reason the wall is not a dead end: an id
    minted through the real primitive opens all three gated sites."""
    executor, spy = _executor(tmp_path)
    assert (
        await executor.power("sleep", confirmation_id=mint_confirmation_id(secret=KEY))
    ).status == "ok"
    assert (
        await executor.launch("steam", confirmation_id=mint_confirmation_id(secret=KEY))
    ).status == "ok"
    assert (
        await executor.close("steam", confirmation_id=mint_confirmation_id(secret=KEY))
    ).status == "ok"
    assert len(spy.calls) == 3


async def test_a_genuine_id_minted_through_the_real_coordinator_is_accepted(
    tmp_path: Path, monkeypatch
):
    """The real path end to end: the owner asks -> prompt -> «نعم» -> the core
    mints AND SIGNS the id, writes the note, forwards it over `exec.*` — and
    the executor, which verifies rather than trusts, executes. Nothing is
    stubbed except the OS spawn edge and the vault transport.

    The env carries the same secret the executor is given, because that is what
    production is: one shared `BRIDGE_TOKEN`, two processes."""
    monkeypatch.setenv("BRIDGE_TOKEN", KEY)
    vault, gh = _vault()
    executor, spy = _executor(tmp_path)
    tunnel = TunnelDouble(executor)

    notifier = Notifier()
    coordinator = PCActionCoordinator(tunnel, vault, notifier)
    assert await coordinator.request_launch("steam", origin="owner_chat") == (
        LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert spy.calls == [], "the unconfirmed attempt must not run"

    assert await coordinator.handle_owner_reply("نعم") == "steam"
    assert spy.calls, "a genuine id must reach the spawn edge"
    sent_id = tunnel.commands[-1][1]["confirmation_id"]
    assert sent_id.startswith(f"{CONFIRMATION_VERSION}."), sent_id
    notes = [p for p in gh.objects if p.startswith(CONFIRMATIONS_DIR)]
    assert len(notes) == 1, "the audit note is still the trail — one note, unchanged"
    meta, _body = split_frontmatter(gh.objects[notes[0]][1])
    assert meta["confirmation_id"] == sent_id, "note and wire carry the same id"
    assert any("نفّذت" in msg for msg in notifier.sent), notifier.sent


async def test_the_core_refuses_rather_than_mint_an_unverifiable_id(monkeypatch, tmp_path: Path):
    """The core's half of fail-closed: with no shared secret it cannot mint an
    id any daemon would accept, so it must refuse the confirmation outright —
    no command on the wire, and no audit note for a confirmation that never
    became one."""
    monkeypatch.setattr("bridge.executor.confirmation_secret", lambda: "")
    vault, gh = _vault()
    sent: list[tuple[str, dict]] = []

    class RecordingTunnel:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            sent.append((cmd, dict(args)))
            return {"status": "ok", "detail": "executed", "audit_code": "PC-1"}

    notifier = Notifier()
    coordinator = PCActionCoordinator(RecordingTunnel(), vault, notifier)
    assert await coordinator.request_power("sleep", origin="owner_chat") == (
        LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert await coordinator.handle_owner_reply("نعم") is None
    assert sent == [], "no command may leave without a verifiable id"
    assert not [p for p in gh.objects if p.startswith(CONFIRMATIONS_DIR)]
    assert any("مفتاح" in msg for msg in notifier.sent), notifier.sent


async def test_two_confirmations_on_one_day_keep_two_notes(tmp_path: Path, monkeypatch):
    """The audit trail must not be weakened by the new id shape. A signed id
    begins with the fixed `cfm1.` version prefix, so naming the note by the id's
    first 8 characters gives every same-day note the SAME name — and `upsert`
    overwrites. Two approvals, two notes: that is the invariant."""
    monkeypatch.setenv("BRIDGE_TOKEN", KEY)
    vault, gh = _vault()
    executor, _spy = _executor(tmp_path)
    coordinator = PCActionCoordinator(TunnelDouble(executor), vault, Notifier())
    for _ in range(2):
        assert await coordinator.request_power("sleep", origin="owner_chat") == (
            LaunchStatus.CONFIRMATION_REQUIRED
        )
        assert await coordinator.handle_owner_reply("نعم") == "sleep"
    notes = sorted(p for p in gh.objects if p.startswith(CONFIRMATIONS_DIR))
    assert len(notes) == 2, notes
    ids = {split_frontmatter(gh.objects[path][1])[0]["confirmation_id"] for path in notes}
    assert len(ids) == 2, "one note was overwritten"


# -- 3. expiry -----------------------------------------------------------------------


async def test_executor_refuses_an_expired_id_with_an_injected_clock(tmp_path: Path):
    """The expiry law at the edge, driven by `now_fn=` — one second inside the
    TTL still executes, one second outside it is refused and never spawns."""
    clock = Clock()
    executor, spy = _executor(tmp_path, now_fn=clock)
    token = mint_confirmation_id(now=clock(), secret=KEY)

    assert (await executor.power("sleep", confirmation_id=token)).status == "ok"
    clock.advance(CONFIRMATION_TTL - timedelta(seconds=1))
    # a second approval minted at the same instant is still inside the window
    assert (
        verify_confirmation_id(
            mint_confirmation_id(now=START, secret=KEY), secret=KEY, now=clock()
        ).ok
        is True
    )
    clock.advance(timedelta(seconds=2))
    expired = await executor.power("shutdown", confirmation_id=token)
    assert expired.status == "error" and "expired" in expired.detail
    assert len(spy.calls) == 1, "the expired attempt must not spawn a second time"


def test_a_token_from_the_future_is_not_expired():
    """A clock skew between the core and the PC must not refuse a live
    confirmation; the TTL is an upper bound on age, not a two-sided window."""
    issued = START - timedelta(minutes=1)
    token = mint_confirmation_id(now=issued, secret=KEY)
    assert verify_confirmation_id(token, secret=KEY, now=START).ok is True


def test_the_daemon_and_the_core_share_one_ttl():
    """Two numbers that can drift is how a 10-minute promise becomes a
    20-minute one. `PENDING_TTL` (core) and `CONFIRMATION_TTL` (enforced
    daemon-side) are the same value now — asserted, not assumed."""
    assert PENDING_TTL == CONFIRMATION_TTL == timedelta(minutes=10)


# -- 4. single use -------------------------------------------------------------------


async def test_a_consumed_id_is_refused_on_second_use(tmp_path: Path):
    """SINGLE-USE, with the limit stated: the replay set lives in this daemon
    process, so the guarantee holds for the process's lifetime and NOT across a
    restart. A guard claiming durability would be a guard the code cannot keep."""
    executor, spy = _executor(tmp_path)
    token = mint_confirmation_id(secret=KEY)
    assert (await executor.power("sleep", confirmation_id=token)).status == "ok"
    replay = await executor.power("shutdown", confirmation_id=token)
    assert replay.status == "error", "a second use of one approval is not an approval"
    assert "already used" in replay.detail, replay.detail
    assert len(spy.calls) == 1, "the replay reached the spawn edge"


def test_the_breaker_burns_a_token_it_verified():
    op = Op(op=OpKind.HOTKEY, value="Alt+F4")
    token = mint_confirmation_id(secret=KEY)
    assert SafetyCircuitBreaker.authorize(op, token, confirm_key=KEY) is True
    assert SafetyCircuitBreaker.authorize(op, token, confirm_key=KEY) is False


# -- 5. fail closed, and the shared secret itself ------------------------------------


async def test_a_verifier_without_a_reachable_secret_refuses_everything(tmp_path: Path):
    """No secret configured must mean "refuse", never "accept" — the fail-open
    reading of an unconfigured verifier is the bug F-2 was filed for."""
    executor, spy = _executor(tmp_path, confirm_key="")
    result = await executor.power("sleep", confirmation_id="anything at all")
    assert result.status == "error" and "unconfigured" in result.detail
    assert spy.calls == []


def test_minting_without_a_shared_secret_yields_no_id(monkeypatch):
    """`mint_confirmation_id` has no fake fallback: no secret, no id."""
    monkeypatch.setattr("bridge.executor.confirmation_secret", lambda: "")
    assert mint_confirmation_id() == ""
    assert verify_confirmation_id("", secret=KEY).ok is False


def test_the_shared_secret_resolves_under_the_suite_environment(monkeypatch):
    """`BRIDGE_TOKEN` is the signing secret on BOTH ends (no new knob). The
    suite must resolve it with no `.env` present, or CI silently loses every
    confirmation — that is what tests/conftest.py's setdefault is for, and this
    is the pin that notices if it is ever dropped."""
    assert confirmation_secret(), "no shared BRIDGE_TOKEN under the suite env"
    monkeypatch.setenv("BRIDGE_TOKEN", "your-env-bridge-token")
    assert confirmation_secret() == "your-env-bridge-token"


def test_the_shared_secret_falls_back_to_settings(monkeypatch):
    """MEASURED (F-2): the daemon's process env does NOT carry BRIDGE_TOKEN —
    `src/config.py` reads it from the `.env` FILE (the daemon already calls
    `get_settings()` for the same token). So the resolver must ask Settings too,
    or the daemon refuses every genuine confirmation in production while a dev
    box that owns a `.env` stays green. The Settings double keeps this hermetic:
    CI runs the suite with no `.env` at all."""
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)

    class _Token:
        @staticmethod
        def get_secret_value() -> str:
            return "your-settings-bridge-token"

    class _Settings:
        bridge_token = _Token()

    monkeypatch.setattr("src.config.get_settings", lambda: _Settings())
    assert confirmation_secret() == "your-settings-bridge-token"

    def _boom():
        raise RuntimeError("no settings reachable")

    monkeypatch.setattr("src.config.get_settings", _boom)
    assert confirmation_secret() == "", "an unreachable secret is empty, never a guess"


# -- 6. the DoD's own grep, as a guard -----------------------------------------------


def test_no_truthiness_shortcut_survives_in_the_bridge():
    """`git grep -n "if not confirmation_id" bridge/` must be empty, and so must
    the second gate shape the pre-F-2 executor used at all three sites. Both
    GATES are named; the verifier's own `(confirmation_id or "").strip()`
    input normalization is deliberately not a hit — it decides nothing, it only
    turns None/blank into a string the grammar check can reject."""
    for rel in ("bridge/executor.py", "bridge/openclaw/breaker.py"):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "if not confirmation_id" not in source, rel
        assert "if not (confirmation_id" not in source, rel
        assert "not (confirmation_id or" not in source, rel
        assert "return bool((confirmation_id" not in source, rel


# -- 7. the two riders ---------------------------------------------------------------


def test_the_daemon_states_its_open_roots_instead_of_inheriting_the_seed():
    """Rider (a): `bridge/__main__.py` builds the daemon's Executor, and it must
    pass `open_roots=` — an implicit seed is a wall the owner never chose."""
    tree = ast.parse((ROOT / "bridge" / "__main__.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Executor"
    ]
    assert calls, "the daemon must build an Executor"
    for call in calls:
        assert "open_roots" in {kw.arg for kw in call.keywords}, (
            "the daemon inherits an implicit open-root seed"
        )


def test_the_open_path_lane_comment_names_the_wall_that_actually_exists():
    """Rider (b): the lane comment claimed "no checks of its own" AFTER F-3 put
    a suffix + containment wall behind the verb. A comment describing a
    codebase that no longer exists is how the next agent removes the wall."""
    tree = ast.parse((ROOT / "src" / "tools.py").read_text(encoding="utf-8"))
    doc = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_do_open_path":
            doc = ast.get_docstring(node) or ""
    assert doc, "_do_open_path must document what it does with the daemon's walls"
    assert "adds no checks of its own" not in doc, "the stale F-3 comment is back"
    assert "OPEN_BLOCKED_SUFFIXES" in doc and "open_roots" in doc, doc
