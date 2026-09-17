"""P6 coverage gap pins, batch 1 (master transformation plan, Phase P6).

Only genuinely uncovered behavior: voice-policy lane resolution, guard
non-dict fail-closed, empty-goal DAG rejection, turn-counter OSError paths,
and protocol decode error matrix. Each catches an untested failure mode.
"""

import json
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _real_disk(monkeypatch):
    """Opt out of the conftest hermeticity fence: these tests exercise real disk."""
    monkeypatch.delenv("SARA_TURN_COUNTER_OFF", raising=False)


def test_edge_module_loaded_raises():
    import src.voice_policy as policy

    sys.modules["edge_tts"] = SimpleNamespace()
    try:
        with pytest.raises(AssertionError, match="Edge-TTS footprint"):
            policy.assert_no_edge()
    finally:
        del sys.modules["edge_tts"]
    policy.assert_no_edge()


def test_fish_lane_unconfigured_raises(monkeypatch):
    from src.voice_policy import fish_lane

    monkeypatch.setattr(
        "src.config.get_settings",
        lambda: SimpleNamespace(fish_audio_ready=False),
    )
    with pytest.raises(RuntimeError, match="unconfigured"):
        fish_lane()


def test_fish_lane_configured_resolves(monkeypatch):
    from src.fish_voice import FishFirstVoice
    from src.voice_policy import fish_lane

    settings = SimpleNamespace(
        fish_audio_ready=True,
        fish_audio_model="fish-audio/s2.1-pro-free:free",
        fish_audio_voice_ref="r",
        fish_audio_key="k",
        fish_audio_speed=0.9,
        fish_audio_endpoint="https://openrouter.ai/api/v1/audio/speech",
    )
    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    assert isinstance(fish_lane(), FishFirstVoice)


def test_guard_nondict_json_fails_closed(tmp_path):
    from bridge.guard import Guard

    wl = tmp_path / "whitelist.json"
    wl.write_text(json.dumps([1, 2]), encoding="utf-8")
    verdict = Guard(wl).check_app("calc.exe")
    assert verdict.allowed_without_confirmation is False
    assert verdict.requires_confirmation is True


def test_build_dag_empty_goal_rejected():
    from src.openclaw.plans import build_dag

    with pytest.raises(ValueError, match="non-empty goal"):
        build_dag(goal="  ", ops=[], weight=1)


def test_counter_read_oserror_recovers(tmp_path, monkeypatch):
    from src import turn_counter

    monkeypatch.setattr(
        "pathlib.Path.read_text",
        lambda self, *a, **k: (_ for _ in ()).throw(OSError("disk gone")),
    )
    assert turn_counter.read_turn_count(tmp_path / "vault") == 0


def test_counter_rename_failure_recovers(tmp_path, monkeypatch):
    from src import turn_counter

    target = tmp_path / "vault" / "State" / "turn_counter.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("garbage!!", encoding="utf-8")
    monkeypatch.setattr(
        turn_counter.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("ro"))
    )
    assert turn_counter.read_turn_count(tmp_path / "vault") == 0
    assert target.exists()


def test_counter_mkdir_failure_never_raises(tmp_path, monkeypatch):
    import pathlib

    from src import turn_counter

    def _boom(self, *a, **k):
        raise OSError("read-only")

    monkeypatch.setattr(pathlib.Path, "mkdir", _boom)
    assert turn_counter.bump_turn_counter(tmp_path / "vault") == 0


class TestDecodeFrameErrors:
    def test_oversize_frame_rejected(self):
        from common.protocol import MAX_FRAME_BYTES, ProtocolError, decode_frame

        with pytest.raises(ProtocolError, match="exceeds"):
            decode_frame(b"x" * (MAX_FRAME_BYTES + 1))

    def test_non_json_rejected(self):
        from common.protocol import ProtocolError, decode_frame

        with pytest.raises(ProtocolError, match="non-JSON"):
            decode_frame(b"\xff\xfe not json")

    def test_non_dict_json_rejected(self):
        from common.protocol import ProtocolError, decode_frame

        with pytest.raises(ProtocolError, match="not a JSON object"):
            decode_frame(b"[1, 2]")

    def test_bad_version_rejected(self):
        from common.protocol import ProtocolError, decode_frame

        with pytest.raises(ProtocolError, match="unsupported protocol version"):
            decode_frame(json.dumps({"v": 999}).encode())

    def test_invalid_shape_rejected(self):
        from common.protocol import PROTOCOL_VERSION, ProtocolError, decode_frame

        with pytest.raises(ProtocolError, match="invalid frame shape"):
            decode_frame(json.dumps({"v": PROTOCOL_VERSION, "ok": "not-a-bool"}).encode())

    def test_unrecognized_shape_rejected(self):
        from common.protocol import PROTOCOL_VERSION, ProtocolError, decode_frame

        with pytest.raises(ProtocolError, match="neither Envelope, HelloAck, nor Hello"):
            decode_frame(json.dumps({"v": PROTOCOL_VERSION, "zzz": 1}).encode())
