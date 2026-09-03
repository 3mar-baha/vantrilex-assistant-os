"""Sprint-2 §2.1 AC1-AC2: consent URL + state, refresh-on-401, encrypted token cache.

All flows hermetic via httpx.MockTransport against a real GoogleSession —
the only boundary mocked is the Google wire (Rule 2: mock boundaries, not internals).
"""

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet

from src.google_auth import (
    AUTH_SCOPES,
    GoogleAPIError,
    GoogleAuthError,
    GoogleSession,
    GoogleTokens,
    build_consent_url,
    load_client_secret,
    load_tokens,
    save_tokens,
    verify_state,
)

FERNET_KEY = Fernet.generate_key()


@pytest.fixture
def client_secret(tmp_path):
    cfg = {
        "client_id": "123-your.apps.googleusercontent.com",
        "client_secret": "your-oauth-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
    path = tmp_path / "google_oauth_client.json"
    path.write_text(json.dumps({"installed": cfg}), encoding="utf-8")
    return path, cfg


def _settings(make_settings, tmp_path):
    return make_settings(
        VAULT_ENC_KEY=FERNET_KEY.decode(),
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "google_oauth_client.json"),
    )


def _token_path(settings) -> "Path":
    from src.google_auth import token_cache_path

    return token_cache_path(settings)


def test_consent_url_contains_scopes(client_secret):
    """AC1a: consent URL carries every scope + offline + consent + loopback
    redirect. Remediation 3.4: exactly THREE scopes — Drive/Contacts readonly
    were never consumed by the OS, so they left the consent screen."""
    _path, cfg = client_secret
    url = build_consent_url(cfg, port=8765, state="st4te")
    for scope in AUTH_SCOPES:
        assert f"scope={scope}" in url
    assert len(AUTH_SCOPES) == 3  # calendar + tasks + gmail.modify only
    assert "drive.readonly" not in url  # never consumed — pruned (3.4)
    assert "contacts.readonly" not in url
    assert "https://www.googleapis.com/auth/gmail.modify" in AUTH_SCOPES  # least-privilege
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765" in url
    assert "state=st4te" in url


def test_oauth_state_verified():
    """AC1b: a tampered callback state aborts before any token exchange."""
    issued = "token_urlsafe_value"
    verify_state(issued, issued)  # matching passes
    with pytest.raises(GoogleAuthError):
        verify_state(issued, "forged")


def test_load_client_secret_missing_loudly(tmp_path):
    with pytest.raises(GoogleAuthError):
        load_client_secret(tmp_path / "absent.json")


def test_load_client_secret_unwraps_installed(client_secret):
    path, cfg = client_secret
    assert load_client_secret(path) == cfg


def test_token_cache_encrypted_at_rest(make_settings, client_secret):
    """AC2b: cache round-trips; raw disk bytes carry NO plaintext token material."""
    tokens = GoogleTokens(access_token="PLAIN-at", refresh_token="PLAIN-rt", expires_at=1.0)
    path = _token_path(_settings(make_settings, client_secret[0].parent))
    save_tokens(path, tokens, enc_key=FERNET_KEY.decode())

    raw = path.read_bytes()
    assert b"PLAIN-at" not in raw and b"PLAIN-rt" not in raw
    assert load_tokens(path, enc_key=FERNET_KEY.decode()) == tokens

    path.write_bytes(b"corrupt-not-fernet")
    assert load_tokens(path, enc_key=FERNET_KEY.decode()) is None  # degraded startup, no crash


async def test_refresh_on_401_reuses_refresh_token_and_retries_once(make_settings, client_secret):
    """AC2: 401 -> refresh grant -> retried exactly once with the new bearer; cache rewritten."""
    _path, _cfg = client_secret
    settings = _settings(make_settings, _path.parent)
    save_tokens(
        _token_path(settings),
        GoogleTokens(access_token="stale-at", refresh_token="rt-keep", expires_at=0.0),
        enc_key=FERNET_KEY.decode(),
    )

    calls: list[tuple[str, httpx.Request, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            calls.append(("token", request, ""))
            body = request.content.decode()
            assert "grant_type=refresh_token" in body and "rt-keep" in body
            return httpx.Response(200, json={"access_token": "fresh-at", "expires_in": 3600})
        calls.append(("api", request, ""))
        if len(calls) == 1:
            return httpx.Response(401, json={"error": {"message": "expired"}})
        return httpx.Response(200, json={"items": []})

    session = GoogleSession(settings, transport=httpx.MockTransport(handler))
    result = await session.request("GET", "https://www.googleapis.com/calendar/v3/x")
    assert result == {"items": []}

    token_requests = [c for c in calls if c[0] == "token"]
    assert len(token_requests) == 1  # exactly one refresh grant
    api_calls = [c for c in calls if c[0] == "api"]
    assert len(api_calls) == 2  # original + single retry
    assert api_calls[-1][1].headers["authorization"] == "Bearer fresh-at"

    cache = load_tokens(_token_path(settings), enc_key=FERNET_KEY.decode())
    assert cache.access_token == "fresh-at"  # cache rewritten after refresh


async def test_second_401_after_refresh_raises_auth_error(make_settings, client_secret):
    """Refreshed retry still 401 -> GoogleAuthError (revoked grant), no infinite retry."""
    _path, _cfg = client_secret
    settings = _settings(make_settings, _path.parent)
    session = GoogleSession(
        settings,
        GoogleTokens(access_token="stale", refresh_token="rt", expires_at=0.0),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": {"message": "revoked"}})
        ),
    )
    with pytest.raises(GoogleAuthError):
        await session.request("GET", "https://www.googleapis.com/x")


async def test_api_error_wraps_non_2xx(make_settings, client_secret):
    """Non-401 API failure -> GoogleAPIError(status, excerpt) chained."""
    _path, _cfg = client_secret
    settings = _settings(make_settings, _path.parent)
    session = GoogleSession(
        settings,
        GoogleTokens(access_token="a", refresh_token=None, expires_at=0.0),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, text="boom-" + "x" * 400)
        ),
    )
    with pytest.raises(GoogleAPIError) as excinfo:
        await session.request("GET", "https://www.googleapis.com/x")
    assert excinfo.value.status == 500
    assert len(excinfo.value.body_excerpt) <= 300


async def test_proactive_refresh_single_flight(make_settings, client_secret):
    """AC6: concurrent callers near expiry -> exactly one token POST, all bearers fresh."""
    _path, _cfg = client_secret
    settings = _settings(make_settings, _path.parent)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "fresh-at", "expires_in": 3600})
        return httpx.Response(200, json={"ok": True})

    session = GoogleSession(
        settings,
        GoogleTokens(access_token="old-at", refresh_token="rt", expires_at=time.time() + 30),
        transport=httpx.MockTransport(handler),
    )
    await asyncio.gather(
        *(session.request("GET", "https://www.googleapis.com/x") for _ in range(5))
    )
    token_posts = [r for r in requests if r.url.host == "oauth2.googleapis.com"]
    assert len(token_posts) == 1
    api_calls = [r for r in requests if r.url.host != "oauth2.googleapis.com"]
    assert len(api_calls) == 5
    assert all(r.headers["authorization"] == "Bearer fresh-at" for r in api_calls)
