"""Pass-4 Firecrawl MCP (v2.0 §3-هـ/1): official integration for extracting
complex web pages/articles into clean compact Markdown — STAGED per §7 behind
FIRECRAWL_API_KEY (the free tier carries the $0.00). Unconfigured = honest
staged-off; configured = real scrapes. Until the key arrives, the open
fallback path is WebIntel.read_page (already live). Results are DATA."""

from __future__ import annotations

from src.skills.firecrawl import FirecrawlClient


class _Resp:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


class FakeHTTP:
    def __init__(self, responses: dict) -> None:
        self.responses = responses
        self.calls = []

    async def post(self, url, *, json=None, headers=None):
        self.calls.append((url, json))
        status, body = self.responses.get(url, (401, {}))
        return _Resp(status, body)


SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"


async def test_scrape_returns_clean_markdown():
    http = FakeHTTP(
        {
            SCRAPE_URL: (
                200,
                {
                    "success": True,
                    "data": {
                        "markdown": "# العنوان\n\nفقرة نظيفة بدون إعلانات.",
                        "metadata": {"title": "العنوان"},
                    },
                },
            )
        }
    )
    client = FirecrawlClient(http=http, api_key="fc-key")
    doc = await client.scrape("https://example.com/article")
    assert doc is not None
    assert "فقرة نظيفة" in doc["markdown"]
    assert doc["title"] == "العنوان"


async def test_scrape_failure_is_none():
    http = FakeHTTP({})
    client = FirecrawlClient(http=http, api_key="fc-key")
    assert await client.scrape("https://nope.example") is None


async def test_scrape_unconfigured_key_is_none():
    """No key (staged off) -> None, never a fabricated doc."""
    client = FirecrawlClient(http=FakeHTTP({}), api_key="")
    assert await client.scrape("https://example.com") is None


async def test_scrape_budgets_the_markdown():
    """Long articles are capped — free-tier token burn is the constraint."""
    http = FakeHTTP(
        {
            SCRAPE_URL: (
                200,
                {"success": True, "data": {"markdown": "كلمة " * 20000, "metadata": {}}},
            )
        }
    )
    client = FirecrawlClient(http=http, api_key="fc-key")
    doc = await client.scrape("https://example.com")
    assert len(doc["markdown"]) <= 4000
