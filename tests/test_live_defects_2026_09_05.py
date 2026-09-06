"""Live-defect regression floor (owner live test 2026-09-05).

Seven production defects reported from real Telegram sessions. Each test below
pins the FIXED behaviour so the failure cannot silently return:

  A  Windows Calculator UWP termination   — bridge/executor.py
  B  Amman prayer times (coords + Awqaf)  — src/external_apis.py
  C  Weather geocode crash (loguru)       — src/skills/weather.py
  D  Dispatcher keyword routing           — src/dispatcher.py
  E  Demanded voice note never text-only  — src/bot.py
  F  Google OAuth single scope param      — src/google_auth.py
  G  Vault dynamic folder creation        — src/tools.py + src/vault.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

import httpx
import pytest

from bridge.executor import Executor, close_images
from bridge.guard import Guard
from src.dispatcher import _keyword_net
from src.external_apis import ExternalAPIs
from src.google_auth import AUTH_SCOPES, build_consent_url

# ---------------------------------------------------------------- A: calculator


def _guard(tmp_path: Path, *, auto: bool = True, name="calculator", exe="calc.exe") -> Guard:
    wl = tmp_path / "whitelist.json"
    wl.write_text(
        json.dumps(
            {
                "allowed_apps": [{"name": name, "executable": exe, "auto_approve": auto}],
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )
    return Guard(wl)


class _FakePsutil:
    """A live process table close() must actually EMPTY (psutil stand-in)."""

    def __init__(self, names: list[str]) -> None:
        self.running = list(names)

    def process_iter(self, attrs=None):
        return [
            type("P", (), {"info": {"name": name, "pid": pid}})()
            for pid, name in enumerate(self.running)
        ]


def test_calculator_close_targets_the_uwp_image(tmp_path: Path):
    """A: Windows 10/11 Calculator runs as CalculatorApp.exe while the
    whitelist says calc.exe — every image must be on the kill list."""
    images = close_images("calculator", "calc.exe")
    assert "CalculatorApp.exe" in images
    assert "Calculator.exe" in images
    assert "calc.exe" in images


def test_arabic_app_name_still_resolves_to_every_image(tmp_path: Path):
    """A: the owner says «الآلة الحاسبة» — the alias map resolves it to
    calculator, whose whitelist executable (calc.exe) unlocks the aliases."""
    images = close_images("الآلة الحاسبة", "calc.exe")
    assert "CalculatorApp.exe" in images


def test_chrome_cmd_and_obsidian_aliases(tmp_path: Path):
    """A: the directive's alias table for the other named apps."""
    assert close_images("chrome", "chrome.exe") == ("chrome.exe",)
    assert close_images("cmd", "cmd.exe") == ("cmd.exe",)
    assert close_images("obsidian", "Obsidian.exe") == ("Obsidian.exe",)


def test_unknown_app_gets_exactly_one_image(tmp_path: Path):
    """A: apps with no alias entry keep the untouched single-image behavior."""
    assert close_images("SomeApp", "SomeApp.exe") == ("SomeApp.exe",)


async def test_close_kills_the_running_uwp_calculator(tmp_path: Path, monkeypatch):
    """A (the live symptom): two Calculator windows open as CalculatorApp.exe.
    The old code killed only calc.exe, found zero, and answered «ما لقيت نسخة
    شغالة هسا» while both windows stayed open. Now the table is really empty
    and the verified count is honest."""
    fake = _FakePsutil(["CalculatorApp.exe", "CalculatorApp.exe"])
    monkeypatch.setitem(sys.modules, "psutil", fake)

    ex = Executor(_guard(tmp_path))
    killed_images: list[str] = []

    async def _spawn(argv: list[str]) -> None:
        image = argv[2]
        killed_images.append(image)
        fake.running = [n for n in fake.running if n.casefold() != image.casefold()]

    ex._spawn = _spawn
    result = await ex.close("calculator")

    assert result.status == "ok"
    assert "CalculatorApp.exe" in killed_images  # the UWP image was hunted
    assert result.killed_processes == 2  # psutil-verified, not claimed
    assert fake.running == []  # genuinely gone


async def test_close_reports_zero_when_nothing_runs(tmp_path: Path, monkeypatch):
    """A: no live copies -> an honest zero, never a fabricated success."""
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil([]))
    ex = Executor(_guard(tmp_path))

    async def _noop(argv: list[str]) -> None:
        return None

    ex._spawn = _noop
    result = await ex.close("calculator")
    assert result.status == "ok"
    assert result.killed_processes == 0


# ------------------------------------------------------------- B: prayer times

_PRAYER_PAYLOAD = {
    "data": {
        "timings": {
            "Fajr": "04:50",
            "Dhuhr": "12:35",
            "Asr": "16:11",
            "Maghrib": "19:01",
            "Isha": "20:19",
        }
    }
}


def _prayer_client(box: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        box.append(request)
        return httpx.Response(200, json=_PRAYER_PAYLOAD)

    session = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ExternalAPIs(http=session)


async def test_prayer_times_anchor_to_exact_amman_coordinates():
    """B: no textual city geocoding — Amman's exact lat/lon ride the request."""
    box: list[httpx.Request] = []
    await _prayer_client(box).get_prayer_times()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(str(box[0].url)).query)
    assert q["latitude"] == ["31.9539"]
    assert q["longitude"] == ["35.9106"]


async def test_prayer_times_use_the_jordanian_awqaf_method():
    """B: method 23 = Ministry of Awqaf, Islamic Affairs and Holy Places,
    Jordan (Fajr 18.0° / Isha 18.0°). method 4 was Umm Al-Qura/Saudi."""
    box: list[httpx.Request] = []
    await _prayer_client(box).get_prayer_times()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(str(box[0].url)).query)
    assert q["method"] == ["23"]


async def test_prayer_times_pin_the_amman_timezone():
    """B: an explicit timezone — without it the whole day silently shifts."""
    box: list[httpx.Request] = []
    await _prayer_client(box).get_prayer_times()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(str(box[0].url)).query)
    assert q["timezonestring"] == ["Asia/Amman"]


async def test_prayer_times_never_send_a_city_name():
    """B: the ambiguity that produced the 30-40min drift («Amman» resolving
    towards the Sultanate of Oman) is structurally gone."""
    box: list[httpx.Request] = []
    await _prayer_client(box).get_prayer_times()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(str(box[0].url)).query)
    assert "city" not in q and "country" not in q


async def test_prayer_times_url_carries_a_date_segment():
    """B (root cause): the date-less endpoints answer 302 and the client does
    not follow redirects — prayer times silently returned None. The date
    segment is mandatory (DD-MM-YYYY), defaulting to today in Amman (UTC+3)."""
    box: list[httpx.Request] = []
    await _prayer_client(box).get_prayer_times()
    path = urllib.parse.urlparse(str(box[0].url)).path
    assert re.search(r"/v1/timings/\d{2}-\d{2}-\d{4}$", path), path


async def test_prayer_times_parsed_and_cached():
    """B: the five prayers come back as HH:MM and the 24h TTL serves once."""
    box: list[httpx.Request] = []
    apis = _prayer_client(box)
    first = await apis.get_prayer_times()
    second = await apis.get_prayer_times()
    assert first == {
        "Fajr": "04:50",
        "Dhuhr": "12:35",
        "Asr": "16:11",
        "Maghrib": "19:01",
        "Isha": "20:19",
    }
    assert first == second
    assert len(box) == 1  # the cache served the second call


# ------------------------------------------------------------------- C: weather


class _GeocodeHttp:
    """Open-Meteo answering 200 with an EMPTY results list (a typo'd place)."""

    def __init__(self, body: str = '{"results": []}') -> None:
        self.body = body

    async def get(self, url, **kwargs):
        return type("R", (), {"status_code": 200, "text": self.body})()


async def test_geocode_empty_results_returns_none_instead_of_indexerror():
    """C: «خريبة السوف» -> an empty list. results[0] raised IndexError and
    killed the turn; now it degrades to None."""
    from src.skills.weather import WeatherClient

    client = WeatherClient(http=_GeocodeHttp())
    assert await client._geocode("خريبة السوف") is None


async def test_unknown_place_is_flagged_and_named_in_the_reply():
    """C: the owner gets a friendly Arabic line naming the place he typed,
    not the vague «ما قدرت جيب الطقس» that implies an outage."""
    from src.skills.weather import WeatherClient
    from src.tools import ToolRegistry

    weather = WeatherClient(http=_GeocodeHttp())
    answer = await ToolRegistry(weather=weather).call("weather", "خريبة السوف")
    assert "خريبة السوف" in answer
    assert "ما لقيت" in answer


async def test_weather_outage_still_uses_the_retry_line():
    """C: a dead service (not a bad name) keeps the «جربها بعد شوي» line —
    the two failures must not be conflated."""
    from src.skills.weather import WeatherClient
    from src.tools import ToolRegistry

    class Dead:
        status_code = 500

        async def get(self, url, **kwargs):
            raise OSError("connection reset")

    answer = await ToolRegistry(weather=WeatherClient(http=Dead())).call("weather", "عمان")
    assert "ما قدرت" in answer


def test_no_mixed_loguru_format_strings_in_the_tree():
    """C + G (structural guard): logger.warning("...{name}...{}", a, b) mixes a
    NAMED placeholder with POSITIONAL args. With the default sink loguru raises
    KeyError from inside the except block — it crashed the weather, web and
    create-folder error paths. Any recurrence fails here."""
    broken = re.compile(
        r'logger\.(?:debug|info|warning|error|exception|critical)\(\s*"[^"]*'
        r"\{[A-Za-z_]\w*\}[^\"]*\{\}"
    )
    root = Path(__file__).resolve().parents[1]
    offenders = [
        f"{path.relative_to(root)}:{i}"
        for path in (*(root / "src").rglob("*.py"), *(root / "bridge").rglob("*.py"))
        if "__pycache__" not in str(path)
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if broken.search(line)
    ]
    assert offenders == [], f"mixed loguru placeholders: {offenders}"


# ---------------------------------------------------------------- D: dispatcher


@pytest.mark.parametrize(
    "url",
    [
        "https://adamlankamer.com/ai",
        "http://example.com/page?x=1",
        "https://docs.python.org/3/library/asyncio.html",
    ],
)
def test_bare_url_routes_to_the_jina_reader(url: str):
    """D: a raw URL with no verb is itself a read request — it used to fall
    through to a plain web search and never reach read_webpage_clean."""
    assert _keyword_net(url) == ("read_page", url)


def test_verb_led_url_still_routes_to_the_reader():
    """D: the existing shapes survive the new alternative."""
    tool, arg = _keyword_net("اقراي https://adamlankamer.com/ai")
    assert tool == "read_page"
    assert arg == "https://adamlankamer.com/ai"


@pytest.mark.parametrize(
    "phrase",
    ["اكتمي الصوت", "وطي الصوت", "ارفعي الصوت", "الصوت على 40", "حطي الصوت على ٧٠"],
)
def test_volume_phrases_beat_the_app_launcher(phrase: str):
    """D: «اكتمي الصوت» was misread as closing an app named «الصوت» and
    answered «الصوت مش موجود بالقائمة المعتمدة»."""
    assert _keyword_net(phrase)[0] == "volume"


@pytest.mark.parametrize("phrase", ["شو سعر البيتكوين", "كم سعر البيتكوين هسا", "شو سعر الكريبتو"])
def test_crypto_questions_beat_plain_web_search(phrase: str):
    """D: crypto asks must reach get_crypto_price, not a generic search."""
    assert _keyword_net(phrase)[0] == "crypto_price"


@pytest.mark.parametrize("phrase", ["شو رقم الايبي للجهاز", "الايبي", "شو الشبكة", "شبكة الجهاز"])
def test_ip_and_network_questions_route_to_network_status(phrase: str):
    """D: «شو رقم الايبي للجهاز» must reach check_network_status."""
    assert _keyword_net(phrase)[0] == "network_status"


# --------------------------------------------------------------------- E: voice


async def test_demanded_note_falls_back_to_edge_when_fish_429s():
    """E: Fish Audio quota exhausted (HTTP 429) must NEVER degrade a DEMANDED
    voice note to a text bubble — the local Edge lane speaks it instead."""
    from src.bot import _speak_demanded
    from src.fish_voice import FishVoiceError

    class FishDead:
        async def synthesize(self, text: str) -> bytes:
            raise FishVoiceError("429 quota exhausted", retry_in_s=3600.0)

    class Edge:
        def __init__(self) -> None:
            self.spoken: str | None = None

        async def synthesize(self, text: str) -> bytes:
            self.spoken = text
            return b"OGGS"

    class Bot:
        def __init__(self) -> None:
            self.voices: list[bytes] = []

        async def send_voice(self, chat_id, payload):
            self.voices.append(payload)

    edge, bot = Edge(), Bot()
    spoke = await _speak_demanded(FishDead(), edge, "هلا والله", bot=bot, chat_id=1)

    assert spoke is True
    assert edge.spoken == "هلا والله"  # the SAME text, not an apology
    assert len(bot.voices) == 1  # the bubble actually dispatched


async def test_demanded_note_reports_failure_only_when_both_lanes_die():
    """E: only a double failure returns False — the honest apology line."""
    from src.bot import _speak_demanded

    class Dead:
        async def synthesize(self, text: str) -> bytes:
            raise OSError("both engines down")

    assert await _speak_demanded(Dead(), Dead(), "هلا", bot=None, chat_id=None) is False


# ----------------------------------------------------------------- F: OAuth URL


def test_consent_url_carries_exactly_one_scope_parameter():
    """F: Google rejected «OAuth 2 parameters can only have a single value:
    scope» — the scopes must ride ONE space-separated param (RFC 6749 §3.3)."""
    url = build_consent_url({"client_id": "abc.apps.googleusercontent.com"}, 8765, "st")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert query["scope"] == [" ".join(AUTH_SCOPES)]
    assert len(query["scope"]) == 1


def test_consent_url_scope_is_a_single_encoded_value():
    """F: exactly one scope= occurrence in the generated URL string."""
    url = build_consent_url({"client_id": "cid"}, 8765, "st")
    assert url.count("scope=") == 1
    assert "%20" in url.split("scope=")[1].split("&")[0]  # spaces encoded


# ------------------------------------------------------------- G: vault folders


class _ExplodingVault:
    """A vault whose write fails — the path that used to crash on logging."""

    async def upsert(self, path, content, *, message, merge=None):
        raise OSError("GitHub 403 — token expired")


async def test_create_folder_failure_returns_the_honest_arabic_line():
    """G: a failed folder write must return Sara's honest Arabic line. The
    KeyError:'name' raised by the log formatter used to escape instead, so the
    owner saw a crash («صار في مشكلة») instead of this message."""
    from src.tools import ToolRegistry

    answer = await ToolRegistry(vault=_ExplodingVault()).call("create_folder", "RoutineTasks")
    assert "ما قدرت أنشئ الفولدر" in answer


async def test_create_folder_commits_an_index_note_creating_the_directory():
    """G: the GitHub Contents API creates a directory by committing its first
    note — one _index.md under the sanitized name, nothing else."""
    from src.tools import ToolRegistry

    class Vault:
        def __init__(self) -> None:
            self.files: dict[str, str] = {}
            self.messages: list[str] = []

        async def upsert(self, path, content, *, message, merge=None):
            self.files[path] = content
            self.messages.append(message)
            return type("W", (), {"commit_sha": "abc", "created": True})()

    vault = Vault()
    answer = await ToolRegistry(vault=vault).call("create_folder", "RoutineTasks")
    assert list(vault.files) == ["RoutineTasks/_index.md"]
    assert "[[RoutineTasks/_index]]" in answer
    assert any("RoutineTasks" in m for m in vault.messages)


async def test_create_folder_sanitizes_a_traversal_name():
    """G: the folder name is DATA — never a path escape out of the vault."""
    from src.tools import ToolRegistry

    class Vault:
        def __init__(self) -> None:
            self.files: dict[str, str] = {}

        async def upsert(self, path, content, *, message, merge=None):
            self.files[path] = content
            return type("W", (), {"commit_sha": "abc", "created": True})()

    vault = Vault()
    await ToolRegistry(vault=vault).call("create_folder", "../Escape")
    assert all(".." not in p for p in vault.files)
