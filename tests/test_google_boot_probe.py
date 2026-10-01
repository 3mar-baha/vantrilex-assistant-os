"""F-4 / C-6 — Google startup and deployment truthfulness.

Three credential states, and the difference between the first two is the whole
point of this file:

* **ABSENT** — the OAuth client JSON is not on disk at all (a box deliberately
  running pure-local). Degrade: ``healthy is False``, the bot still boots, the
  Google tools answer the honest ar-JO offline line. NEVER a crash.
* **BROKEN** — the file IS there and cannot be used. ``GoogleAuthError`` at
  ``GoogleSession`` CONSTRUCTION, boot fails fast: a silently wrong secret
  would otherwise be discovered at the owner's first request, not at boot.
* **UNREACHABLE** — the file is fine, a grant is cached, and the cheap
  authenticated probe still fails (network, quota, a dead refresh token).
  ``healthy is False`` plus the honest offline line. NEVER a crash.

Collapsing ABSENT and BROKEN either crashes every pure-local deployment or
reintroduces discovery-at-first-request — the two ends of the regression the
work order names, so each one is pinned by its own guard below.

**Nothing here reaches the network.** Every probe rides an injected
``httpx.MockTransport``, and the two states that must not dial out at all
(credentials absent, and "no grant cached") are asserted to have issued ZERO
requests — that assertion is what keeps the boot probe honest about cost.

The deployment half of the same defect (the image missing the config path, the
compose losing config and vault on redeploy) is pinned structurally: the
Dockerfile COPY line and the parsed compose volumes, not by a prose claim.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import httpx
import pytest
import yaml

from src.google_auth import (
    GoogleAuthError,
    GoogleSession,
    GoogleTokens,
    save_tokens,
    token_cache_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- fakes ------------------------------------------------------------------


async def _probe(settings, **kwargs):
    """Import at call time, deliberately: a module-level import of a not-yet-
    existing symbol would abort COLLECTION and every guard below would report
    zero runs instead of its own failure. Directive 2 wants the failure per
    guard, not one shared collection error."""
    from src.google_auth import probe_google

    return await probe_google(settings, **kwargs)


class _Spy:
    """Records every request the probe tries to make. Zero calls == no dial-out."""

    def __init__(self, handler) -> None:
        self.seen: list[httpx.Request] = []
        self._handler = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        return self._handler(request)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"kind": "calendar#calendarList", "items": []})


def _client_secret(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"installed":{"client_id":"cid.apps.googleusercontent.com",'
        '"client_secret":"shh","auth_uri":"https://accounts.google.com/o/oauth2/auth",'
        '"token_uri":"https://oauth2.googleapis.com/token"}}',
        encoding="utf-8",
    )
    return path


def _seeded(settings, tmp_path: Path, *, access: str | None = "tok-abc") -> str:
    """A box with BOTH a valid client secret and a cached grant."""
    _client_secret(Path(settings.google_oauth_client_json))
    if access is not None:
        save_tokens(
            token_cache_path(settings),
            GoogleTokens(access_token=access, refresh_token="r-abc", expires_at=9e9),
            enc_key=settings.vault_enc_key,
        )
    return settings.google_oauth_client_json


# --- state 1: ABSENT — degrade, never crash, never dial out -------------------


async def test_absent_credentials_do_not_raise_at_construction(make_settings, tmp_path):
    """A box with no OAuth client file is a supported deployment (pure-local).
    `GoogleSession` must construct; nothing about a missing file is an error."""
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "nowhere" / "google_oauth_client.json"),
    )

    session = GoogleSession(settings)  # must NOT raise

    assert session.credentials_present is False


async def test_absent_credentials_report_unhealthy_without_dialing_out(make_settings, tmp_path):
    """Absent is a VERDICT (unhealthy), not a crash — and the probe must not
    spend a request to learn something it already knows."""
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "nowhere" / "google_oauth_client.json"),
    )
    spy = _Spy(_ok)

    health = await _probe(settings, transport=spy.transport)

    assert health.healthy is False
    assert health.credentials_present is False
    assert health.reason  # an operator-readable reason, never empty
    assert spy.seen == [], "absent credentials must not trigger any network call"


async def test_absent_credentials_never_reach_a_missing_grant_for_a_token_request(
    make_settings, tmp_path
):
    """No credentials AND no cached grant: still zero requests. The probe
    short-circuits before the transport exists."""
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "nowhere" / "google_oauth_client.json"),
    )
    spy = _Spy(_ok)

    await _probe(settings, transport=spy.transport)

    assert spy.seen == []


# --- state 2: BROKEN — typed error, fail fast, at CONSTRUCTION ----------------


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("{not json at all", id="unparseable"),
        pytest.param('{"web": {"client_id": "x"}}', id="no-installed-block"),
        pytest.param('{"installed": {"client_id": "x"}}', id="installed-without-secret"),
    ],
)
async def test_broken_credentials_raise_the_existing_typed_error_at_construction(
    make_settings, tmp_path, content
):
    """The file exists and is unusable -> GoogleAuthError NOW, not at the owner's
    first calendar read. Asserted on the EXISTING class: a parallel hierarchy
    would leave every `except GoogleAuthError` in the codebase dead."""
    secret = tmp_path / "config" / "google_oauth_client.json"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(content, encoding="utf-8")
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(secret),
    )

    with pytest.raises(GoogleAuthError) as raised:
        GoogleSession(settings)

    assert type(raised.value) is GoogleAuthError, "the established class, not a subclass"
    assert isinstance(raised.value, RuntimeError)


async def test_unreadable_credentials_raise_the_typed_error_not_a_bare_oserror(
    make_settings, tmp_path
):
    """A path that exists but cannot be read is BROKEN, not ABSENT. The typed
    error is the whole reason `path.exists()` is checked first — a bare
    PermissionError would escape every `except GoogleAuthError` handler."""
    secret = tmp_path / "config" / "google_oauth_client.json"
    secret.mkdir(parents=True)  # a DIRECTORY where the JSON should be
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(secret),
    )

    with pytest.raises(GoogleAuthError):
        GoogleSession(settings)


async def test_broken_credentials_fail_the_boot_fast(make_settings, tmp_path):
    """`build_google_stack` propagates the typed error instead of degrading: a
    broken secret is an operator fault, and hiding it re-creates the silent
    discovery this milestone exists to end."""
    from src.bot import build_google_stack

    secret = tmp_path / "config" / "google_oauth_client.json"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("{oops", encoding="utf-8")
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(secret),
    )

    with pytest.raises(GoogleAuthError):
        await build_google_stack(settings)


# --- state 3: the probe really fires an authenticated call --------------------


async def test_probe_issues_exactly_one_authenticated_calendar_list_call(
    make_settings, tmp_path
):
    """THE anti-no-op guard. The pre-F-4 boot code constructed a session and
    hoped; this pins that a real bearer-authenticated `calendarList.list` with
    maxResults=1 now leaves the box at boot. Reverting the probe to a
    construct-and-hope no-op turns this RED."""
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
    )
    _seeded(settings, tmp_path)
    spy = _Spy(_ok)

    health = await _probe(settings, transport=spy.transport)

    assert health.healthy is True, health.reason
    assert health.credentials_present is True
    assert len(spy.seen) == 1, "the probe must make exactly one cheap call"
    sent = spy.seen[0]
    assert sent.method == "GET"
    assert "calendarList" in str(sent.url)
    assert sent.url.params["maxResults"] == "1", "the cheap call must stay cheap"
    assert sent.headers["authorization"] == "Bearer tok-abc"


async def test_probe_failure_marks_unhealthy_without_raising(make_settings, tmp_path):
    """Credentials fine, grant cached, Google unreachable -> unhealthy, no
    exception escapes the boot. The bot must degrade, not die."""
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
    )
    _seeded(settings, tmp_path)
    spy = _Spy(lambda request: httpx.Response(503, json={"error": "backendError"}))

    health = await _probe(settings, transport=spy.transport)

    assert health.healthy is False
    assert health.reason
    assert health.session is None


async def test_probe_timeout_marks_unhealthy_without_raising(make_settings, tmp_path):
    """A hung network is the common case on a laptop lid-closed; it must cost
    boot a bounded pause, never an exception."""
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
    )
    _seeded(settings, tmp_path)

    def _hang(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated stall", request=request)

    health = await _probe(settings, transport=_Spy(_hang).transport, timeout=0.05)

    assert health.healthy is False
    assert health.session is None


async def test_no_cached_grant_is_unhealthy_and_never_dials_out(make_settings, tmp_path):
    """An authenticated call is impossible without a grant, and pretending
    otherwise would spend a request to learn it. Stated as a law so the cheap
    short-circuit is a decision, not an accident."""
    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
    )
    _client_secret(Path(settings.google_oauth_client_json))
    spy = _Spy(_ok)

    health = await _probe(settings, transport=spy.transport)

    assert health.healthy is False
    assert spy.seen == []


# --- the tool surface reads the verdict ---------------------------------------


async def test_unhealthy_probe_binds_no_oauth_surface(make_settings, tmp_path):
    from src.bot import build_google_stack

    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
    )
    _seeded(settings, tmp_path)
    spy = _Spy(lambda request: httpx.Response(503, json={}))

    stack = await build_google_stack(settings, transport=spy.transport)

    assert stack.healthy is False
    assert stack.suite is None, "a broken OAuth grant must never reach the tools"
    assert stack.inbox is None
    assert stack.composer is None


async def test_healthy_probe_binds_the_oauth_surfaces(make_settings, tmp_path):
    from src.bot import build_google_stack
    from src.google_suite import GoogleSuite

    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
    )
    _seeded(settings, tmp_path)

    stack = await build_google_stack(settings, transport=_Spy(_ok).transport)

    assert stack.healthy is True, stack.reason
    assert isinstance(stack.suite, GoogleSuite)
    assert stack.inbox is not None
    assert stack.composer is not None


async def test_unhealthy_oauth_leaves_the_key_driven_cloud_surface_bound(
    make_settings, tmp_path
):
    """Places/CSE authenticate with API KEYS, not the OAuth grant. Nulling the
    cloud surface on an OAuth failure would break a working feature for a box
    that holds a Places key and has never run the OAuth bootstrap."""
    from src.bot import build_google_stack
    from src.google_cloud_client import GoogleCloudClient

    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
        GOOGLE_PLACES_KEY="places-key-fixture",
    )
    _seeded(settings, tmp_path)

    stack = await build_google_stack(
        settings, transport=_Spy(lambda request: httpx.Response(503, json={})).transport
    )

    assert stack.healthy is False
    assert isinstance(stack.cloud, GoogleCloudClient)


async def test_unhealthy_google_answers_the_honest_line_and_never_raises(
    make_settings, tmp_path
):
    """The end-to-end law, against the REAL ToolRegistry: with health False the
    calendar tool returns the honest ar-JO offline line. It must not raise, and
    it must not return the generic crash line (`TOOL_FAIL_AR`) either — that is
    exactly what an unbound-versus-broken mix-up looks like from the owner's
    Telegram."""
    from src.bot import build_google_stack
    from src.tools import GOOGLE_OFFLINE_AR, TOOL_FAIL_AR, ToolRegistry

    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "config" / "google_oauth_client.json"),
    )
    _seeded(settings, tmp_path)
    spy = _Spy(lambda request: httpx.Response(503, json={}))

    stack = await build_google_stack(settings, transport=spy.transport)
    tools = ToolRegistry(suite=stack.suite, inbox=stack.inbox, composer=stack.composer)

    # the handler itself must not raise — not merely be swallowed by ToolRegistry.call
    direct = await tools._do_calendar("")
    assert direct == GOOGLE_OFFLINE_AR

    assert await tools.call("calendar") == GOOGLE_OFFLINE_AR
    assert await tools.call("calendar") != TOOL_FAIL_AR
    assert await tools.call("tasks") == GOOGLE_OFFLINE_AR
    assert await tools.call("gmail") == GOOGLE_OFFLINE_AR


async def test_absent_credentials_boot_the_bot_and_answer_honestly(make_settings, tmp_path):
    """The regression the work order calls out: a box intentionally running
    without Google must NOT crash, and must still be polite in Jordanian."""
    from src.bot import build_google_stack
    from src.tools import GOOGLE_OFFLINE_AR, ToolRegistry

    settings = make_settings(
        VAULT_LOCAL_PATH=str(tmp_path / "vault"),
        GOOGLE_OAUTH_CLIENT_JSON=str(tmp_path / "nowhere" / "google_oauth_client.json"),
    )
    spy = _Spy(_ok)

    stack = await build_google_stack(settings, transport=spy.transport)
    tools = ToolRegistry(suite=stack.suite, inbox=stack.inbox)

    assert stack.healthy is False
    assert spy.seen == []
    assert await tools.call("calendar") == GOOGLE_OFFLINE_AR


def test_the_honest_offline_line_is_arabic_and_leaks_nothing():
    """Sara's voice is a standing invariant, and the offline line is what the
    owner sees when Google is down — it must not become an English error string,
    and it must not name a path, a file, or a token."""
    from src.tools import GOOGLE_OFFLINE_AR

    assert GOOGLE_OFFLINE_AR == "الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل"
    arabic = sum(1 for ch in GOOGLE_OFFLINE_AR if "؀" <= ch <= "ۿ")
    assert arabic >= len(GOOGLE_OFFLINE_AR) * 0.8, "not a translated English sentence"
    assert not re.search(r"[A-Za-z]{2,}", GOOGLE_OFFLINE_AR), "no English words"
    for leak in ("/", "\\", ".json", "config", "vault", "token", "Bearer", "http"):
        assert leak not in GOOGLE_OFFLINE_AR, f"the offline line leaks {leak!r}"


def test_the_boot_failure_log_line_names_no_path_or_secret():
    """The reason string reaches the operator's log, so it is pinned to carry the
    FAULT CLASS only — never the secret path or any token material."""
    from src.google_auth import describe_probe_failure

    described = describe_probe_failure(httpx.ReadTimeout("token abc123 leaked"))
    assert "abc123" not in described
    assert "/" not in described and "\\" not in described
    assert described == "httpx.ReadTimeout"


# --- deployment truthfulness: the image and the compose -----------------------


def _dockerfile_lines() -> list[str]:
    return (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()


def test_dockerfile_copies_the_config_path_into_the_image():
    """The container has to be able to FIND `config/google_oauth_client.json`
    (src/config.py's documented default) or it can never authenticate. Pre-F-4
    the Dockerfile had no config line at all."""
    copies = [
        line.split()[2]
        for line in _dockerfile_lines()
        if line.strip().upper().startswith("COPY ") and len(line.split()) >= 3
    ]
    assert any(
        dest.rstrip("/") in ("/app/config", "app/config") for dest in copies
    ), f"no COPY lands the config path in the image; destinations={copies}"


def test_dockerfile_never_bakes_the_oauth_client_secret_into_an_image_layer():
    """CLAUDE.md §2.2 — OAuth client credentials are never committed, and an
    image layer is the same leak with a longer half-life (`docker save` keeps it
    forever). The tracked, non-secret whitelist is baked; the secret is a
    runtime mount."""
    offenders = [
        line
        for line in _dockerfile_lines()
        if "google_oauth_client" in line or re.search(r"COPY\s+config/?\s", line)
    ]
    assert offenders == [], f"the OAuth secret would be baked into the image: {offenders}"


def _gitignore_matches(relative: str) -> str | None:
    """Return the .gitignore rule that ignores `relative`, or None."""
    for raw in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
        rule = raw.strip()
        if not rule or rule.startswith("#") or rule.startswith("!"):
            continue
        pattern = rule.rstrip("/")
        if fnmatch.fnmatch(relative, pattern) or Path(relative).match(pattern):
            return rule
    return None


def test_the_oauth_client_json_stays_gitignored_after_the_dockerfile_change():
    """The work order's question, answered by a law: adding a config COPY to the
    Dockerfile must never make `config/google_oauth_client.json` committable."""
    assert _gitignore_matches("config/google_oauth_client.json") is not None


def _compose_snippet() -> dict:
    text = (REPO_ROOT / "docs" / "15-ORACLE-DEPLOY.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\n(.*?)```", text, flags=re.DOTALL)
    assert blocks, "no yaml block in the Oracle deploy guide"
    for block in blocks:
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict) and "services" in parsed:
            return parsed
    raise AssertionError("no compose-shaped yaml block (a `services:` key) in the guide")


def test_oracle_compose_mounts_the_config_and_vault_volumes():
    """ADR-15 puts the core on a disposable filesystem: without these two mounts
    the OAuth client secret AND the encrypted token cache are destroyed on every
    `docker compose up -d`, which means a browser consent every single redeploy.
    Parsed as YAML, not string-matched, so a reformatted-but-equivalent snippet
    stays green and a removed volume goes red."""
    sara = _compose_snippet()["services"]["sara"]
    mounts = [str(v) for v in (sara.get("volumes") or [])]
    assert mounts, "the sara service mounts nothing: config and vault are disposable"
    container_paths = [m.split(":")[1] for m in mounts]
    assert "/app/config" in container_paths, f"no /app/config mount: {mounts}"
    assert "/app/vault" in container_paths, f"no /app/vault mount: {mounts}"


def test_the_deploy_guide_explains_the_re_auth_cost_of_the_token_cache():
    """The token cache is Fernet-sealed under the vault root
    (`{vault_local_path}/State/google_token.json.enc`). Losing /app/vault means
    losing it, and the report's item 5 is explicit: silence is not an acceptable
    answer. A mounted vault is the answer, and the guide has to say so."""
    text = (REPO_ROOT / "docs" / "15-ORACLE-DEPLOY.md").read_text(encoding="utf-8")
    assert "google_token.json.enc" in text, "the re-auth cost is undocumented"
    assert "State" in text


def test_remediation_plan_records_c6():
    """The audit finding gets a tracked entry, so C-6 cannot quietly stay
    unaddressed while its code lands."""
    text = (REPO_ROOT / "docs" / "REMEDIATION_PLAN.md").read_text(encoding="utf-8")
    assert "C-6" in text