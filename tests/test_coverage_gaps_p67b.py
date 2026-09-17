"""P6 batch 7b — small-module edge pins: src/telemetry happy report,
voice_to_vault taught-pair shapes + stubbed loader, web_intel redirect/exception/
dedup/cap/empty paths, weather transport failures + unknown-place flag,
sara_tool_skills sync-failure + unknown-guide paths.
"""

from __future__ import annotations

import sys
import types
from concurrent.futures import ThreadPoolExecutor

from src.skills.sara_tool_skills import (
    _SKILLS,
    read_skill_guide,
    sync_skill_guides,
)
from src.skills.voice_to_vault_transcriber import (
    VoiceToVault,
    _load_model,
    _parse_taught,
)
from src.skills.weather import WeatherClient
from src.skills.web_intel import WebIntel, _ddg_redirect
from src.telemetry import TelemetryClient


class _Brain:
    def __init__(self, reply="ok"):
        self.reply = reply

    async def chat(self, messages, **kwargs):
        return self.reply


class _Bridge:
    def __init__(self, payload):
        self._payload = payload

    async def send_cmd(self, name, args, *, timeout_s=20.0):
        assert name == "telemetry.state"
        return self._payload


async def test_telemetry_happy_report_narrates_live_state():
    client = TelemetryClient(
        _Bridge({"cpu_percent": 23.0, "top_process": "code.exe"}), _Brain("تمام")
    )
    assert await client.report() == "تمام"
    state = await client.fetch_state()
    assert state.cpu_percent == 23.0 and state.top_process == "code.exe"
    assert await client.narrate(state) == "تمام"


def test_parse_taught_tuple_arrow_and_junk():
    assert _parse_taught((("a", "b"),)) == (("a", "b"),)
    assert _parse_taught(("كفيك -> كفايك",)) == (("كفيك", "كفايك"),)
    assert _parse_taught(("lonely", 7, ("x", "y", "z"))) == ()


def test_update_prompt_terms_replaces_pairs(tmp_path):
    with ThreadPoolExecutor(max_workers=1) as pool:
        vault = VoiceToVault(
            model_size="tiny",
            compute_type="int8",
            executor=pool,
            vault_dir=tmp_path,
            model_loader=lambda size, kind: object(),
        )
        vault.update_prompt_terms(("a -> b",))
        assert vault._taught_pairs == (("a", "b"),)
        vault.update_prompt_terms(())
        assert vault._taught_pairs == ()


def test_load_model_uses_lazy_whisper_import(monkeypatch):
    """_load_model's real branch runs against a stub faster_whisper module —
    no network, no weights, the lazy-import line genuinely executes."""
    seen = {}

    class _StubModel:
        def __init__(self, size, *, device, compute_type):
            seen.update(size=size, device=device, compute_type=compute_type)

    stub = types.ModuleType("faster_whisper")
    stub.WhisperModel = _StubModel
    monkeypatch.setitem(sys.modules, "faster_whisper", stub)
    _load_model("tiny", "int8")
    assert seen == {"size": "tiny", "device": "cpu", "compute_type": "int8"}


def test_ddg_redirect_unwrap_and_passthrough():
    assert _ddg_redirect("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fx&rut=a") == (
        "https://example.com/x"
    )
    assert _ddg_redirect("https://example.com/plain") == "https://example.com/plain"


class _Http:
    def __init__(self, responses=None, boom_urls=()):
        self.responses = responses or {}
        self.boom = set(boom_urls)

    async def get(self, url, *, headers=None, follow_redirects=True):
        if url in self.boom:
            raise ConnectionError("net down")
        status, body = self.responses.get(url, (404, ""))
        return type("Resp", (), {"status_code": status, "text": body})()


def _result_row(url, title):
    return f'<a class="result__a" href="{url}">{title}</a>'


async def test_web_search_skips_dups_blanks_and_caps_at_six():
    from urllib.parse import quote_plus

    url = "https://html.duckduckgo.com/html/?q=" + quote_plus("q")
    rows = [_result_row("https://e.com/0", "  "), _result_row("https://e.com/1", "one")]
    rows += [_result_row("https://e.com/1", "one again")]
    rows += [_result_row("ftp://e.com/x", "ftp skipped")]
    rows += [_result_row(f"https://e.com/{i}", f"t{i}") for i in range(2, 9)]
    intel = WebIntel(http=_Http({url: (200, "<html>" + "".join(rows) + "</html>")}))
    results = await intel.search("q")
    assert len(results) == 6  # budget cap genuinely breaks the loop
    assert results[0] == {"title": "one", "url": "https://e.com/1"}


async def test_web_get_exception_is_honest_empty():
    intel = WebIntel(
        http=_Http(boom_urls=("https://html.duckduckgo.com/html/?q=q", "https://x.com"))
    )
    assert await intel.search("q") == []
    assert await intel.read_page("https://x.com") is None
    assert "جربها بصياغة تانية" in await intel.search_block("q")


async def test_weather_transport_failures_are_none_and_flagged():
    fcast = "https://api.open-meteo.com/v1/forecast?latitude=31.95&longitude=35.93&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
    assert await WeatherClient(http=_Http(boom_urls=(fcast,))).current("عمان") is None
    geo = "https://geocoding-api.open-meteo.com/v1/search?name=Nowhere&count=1&language=ar"
    client = WeatherClient(http=_Http(boom_urls=(geo,)))
    assert await client.current("Nowhere") is None
    assert client.is_unknown_place("Nowhere") is False  # outage, not a bad name


async def test_weather_geocode_miss_flags_unknown_place():
    geo = "https://geocoding-api.open-meteo.com/v1/search?name=خريبة&count=1&language=ar"
    client = WeatherClient(http=_Http({geo: (200, '{"results": []}')}))
    assert await client.current("خريبة") is None
    assert client.is_unknown_place("خريبة") is True
    assert client.is_unknown_place("عمان") is False


class _Vault:
    def __init__(self, fail_on=()):
        self.fail_on = set(fail_on)
        self.written = {}

    async def upsert(self, path, content, *, message=""):
        if path in self.fail_on:
            raise OSError("disk full")
        self.written[path] = content

    async def read(self, path):
        raise FileNotFoundError(path)


async def test_sync_skill_guides_counts_only_what_landed():
    first = f"02_Areas/Profile/Sara_Skills/{_SKILLS[0][0]}"
    written = await sync_skill_guides(_Vault(fail_on=(first,)))
    assert written == len(_SKILLS) - 1


async def test_read_unknown_skill_guide_is_none_without_touching_vault():
    assert await read_skill_guide(None, "no-such-tool") is None
    assert await read_skill_guide(_Vault(), "no-such-tool") is None
