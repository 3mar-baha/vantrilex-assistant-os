"""Sprint-1 §1.1 AC5-AC6: health probe statuses; --health exits without polling.

REWRITTEN for N3 / F-8's vocabulary, and the rewrite is DECLARED rather than
quiet. These four guards encoded the old words — `"ok"`, `"set"`, `"found"`,
`overall == "ok"` — which is precisely the presence-as-state claim the node
exists to delete. Their LAWS are unchanged and their names are unchanged:

* a green sweep is green and a refused gateway degrades with a warning and no
  raise;
* `--health` prints JSON, exits 0/1, and never reaches the bot runner;
* a crashing vault probe degrades its OWN row and the rollup, nothing else;
* the Google lane reports its real state rather than a file's existence.

What changed is which WORD each law compares against: `healthy` /
`misconfigured` / `unreachable`, closed and asserted in
`tests/test_health_truthfulness.py`. The probe seam is now the explicit
`transport=` argument instead of a monkeypatched `httpx.AsyncClient` factory,
because the lanes no longer share one client.

Every Settings here pins `VAULT_LOCAL_PATH` and `GOOGLE_OAUTH_CLIENT_JSON` at
non-existent paths: both default to the owner's real `./vault` and `./config`,
both exist on a working box, and a guard whose answer changes with the machine
is not a guard.
"""

import json
import sys
import types

import httpx
from loguru import logger

from src import health
from src.health import Lane, healthcheck
from src.main import run

_REAL_ASYNC_CLIENT = httpx.AsyncClient  # captured pre-patch; _patch_client may stack

_NOPE_VAULT = "./_nonexistent_test_vault"
_NOPE_CLIENT_JSON = "./_nonexistent_google_client.json"


def _settings(make_settings, **overrides: str):
    return make_settings(
        VAULT_LOCAL_PATH=_NOPE_VAULT,
        GOOGLE_OAUTH_CLIENT_JSON=_NOPE_CLIENT_JSON,
        **overrides,
    )


def _all_ok(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "api.telegram.org":
        return httpx.Response(200, json={"ok": True, "result": {"id": 1, "is_bot": True}})
    if host == "api.github.com":
        return httpx.Response(200, json={"login": "owner"})
    if host == "www.googleapis.com":
        return httpx.Response(200, json={"items": []})
    return httpx.Response(200, json={"object": "list"})


def _patch_client(monkeypatch, handler):
    """Route every one-shot client the probe opens through MockTransport(handler).
    Used only where the caller under test cannot pass a `transport` — i.e. the
    `--health` path, which reaches `healthcheck` through `src/main.py`."""

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_ASYNC_CLIENT(*args, **kwargs)

    monkeypatch.setattr(health.httpx, "AsyncClient", factory)


def _good_ffmpeg(monkeypatch):
    monkeypatch.setattr(health, "_probe_ffmpeg", _ffmpeg_healthy)


async def _ffmpeg_healthy(_settings, *, transport=None):
    return Lane(health.STATE_HEALTHY)


async def test_healthcheck_reports_gateway_status(monkeypatch, make_settings):
    """AC5: a 200 -> healthy/healthy; connection refused -> unreachable/degraded +
    warning, no raise."""
    settings = _settings(make_settings)
    _good_ffmpeg(monkeypatch)

    report = await healthcheck(settings, transport=httpx.MockTransport(_all_ok))
    assert report["lanes"]["gateway"]["state"] == health.STATE_HEALTHY
    assert report["overall"] == health.STATE_HEALTHY

    def refused(request):
        raise httpx.ConnectError("connection refused")

    async def _no_ffmpeg(_settings, *, transport=None):
        return Lane(health.STATE_MISCONFIGURED, reason="ffmpeg is not on PATH")

    monkeypatch.setattr(health, "_probe_ffmpeg", _no_ffmpeg)
    warnings: list = []
    sink_id = logger.add(warnings.append, level="WARNING")
    try:
        report = await healthcheck(  # must not raise
            settings, transport=httpx.MockTransport(refused)
        )
    finally:
        logger.remove(sink_id)
    assert report["lanes"]["gateway"]["state"] == health.STATE_UNREACHABLE
    assert report["lanes"]["ffmpeg"]["state"] == health.STATE_MISCONFIGURED
    assert report["overall"] != health.STATE_HEALTHY
    assert warnings, "gateway failure must log at warning level"


async def test_main_dash_health_exits_without_polling(monkeypatch, make_settings, capsys):
    """AC6: --health prints JSON, exits 0/1 per status, never reaches the bot runner."""
    import src.main as main_mod

    settings = _settings(make_settings)
    monkeypatch.setattr(main_mod, "Settings", lambda: settings)
    _good_ffmpeg(monkeypatch)

    sentinel = types.ModuleType("src.bot")  # runner lands with task 1.4
    polled: list = []

    async def fake_run_bot(s):
        polled.append(s)

    sentinel.run_bot = fake_run_bot
    monkeypatch.setitem(sys.modules, "src.bot", sentinel)

    _patch_client(monkeypatch, _all_ok)
    assert await run(["--health"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["overall"] == health.STATE_HEALTHY

    def refused(request):
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, refused)

    async def _no_ffmpeg(_settings, *, transport=None):
        return Lane(health.STATE_MISCONFIGURED, reason="ffmpeg is not on PATH")

    monkeypatch.setattr(health, "_probe_ffmpeg", _no_ffmpeg)
    assert await run(["--health"]) == 1
    second = json.loads(capsys.readouterr().out)
    assert second["lanes"]["gateway"]["state"] == health.STATE_UNREACHABLE

    assert polled == [], "--health must exit before the polling runner is invoked"


# --- deferred queue §13: health honesty (vault + Google state) ----------------------


async def test_health_reports_vault_and_google_states(make_settings, monkeypatch):
    """§13: /health must not read green while Gmail is actually failing — the
    vault lane and the Google lane report their real state."""

    settings = _settings(make_settings)

    async def _fail_vault(_settings, *, transport=None):
        raise RuntimeError("vault down")

    async def _ok_vault(_settings, *, transport=None):
        return Lane(health.STATE_HEALTHY)

    # vault unreachable -> a loud degraded row, overall degraded
    monkeypatch.setattr("src.health._probe_vault", _fail_vault)
    report = await healthcheck(
        settings, probe_gateway=False, transport=httpx.MockTransport(_all_ok)
    )
    assert report["lanes"]["vault"]["state"] == health.STATE_UNREACHABLE
    assert report["overall"] != health.STATE_HEALTHY

    # vault fine -> row healthy
    monkeypatch.setattr("src.health._probe_vault", _ok_vault)
    report = await healthcheck(
        settings, probe_gateway=False, transport=httpx.MockTransport(_all_ok)
    )
    assert report["lanes"]["vault"]["state"] == health.STATE_HEALTHY


async def test_health_reports_google_state(make_settings, monkeypatch):
    """The Google lane is part of the report — an absent OAuth secret is a stated
    `misconfigured` row on a lane the rollup does not gate, never a silent green.

    §13 called this row «missing», which was a FILENAME's status. What the owner
    needs to know is whether Google WORKS, and that is a three-state question
    now (N3 / F-8)."""
    settings = _settings(make_settings)

    async def _no_google(_settings, *, transport=None):
        return Lane(health.STATE_MISCONFIGURED, required=False, reason="no OAuth client secret")

    async def _has_google(_settings, *, transport=None):
        return Lane(health.STATE_HEALTHY)

    monkeypatch.setattr("src.health._probe_google", _no_google)
    report = await healthcheck(
        settings, probe_gateway=False, transport=httpx.MockTransport(_all_ok)
    )
    assert report["lanes"]["google"]["state"] == health.STATE_MISCONFIGURED
    assert report["reasons"]["google"] == "no OAuth client secret"

    monkeypatch.setattr("src.health._probe_google", _has_google)
    report = await healthcheck(
        settings, probe_gateway=False, transport=httpx.MockTransport(_all_ok)
    )
    assert report["lanes"]["google"]["state"] == health.STATE_HEALTHY
    assert "google" not in report["reasons"]
