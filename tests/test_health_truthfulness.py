"""N3 / F-8 — deploy truthfulness: the health probe must distinguish a key that is
PRESENT from a key that WORKS.

The node exists because `src/health.py` reported ``telegram_token: "set"`` for a
token that was set AND revoked, and because `src/main.py`'s `/health` responder
answered ``200 {"status":"ok"}`` unconditionally — a body that could not disagree
with reality, so it was not evidence of anything.

LAW 1 — the vocabulary is CLOSED. Exactly three values, and no lane may report a
fourth:

  healthy        proven working; a real call succeeded
  misconfigured  determinable and wrong (present but refused; absent when required)
  unreachable    COULD NOT BE DETERMINED. Never healthy. Never a vague "ok".

LAW 2 — fail closed. Anything that cannot be proven working is not healthy.

LAW 3 — the two failure states are DISTINGUISHABLE. A refused key and an
unreachable network are different operator problems; collapsing them into one
"not ok" is the vagueness this node deletes.

LAW 4 — no secret leaves the probe. Not the token, not the header value, not the
probe URL (the Telegram token lives in its path), not a response body, not a path.

LAW 5 — no new rate-limit path. The `/health` endpoint reads a TTL cache and never
probes per poll.

Every guard here names what it proves. No test reaches the network: every remote
lane is driven through `httpx.MockTransport`, the ffmpeg lane through a launcher
double, and `tests/conftest.py`'s hermetic guard would raise on a real socket.
"""

from __future__ import annotations

import asyncio
import contextlib
import http.client
import json
import sys
import time
import types

import httpx
import pytest
from cryptography.fernet import Fernet
from loguru import logger

from src import health, main as main_mod
from src.google_auth import GoogleTokens, save_tokens

# ── doubles ────────────────────────────────────────────────────────────────────────

#: A secret-shaped Telegram token: real Telegram tokens are `<id>:<35 chars>`.
TG_TOKEN = "9988776655:AAtelegramTokenValueThatMustNeverAppear"
#: A GitHub fine-grained PAT, `ghp_`-shaped so `src.vault.redact_secret`'s generic
#: pass WOULD also catch it — this guard does not rely on that pass firing.
GH_PAT = "ghp_" + "A" * 36
#: The marker a Google 403 body carries. `GoogleAPIError` embeds 300 chars of a
#: live response body (F-4), so this is the exact leak vector.
GOOGLE_BODY_MARKER = "SENTINEL-google-response-body-must-never-surface"


def _everything_ok(request: httpx.Request) -> httpx.Response:
    """Every remote lane proven working, by a real answer from each."""
    host = request.url.host
    if host == "api.telegram.org":
        return httpx.Response(200, json={"ok": True, "result": {"id": 1, "is_bot": True}})
    if host == "api.github.com":
        return httpx.Response(200, json={"login": "owner"})
    if host == "www.googleapis.com":
        return httpx.Response(200, json={"items": []})
    return httpx.Response(200, json={"object": "list"})


def _refuses_everything(request: httpx.Request) -> httpx.Response:
    """A credential PRESENT and REFUSED by every remote service (HTTP 401)."""
    if request.url.host == "api.github.com":
        return httpx.Response(401, json={"message": "Bad credentials"})
    if request.url.host == "oauth2.googleapis.com":
        return httpx.Response(400, json={"error": "invalid_grant"})
    return httpx.Response(401, json={"error": "unauthorized"})


def _unreachable_everything(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


def _transport(handler):
    return httpx.MockTransport(handler)


@contextlib.contextmanager
def _warnings():
    """Capture every WARNING+ loguru record's rendered text."""
    records: list[str] = []
    sink = logger.add(lambda m: records.append(str(m)), level="WARNING")
    try:
        yield records
    finally:
        logger.remove(sink)


def _assert_no_secret(sink: str | list[str], *secrets: str) -> None:
    """Nothing in `sink` — a JSON body or a log buffer — may carry a secret."""
    texts = sink if isinstance(sink, list) else [sink]
    for secret in secrets:
        for text in texts:
            assert secret not in text, f"secret leaked into probe output: {secret[:6]}…"


def _real_ffmpeg(code: int = 0):
    async def _launch(_exe: str):
        return code, None

    return _launch


def _exploding(_exe: str):
    async def _launch(_exe: str):
        return None, OSError("not a valid Win32 application")

    return _launch


def _exploding_probe(message: str):
    """A probe double that crashes — the fail-closed path must survive it."""

    async def _probe(_settings, *, transport=None):
        raise RuntimeError(message)

    return _probe


def _google_settings(make_settings, tmp_path, *, client: bool = True, grant: bool = True):
    """Settings whose Google lane runs through the REAL `src.google_auth` session:
    a real client-secret file and a real Fernet-sealed token cache."""
    enc = Fernet.generate_key().decode()
    client_path = tmp_path / "google_oauth_client.json"
    if client:
        client_path.write_text(
            json.dumps(
                {
                    "installed": {
                        "client_id": "cid.apps.googleusercontent.com",
                        "client_secret": "client-secret-value",
                    }
                }
            ),
            encoding="utf-8",
        )
    vault = tmp_path / "vault"
    if grant:
        save_tokens(
            vault / "State" / "google_token.json.enc",
            GoogleTokens(
                access_token="ya29.access-token",
                refresh_token="1//refresh-token",
                expires_at=time.time() + 3600,
            ),
            enc_key=enc,
        )
    return make_settings(
        TELEGRAM_BOT_TOKEN=TG_TOKEN,
        VAULT_GITHUB_TOKEN=GH_PAT,
        VAULT_LOCAL_PATH=str(vault),
        VAULT_ENC_KEY=enc,
        GOOGLE_OAUTH_CLIENT_JSON=str(client_path),
    )


# NOTE ON ISOLATION. `healthcheck` never writes the cache — only the endpoint's
# background sweep does — so the five cache-touching guards below reset it
# explicitly and the rest of the file is order-independent by construction.


# ── LAW 1: the vocabulary is closed ────────────────────────────────────────────────


async def test_every_lane_reports_one_of_exactly_three_states(monkeypatch, make_settings):
    """The law: no lane may answer a fourth value — `ok`, `found`, `set`,
    `missing`, `unchecked` or anything else. Asserted over BOTH a green sweep and
    a fully-red sweep, because a closed vocabulary that only holds when things are
    working is not closed."""
    settings = make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN, VAULT_GITHUB_TOKEN=GH_PAT)
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())

    green = await health.healthcheck(settings, transport=_transport(_everything_ok))
    assert {lane["state"] for lane in green["lanes"].values()} == {health.STATE_HEALTHY}

    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg(code=1))
    for name in ("_probe_gateway", "_probe_telegram", "_probe_vault", "_probe_google"):
        monkeypatch.setattr(health, name, _exploding_probe(f"probe {name} exploded"))
    red = await health.healthcheck(settings, transport=_transport(_everything_ok))
    assert {lane["state"] for lane in red["lanes"].values()} <= {health.STATE_UNREACHABLE}

    assert health.LANE_STATES == frozenset(
        {health.STATE_HEALTHY, health.STATE_MISCONFIGURED, health.STATE_UNREACHABLE}
    )
    for report in (green, red):
        for lane_name, lane in report["lanes"].items():
            assert lane["state"] in health.LANE_STATES, (lane_name, lane["state"])


async def test_the_report_body_carries_no_vague_ok_setting(monkeypatch, make_settings):
    """`"ok"` is the value this node deletes: it is what a probe says when it has
    not actually looked. Asserted against the RENDERED body, not the dict, so a
    nested `"status": "ok"` cannot hide."""
    settings = make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN, VAULT_GITHUB_TOKEN=GH_PAT)
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(settings, transport=_transport(_everything_ok))
    body = health.encode_body(report).decode("utf-8")
    for banned in ('"ok"', '"found"', '"set"', '"missing"', '"unchecked"', '"degraded"'):
        assert banned not in body, banned
    assert set(report["lanes"]) == set(health.LANE_NAMES)


async def test_the_overall_rollup_is_itself_one_of_the_three_states(monkeypatch, make_settings):
    """`overall` is a rollup, not a lane, but a fourth word in the same body is the
    same lie. It is a state, and `src/main.py`'s exit code reads it."""
    settings = make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN, VAULT_GITHUB_TOKEN=GH_PAT)
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(settings, transport=_transport(_everything_ok))
    assert report["overall"] in health.LANE_STATES


# ── LAW 2 / the headline: PRESENT is not WORKING ───────────────────────────────────


async def test_a_present_but_revoked_telegram_token_is_misconfigured_not_healthy(
    monkeypatch, make_settings
):
    """THE HEADLINE GUARD. A token that is SET and REFUSED by `getMe` is
    `misconfigured`. The old lane answered `"set"` for exactly this deployment and
    put `overall: "ok"` on top of it."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN), transport=_transport(_refuses_everything)
    )
    lane = report["lanes"]["telegram_token"]
    assert lane["state"] == health.STATE_MISCONFIGURED
    assert lane["state"] != health.STATE_HEALTHY
    assert report["overall"] != health.STATE_HEALTHY


async def test_a_telegram_200_that_says_ok_false_is_still_a_refusal(monkeypatch, make_settings):
    """Telegram wraps a rejected token in HTTP 200 with `{"ok": false}`. A probe
    that reads only the status code reports that deployment healthy — the same
    lie, one layer below the status code."""
    settings = make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN)
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.telegram.org":
            return httpx.Response(
                200, json={"ok": False, "error_code": 401, "description": "Unauthorized"}
            )
        return _everything_ok(request)

    report = await health.healthcheck(settings, transport=_transport(handler))
    assert report["lanes"]["telegram_token"]["state"] == health.STATE_MISCONFIGURED
    assert report["overall"] != health.STATE_HEALTHY


async def test_a_present_but_revoked_vault_pat_is_misconfigured_not_healthy(
    monkeypatch, make_settings
):
    """The vault lane was PURE PRESENCE: `str(SecretStr)` is `"**********"`, so any
    non-empty token read as healthy. A PAT GitHub answers 401 to is
    `misconfigured`."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(VAULT_GITHUB_TOKEN=GH_PAT), transport=_transport(_refuses_everything)
    )
    assert report["lanes"]["vault"]["state"] == health.STATE_MISCONFIGURED
    assert report["overall"] != health.STATE_HEALTHY


async def test_a_revoked_google_grant_is_not_healthy(monkeypatch, make_settings, tmp_path):
    """The Google lane was PURE PRESENCE: `google_token.json.enc` existing. A grant
    Google refuses is not a working grant."""
    settings = _google_settings(make_settings, tmp_path)
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(settings, transport=_transport(_refuses_everything))
    assert report["lanes"]["google"]["state"] != health.STATE_HEALTHY
    assert report["overall"] != health.STATE_HEALTHY


async def test_an_absent_telegram_token_is_misconfigured_not_a_pass(monkeypatch, make_settings):
    """`""` is not "unset, fine" — the bot cannot receive a single message without
    the token, so it is absent-when-required."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(TELEGRAM_BOT_TOKEN=""), transport=_transport(_everything_ok)
    )
    assert report["lanes"]["telegram_token"]["state"] == health.STATE_MISCONFIGURED


async def test_an_ffmpeg_on_path_that_will_not_run_is_not_healthy(monkeypatch, make_settings):
    """`shutil.which` is PRESENCE. A truncated or DLL-broken ffmpeg — a real
    Windows failure this repository has hit — is on PATH and answers nothing."""
    settings = make_settings()
    monkeypatch.setattr(health.shutil, "which", lambda _name: "C:/ffmpeg/ffmpeg.exe")
    monkeypatch.setattr(health, "_launch_ffmpeg", _real_ffmpeg(code=1))
    report = await health.healthcheck(settings, transport=_transport(_everything_ok))
    assert report["lanes"]["ffmpeg"]["state"] == health.STATE_MISCONFIGURED


async def test_an_ffmpeg_that_cannot_be_launched_is_misconfigured(monkeypatch, make_settings):
    """The binary resolves but the exec raises — determinable and wrong, so
    `misconfigured`, not an undetermined network problem."""
    settings = make_settings()
    monkeypatch.setattr(health.shutil, "which", lambda _name: "C:/ffmpeg/ffmpeg.exe")
    monkeypatch.setattr(health, "_launch_ffmpeg", _exploding)
    report = await health.healthcheck(settings, transport=_transport(_everything_ok))
    assert report["lanes"]["ffmpeg"]["state"] == health.STATE_MISCONFIGURED


# ── LAW 2, the other half: UNREACHABLE IS NOT HEALTHY ─────────────────────────────


async def test_an_unreachable_gateway_is_never_healthy(monkeypatch, make_settings):
    """The fail-closed half, lane by lane. Each of these read green before N3
    whenever the transport misbehaved in a way the old code did not model."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(), transport=_transport(_unreachable_everything)
    )
    assert report["lanes"]["gateway"]["state"] == health.STATE_UNREACHABLE
    assert report["lanes"]["gateway"]["state"] != health.STATE_HEALTHY
    assert report["overall"] != health.STATE_HEALTHY


async def test_an_unreachable_telegram_is_never_healthy(monkeypatch, make_settings):
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN),
        transport=_transport(_unreachable_everything),
    )
    assert report["lanes"]["telegram_token"]["state"] == health.STATE_UNREACHABLE


async def test_an_unreachable_vault_is_never_healthy(monkeypatch, make_settings):
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(VAULT_GITHUB_TOKEN=GH_PAT),
        transport=_transport(_unreachable_everything),
    )
    assert report["lanes"]["vault"]["state"] == health.STATE_UNREACHABLE


async def test_an_unreachable_google_is_never_healthy(monkeypatch, make_settings, tmp_path):
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    settings = _google_settings(make_settings, tmp_path)
    report = await health.healthcheck(settings, transport=_transport(_unreachable_everything))
    assert report["lanes"]["google"]["state"] == health.STATE_UNREACHABLE


async def test_a_gateway_answering_5xx_leaves_the_lane_undetermined(monkeypatch, make_settings):
    """A 503 from the gateway says nothing about whether anything else is wrong,
    so the honest answer is `unreachable` — NOT `misconfigured`, which would send
    the operator to rotate a working key."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "localhost":
            return httpx.Response(503, text="upstream unavailable")
        return _everything_ok(request)

    report = await health.healthcheck(make_settings(), transport=_transport(handler))
    assert report["lanes"]["gateway"]["state"] == health.STATE_UNREACHABLE
    assert report["overall"] != health.STATE_HEALTHY


async def test_a_probe_that_crashes_degrades_only_its_own_lane(monkeypatch, make_settings):
    """An exploding probe must not take the report with it, and must not report
    healthy either — it reports the truth it has, which is nothing."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    monkeypatch.setattr(health, "_probe_vault", _exploding_probe("vault double exploded"))
    report = await health.healthcheck(make_settings(), transport=_transport(_everything_ok))
    assert report["lanes"]["vault"]["state"] == health.STATE_UNREACHABLE
    assert report["lanes"]["gateway"]["state"] == health.STATE_HEALTHY
    assert report["overall"] != health.STATE_HEALTHY


async def test_an_unchecked_lane_is_undetermined_and_does_not_gate_the_rollup(
    monkeypatch, make_settings
):
    """`probe_gateway=False` used to emit a fourth value, `"unchecked"`, which
    `overall` then tolerated. An unprobed lane is an UNDETERMINED lane, so it reads
    `unreachable`; it does not gate `overall` because the caller declined to probe
    it — stated in the body rather than left as an accident."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(), probe_gateway=False, transport=_transport(_everything_ok)
    )
    assert report["lanes"]["gateway"]["state"] == health.STATE_UNREACHABLE
    assert report["lanes"]["gateway"]["required"] is False
    assert report["overall"] != health.STATE_UNREACHABLE


# ── LAW 3: the two failure states are distinguishable ─────────────────────────────


async def test_a_refused_key_and_an_unreachable_network_are_different_states(
    monkeypatch, make_settings
):
    """Same lane, same settings, two transports — two DIFFERENT answers, and both
    of them not-healthy. One value for both would tell the operator the wrong thing
    about which knob to turn."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    refused = await health.healthcheck(
        make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN), transport=_transport(_refuses_everything)
    )
    dead = await health.healthcheck(
        make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN),
        transport=_transport(_unreachable_everything),
    )
    a = refused["lanes"]["telegram_token"]
    b = dead["lanes"]["telegram_token"]
    assert a["state"] == health.STATE_MISCONFIGURED
    assert b["state"] == health.STATE_UNREACHABLE
    assert a["state"] != b["state"]
    assert a["reason"] != b["reason"]


async def test_a_refused_google_grant_and_an_unreachable_google_are_different_states(
    monkeypatch, make_settings, tmp_path
):
    """Google's own classification, driven through the REAL session: a 401 that
    survives the refresh replay means the grant was PRESENT and REFUSED
    (`misconfigured`); a connect error means nobody answered (`unreachable`)."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    settings = _google_settings(make_settings, tmp_path)
    a = await health.healthcheck(settings, transport=_transport(_refuses_everything))
    b = await health.healthcheck(settings, transport=_transport(_unreachable_everything))
    assert a["lanes"]["google"]["state"] == health.STATE_MISCONFIGURED
    assert b["lanes"]["google"]["state"] == health.STATE_UNREACHABLE


async def test_a_google_deployment_without_an_oauth_secret_is_not_required(
    monkeypatch, make_settings, tmp_path
):
    """F-4's supported pure-local box: no OAuth client secret is a legitimate
    deployment, so the lane is non-REQUIRED and `overall` is unaffected — while the
    body still shows the lane honestly instead of reading green."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    settings = _google_settings(make_settings, tmp_path, client=False, grant=False)
    report = await health.healthcheck(settings, transport=_transport(_everything_ok))
    assert report["lanes"]["google"]["required"] is False
    assert report["overall"] == health.STATE_HEALTHY


# ── LAW 4: no secret leaves the probe — one guard per class ───────────────────────


async def test_the_telegram_bot_token_never_reaches_the_body_or_the_log(
    monkeypatch, make_settings
):
    """CLASS `telegram_bot_token`. Drives a REFUSED token — the state a real leak
    would accompany — and asserts the token is in neither the rendered body nor any
    WARNING log record."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    with _warnings() as records:
        report = await health.healthcheck(
            make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN),
            transport=_transport(_refuses_everything),
        )
    _assert_no_secret(health.encode_body(report).decode("utf-8"), TG_TOKEN)
    _assert_no_secret(records, TG_TOKEN)


async def test_the_telegram_probe_url_never_reaches_the_body_or_the_log(
    monkeypatch, make_settings
):
    """CLASS `telegram_probe_url`. Telegram's bot API puts the credential IN THE
    URL PATH, so the URL is itself the secret: a reason built from
    `str(request.url)` would carry it. A different vector from the token alone, and
    it gets its own guard."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    with _warnings() as records:
        report = await health.healthcheck(
            make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN),
            transport=_transport(_unreachable_everything),
        )
    body = health.encode_body(report).decode("utf-8")
    _assert_no_secret(body, TG_TOKEN)
    _assert_no_secret(records, TG_TOKEN)
    assert f"/bot{TG_TOKEN}/" not in body


async def test_the_vault_pat_never_reaches_the_body_or_the_log(monkeypatch, make_settings):
    """CLASS `vault_pat`. `settings.vault_github_token` is a `SecretStr`; the probe
    must unwrap it to CALL GitHub and must not carry the unwrapped value anywhere
    else."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    with _warnings() as records:
        report = await health.healthcheck(
            make_settings(VAULT_GITHUB_TOKEN=GH_PAT), transport=_transport(_refuses_everything)
        )
    _assert_no_secret(health.encode_body(report).decode("utf-8"), GH_PAT)
    _assert_no_secret(records, GH_PAT)


async def test_the_authorization_header_value_never_reaches_the_body_or_the_log(
    monkeypatch, make_settings
):
    """CLASS `authorization_header`. The vault call carries
    `Authorization: Bearer <PAT>`; the header VALUE must not be echoed even as a
    labelled fragment. N1 closed exactly this shape inside `redact_arg`, and this
    probe is a second, independent place it could leak."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    with _warnings() as records:
        report = await health.healthcheck(
            make_settings(VAULT_GITHUB_TOKEN=GH_PAT), transport=_transport(_refuses_everything)
        )
    body = health.encode_body(report).decode("utf-8")
    _assert_no_secret(body, GH_PAT)
    assert "Bearer" not in body
    _assert_no_secret(records, GH_PAT)


async def test_a_google_response_body_never_reaches_the_body_or_the_log(
    monkeypatch, make_settings, tmp_path
):
    """CLASS `google_response_body` — F-4's REGRESSION guard. `GoogleAPIError`
    embeds 300 characters of a live response body, so its `str()` can carry an
    account id or owner data. `describe_probe_failure` returns the exception CLASS
    name only, and the reason built from it must stay that way: a 403 body stuffed
    with a sentinel must surface nowhere."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    settings = _google_settings(make_settings, tmp_path)

    def google_403(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.googleapis.com":
            return httpx.Response(
                403, json={"error": GOOGLE_BODY_MARKER, "ownerEmail": "owner@example.com"}
            )
        return _everything_ok(request)

    with _warnings() as records:
        report = await health.healthcheck(settings, transport=_transport(google_403))
    body = health.encode_body(report).decode("utf-8")
    _assert_no_secret(body, GOOGLE_BODY_MARKER, "owner@example.com")
    _assert_no_secret(records, GOOGLE_BODY_MARKER, "owner@example.com")
    assert report["lanes"]["google"]["state"] == health.STATE_UNREACHABLE


async def test_a_settings_path_never_reaches_the_body_or_the_log(
    monkeypatch, make_settings, tmp_path
):
    """CLASS `filesystem_path`. A reason is "a fault class or a one-clause
    explanation" (F-4) — never a path. The owner's vault root and the OAuth client
    file both name directories the operator did not choose to publish."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    settings = _google_settings(make_settings, tmp_path)
    with _warnings() as records:
        report = await health.healthcheck(settings, transport=_transport(_unreachable_everything))
    body = health.encode_body(report).decode("utf-8")
    _assert_no_secret(body, str(tmp_path), str(settings.google_oauth_client_json))
    _assert_no_secret(records, str(tmp_path), str(settings.google_oauth_client_json))


def test_the_reason_redactor_screens_a_secret_a_probe_interpolated_by_mistake():
    """CLASS `redaction_backstop`. The probes build reasons from templates and a
    class name, so a secret should never reach the redactor at all. This guard
    covers the SECOND line of defence: if a future probe interpolates the token by
    mistake, `redact_reason` must still keep it out. It cannot prove the first
    line, and does not claim to."""
    scrubbed = health.redact_reason(f"probe said {GH_PAT} while calling GitHub")
    assert GH_PAT not in scrubbed
    assert "GitHub" in scrubbed, "redaction must not eat the operator-readable clause"


async def test_a_reason_is_a_clause_and_names_the_fault_class(monkeypatch, make_settings):
    """F-4's `reason` law, re-applied here: a fault class OR a one-clause
    explanation — the probe's reasons must be prose an operator can act on, and
    must still name the class where a class is what went wrong."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(
        make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN),
        transport=_transport(_unreachable_everything),
    )
    reason = report["lanes"]["telegram_token"]["reason"]
    assert reason and " " in reason, reason
    assert ".ConnectError" in reason, reason


# ── the report shape: reasons only where something is wrong ───────────────────────


async def test_a_reason_is_present_only_for_a_lane_that_is_not_healthy(
    monkeypatch, make_settings
):
    """A `reason` on a `healthy` lane would be a claim the probe cannot support,
    and it is how a report grows a fourth vocabulary one string at a time."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(make_settings(), transport=_transport(_everything_ok))
    assert report["reasons"] == {}, report["reasons"]
    assert set(report["reasons"]) <= {
        name for name, lane in report["lanes"].items() if lane["state"] != health.STATE_HEALTHY
    }


async def test_every_lane_reports_its_own_requirement(monkeypatch, make_settings):
    """The rollup is auditable: the body says WHICH lanes gate it, so `overall`
    cannot quietly stop meaning something."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    report = await health.healthcheck(make_settings(), transport=_transport(_everything_ok))
    for name in health.LANE_NAMES:
        assert isinstance(report["lanes"][name]["required"], bool), name
    assert set(report["lanes"]) == set(health.LANE_NAMES)


# ── LAW 5: the cache — no new rate-limit path ─────────────────────────────────────


def test_the_cold_cache_reports_every_lane_unknown_rather_than_healthy():
    """THE FAIL-CLOSED HALF OF THE ENDPOINT. Before any probe has run there is no
    evidence at all, so every lane reads `unreachable` and `overall` does too. The
    old responder answered `{"status":"ok"}` here — it could not disagree with
    reality because it never asked."""
    health.reset_cache()
    report = health.snapshot()
    assert report is not None, "a cold responder must still answer, with the truth"
    assert {lane["state"] for lane in report["lanes"].values()} == {health.STATE_UNREACHABLE}
    assert report["overall"] == health.STATE_UNREACHABLE


async def test_the_snapshot_answers_from_cache_and_never_probes_per_poll(
    monkeypatch, make_settings
):
    """The `/health` endpoint is polled. Probing on every poll would hammer GitHub
    and Telegram — and GitHub answers 403 for BOTH a rate limit and bad scopes, so
    the probe would manufacture the very ambiguity N5 has to resolve. A second
    schedule inside the TTL must perform no sweep at all."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    health.reset_cache()
    sweeps: list[int] = []
    real = health.healthcheck

    async def counting(settings, **kwargs):
        sweeps.append(1)
        return await real(settings, **kwargs)

    monkeypatch.setattr(health, "healthcheck", counting)

    settings = make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN, VAULT_GITHUB_TOKEN=GH_PAT)
    health.schedule_refresh(settings, transport=_transport(_everything_ok))
    await _until(lambda: health.snapshot_is_populated())
    first = health.snapshot()

    health.schedule_refresh(settings, transport=_transport(_everything_ok))
    await asyncio.sleep(0.05)
    second = health.snapshot()

    assert len(sweeps) == 1, f"a poll inside the TTL re-probed ({len(sweeps)} sweeps)"
    assert second == first
    assert health.snapshot_is_stale() is False
    assert health.PROBE_TTL_S == 30.0


async def test_an_expired_cache_is_refreshed(monkeypatch, make_settings):
    """The cache must expire, or a lapsed Google token would read healthy forever.
    Past the TTL the next schedule starts a fresh sweep."""
    health.reset_cache()
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    settings = make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN, VAULT_GITHUB_TOKEN=GH_PAT)
    health.schedule_refresh(settings, transport=_transport(_everything_ok))
    await _until(lambda: health.snapshot_is_populated())
    assert health.snapshot()["overall"] == health.STATE_HEALTHY

    monkeypatch.setattr(health, "PROBE_TTL_S", 0.0)
    assert health.snapshot_is_stale() is True
    health.schedule_refresh(settings, transport=_transport(_unreachable_everything))
    await _until(lambda: health.snapshot()["overall"] == health.STATE_UNREACHABLE)


def test_the_probe_timeout_is_declared_so_no_lane_can_hang_the_report():
    """Every remote lane is bounded. A closed lid must cost the probe a pause,
    never a hang — the same bound F-4 gives the boot probe."""
    assert 0 < health.PROBE_TIMEOUT_S <= 30.0


# ── the `/health` responder: body carries the truth, status stays 200 ─────────────


def test_every_lane_state_maps_to_200_and_the_decision_is_a_named_table():
    """THE STATUS-CODE DECISION, asserted rather than left implicit. Report §48
    step 1 offers 503 or «keep 200 with a machine-readable body». This is the
    second one, and the table IS the documentation: a Space treats a non-200 as
    «the app is down» and may restart it, so flapping the whole container because a
    Google token lapsed would be worse than reporting the truth in the body. The
    operator signal is the `--health` EXIT CODE, which is non-zero."""
    assert health.HTTP_STATUS_BY_STATE == {
        health.STATE_HEALTHY: 200,
        health.STATE_MISCONFIGURED: 200,
        health.STATE_UNREACHABLE: 200,
    }


async def test_the_public_port_answers_200_with_every_lane_state_in_the_body(monkeypatch,
                                                                             make_settings):
    """`/health` over a REAL loopback socket: the status is 200 and the body
    carries a state per lane. The old responder answered `200 {"status":"ok"}`
    with no lane at all, which is why it could never be evidence of anything."""
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    health.reset_cache()
    bridge, port = await main_mod.start_public_port(make_settings(), 0, host="127.0.0.1")
    try:
        status, body = await asyncio.to_thread(_http_get, port)
    finally:
        await bridge.close()
    assert status == 200
    parsed = json.loads(body)
    assert set(parsed["lanes"]) == set(health.LANE_NAMES)
    assert parsed["overall"] in health.LANE_STATES


async def test_the_public_port_answers_without_waiting_for_a_probe(monkeypatch, make_settings):
    """`/health` must not block the bridge's event loop on four network calls —
    the responder shares the loop with the authenticated WSS tunnel. Measured:
    the whole request returns in well under a second with a cold cache."""
    health.reset_cache()
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())
    bridge, port = await main_mod.start_public_port(make_settings(), 0, host="127.0.0.1")
    try:
        started = time.perf_counter()
        status, body = await asyncio.to_thread(_http_get, port)
        elapsed = time.perf_counter() - started
    finally:
        await bridge.close()
    assert status == 200
    assert elapsed < 1.0, f"the responder blocked for {elapsed:.2f}s on a cold cache"
    assert json.loads(body)["overall"] == health.STATE_UNREACHABLE


# ── the exit-code contract ────────────────────────────────────────────────────────


def test_the_exit_code_is_zero_only_when_overall_is_healthy():
    """`src/main.py`'s contract, kept: 0 when healthy, 1 otherwise. What changed is
    the WORD it compares against, not the contract."""
    assert health.exit_code_for({"overall": health.STATE_HEALTHY}) == 0
    assert health.exit_code_for({"overall": health.STATE_MISCONFIGURED}) == 1
    assert health.exit_code_for({"overall": health.STATE_UNREACHABLE}) == 1


async def test_the_cli_probe_exits_zero_and_one_without_polling(monkeypatch, capsys, make_settings):
    """The `--health` lane end to end: a green sweep exits 0 and prints the body, a
    red sweep exits 1, and the bot runner is never reached."""
    settings = make_settings(TELEGRAM_BOT_TOKEN=TG_TOKEN, VAULT_GITHUB_TOKEN=GH_PAT)
    monkeypatch.setattr(main_mod, "Settings", lambda: settings)
    monkeypatch.setattr(health, "_probe_ffmpeg", _real_ffmpeg())

    outcome = {"healthy": True}

    async def _report(_settings, *, probe_gateway=True, transport=None):
        handler = _everything_ok if outcome["healthy"] else _unreachable_everything
        return await health.healthcheck(
            settings, probe_gateway=probe_gateway, transport=_transport(handler)
        )

    monkeypatch.setattr(main_mod, "healthcheck", _report)

    polled: list[object] = []
    sentinel = types.ModuleType("src.bot")

    async def _poll(_s, bridge=None):
        polled.append(1)

    sentinel.run_bot = _poll
    monkeypatch.setitem(sys.modules, "src.bot", sentinel)

    assert await main_mod.run(["--health"]) == 0
    assert json.loads(capsys.readouterr().out)["overall"] == health.STATE_HEALTHY

    outcome["healthy"] = False
    assert await main_mod.run(["--health"]) == 1
    assert json.loads(capsys.readouterr().out)["overall"] != health.STATE_HEALTHY
    assert polled == [], "--health must exit before the polling runner is invoked"


# ── helpers ───────────────────────────────────────────────────────────────────────


async def _until(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.perf_counter() + timeout
    while not predicate():
        if time.perf_counter() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.005)


def _http_get(port: int) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/health")
        response = conn.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        conn.close()