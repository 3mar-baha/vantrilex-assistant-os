"""Simulated web double (Phase 4): recorded a11y snapshots + SoM boxes.

A tiny in-memory web: pages are recorded trees, navigation is a dict
lookup, fills/clicks are recorded calls. Unknown URLs refuse loudly
(WebNotRecorded) — the double never improvises content.
"""

from __future__ import annotations

from io import BytesIO

SHOP_TREE = {
    "role": "WebArea",
    "name": "Shop",
    "children": [
        {"role": "textbox", "name": "Search products"},
        {"role": "button", "name": "Search"},
        {"role": "link", "name": "Cart (2)"},
        {
            "role": "dialog",
            "name": "Sale popup",
            "children": [{"role": "button", "name": "Dismiss"}],
        },
    ],
}

LOGIN_TREE = {
    "role": "WebArea",
    "name": "Login",
    "children": [
        {"role": "textbox", "name": "Username"},
        {"role": "textbox", "name": "Password"},
        {"role": "button", "name": "Sign in"},
    ],
}

RECORDED_PAGES: dict[str, dict] = {
    "https://shop.example/": {"tree": SHOP_TREE, "boxes": {"e2": (10, 10, 200, 40)}},
    "https://shop.example/login": {"tree": LOGIN_TREE, "boxes": {}},
}


class WebNotRecorded(Exception):
    """Navigation to a URL outside the recorded set."""


class WebElementMissing(Exception):
    """Role/name lookup missed the current snapshot."""


class MockLocator:
    def __init__(self, page: MockWebPage, role: str, name: str | None) -> None:
        self._page = page
        self._role = (role or "").casefold()
        self._name = (name or "").casefold()

    @property
    def first(self) -> MockLocator:
        return self

    def _resolve(self) -> dict:
        for node in _walk(self._page.tree):
            if node.get("role", "").casefold() != self._role:
                continue
            if self._name and self._name not in node.get("name", "").casefold():
                continue
            return node
        raise WebElementMissing(f"{self._role}/{self._name or ''}")

    async def click(self) -> None:
        node = self._resolve()
        self._page.calls.append(("click", node.get("role"), node.get("name")))

    async def fill(self, text: str) -> None:
        node = self._resolve()
        node["filled"] = text
        self._page.calls.append(("fill", node.get("role"), node.get("name"), text))


def _walk(tree: dict):
    yield tree
    for child in tree.get("children") or []:
        yield from _walk(child)


class MockMouse:
    def __init__(self, page: MockWebPage) -> None:
        self._page = page

    async def wheel(self, dx: int, dy: int) -> None:
        self._page.calls.append(("wheel", dx, dy))


class MockWebPage:
    def __init__(self, pages: dict[str, dict] | None = None) -> None:
        self._pages = pages if pages is not None else dict(RECORDED_PAGES)
        self.tree: dict = {"role": "WebArea", "name": "blank", "children": []}
        self.url = "about:blank"
        self.calls: list[tuple] = []
        self.mouse = MockMouse(self)

    @property
    def accessibility(self) -> MockWebPage:
        return self

    async def snapshot(self) -> dict:
        return self.tree

    def get_by_role(self, role: str, name: str | None = None) -> MockLocator:
        return MockLocator(self, role, name)

    async def goto(self, url: str) -> None:
        if url not in self._pages:
            raise WebNotRecorded(url)
        self.url = url
        import copy

        self.tree = copy.deepcopy(self._pages[url]["tree"])
        self.calls.append(("goto", url))

    async def screenshot(self) -> bytes:
        from PIL import Image

        img = Image.new("RGB", (320, 200), "white")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        self.calls.append(("screenshot",))
        return buf.getvalue()


class MockWebSession:
    def __init__(self, page: MockWebPage) -> None:
        self.page = page
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def mock_browser_factory(pages: dict[str, dict] | None = None):
    """BrowserArm factory double: fresh recorded page per session."""

    async def _factory(profile_dir: str) -> MockWebSession:
        _factory.seen = str(profile_dir)
        return MockWebSession(MockWebPage(pages))

    return _factory
