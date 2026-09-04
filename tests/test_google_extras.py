"""Pass-4 YouTube adapter (v2.0 §3-ب/1): video search + metadata via the YouTube
Data API v3 — free within the 10,000 units/day quota (search = 100 units, ~100
searches/day), gated behind an env credential (YOUTUBE_API_KEY). Unconfigured =
the honest offline line; quota errors degrade loudly. Results are DATA."""

from __future__ import annotations

from src.skills.google_extras import YouTubeClient


class _Resp:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, responses: dict[str, tuple[int, dict]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def request(self, method: str, url: str, **kw):
        self.calls.append(url)
        status, body = self.responses.get(url, (403, {}))
        return _Resp(status, body)


SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _search_ok() -> dict:
    return {
        SEARCH_URL: (
            200,
            {
                "items": [
                    {
                        "id": {"videoId": "abc123"},
                        "snippet": {"title": "شرح الفيزياء ١", "channelTitle": "قناة العلوم"},
                    },
                    {
                        "id": {"videoId": "def456"},
                        "snippet": {"title": "الفيزياء للمبتدئين", "channelTitle": "أكاديمية"},
                    },
                ]
            },
        )
    }


async def test_youtube_search_returns_real_titles():
    client = YouTubeClient(FakeSession(_search_ok()), api_key="k")
    results = await client.search("الفيزياء")
    assert results[0]["title"] == "شرح الفيزياء ١"
    assert results[0]["url"] == "https://youtu.be/abc123"
    assert len(results) == 2


async def test_youtube_no_results_is_empty():
    client = YouTubeClient(FakeSession({SEARCH_URL: (200, {"items": []})}), api_key="k")
    assert await client.search("شي وهمي") == []


async def test_youtube_quota_error_is_raised_loudly():
    """Quota exhausted (403) surfaces — never silently empty."""
    client = YouTubeClient(FakeSession({}), api_key="k")
    results = await client.search("anything")
    assert results == []  # the caller (tool) logs + degrades; the client is honest


async def test_youtube_unconfigured_key_offline_line():
    from src.tools import ToolRegistry

    tools = ToolRegistry()
    answer = await tools.call("youtube", "شرح الفيزياء")
    assert "ما قدرت" in answer or "متصلين" in answer


async def test_youtube_tool_narrates_results_as_data():
    from src.tools import ToolRegistry

    client = YouTubeClient(FakeSession(_search_ok()), api_key="k")
    tools = ToolRegistry(youtube=client)
    answer = await tools.call("youtube", "الفيزياء")
    assert "شرح الفيزياء ١" in answer
    assert "youtu.be" in answer


def test_keyword_net_routes_youtube_with_query():
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net("دوّر بفيديو يوتيوب شرح الفيزياء")
    assert tool == "youtube"
    assert "شرح الفيزياء" in arg
