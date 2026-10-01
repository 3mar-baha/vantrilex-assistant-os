"""Remediation 3.1 (owner-promised loops never launched): the production wiring
must start FOUR background loops — morning brief, evening journaler, gmail
poll, daily summary — and cancel every one on shutdown. The stitch point
`start_background_loops` is testable without polling."""

from __future__ import annotations

import asyncio

import httpx

from src.bot import start_background_loops


class _LoopSpy:
    """Records run_forever launches; never completes on its own (a real loop)."""

    launched = 0

    async def run_forever(self) -> None:
        _LoopSpy.launched += 1
        while True:
            await asyncio.sleep(3600)

    @classmethod
    def reset(cls) -> None:
        cls.launched = 0


class _PollSpy:
    launched = 0

    async def __call__(self, inbox, dispatcher, classifier, settings) -> None:
        _PollSpy.launched += 1
        while True:
            await asyncio.sleep(3600)

    @classmethod
    def reset(cls) -> None:
        cls.launched = 0


def _rig(make_settings, **env):
    _LoopSpy.reset()
    _PollSpy.reset()
    settings = make_settings(**env)
    return (
        {
            "brief": _LoopSpy(),
            "journaler": _LoopSpy(),
            "summarizer": _LoopSpy(),
        },
        _PollSpy(),
        settings,
    )


async def test_four_loops_created_and_cancelled_on_shutdown(make_settings):
    """Brief + journaler + gmail poll + daily summary: all four tasks live,
    all cancelled in the finally — no orphan loops, no missed owner promises."""
    loops, poll, settings = _rig(make_settings)
    tasks = start_background_loops(
        brief=loops["brief"],
        journaler=loops["journaler"],
        summarizer=loops["summarizer"],
        gmail_poll=poll,
        inbox=object(),
        dispatcher=object(),
        classifier=object(),
        settings=settings,
    )
    try:
        assert len(tasks) == 4  # four loops: brief + journaler + summary + gmail
        assert all(not t.done() for t in tasks)  # all alive
        await asyncio.sleep(0.05)  # let them enter their loops
        assert _LoopSpy.launched == 3  # brief + journaler + summarizer entered
        assert _PollSpy.launched == 1  # gmail poll entered
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert all(t.cancelled() or t.done() for t in tasks)  # every loop reaped


async def test_brief_disabled_blocks_only_the_brief(make_settings):
    """BRIEF_ENABLED=false → three loops, the brief never launches; the other
    promises (journaler, summary, gmail) stay live."""
    loops, poll, settings = _rig(make_settings, BRIEF_ENABLED="false")
    tasks = start_background_loops(
        brief=loops["brief"],
        journaler=loops["journaler"],
        summarizer=loops["summarizer"],
        gmail_poll=poll,
        inbox=object(),
        dispatcher=object(),
        classifier=object(),
        settings=settings,
    )
    try:
        await asyncio.sleep(0.05)
        assert _LoopSpy.launched == 2  # journaler + summarizer only
        assert _PollSpy.launched == 1
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_no_gmail_stack_degrades_to_three_loops(make_settings):
    """Google stack offline (inbox None) → the gmail poll never starts; the
    chat promises (journaler, summary) + brief still run."""
    loops, poll, settings = _rig(make_settings)
    tasks = start_background_loops(
        brief=loops["brief"],
        journaler=loops["journaler"],
        summarizer=loops["summarizer"],
        gmail_poll=poll,
        inbox=None,  # degraded boot: no Google creds
        dispatcher=object(),
        classifier=object(),
        settings=settings,
    )
    try:
        await asyncio.sleep(0.05)
        assert len(tasks) == 3  # no gmail task
        assert _LoopSpy.launched == 3
        assert _PollSpy.launched == 0  # poll never called
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_outreach_engine_joins_the_loops(make_settings):
    """3.2: the proactive engine rides the same stitch — five loops with it,
    and PROACTIVE_ENABLED=false is enforced INSIDE the engine's own gating
    (the loop task still exists, fire_once stays silent)."""
    loops, poll, settings = _rig(make_settings)
    tasks = start_background_loops(
        brief=loops["brief"],
        journaler=loops["journaler"],
        summarizer=loops["summarizer"],
        gmail_poll=poll,
        inbox=None,
        dispatcher=object(),
        classifier=object(),
        settings=settings,
        outreach=_LoopSpy(),  # 3.2 engine double — a run_forever loop
    )
    try:
        await asyncio.sleep(0.05)
        assert len(tasks) == 4  # summary + brief + journaler + outreach
        assert _LoopSpy.launched == 4  # outreach entered its loop too
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# --- pass-4: shutdown-mid-tick cleanliness -----------------------------------------


async def test_all_loops_cancel_cleanly_mid_tick(make_settings):
    """Every background loop must swallow ONLY CancelledError — a mid-tick
    cancel never leaks a wrapper exception into the shutdown gather."""
    import asyncio

    class TickLoop:
        def __init__(self):
            self.ticks = 0

        async def run_forever(self):
            while True:
                self.ticks += 1
                await asyncio.sleep(0.001)

    loops = {name: TickLoop() for name in ("brief", "journaler", "summarizer")}
    tasks = [asyncio.create_task(loop.run_forever()) for loop in loops.values()]
    await asyncio.sleep(0.02)  # let them tick
    for t in tasks:
        t.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, asyncio.CancelledError) or r is None for r in results), results
    assert all(loop.ticks > 0 for loop in loops.values())  # they genuinely ran


# --- M-4 (deferred queue): the REAL run_bot boots and shuts down --------------------


def _vault_factory(real_client, gh, built: list[dict], edges: list[httpx.AsyncClient]):
    """Wrap the REAL `VaultClient` constructor with a faked HTTP edge.

    Deliberately NOT a fake vault class: `VaultClient.__init__` still runs with
    the real repo/token/branch `run_bot` hands it, so this keeps proving the
    vault is constructible from settings. Only the network edge is swapped
    (test-guard rule 2: HTTP is a system boundary) — `helpers_vault.FakeGitHub`
    answers with real GitHub status codes, so status handling is still exercised.
    """

    def build(repo, token, *, branch="main", session=None):
        built.append({"repo": repo, "token": token, "branch": branch})
        edge = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
        edges.append(edge)
        # session=... -> _owns_session False, so VaultClient never owns it and
        # run_bot's own vault.aclose() stays a no-op; the test closes it.
        return real_client(repo, token, branch=branch, session=edge)

    return build


async def test_run_bot_boots_all_components_and_shuts_down(make_settings, monkeypatch, tmp_path):
    """The production entry assembles EVERYTHING — gateway, voice, vault,
    memory, writers, tools, coordinator, dispatcher, and all six background
    loops — and the finally cancels them cleanly. Polling is stubbed (a
    one-iteration mock); the vault's HTTP edge is stubbed; everything else is
    the REAL wiring.

    The vault fake exists because boot is NOT network-free: it issues one read
    for the dialect notes, one capabilities-manifest upsert and one upsert per
    per-tool skill guide — 31 sequential GitHub calls. Unfaked, the
    `.env.example` placeholder PAT 401s on every one of them (~1 s each), which
    is what burned this test's 30 s budget and failed it.
    """
    import asyncio as aio
    from unittest.mock import AsyncMock

    from helpers_vault import FakeGitHub

    from src import bot as bot_mod
    from src.memory import SARA_CAPABILITIES_PATH
    from src.skills.sara_tool_skills import SARA_SKILLS_DIR, build_skill_guides

    settings = make_settings(VAULT_LOCAL_PATH=str(tmp_path / "vault"))

    gh = FakeGitHub(repo=settings.vault_github_repo, branch=settings.vault_branch)
    built: list[dict] = []
    edges: list[httpx.AsyncClient] = []
    real_vault_client = bot_mod.VaultClient
    monkeypatch.setattr(bot_mod, "VaultClient", _vault_factory(real_vault_client, gh, built, edges))

    # stop polling after one loop tick; record the dispatcher it was built with
    started = aio.Event()
    real_build = bot_mod.build_dispatcher

    def build_spy(gateway, voice, settings_, **kwargs):
        started.set()
        return real_build(gateway, voice, settings_, **kwargs)

    monkeypatch.setattr(bot_mod, "build_dispatcher", build_spy)

    class _OneShotPoller:
        async def start_polling(self, bot, **kwargs):
            await aio.sleep(0.05)  # one brief tick — the loops get a heartbeat

    monkeypatch.setattr(bot_mod.Dispatcher, "start_polling", _OneShotPoller.start_polling)
    # a dead outbound bot never reaches Telegram (no network in tests)
    monkeypatch.setattr(bot_mod, "Bot", lambda token: AsyncMock())

    try:
        await aio.wait_for(bot_mod.run_bot(settings, bridge=None), timeout=30)
    finally:
        for edge in edges:
            await edge.aclose()

    assert started.is_set()  # the full wiring actually assembled

    # The REAL VaultClient was built from the REAL settings — the fake replaced
    # the socket, not the constructor.
    assert built == [
        {
            "repo": settings.vault_github_repo,
            "token": settings.vault_github_token.get_secret_value(),
            "branch": settings.vault_branch,
        }
    ]

    # ...and boot's vault WRITES landed. This is the half the old version could
    # never assert: every guide 401'd, so the manifest and all 29 guides
    # silently vanished and the test had nothing left to check.
    landed = set(gh.objects)
    assert SARA_CAPABILITIES_PATH in landed, "capabilities manifest never reached the vault"
    missing = {name for name in build_skill_guides() if f"{SARA_SKILLS_DIR}/{name}" not in landed}
    assert not missing, f"{len(missing)} per-tool guides never synced, e.g. {sorted(missing)[:3]}"
