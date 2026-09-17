"""P6 coverage, batch 5a: voice biometrics, Google auth flows, main entry.

Only uncovered branches: Fernet key errors, cosine edges, guest-note
variants, gate verdicts, short-note guard, model-load import error, client
secret shapes, token cache chmod path, code/refresh grants, 401 matrix,
proactive double-check, and --health exit codes. Model-weight paths
(torch/ECAPA download) stay uncovered by design — never in CI.
"""

import json
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet

KEY = Fernet.generate_key().decode()
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def test_fernet_empty_and_invalid_keys():
    from src.skills.voice_biometric_auth import VoiceprintError, _fernet

    with pytest.raises(VoiceprintError, match="not set"):
        _fernet("")
    with pytest.raises(VoiceprintError, match="not a valid Fernet key"):
        _fernet("nope")
    assert _fernet(KEY) is not None


def test_cosine_edges():
    from src.skills.voice_biometric_auth import _cosine

    assert _cosine([], [1.0]) == 0.0
    assert _cosine([1.0], [1.0, 2.0]) == 0.0
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_stage_guest_note_variants(tmp_path):
    from datetime import datetime

    from src.skills.voice_biometric_auth import stage_guest_note

    moment = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    first = stage_guest_note(tmp_path, [0.1] * 4, enc_key=KEY, transcript="hi", now=moment)
    second = stage_guest_note(tmp_path, [0.1] * 4, enc_key=KEY, transcript="hi", now=moment)
    assert first != second  # same-minute collision suffixes
    assert second.name.endswith("-2.json")
    no_vector = stage_guest_note(tmp_path, [], enc_key=KEY)
    assert json.loads(no_vector.read_text(encoding="utf-8"))["voiceprint_enc"] is None
    named = stage_guest_note(tmp_path, [0.2] * 4, enc_key=KEY, claimed_name="Sam")
    assert json.loads(named.read_text(encoding="utf-8"))["claimed_name"] == "Sam"


def test_owner_gate_verdicts_and_probe_failure(tmp_path):
    import asyncio as _aio

    from src.skills.voice_biometric_auth import owner_voice_gate

    class _Bio:
        last_vector = None

        async def verify(self, ogg):
            return True

    class _DeadBio:
        last_vector = [0.1] * 4

        async def verify(self, ogg):
            raise RuntimeError("mic dead")

    bio = _Bio()
    assert (
        _aio.run(
            owner_voice_gate(
                bio=bio,
                ogg_opus=b"ogg",
                chat_id=7,
                authorized_id=7,
                vault_root=tmp_path,
                enc_key=KEY,
            )
        )
        is True
    )
    assert (
        _aio.run(
            owner_voice_gate(
                bio=_DeadBio(),
                ogg_opus=b"ogg",
                chat_id=7,
                authorized_id=7,
                vault_root=tmp_path,
                enc_key=KEY,
            )
        )
        is True
    )
    assert (
        _aio.run(
            owner_voice_gate(
                bio=bio,
                ogg_opus=b"ogg",
                chat_id=9,
                authorized_id=7,
                vault_root=tmp_path,
                enc_key=KEY,
            )
        )
        is False
    )


def test_enroll_short_note_rejected(tmp_path):
    import asyncio as _aio

    from src.skills.voice_biometric_auth import VoiceBiometrics, VoiceprintError

    bio = VoiceBiometrics(embedding_path=tmp_path / "State" / "owner.enc", enc_key=KEY)
    bio._decode_pcm = lambda ogg: b"\x00" * 100
    with pytest.raises(VoiceprintError, match="too short"):
        _aio.run(bio.enroll(b"ogg"))


def test_enroll_blend_and_chmod_failure(tmp_path, monkeypatch):
    import asyncio as _aio
    import pathlib

    from src.skills.voice_biometric_auth import VoiceBiometrics

    bio = VoiceBiometrics(embedding_path=tmp_path / "State" / "owner.enc", enc_key=KEY)
    bio._decode_pcm = lambda ogg: b"\x00" * 200000
    bio._embed_pcm_sync = lambda pcm: [0.5] * 8
    _aio.run(bio.enroll(b"ogg"))
    assert bio._owner_vector == [0.5] * 8
    bio._owner_vector = [0.5] * 8
    monkeypatch.setattr(
        pathlib.Path, "chmod", lambda self, *a, **k: (_ for _ in ()).throw(OSError("ro"))
    )
    _aio.run(bio.enroll(b"ogg"))
    assert bio._owner_vector == [0.5] * 8  # centroid of identical prints


def test_load_model_import_error(monkeypatch, tmp_path):
    import sys

    from src.skills.voice_biometric_auth import VoiceBiometrics, VoiceprintError

    bio = VoiceBiometrics(embedding_path=tmp_path / "o.enc", enc_key=KEY)
    monkeypatch.setitem(sys.modules, "speechbrain.inference.speaker", None)
    with pytest.raises(VoiceprintError, match="not installed"):
        bio._load_model()


def test_corrupt_and_empty_prints_unenrolled(tmp_path):
    from src.skills.voice_biometric_auth import VoiceBiometrics

    target = tmp_path / "o.enc"
    target.write_bytes(b"garbage-bytes")
    bio = VoiceBiometrics(embedding_path=target, enc_key=KEY)
    assert bio.enrolled is False
    sealed = Fernet(KEY).encrypt(json.dumps({"model": "m", "vector": []}).encode())
    target.write_bytes(sealed)
    bio2 = VoiceBiometrics(embedding_path=target, enc_key=KEY)
    assert bio2.enrolled is False


def test_client_secret_requires_installed_block(tmp_path):
    from src.google_auth import GoogleAuthError, load_client_secret

    target = tmp_path / "client.json"
    target.write_text(json.dumps({"web": {}}), encoding="utf-8")
    with pytest.raises(GoogleAuthError, match="installed"):
        load_client_secret(target)


def test_save_chmod_failure_best_effort(tmp_path, monkeypatch):
    import pathlib

    from src.google_auth import GoogleTokens, save_tokens

    real_chmod = pathlib.Path.chmod

    def _boom(self, *args, **kwargs):
        raise OSError("ro fs")

    monkeypatch.setattr(pathlib.Path, "chmod", _boom)
    tokens = GoogleTokens(
        access_token="a", refresh_token="r", expires_at=9999999999.0, scopes=["x"]
    )
    save_tokens(tmp_path / "tok.enc", tokens, enc_key=KEY)


def test_exchange_and_refresh_grants():
    import asyncio as _aio

    import httpx

    from src.google_auth import GoogleTokens, exchange_code, refresh_tokens

    def _ok(request):
        return httpx.Response(
            200,
            json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600, "scope": "a b"},
        )

    async def _run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(_ok)) as http:
            exchanged = await exchange_code(
                http, {"client_id": "c", "client_secret": "s"}, "code", 9000
            )
            assert exchanged.access_token == "a1" and exchanged.scopes == ["a", "b"]
            refreshed = await refresh_tokens(
                http,
                {"client_id": "c", "client_secret": "s"},
                GoogleTokens(access_token="o", refresh_token="r", expires_at=0, scopes=[]),
            )
            assert refreshed.refresh_token == "r1"

    _aio.run(_run())


def test_session_tokens_property_and_double_401():
    import asyncio as _aio

    import httpx

    from src.google_auth import GoogleAuthError, GoogleSession, GoogleTokens

    tokens = GoogleTokens(access_token="a", refresh_token="r", expires_at=9999999999.0, scopes=[])
    session = GoogleSession(object(), tokens=tokens)
    assert session.tokens is tokens

    async def _fake_refresh():
        session._tokens = GoogleTokens(
            access_token="b", refresh_token="r", expires_at=9999999999.0, scopes=[]
        )

    async def _run():
        def _denied(request):
            return httpx.Response(401, text="nope")

        session._http = httpx.AsyncClient(transport=httpx.MockTransport(_denied))
        session._do_refresh = _fake_refresh
        with pytest.raises(GoogleAuthError, match="re-run the OAuth bootstrap"):
            await session.request("GET", "https://x")

    _aio.run(_run())


def test_refresh_on_401_replay_when_already_refreshed():
    import asyncio as _aio

    from src.google_auth import GoogleSession, GoogleTokens

    session = GoogleSession(
        object(),
        tokens=GoogleTokens(
            access_token="new", refresh_token="r", expires_at=9999999999.0, scopes=[]
        ),
    )
    _aio.run(session._refresh_on_401(bearer_sent="old"))  # returns silently, no HTTP


def test_proactive_double_check_skips_second_refresh(monkeypatch):
    import asyncio as _aio
    import time as _time

    from src.google_auth import GoogleSession, GoogleTokens

    session = GoogleSession(
        object(),
        tokens=GoogleTokens(
            access_token="a", refresh_token="r", expires_at=_time.time() - 10, scopes=[]
        ),
    )
    calls = {"n": 0}

    async def _once():
        calls["n"] += 1
        session._tokens = GoogleTokens(
            access_token="fresh", refresh_token="r", expires_at=9999999999.0, scopes=[]
        )

    monkeypatch.setattr(session, "_do_refresh", _once)
    _aio.run(session._refresh_proactive())
    assert calls["n"] == 1


def test_main_health_exits_and_invalid_env(monkeypatch):
    import asyncio as _aio

    import src.main as main_mod

    class _Settings:
        log_level = "INFO"

    async def _ok(settings):
        return {"overall": "ok"}

    async def _bad(settings):
        return {"overall": "degraded"}

    monkeypatch.setattr(main_mod, "Settings", lambda: _Settings())
    monkeypatch.setattr(main_mod, "configure_logging", lambda level: None)
    monkeypatch.setattr(main_mod, "healthcheck", _ok)
    assert _aio.run(main_mod.run(["--health"])) == 0
    monkeypatch.setattr(main_mod, "healthcheck", _bad)
    assert _aio.run(main_mod.run(["--health"])) == 1

    def _boom():
        from pydantic import BaseModel

        class _Cfg(BaseModel):
            required_field: str

        return _Cfg.model_validate({})

    monkeypatch.setattr(main_mod, "Settings", _boom)
    assert _aio.run(main_mod.run([])) == 2
