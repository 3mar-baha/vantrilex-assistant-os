"""Remediation 3.2 (owner directive 3 — proactive engine): Sara INITIATES.
A ~45-min smart loop asks the HEAVY model (nemotron) ONE question with real
context (today's ledger tail + User_Info excerpt + time): does the state
deserve a proactive message? Gates: PROACTIVE_ENABLED, 08:00-22:30 window,
cooldown, daily cap 3, calendar-conflict guard; model failure = silent skip;
NEVER claims actions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.config import Settings
from src.skills.proactive_outreach import ProactiveOutreach

AMMAN = ZoneInfo("Asia/Amman")
OWNER_ID = 123456789
TUE_2026_09_01 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)  # 13:00 Amman, in-window


class FakeBrain:
    """Scripted HEAVY verdict; counts calls."""

    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list = []

    async def chat(self, messages, *, tier, **kwargs):
        self.calls.append({"messages": messages, "tier": tier})
        return self.reply


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append(text)


class FakeVault:
    def __init__(self, files: dict | None = None, fail: bool = False):
        self.files = files or {}
        self.fail = fail

    async def read(self, path: str) -> str:
        if self.fail:
            raise RuntimeError("vault down")
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]


class FakeSuite:
    def __init__(self, events: list | None = None, error: Exception | None = None):
        self.events = events or []
        self.error = error

    async def list_events(self, start, end) -> list:
        if self.error is not None:
            raise self.error
        return self.events


class _Event:
    def __init__(self, summary="اجتماع"):
        self.summary = summary
        self.start = TUE_2026_09_01
        self.end = TUE_2026_09_01


def _settings(tmp_path, **env) -> Settings:
    from tests.conftest import ENV_EXAMPLE

    base = {name.lower(): value for name, value in ENV_EXAMPLE.items()}
    base.setdefault("vault_enc_key", "your-fernet-key")
    base.update({k.lower(): v for k, v in env.items()})
    return Settings(_env_file=None, **base)


def _rig(tmp_path, brain_reply="no", *, events=None, suite_error=None, **env):
    brain = FakeBrain(brain_reply)
    bot = FakeBot()
    vault = FakeVault(
        {
            "Daily_Logs/2026-09-01.md": "---\n---\n## دردشة 09:00\n\n**المالك:** شايف الرسالة؟",
            "02_Areas/Profile/User_Info.md": "---\n---\nالمالك عمر، مهندس.",
        }
    )
    suite = FakeSuite(events=events, error=suite_error)
    engine = ProactiveOutreach(
        brain=brain,
        bot=bot,
        chat_id=OWNER_ID,
        vault=vault,
        suite=suite,
        settings=_settings(tmp_path, **env),
        state_path=tmp_path / "State" / "proactive.json",
    )
    return engine, brain, bot


# --- gate contract -------------------------------------------------------------


async def test_out_of_window_blocks(tmp_path):
    """03:00 Amman (out of 08:00-22:30) — no HEAVY call, no send."""
    engine, brain, bot = _rig(tmp_path, brain_reply='{"should": true, "message": "هلا"}')
    night = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)  # 03:00 Amman
    assert await engine.fire_once(night) is False
    assert brain.calls == []  # the gate fires BEFORE the model call
    assert bot.sent == []


async def test_disabled_blocks(tmp_path):
    engine, brain, bot = _rig(
        tmp_path, brain_reply='{"should": true, "message": "هلا"}', PROACTIVE_ENABLED="false"
    )
    assert await engine.fire_once(TUE_2026_09_01) is False
    assert brain.calls == []
    assert bot.sent == []


async def test_daily_cap_blocks_after_three(tmp_path):
    """Three sends in one day — the fourth cycle never consults the model.
    Cooldown zeroed so the cap (not the spacing) is the gate under test."""
    engine, brain, bot = _rig(
        tmp_path,
        brain_reply='{"should": true, "message": "هلا عمر"}',
        PROACTIVE_COOLDOWN_MIN="0",
    )
    for _ in range(3):
        assert await engine.fire_once(TUE_2026_09_01) is True
    assert len(bot.sent) == 3
    assert await engine.fire_once(TUE_2026_09_01) is False
    assert len(brain.calls) == 3  # the 4th was gated before the model


async def test_cooldown_blocks_between_sends(tmp_path):
    engine, brain, _bot = _rig(
        tmp_path,
        brain_reply='{"should": true, "message": "هلا عمر"}',
        PROACTIVE_COOLDOWN_MIN="45",
    )
    assert await engine.fire_once(TUE_2026_09_01) is True
    soon = TUE_2026_09_01.replace(minute=30)  # 30 min later — inside cooldown
    assert await engine.fire_once(soon) is False
    assert len(brain.calls) == 1  # cooldown gates before the model


async def test_calendar_conflict_blocks_send(tmp_path):
    """Owner in a meeting — the initiative holds (calendar guard, §2.6 pattern)."""
    engine, _brain, bot = _rig(
        tmp_path, brain_reply='{"should": true, "message": "هلا"}', events=[_Event()]
    )
    assert await engine.fire_once(TUE_2026_09_01) is False
    assert bot.sent == []


async def test_heavy_yes_sends_one_warm_message(tmp_path):
    """HEAVY verdict should=true → EXACTLY one send, one HEAVY call, message
    from the verdict. Sara initiates — first time."""
    engine, brain, bot = _rig(
        tmp_path, brain_reply='{"should": true, "message": "عمور شايفك مشغول اليوم؟"}'
    )
    assert await engine.fire_once(TUE_2026_09_01) is True
    assert bot.sent == ["عمور شايفك مشغول اليوم؟"]
    assert len(brain.calls) == 1
    assert brain.calls[0]["tier"].name == "HEAVY"


async def test_heavy_no_stays_silent(tmp_path):
    engine, brain, bot = _rig(tmp_path, brain_reply='{"should": false}')
    assert await engine.fire_once(TUE_2026_09_01) is False
    assert bot.sent == []
    assert len(brain.calls) == 1  # consulted, decided no


async def test_model_failure_skips_silently(tmp_path):
    class DeadBrain(FakeBrain):
        async def chat(self, messages, *, tier, **kwargs):
            self.calls.append({"tier": tier})
            raise RuntimeError("nemotron down")

    brain = DeadBrain("x")
    bot = FakeBot()
    engine = ProactiveOutreach(
        brain=brain,
        bot=bot,
        chat_id=OWNER_ID,
        vault=FakeVault(
            {
                "Daily_Logs/2026-09-01.md": "---\n---\n**المالك:** مرحبا",
                "02_Areas/Profile/User_Info.md": "عمر",
            }
        ),
        suite=FakeSuite(),
        settings=_settings(tmp_path),
        state_path=tmp_path / "State" / "proactive.json",
    )
    assert await engine.fire_once(TUE_2026_09_01) is False
    assert bot.sent == []
    assert await engine.fire_once(TUE_2026_09_01) is False  # loop survives


async def test_unparsable_verdict_skips_silently(tmp_path):
    engine, _brain, bot = _rig(tmp_path, brain_reply="هههه ما بعرف")
    assert await engine.fire_once(TUE_2026_09_01) is False
    assert bot.sent == []


async def test_vault_down_degrades_to_no_context_still_works(tmp_path):
    """Vault read failure → the turn continues with time-only context (the
    outreach is best-effort, never crashes)."""
    brain = FakeBrain('{"should": true, "message": "هلا"}')
    bot = FakeBot()
    engine = ProactiveOutreach(
        brain=brain,
        bot=bot,
        chat_id=OWNER_ID,
        vault=FakeVault(fail=True),
        suite=FakeSuite(),
        settings=_settings(tmp_path),
        state_path=tmp_path / "State" / "proactive.json",
    )
    assert await engine.fire_once(TUE_2026_09_01) is True
    assert bot.sent == ["هلا"]


async def test_context_reaches_the_model(tmp_path):
    """The HEAVY prompt carries today's ledger tail + User_Info excerpt + time."""
    engine, brain, _bot = _rig(tmp_path, brain_reply='{"should": false}')
    await engine.fire_once(TUE_2026_09_01)
    prompt = brain.calls[0]["messages"][-1]["content"]
    assert "شايف الرسالة" in prompt  # today's ledger tail
    assert "مهندس" in prompt  # User_Info excerpt
    assert "13:0" in prompt or "13:" in prompt  # local time present


async def test_state_persists_across_instances(tmp_path):
    engine, _brain, _bot = _rig(tmp_path, brain_reply='{"should": true, "message": "هلا"}')
    assert await engine.fire_once(TUE_2026_09_01) is True
    # a "restart" — new instance, same state file — honors the cooldown
    engine2, _brain2, bot2 = _rig(tmp_path, brain_reply='{"should": true, "message": "هلا2"}')
    assert await engine2.fire_once(TUE_2026_09_01) is False  # cooldown held
    assert bot2.sent == []


def test_prompt_forbids_action_claims(tmp_path):
    """The outreach is a warm check-in — the prompt must forbid claiming actions."""
    engine, _brain, _bot = _rig(tmp_path)
    prompt = engine._verdict_prompt("ctx", "13:00")
    assert "ما تدّعي" in prompt or "لا تدّعي" in prompt or "لا تعتادي تنفيذ" in prompt


async def test_model_failure_backs_off_not_hammer(tmp_path):
    """Live 2026-09-03 21:52-22:00: a dead gateway made the loop retry the FULL
    chain every ~30s for 9 minutes (6 model calls/cycle). A failure must park
    the outreach for a backoff window — the next ticks inside it never consult
    the model."""
    calls: list = []

    class DeadBrain(FakeBrain):
        async def chat(self, messages, *, tier, **kwargs):
            calls.append(1)
            raise RuntimeError("gateway down")

    brain = DeadBrain("x")
    bot = FakeBot()
    engine = ProactiveOutreach(
        brain=brain,
        bot=bot,
        chat_id=OWNER_ID,
        vault=FakeVault(fail=True),
        suite=FakeSuite(),
        settings=_settings(tmp_path),
        state_path=tmp_path / "State" / "proactive.json",
    )
    t0 = TUE_2026_09_01
    assert await engine.fire_once(t0) is False  # first failure: one call, backoff starts
    assert len(calls) == 1
    for _ in range(5):  # five more ticks inside the backoff window
        assert await engine.fire_once(t0) is False
    assert len(calls) == 1  # parked — no hammering
    after = t0 + timedelta(minutes=31)  # past the 30-min backoff
    assert await engine.fire_once(after) is False  # one more attempt (still down)...
    assert len(calls) == 2  # ...and parks again


async def test_model_recovery_ends_backoff(tmp_path):
    """After the backoff, a healthy verdict flows normally."""

    class HalfDead(FakeBrain):
        fail = True

        async def chat(self, messages, *, tier, **kwargs):
            if self.fail:
                self.fail = False
                raise RuntimeError("gateway down")
            return await super().chat(messages, tier=tier, **kwargs)

    brain = HalfDead('{"should": true, "message": "هلا عمر"}')
    bot = FakeBot()
    engine = ProactiveOutreach(
        brain=brain,
        bot=bot,
        chat_id=OWNER_ID,
        vault=FakeVault(fail=True),
        suite=FakeSuite(),
        settings=_settings(tmp_path),
        state_path=tmp_path / "State" / "proactive.json",
    )
    t0 = TUE_2026_09_01
    assert await engine.fire_once(t0) is False  # fails, parks
    after = t0 + timedelta(minutes=31)
    assert await engine.fire_once(after) is True  # recovered — sends
    assert bot.sent == ["هلا عمر"]
