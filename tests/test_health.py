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
    report = await healthcheck(settings)
    assert report == {
        "gateway": "ok",
        "telegram_token": "set",
        "ffmpeg": "found",
        "overall": "ok",
    }

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
