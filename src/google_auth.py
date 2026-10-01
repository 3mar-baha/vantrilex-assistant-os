"""Google OAuth + authenticated session (sprint-2 §2.1, foundation — not a skill).

Desktop loopback OAuth with state verification, refresh-once-on-401 session,
and the encrypted vault token cache (ADR-15): the token cache lives at
``{vault_local_path}/State/google_token.json.enc`` — Fernet-encrypted JSON
under VAULT_ENC_KEY, never plaintext on disk, never logged.

Boot truthfulness (F-4 / C-6). Two separate facts are now established at
construction and at boot, and the report called the old code a no-op because it
established neither:

* **absent** — no client secret on disk. A supported pure-local deployment.
  Nothing raises; `probe_google` answers `healthy=False` and the Google tools
  return the honest ar-JO offline line.
* **broken** — a client secret that exists and cannot be used. `GoogleAuthError`
  at `GoogleSession` construction, so the fault surfaces at boot rather than at
  the owner's first calendar read.

The token cache is disposable with the vault root (ADR-15), so a container
without a `/app/vault` mount silently loses the grant and pays a browser
consent on every redeploy. `docs/15-ORACLE-DEPLOY.md` mounts it; this module
only records the path.
"""

import asyncio
import dataclasses
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

# F-4 / C-6 boot probe: the cheapest authenticated call that exists. It reads
# one field off the owner's calendar LIST (never an event, never owner data),
# and `maxResults=1` keeps the quota cost at the floor.
GOOGLE_PROBE_URL: Final[str] = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
GOOGLE_PROBE_TIMEOUT_S: Final[float] = 8.0

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


def client_secret_present(settings) -> bool:
    """Eager boot-time answer to "is the OAuth client secret usable?".

    Two answers, and the caller must keep them apart (F-4 / C-6):

    * **absent** — no file at that path. Returns ``False`` and raises nothing:
      a box deliberately running without Google is a supported deployment, and
      crashing it would be the regression this function exists to avoid.
    * **broken** — a file that exists and cannot be used. Raises
      ``GoogleAuthError`` NOW. Fail fast at boot beats discovering a wrong
      secret at the owner's first calendar read, minutes or hours later.

    ``load_client_secret`` already raises the typed error for unparseable JSON
    and a missing ``installed`` block. ``OSError`` (permissions, a directory in
    the file's place) is re-raised as the SAME class rather than escaping bare,
    so no ``except GoogleAuthError`` in this codebase is left dead.
    """
    path = Path(settings.google_oauth_client_json)
    if not path.exists():
        return False
    try:
        load_client_secret(path)
    except GoogleAuthError:
        raise
    except OSError as error:  # unreadable, or a directory where the file belongs
        raise GoogleAuthError(
            f"OAuth client secret at {path} is unreadable ({type(error).__name__}) — "
            "fix the file, or remove it to run without Google"
        ) from error
    return True


def describe_probe_failure(error: BaseException) -> str:
    """The probe's log-safe fault label: the fully-qualified exception CLASS.

    ``GoogleAPIError`` embeds up to 300 characters of a live response body and
    httpx errors embed the request URL, so ``str(error)`` can carry an account
    id, a query, or token material into the operator's log. The class name is
    what an operator acts on; the payload is what leaks.

    The module prefix is deliberate: it tells an httpx stall from a Google 403
    at a glance, which is the distinction that decides whether to retry or to
    re-consent. `__qualname__` only, never the message, never the arguments.
    """
    kind = type(error)
    return f"{kind.__module__}.{kind.__qualname__}"


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
    # F-4 / C-6: an "installed" block that parses is not yet a usable credential.
    # Without this check a JSON missing client_secret sails through construction
    # and dies as a bare KeyError inside the token exchange — at the owner's
    # first request, which is the discovery-at-first-request this rejects.
    missing = [key for key in ("client_id", "client_secret") if not cfg.get(key)]
    if missing:
        raise GoogleAuthError(
            f"client secret JSON at {path} is missing {' and '.join(missing)} — "
            "re-download the desktop client JSON per RUNBOOK 'Google OAuth bootstrap'"
        )
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
        # F-4 / C-6: the client secret is judged HERE, not at the first request.
        # Raises GoogleAuthError when it exists and is unusable; a missing file
        # is a pure-local deployment and raises nothing.
        self._credentials_present = client_secret_present(settings)
        self._tokens = tokens or self._load_cached(settings)
        self._http = httpx.AsyncClient(transport=transport)
        self._lock = asyncio.Lock()

    @property
    def credentials_present(self) -> bool:
        """False when the OAuth client secret is simply absent (pure-local)."""
        return self._credentials_present

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


@dataclasses.dataclass(frozen=True)
class GoogleBootHealth:
    """What boot actually established about Google (F-4 / C-6).

    ``healthy`` is the flag the tool surface reads. When it is False the
    OAuth-backed surfaces (calendar, tasks, gmail) are left UNBOUND so they
    answer the honest ar-JO offline line instead of raising mid-turn.

    ``session`` is always the constructed session whenever credentials were
    present, healthy or not: the Places / Custom Search surface authenticates
    with API KEYS, not this grant, so nulling it on an OAuth failure would
    break a feature that was working. Binding is the CALLER's decision, and
    ``healthy`` is what it decides on.

    ``reason`` is operator-readable and non-secret — a fault class or a
    one-clause explanation, never a path, a response body, or token material.
    """

    healthy: bool
    credentials_present: bool
    reason: str
    session: GoogleSession | None = None


async def probe_google(
    settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = GOOGLE_PROBE_TIMEOUT_S,
) -> GoogleBootHealth:
    """The REAL boot probe — it replaces the construct-and-hope the report
    called a no-op (F-4 / C-6).

    ``calendarList.list(maxResults=1)`` runs through the ordinary session path,
    so a stale token is refreshed first and a dead refresh token is discovered
    here rather than by the owner. The call is bounded by ``timeout``: a closed
    laptop lid costs boot a pause, never a hang.

    Returns a verdict rather than raising, with exactly one exception — a
    BROKEN client secret file, which `GoogleSession.__init__` rejects and which
    must stop a misconfigured deployment instead of leaving it serving an
    offline bot indefinitely.
    """
    session = GoogleSession(settings, transport=transport)  # raises on BROKEN
    if not session.credentials_present:
        return GoogleBootHealth(
            False, False, "OAuth client secret absent — running without Google", session
        )
    if not (session.tokens.access_token or session.tokens.refresh_token):
        # An authenticated call is impossible without a grant. Saying so is
        # cheaper than spending a request to learn it.
        return GoogleBootHealth(
            False, True, "no cached Google grant — run the OAuth bootstrap", session
        )
    try:
        async with asyncio.timeout(timeout):
            await session.request("GET", GOOGLE_PROBE_URL, params={"maxResults": 1})
    except (TimeoutError, httpx.HTTPError, GoogleAPIError, GoogleAuthError, ValueError) as error:
        return GoogleBootHealth(
            False, True, f"Google probe failed ({describe_probe_failure(error)})", session
        )
    return GoogleBootHealth(True, True, "Google probe ok", session)


if __name__ == "__main__":
    from src.config import get_settings

    asyncio.run(authorize_interactive(get_settings()))
