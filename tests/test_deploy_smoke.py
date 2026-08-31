"""Sprint-4 §4.4b deploy smoke: five health checks turned into an exit code. The
doubles live at the httpx edge (MockTransport); the per-check timeout and the
secret redaction paths are exercised for real."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import deploy_smoke
from deploy_smoke import CheckResult, run_all

TELEGRAM_TOKEN = "your-telegram-token-value-0123456789"
GH_TOKEN = "your-github-pat-value-0123456789"
BRIDGE = "your-bridge-token-value-0123456789"
SECRET_SETTINGS = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_TOKEN,
    "VAULT_GITHUB_TOKEN": GH_TOKEN,
    "BRIDGE_TOKEN": BRIDGE,
}
CHECK_ORDER = ["gateway", "telegram", "vault", "google_token_cache", "space_health"]


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok_handler(request: httpx.Request) -> httpx.Response:
    if "getMe" in str(request.url):
        return httpx.Response(200, json={"ok": True})
    return httpx.Response(200, json={"data": []})


def _green_clients() -> dict[str, httpx.AsyncClient]:
    return {name: _client(_ok_handler) for name in ("gateway", "telegram", "vault", "space_health")}


async def _close(clients: dict[str, httpx.AsyncClient]) -> None:
    for client in clients.values():
        await client.aclose()


async def test_all_green_exits_zero(make_settings, tmp_path, monkeypatch):
    """AC7 (green half) — all five checks green, every check named, in order."""
    settings = make_settings(SPACE_URL="https://sara-example.hf.space", **SECRET_SETTINGS)
    cache = tmp_path / "google_token.json.enc"
    cache.write_bytes(b"sealed")
    monkeypatch.setattr(deploy_smoke, "token_cache_path", lambda _settings: cache)
    clients = _green_clients()
    try:
        results = await run_all(settings, timeout_s=5.0, clients=clients)
    finally:
        await _close(clients)
    assert [result.name for result in results] == CHECK_ORDER
    assert all(result.ok for result in results), [r.detail for r in results]


async def test_single_failure_exits_one_others_still_run(make_settings, tmp_path, monkeypatch):
    """AC7 (red half) — one failing check never masks the rest; the verdict exits 1."""
    settings = make_settings(SPACE_URL="https://sara-example.hf.space", **SECRET_SETTINGS)
    cache = tmp_path / "google_token.json.enc"
    cache.write_bytes(b"sealed")
    monkeypatch.setattr(deploy_smoke, "token_cache_path", lambda _settings: cache)

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}")

    clients = {
        "gateway": _client(broken),
        "telegram": _client(_ok_handler),
        "vault": _client(_ok_handler),
        "space_health": _client(_ok_handler),
    }
    try:
        results = await run_all(settings, timeout_s=5.0, clients=clients)
    finally:
        await _close(clients)
    by_name = {result.name: result for result in results}
    assert set(by_name) == set(CHECK_ORDER), "every check runs even after one fails"
    assert by_name["gateway"].ok is False
    assert by_name["telegram"].ok and by_name["vault"].ok and by_name["space_health"].ok
    assert by_name["google_token_cache"].ok


def test_main_exit_codes(make_settings, monkeypatch):
    """AC7 — the verdict: exit 0 iff every check is green."""
    settings = make_settings(**SECRET_SETTINGS)
    red = [CheckResult("gateway", False, "models endpoint HTTP 500")] + [
        CheckResult(name, True, "ok") for name in CHECK_ORDER[1:]
    ]

    async def fake_run(_settings, **_kwargs):
        return red

    monkeypatch.setattr(deploy_smoke, "run_all", fake_run)
    assert deploy_smoke.main(settings=settings) == 1

    async def fake_green(_settings, **_kwargs):
        return [CheckResult(name, True, "ok") for name in CHECK_ORDER]

    monkeypatch.setattr(deploy_smoke, "run_all", fake_green)
    assert deploy_smoke.main(settings=settings) == 0


async def test_timeout_bounded_per_check(make_settings, tmp_path, monkeypatch):
    """AC7 — a hung check becomes a failed CheckResult bounded by the per-check
    budget, and the other checks still answer."""
    settings = make_settings(SPACE_URL="https://sara-example.hf.space", **SECRET_SETTINGS)
    cache = tmp_path / "google_token.json.enc"
    cache.write_bytes(b"sealed")
    monkeypatch.setattr(deploy_smoke, "token_cache_path", lambda _settings: cache)

    async def hang(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(30)

    clients = {
        "gateway": _client(hang),
        "telegram": _client(_ok_handler),
        "vault": _client(_ok_handler),
        "space_health": _client(_ok_handler),
    }
    try:
        results = await run_all(settings, timeout_s=0.2, clients=clients)
    finally:
        await _close(clients)
    by_name = {result.name: result for result in results}
    assert by_name["gateway"].ok is False
    assert "timed out" in by_name["gateway"].detail
    assert all(by_name[name].ok for name in CHECK_ORDER[1:])


async def test_failure_details_redacted(make_settings):
    """AC8 — httpx errors embed the FULL request URL (including the bot token); the
    Settings-aware masker screens every detail before it lands."""
    settings = make_settings(**SECRET_SETTINGS)

    def leaking(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"connection refused while fetching {request.url}")

    client = _client(leaking)
    try:
        result = await deploy_smoke.check_telegram(settings, client=client)
    finally:
        await client.aclose()
    assert result.ok is False
    assert TELEGRAM_TOKEN not in result.detail, "bot token leaked into the smoke detail"
    assert "api.telegram.org" in result.detail, "host + path class remain for debugging"


def test_masker_strips_every_owner_secret(make_settings):
    """AC8 — the masker strips all three owner secrets, never just the convenient one."""
    settings = make_settings(**SECRET_SETTINGS)
    mask = deploy_smoke._masker(settings)
    blob = f"t={TELEGRAM_TOKEN} g={GH_TOKEN} b={BRIDGE}"
    masked = mask(blob)
    for secret in (TELEGRAM_TOKEN, GH_TOKEN, BRIDGE):
        assert secret not in masked
    assert masked.count("***") == 3


async def test_space_health_skipped_when_not_hosted(make_settings):
    """Support — without SPACE_URL the check reports a skipped-healthy local run."""
    settings = make_settings(**SECRET_SETTINGS)
    result = await deploy_smoke.check_space_health(settings)
    assert result.ok is True
    assert "skip" in result.detail.lower()


async def test_vault_check_requires_200(make_settings):
    """Support — a non-200 from the vault repo endpoint fails the check honestly."""
    settings = make_settings(**SECRET_SETTINGS)

    def forbidden(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {GH_TOKEN}"
        return httpx.Response(404, json={"message": "Not Found"})

    client = _client(forbidden)
    try:
        result = await deploy_smoke.check_vault(settings, client=client)
    finally:
        await client.aclose()
    assert result.ok is False
    assert "404" in result.detail
