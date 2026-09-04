"""Sprint-1 §1.1 AC5-AC6: health probe statuses; --health exits without polling."""

import json
import sys
import types

import httpx
from loguru import logger

from src import health
from src.health import healthcheck
from src.main import run

_REAL_ASYNC_CLIENT = httpx.AsyncClient  # captured pre-patch; _patch_gateway may stack


def _patch_gateway(monkeypatch, handler):
    """Route healthcheck's one-shot client through httpx.MockTransport(handler)."""

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_ASYNC_CLIENT(*args, **kwargs)

    monkeypatch.setattr(health.httpx, "AsyncClient", factory)


async def test_healthcheck_reports_gateway_status(monkeypatch, make_settings):
    """AC5: 200 -> ok/ok; connection refused -> unreachable/degraded + warning, no raise."""
    settings = make_settings()

    _patch_gateway(monkeypatch, lambda request: httpx.Response(200, json={"object": "list"}))
    monkeypatch.setattr(health.shutil, "which", lambda _name: "C:/ffmpeg/ffmpeg.exe")

    async def _probe_ok(_settings):
        return "ok"

    async def _probe_missing(_settings):
        return "missing"

    monkeypatch.setattr(health, "_probe_vault", _probe_ok)
    monkeypatch.setattr(health, "_probe_google", _probe_ok)
    report = await healthcheck(settings)
    assert report == {
        "gateway": "ok",
        "telegram_token": "set",
        "ffmpeg": "found",
        "vault": "ok",
        "google": "ok",
        "overall": "ok",
    }
    monkeypatch.setattr(health, "_probe_google", _probe_missing)

    def refused(request):
        raise httpx.ConnectError("connection refused")

    _patch_gateway(monkeypatch, refused)
    monkeypatch.setattr(health.shutil, "which", lambda _name: None)
    warnings: list = []
    sink_id = logger.add(warnings.append, level="WARNING")
    try:
        report = await healthcheck(settings)  # must not raise
    finally:
        logger.remove(sink_id)
    assert report["gateway"] == "unreachable"
    assert report["ffmpeg"] == "missing"
    assert report["overall"] == "degraded"
    assert warnings, "gateway failure must log at warning level"


async def test_main_dash_health_exits_without_polling(monkeypatch, make_settings, capsys):
    """AC6: --health prints JSON, exits 0/1 per status, never reaches the bot runner."""
    import src.main as main_mod

    settings = make_settings()
    monkeypatch.setattr(main_mod, "Settings", lambda: settings)

    sentinel = types.ModuleType("src.bot")  # runner lands with task 1.4
    polled: list = []

    async def fake_run_bot(s):
        polled.append(s)

    sentinel.run_bot = fake_run_bot
    monkeypatch.setitem(sys.modules, "src.bot", sentinel)

    _patch_gateway(monkeypatch, lambda request: httpx.Response(200))
    monkeypatch.setattr(health.shutil, "which", lambda _name: "ffmpeg-here")
    assert await run(["--health"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["overall"] == "ok"

    def refused(request):
        raise httpx.ConnectError("connection refused")

    _patch_gateway(monkeypatch, refused)
    monkeypatch.setattr(health.shutil, "which", lambda _name: None)
    assert await run(["--health"]) == 1
    second = json.loads(capsys.readouterr().out)
    assert second["gateway"] == "unreachable"

    assert polled == [], "--health must exit before the polling runner is invoked"


# --- deferred queue §13: health honesty (vault + Google state) ----------------------


async def test_health_reports_vault_and_google_states(make_settings, monkeypatch):
    """§13: /health must not read green while Gmail is actually failing —
    the vault token and the Google token cache report their real state."""

    from src.health import healthcheck

    settings = make_settings()

    async def _fail_vault(_settings):
        raise RuntimeError("vault down")

    async def _ok_vault(_settings):
        return "ok"

    # vault unreachable -> a loud degraded row, overall degraded
    monkeypatch.setattr("src.health._probe_vault", _fail_vault)
    report = await healthcheck(settings, probe_gateway=False)
    assert report["vault"] == "unreachable"
    assert report["overall"] == "degraded"

    # vault fine -> row ok
    monkeypatch.setattr("src.health._probe_vault", _ok_vault)
    report = await healthcheck(settings, probe_gateway=False)
    assert report["vault"] == "ok"


async def test_health_reports_google_state(make_settings, monkeypatch):
    """The Google token cache presence is part of the report — an absent
    cache is a 'missing' row (the honest cause of live Gmail failures),
    never a silent green."""
    from src.health import healthcheck

    settings = make_settings()

    async def _no_google(_settings):
        return "missing"  # no token cache

    async def _has_google(_settings):
        return "ok"

    monkeypatch.setattr("src.health._probe_google", _no_google)
    report = await healthcheck(settings, probe_gateway=False)
    assert report["google"] == "missing"

    monkeypatch.setattr("src.health._probe_google", _has_google)
    report = await healthcheck(settings, probe_gateway=False)
    assert report["google"] == "ok"
