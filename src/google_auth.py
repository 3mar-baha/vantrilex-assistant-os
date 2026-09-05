"""Google OAuth + authenticated session (sprint-2 §2.1, foundation — not a skill).

Desktop loopback OAuth with state verification, refresh-once-on-401 session,
and the encrypted vault token cache (ADR-15): the token cache lives at
``{vault_local_path}/State/google_token.json.enc`` — Fernet-encrypted JSON
under VAULT_ENC_KEY, never plaintext on disk, never logged.
"""

import asyncio
import http.server
import json
import secrets
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Final

import httpx
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger
from pydantic import BaseModel

OAUTH_AUTH_URL: Final[str] = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL: Final[str] = "https://oauth2.googleapis.com/token"

# Three scopes (remediation 3.4): Calendar + Tasks + Gmail.modify — the OS
# reads no Drive/Contacts data anywhere, so those consent screens are noise.
AUTH_SCOPES: Final[tuple[str, ...]] = (
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.modify",
)


class GoogleAuthError(RuntimeError):
    pass


class GoogleAPIError(RuntimeError):
    def __init__(self, status: int, body_excerpt: str) -> None:
        super().__init__(f"Google API HTTP {status}: {body_excerpt}")
        self.status = status
        self.body_excerpt = body_excerpt


class GoogleTokens(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: float = 0.0
    scopes: list[str] = []


def token_cache_path(settings) -> Path:
    return Path(settings.vault_local_path) / "State" / "google_token.json.enc"


def load_client_secret(path: str | Path) -> dict:
    """Unwrap the {"installed": ...} desktop-client JSON; missing -> loud abort."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise GoogleAuthError(
            f"OAuth client secret not found/readable at {path} — download the desktop "
            "client JSON to config/google_oauth_client.json per RUNBOOK 'Google OAuth "
            "bootstrap'"
        ) from error
    cfg = raw.get("installed")
    if not cfg:
        raise GoogleAuthError(f"client secret JSON at {path} lacks the 'installed' block")
    return cfg


def build_consent_url(cfg: dict, port: int, state: str) -> str:
    """Loopback consent URL: the scopes joined into ONE space-separated
    scope param (Google rejects a repeated scope param: «OAuth 2 parameters
    can only have a single value: scope» — live 2026-09-05), offline +
    consent + state."""
    redirect_uri = urllib.parse.quote(f"http://localhost:{port}", safe="")
    scopes = urllib.parse.quote(" ".join(AUTH_SCOPES), safe="")
    return (
        f"{OAUTH_AUTH_URL}?client_id={cfg['client_id']}"
        f"&redirect_uri={redirect_uri}&response_type=code&scope={scopes}"
        f"&access_type=offline&prompt=consent&state={state}"
    )


def verify_state(expected: str, received: str | None) -> None:
    """Callback state must match the issued token_urlsafe value (CSRF guard)."""
    if not received or not secrets.compare_digest(received, expected):
        raise GoogleAuthError("OAuth state mismatch — callback rejected (possible CSRF)")


def _fernet(enc_key: str) -> Fernet:
    return Fernet(enc_key.encode())


def save_tokens(path: str | Path, tokens: GoogleTokens, *, enc_key: str) -> None:
    """Atomic tmp+replace write of the Fernet-sealed cache; chmod 600 best-effort."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sealed = _fernet(enc_key).encrypt(tokens.model_dump_json().encode())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(sealed)
    try:
        tmp.chmod(0o600)
    except OSError:  # non-POSIX filesystems: contents stay Fernet-sealed regardless
        pass
    tmp.replace(path)


def load_tokens(path: str | Path, *, enc_key: str) -> GoogleTokens | None:
    """Corrupt/missing -> warn + None (degraded startup, re-consent via RUNBOOK)."""
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return None
    try:
        return GoogleTokens.model_validate_json(_fernet(enc_key).decrypt(raw))
    except (InvalidToken, ValueError) as error:
        logger.warning("google token cache corrupt -> treating absent, re-consent: {}", error)
        return None


def _token_payload(response: httpx.Response, what: str) -> GoogleTokens:
    if response.status_code != 200:
        raise GoogleAuthError(f"Google {what} failed: HTTP {response.status_code}")
    data = response.json()
    return GoogleTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=time.time() + data.get("expires_in", 3600),
        scopes=data.get("scope", "").split() if data.get("scope") else [],
    )


async def exchange_code(http: httpx.AsyncClient, cfg: dict, code: str, port: int) -> GoogleTokens:
    response = await http.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"http://localhost:{port}",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        },
    )
    return _token_payload(response, "code exchange")


async def refresh_tokens(http: httpx.AsyncClient, cfg: dict, tokens: GoogleTokens) -> GoogleTokens:
    response = await http.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens.refresh_token or "",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        },
    )
    return _token_payload(response, "refresh grant")


async def authorize_interactive(settings) -> GoogleTokens:
    """Browser bootstrap: ephemeral loopback listener, consent URL, sealed save."""
    cfg = load_client_secret(Path(settings.google_oauth_client_json))
    state = secrets.token_urlsafe(24)
    captured: dict[str, str | None] = {}

    class _Loopback(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            captured["code"] = query.get("code", [None])[0]
            captured["state"] = query.get("state", [""])[0]
            captured["error"] = query.get("error", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write("تم تسجيل الدخول — يمكنك إغلاق هذه الصفحة.".encode())

        def log_message(self, *args) -> None:  # silence per-request stderr noise
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Loopback)
    port = server.server_address[1]
    threading.Thread(target=server.handle_request, daemon=True).start()

    print("افتح هذا الرابط في المتصفح وأكمل الموافقة:\n" + build_consent_url(cfg, port, state))
    deadline = time.monotonic() + 300
    try:
        while captured.get("code") is None and captured.get("error") is None:
            if time.monotonic() > deadline:
                raise GoogleAuthError("OAuth bootstrap timed out after 300s waiting for callback")
            await asyncio.sleep(0.1)
    finally:
        server.server_close()

    if captured.get("error"):
        raise GoogleAuthError(f"consent denied: {captured['error']}")
    verify_state(state, captured.get("state") or "")

    async with httpx.AsyncClient() as client:
        tokens = await exchange_code(client, cfg, captured["code"], port)
    save_tokens(token_cache_path(settings), tokens, enc_key=settings.vault_enc_key)
    logger.info("google tokens sealed to the vault state cache")
    return tokens


class GoogleSession:
    """Bearer session: proactive single-flight refresh + one retry on 401."""

    def __init__(
        self,
        settings,
        tokens: GoogleTokens | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._tokens = tokens or self._load_cached(settings)
        self._http = httpx.AsyncClient(transport=transport)
        self._lock = asyncio.Lock()

    @staticmethod
    def _load_cached(settings) -> GoogleTokens:
        return (
            load_tokens(token_cache_path(settings), enc_key=settings.vault_enc_key)
            or GoogleTokens()
        )

    @property
    def tokens(self) -> GoogleTokens:
        return self._tokens

    def _stale(self) -> bool:
        """Proactive threshold; expires_at==0 means unknown expiry (401 handles it)."""
        tokens = self._tokens
        return (
            bool(tokens.refresh_token)
            and bool(tokens.expires_at)
            and tokens.expires_at - 60 < time.time()
        )

    async def request(
        self, method: str, url: str, *, params: dict | None = None, json: dict | None = None
    ) -> Any:
        await self._refresh_proactive()
        response = await self._send(method, url, params=params, json=json)
        if response.status_code == 401:
            await self._refresh_on_401(bearer_sent=self._tokens.access_token)
            response = await self._send(method, url, params=params, json=json)
            if response.status_code == 401:
                raise GoogleAuthError(
                    "Google rejected the refreshed grant (401) — re-run the OAuth "
                    "bootstrap per RUNBOOK 'Google OAuth bootstrap'"
                )
        if response.status_code >= 400:
            raise GoogleAPIError(response.status_code, response.text[:300])
        return response.json() if response.content else None

    async def _send(
        self, method: str, url: str, *, params: dict | None = None, json: dict | None = None
    ) -> httpx.Response:
        return await self._http.request(
            method,
            url,
            params=params,
            json=json,
            headers={"authorization": f"Bearer {self._tokens.access_token}"},
        )

    async def _refresh_proactive(self) -> None:
        if not self._stale():
            return
        async with self._lock:
            if not self._stale():  # another caller refreshed while we waited on the lock
                return
            await self._do_refresh()

    async def _refresh_on_401(self, *, bearer_sent: str | None) -> None:
        async with self._lock:
            if self._tokens.access_token != bearer_sent:
                return  # another caller already refreshed this grant — just replay
            await self._do_refresh()

    async def _do_refresh(self) -> None:
        cfg = load_client_secret(Path(self._settings.google_oauth_client_json))
        fresh = await refresh_tokens(self._http, cfg, self._tokens)
        fresh.refresh_token = fresh.refresh_token or self._tokens.refresh_token
        fresh.scopes = fresh.scopes or self._tokens.scopes
        self._tokens = fresh
        save_tokens(token_cache_path(self._settings), fresh, enc_key=self._settings.vault_enc_key)
        logger.debug("google bearer refreshed (proactive or post-401)")


if __name__ == "__main__":
    from src.config import get_settings

    asyncio.run(authorize_interactive(get_settings()))
