"""Sprint-4 §4.2 / M4: dynamic capability expansion — owner hands Sara a credential,
Sara registers a background async task from natural-language Arabic cron WITHOUT
redeploy, fails loudly, and state survives restarts via the vault (ADR-15).

Boundaries: the vault runs over the FakeGitHub transport (real HTTP semantics); the
scheduler is REAL asyncio (lock, jobs, timeout); only the clock and the owner notifier
are faked."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from unittest import mock

import httpx
import pytest
from helpers_vault import FakeGitHub
from loguru import logger

from src.config import Settings
from src.expansion import (
    CAPABILITIES_STATE_PATH,
    RESERVED_TASK_NAMES,
    CapabilityScheduler,
    ExpansionError,
    parse_nl_cron,
)
from src.vault import VaultClient

TOKEN = "your-github-test-pat-abcdef0123456789"
CRED_ENV = "MY_NEW_API_KEY"
SECRET_VALUE = "sk-test-credential-value-0123456789"  # >= 16 chars, no whitespace


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def notify(self, text: str) -> None:
        self.sent.append(text)


def _vault() -> tuple[VaultClient, FakeGitHub]:
    gh = FakeGitHub()
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    return VaultClient("owner/vault-repo", TOKEN, session=session), gh


def _scheduler(vault, *, notifier=None, **kwargs) -> CapabilityScheduler:
    kwargs.setdefault("task_timeout_s", 2.0)
    return CapabilityScheduler(vault=vault, notifier=notifier or FakeNotifier(), **kwargs)


def _register(scheduler, settings: Settings, name: str = "weather-fetch", pipeline=None):
    async def _default_pipeline(ctx):
        pass

    return scheduler.register_capability(
        name=name,
        schedule_text="كل صباح 7",
        credential_env=CRED_ENV,
        pipeline=pipeline or _default_pipeline,
        settings=settings,
    )


async def test_nl_cron_parses_arabic_schedule():
    """AC1 — Arabic + English schedule phrasing parse; gibberish raises."""
    spec = parse_nl_cron("كل صباح 7")
    assert spec.kind == "daily"
    assert (spec.hour, spec.minute) == (7, 0)

    english = parse_nl_cron("every morning at 7")
    assert english.kind == "daily"
    assert (english.hour, english.minute) == (7, 0)

    weekly = parse_nl_cron("كل اثنين 9")
    assert weekly.kind == "weekly" and weekly.weekday == 0 and weekly.hour == 9

    hourly = parse_nl_cron("كل ساعة")
    assert hourly.kind == "hourly"

    with pytest.raises(ExpansionError):
        parse_nl_cron("كل شيء ما بيتشابه هسا")


async def test_task_registers_without_redeploy(make_settings):
    """AC2 — registration is observable in the live scheduler inventory, no restart."""
    vault, _gh = _vault()
    scheduler = _scheduler(vault)
    assert scheduler.inventory() == []
    with mock.patch.dict(os.environ, {CRED_ENV: SECRET_VALUE}):
        handle = await _register(scheduler, make_settings())
    assert scheduler.inventory() == ["weather-fetch"]
    assert handle.name == "weather-fetch"
    assert handle.enabled is True
    assert handle.spec.tz == "Asia/Amman"  # clock-zone pinned to settings.tz


async def test_invalid_credential_rejected_loudly(make_settings):
    """AC3 — missing/bad-format credential: ExpansionError, nothing registered, the
    secret VALUE never reaches any log."""
    vault, _gh = _vault()
    scheduler = _scheduler(vault)
    records: list = []
    handler_id = logger.add(records.append, level="DEBUG")
    try:
        with mock.patch.dict(os.environ, {}, clear=True), pytest.raises(ExpansionError):
            await _register(scheduler, make_settings())
        with mock.patch.dict(os.environ, {CRED_ENV: "short"}), pytest.raises(ExpansionError):
            await _register(scheduler, make_settings())
        assert scheduler.inventory() == []  # nothing registered
    finally:
        logger.remove(handler_id)
    blob = "".join(str(r) for r in records) + "".join(
        str(r.record["message"]) for r in records if hasattr(r, "record")
    )
    assert SECRET_VALUE not in blob
    assert CRED_ENV in blob  # the NAME is what's handled


async def test_task_failure_disables_and_logs(make_settings):
    """AC4 — failing pipeline: disabled after the attempt, loud log with the task
    name, owner notified once; further runs are no-ops until explicit re-enable."""
    vault, _gh = _vault()
    notifier = FakeNotifier()
    scheduler = _scheduler(vault, notifier=notifier)
    calls: list[dict] = []

    async def pipeline(ctx):
        calls.append(ctx)
        raise RuntimeError("boom")

    with mock.patch.dict(os.environ, {CRED_ENV: SECRET_VALUE}):
        handle = await _register(scheduler, make_settings(), pipeline=pipeline)
    captured: list = []
    hid = logger.add(captured.append, level="ERROR")
    try:
        ran = await scheduler.run_once("weather-fetch")
        assert ran is True
        assert calls, "pipeline never executed"
        assert handle.enabled is False
        assert "boom" in (handle.last_error or "")
        again = await scheduler.run_once("weather-fetch")
    finally:
        logger.remove(hid)
    assert again is False
    assert len(calls) == 1  # disabled tasks never re-execute
    assert notifier.sent, "owner never notified"
    assert len(notifier.sent) == 1
    assert any(
        rec.record["level"].name == "ERROR" and "weather-fetch" in rec.record["message"]
        for rec in captured
    )


async def test_task_output_files_to_vault(make_settings):
    """AC5 — the pipeline's output files a note to the vault via the 3.1 client."""
    vault, gh = _vault()
    scheduler = _scheduler(vault)

    async def pipeline(ctx):
        assert ctx["credential_env"] == CRED_ENV
        assert SECRET_VALUE not in str(ctx)  # only the NAME travels
        await ctx["vault"].upsert(
            "Studies/task-output.md", "fetched data", message="sara: task output"
        )

    with mock.patch.dict(os.environ, {CRED_ENV: SECRET_VALUE}):
        await _register(scheduler, make_settings(), pipeline=pipeline)
    await scheduler.run_once("weather-fetch")
    assert "Studies/task-output.md" in gh.objects


async def test_tasks_survive_restart_from_vault(make_settings):
    """AC6 — a fresh scheduler re-derives the registered task set from the vault."""
    vault, _gh = _vault()
    scheduler = _scheduler(vault)

    async def pipeline(ctx):
        pass

    with mock.patch.dict(os.environ, {CRED_ENV: SECRET_VALUE}):
        await _register(scheduler, make_settings(), pipeline=pipeline)
    assert scheduler.inventory() == ["weather-fetch"]

    restarted = _scheduler(vault)  # fresh process memory, same vault
    assert restarted.inventory() == []
    restored = await restarted.restore({"weather-fetch": pipeline})
    assert restored == ["weather-fetch"]
    handle = restarted.get("weather-fetch")
    assert handle is not None
    assert handle.credential_env == CRED_ENV
    assert handle.enabled is True
    assert handle.spec.kind == "daily" and handle.spec.hour == 7


async def test_task_budget_timeout_disables(make_settings):
    """AC7 — runaway task cancelled by the per-task timeout and disabled."""
    vault, _gh = _vault()
    notifier = FakeNotifier()
    scheduler = _scheduler(vault, notifier=notifier, task_timeout_s=0.05)
    captured: list = []

    async def runaway(ctx):
        await asyncio.sleep(5)

    with mock.patch.dict(os.environ, {CRED_ENV: SECRET_VALUE}):
        handle = await _register(scheduler, make_settings(), pipeline=runaway)
    hid = logger.add(captured.append, level="WARNING")
    try:
        ran = await scheduler.run_once("weather-fetch")
    finally:
        logger.remove(hid)
    assert ran is True
    assert handle.enabled is False
    assert any("weather-fetch" in rec.record["message"] for rec in captured)
    assert notifier.sent


async def test_reserved_names_refused(make_settings):
    """AC8 — reserved/owner-tier task names are refused (no shadowing internals)."""
    vault, _gh = _vault()
    scheduler = _scheduler(vault)
    assert RESERVED_TASK_NAMES
    for name in ("triage", "bridge", "telemetry"):
        assert name in RESERVED_TASK_NAMES
        with (
            mock.patch.dict(os.environ, {CRED_ENV: SECRET_VALUE}),
            pytest.raises(ExpansionError),
        ):
            await _register(scheduler, make_settings(), name=name)
    assert scheduler.inventory() == []


async def test_concurrent_registration_single_entry(make_settings):
    """AC9 — concurrent registrations serialize on one lock; no double-schedule."""
    vault, _gh = _vault()
    scheduler = _scheduler(vault)
    outcomes = []

    async def pipeline(ctx):
        pass

    with mock.patch.dict(os.environ, {CRED_ENV: SECRET_VALUE}):
        results = await asyncio.gather(
            _register(scheduler, make_settings(), pipeline=pipeline),
            _register(scheduler, make_settings(), pipeline=pipeline),
            return_exceptions=True,
        )
    for result in results:
        outcomes.append(isinstance(result, ExpansionError))
    assert sorted(outcomes) == [False, True]  # one wins, one refuses
    assert scheduler.inventory() == ["weather-fetch"]
    assert CAPABILITIES_STATE_PATH  # state path constant is the vault record


def test_next_run_advances():
    """Support — next-occurrence arithmetic: daily spec advances a day in its tz."""
    spec = parse_nl_cron("كل صباح 7")
    now = spec.now_tz() - timedelta(minutes=1)
    nxt = spec.next_after(now)
    assert nxt.hour == 7
    assert nxt > now
