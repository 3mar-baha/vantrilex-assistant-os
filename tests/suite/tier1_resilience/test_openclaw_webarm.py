"""Tier 1 — OpenClaw Phase-3.3 interactive web arm. Hermetic.

Every browser handle is a fake: no Playwright wheels (absent in dev/CI),
no window ever opens, no network flows. The missing-wheels path is
deterministic via sys.modules masking (not via env luck).
"""

import sys

import pytest

from bridge.openclaw.protocol import ElementHandle
from bridge.openclaw.web_arm import (
    BrowserArm,
    BrowserUnavailable,
    parse_a11y_tree,
    render_marks,
)

TREE = {
    "role": "WebArea",
    "name": "Shop",
    "children": [
        {"role": "textbox", "name": "Search products"},
        {
            "role": "button",
            "name": "Search",
            "children": [{"role": "text", "name": "go"}],
        },
        {"role": "link", "name": "Cart (2)"},
        {"role": "generic"},  # nameless node still resolves
    ],
}


def test_parse_a11y_tree_assigns_stable_ids():
    handles = parse_a11y_tree(TREE)
    by_id = {h.id: h for h in handles}
    assert [h.role for h in handles] == ["WebArea", "textbox", "button", "text", "link", "generic"]
    assert by_id["e2"].name == "Search products"
    assert all(h.source == "dom" for h in handles)
    assert all(isinstance(h, ElementHandle) for h in handles)
    # deterministic: same tree, same ids, every run
    assert [h.id for h in parse_a11y_tree(TREE)] == [h.id for h in handles]


class _FakeLocator:
    def __init__(self, page, role, name):
        self._page = page
        self.role = role
        self.name = name

    @property
    def first(self):
        return self

    async def click(self):
        self._page.calls.append(("click", self.role, self.name))

    async def fill(self, text):
        self._page.calls.append(("fill", self.role, self.name, text))


class _FakeMouse:
    def __init__(self, page):
        self._page = page

    async def wheel(self, dx, dy):
        self._page.calls.append(("wheel", dx, dy))


class _FakeAPage:
    def __init__(self, tree):
        self.tree = tree
        self.calls = []
        self.mouse = _FakeMouse(self)

    @property
    def accessibility(self):
        page = self

        class _A11y:
            async def snapshot(self):
                return page.tree

        return _A11y()

    def get_by_role(self, role, name=None):
        return _FakeLocator(self, role, name)

    async def goto(self, url):
        self.calls.append(("goto", url))

    async def screenshot(self):
        return b"SHOT"


class _FakeSession:
    def __init__(self, page):
        self.page = page
        self.closed = False

    async def aclose(self):
        self.closed = True


def _arm(tree=TREE):
    page = _FakeAPage(tree)

    async def factory(profile_dir):
        factory.seen = str(profile_dir)
        return _FakeSession(page)

    arm = BrowserArm(profile_dir="/tmp/sara-prof", factory=factory)
    return arm, page


async def test_snapshot_maps_tree_to_handles():
    arm, _page = _arm()
    await arm.start()
    handles = await arm.snapshot()
    assert [h.id for h in handles][:3] == ["e1", "e2", "e3"]
    assert handles[2].name == "Search"
    await arm.close()


async def test_navigate_validates_and_drives():
    arm, page = _arm()
    await arm.start()
    obs = await arm.navigate("https://example.com/x")
    assert obs["ok"] is True and ("goto", "https://example.com/x") in page.calls
    with pytest.raises(ValueError):
        await arm.navigate("file:///etc/passwd")
    await arm.close()


async def test_click_and_type_relocate_by_role():
    arm, page = _arm()
    await arm.start()
    await arm.click_by_role("button", "Search")
    await arm.type_into("textbox", "Search products", "منسف")
    assert ("click", "button", "Search") in page.calls
    assert ("fill", "textbox", "Search products", "منسف") in page.calls
    # fill never submits: no Enter/\\n smuggled into the typed text
    fills = [c for c in page.calls if c[0] == "fill"]
    assert all("\n" not in c[3] and "{ENTER}" not in c[3] for c in fills)
    await arm.close()


async def test_scroll_signed_deltas():
    arm, page = _arm()
    await arm.start()
    await arm.scroll("down")
    await arm.scroll("up")
    assert ("wheel", 0, 500) in page.calls
    assert ("wheel", 0, -500) in page.calls
    await arm.close()


async def test_unstarted_arm_is_honest():
    arm, _page = _arm()
    with pytest.raises(BrowserUnavailable):
        await arm.snapshot()
    await arm.close()  # safe no-op, never raises


async def test_missing_wheels_raise_unavailable(monkeypatch):
    """Deterministic missing-Playwright: mask the module, no env luck."""
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.async_api", None)
    arm = BrowserArm(profile_dir="/tmp/sara-prof")
    with pytest.raises(BrowserUnavailable):
        await arm.start()


def test_som_overlay_marks_boxes():
    from io import BytesIO

    from PIL import Image

    blank = Image.new("RGB", (200, 100), "white")
    buf = BytesIO()
    blank.save(buf, format="JPEG")
    out = render_marks(buf.getvalue(), [("e1", (10, 10, 60, 40)), ("e2", (100, 20, 180, 80))])
    assert isinstance(out, bytes) and len(out) > 0
    img = Image.open(BytesIO(out))
    assert img.size == (200, 100)
    px = img.load()
    reds = sum(
        1
        for x in range(0, 200, 2)
        for y in range(0, 100, 2)
        if px[x, y][0] > 200 and px[x, y][1] < 100 and px[x, y][2] < 100
    )
    assert reds > 10  # two outlined boxes + numeric labels actually painted
