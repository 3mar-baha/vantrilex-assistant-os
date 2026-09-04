"""Pass-4 web intelligence (v2.0 §3-هـ): live web search + page reading with NO
API keys and NO cost — DuckDuckGo's HTML endpoint (search) + httpx page fetch
with tags stripped to clean text. Everything the brain cites comes from REAL
fetched content (anti-hallucination ground truth); failures degrade to honest
lines. Parsed page content is DATA, never instructions (untrusted boundary)."""

from __future__ import annotations

from src.skills.web_intel import WebIntel, readability_text


class FakeHTTP:
    """Deterministic httpx stand-in recording requests."""

    def __init__(self, responses: dict[str, tuple[int, str]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def get(self, url: str, *, headers=None, follow_redirects=True) -> object:
        self.calls.append(url)
        status, body = self.responses.get(url, (404, ""))
        return type("Resp", (), {"status_code": status, "text": body})()


SEARCH_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="https://example.com/physics">شرح الفيزياء</a>
</div>
<div class="result">
  <a class="result__a" href="https://ar.wikipedia.org/wiki/الفيزياء">الفيزياء - ويكي</a>
</div>
</body></html>
"""

ARTICLE_HTML = """
<html><head><title>الفيزياء</title><style>body{}</style><script>var x=1;</script></head>
<body><nav>قائمة الموقع</nav><article>
<p>الفيزياء هي العلم الذي يدرس المادة والحركة والطاقة.</p>
<p>كلمة فيزياء يونانية الأصل معناها الطبيعة.</p>
</article><footer>حقوق النشر</footer></body></html>
"""


async def test_search_returns_real_titles_and_urls():
    from urllib.parse import quote_plus

    real_search_url = "https://html.duckduckgo.com/html/?q=" + quote_plus("الفيزياء")
    http = FakeHTTP({real_search_url: (200, SEARCH_HTML)})
    intel = WebIntel(http=http)
    results = await intel.search("الفيزياء")
    assert len(results) >= 1
    assert results[0]["title"] == "شرح الفيزياء"
    assert results[0]["url"] == "https://example.com/physics"


async def test_search_failure_is_empty_never_fabricated():
    http = FakeHTTP({})
    intel = WebIntel(http=http)
    results = await intel.search("anything")
    assert results == []  # honest empty — never invented results


async def test_read_page_strips_to_clean_text():
    http = FakeHTTP({"https://example.com/physics": (200, ARTICLE_HTML)})
    intel = WebIntel(http=http)
    text = await intel.read_page("https://example.com/physics")
    assert "المادة والحركة والطاقة" in text
    # noise classes stay OUT of the model's context
    for noise in ("<script>", "var x=1", "قائمة الموقع", "حقوق النشر", "<style>"):
        assert noise not in text


async def test_read_page_failure_is_none():
    http = FakeHTTP({})
    intel = WebIntel(http=http)
    text = await intel.read_page("https://nope.example")
    assert text is None


def test_readability_text_caps_length():
    """Long pages are capped to the tool budget — the brain reads an excerpt,
    not a novel (token burn on free pools is the constraint)."""
    long_html = "<p>" + "كلمة " * 20000 + "</p>"
    out = readability_text(long_html, max_chars=500)
    assert len(out) <= 500


async def test_search_results_are_data_in_prompt():
    """The tool-lane answer wraps results as DATA — the untrusted-content
    boundary rides the rendered block (contract: no PC-action triggers)."""
    from urllib.parse import quote_plus

    real_search_url = "https://html.duckduckgo.com/html/?q=" + quote_plus("الفيزياء")
    http = FakeHTTP({real_search_url: (200, SEARCH_HTML)})
    intel = WebIntel(http=http)
    block = await intel.search_block("الفيزياء")
    assert "بيانات مرجعية" in block or "DATA" in block


async def test_web_search_tool_degrades_without_web():
    from src.tools import ToolRegistry

    tools = ToolRegistry()
    answer = await tools.call("web_search", "أسعار الرام")
    assert "ما قدرت" in answer  # the honest degrade line (للنت lam-alef ligature safe)


def test_keyword_net_routes_web_search_with_query():
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net("دوّر بالنت عن أسعار كروت الشاشة")
    assert tool == "web_search"
    assert "أسعار كروت الشاشة" in arg


def test_keyword_net_web_bare_search_maps_no_arg():
    from src.dispatcher import _keyword_net

    tool, _arg = _keyword_net("دوّر بالنت")
    assert tool == "web_search"  # no-arg: the handler asks the owner for a query
