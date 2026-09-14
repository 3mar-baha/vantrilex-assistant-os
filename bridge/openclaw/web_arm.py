"""Interactive Web Arm (Phase 3.3): Playwright over an isolated profile.

- Dedicated profile dir (default ~/.sara/browser_profile/) — NEVER the
  owner's real Chrome profile (session-theft blast radius).
- Perception: accessibility-tree snapshot -> ElementHandle list
  (deterministic e1..en ids, source="dom"). Relocation re-queries by
  (role, name): duplicate names resolve first-match (documented limit;
  SoM vision disambiguates in later phases).
- Actions: navigate (http/https only), click_by_role, type_into_input
  (fill — never submits), scroll. All return observation dicts.
- SoM-lite: render_marks() overlays numbered boxes on a capture via
  Pillow when tree lookup fails.

Playwright imports lazily (PC wheels only) — missing wheels raise
BrowserUnavailable, never ImportError outward. Every browser handle
injects through `factory`, so tests run headless-by-construction.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from io import BytesIO
from pathlib import Path
from typing import Any, Final

from loguru import logger

from bridge.openclaw.fetch_arm import check_url
from bridge.openclaw.protocol import ElementHandle

DEFAULT_PROFILE_DIR: Final[str] = str(Path.home() / ".sara" / "browser_profile")
SCROLL_STEP_PX: Final[int] = 500


class BrowserUnavailable(Exception):
    """No browser backend (wheels missing, session unstarted/failed)."""


def parse_a11y_tree(tree: dict[str, Any]) -> list[ElementHandle]:
    """Depth-first walk of a Playwright accessibility snapshot into stable
    handles. Nameless nodes keep their role (resolvable, honest)."""

    handles: list[ElementHandle] = []

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        role = str(node.get("role") or "unknown")
        name = str(node.get("name") or "")
        handles.append(ElementHandle(id=f"e{len(handles) + 1}", role=role, name=name, source="dom"))
        for child in node.get("children") or []:
            _walk(child)

    _walk(tree or {})
    return handles


def render_marks(jpeg: bytes, marks: list[tuple[str, tuple[int, int, int, int]]]) -> bytes:
    """Set-of-Marks lite: numbered red boxes over a capture. Pure Pillow."""
    from PIL import Image, ImageDraw

    img = Image.open(BytesIO(jpeg)).convert("RGB")
    draw = ImageDraw.Draw(img)
    for index, (_handle_id, box) in enumerate(marks, start=1):
        x0, y0, x1, y1 = (int(v) for v in box)
        draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=3)
        draw.text((x0 + 4, y0 + 4), str(index), fill=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


class BrowserArm:
    """Isolated-profile browser session. All Playwright contact flows
    through the injected factory; the default factory lazy-loads wheels."""

    def __init__(
        self,
        *,
        profile_dir: str | None = None,
        factory: Callable[[str], Awaitable[Any]] | None = None,
        headless: bool = True,
    ) -> None:
        self._profile_dir = profile_dir or DEFAULT_PROFILE_DIR
        self._factory = factory
        self._headless = headless
        self._session: Any = None

    async def start(self) -> dict[str, Any]:
        if self._session is not None:
            return {"ok": True, "reused": True}
        factory = self._factory or _default_factory(self._headless)
        try:
            self._session = await factory(self._profile_dir)
        except ImportError as exc:
            raise BrowserUnavailable(f"playwright wheels not installed: {exc}") from exc
        except Exception as exc:
            raise BrowserUnavailable(f"browser launch failed: {exc}") from exc
        logger.info("openclaw browser session started (profile {})", self._profile_dir)
        return {"ok": True, "profile": self._profile_dir}

    async def close(self) -> None:
        session, self._session = self._session, None
        if session is None:
            return
        try:
            await session.aclose()
        except Exception as exc:  # noqa: BLE001 — close is best-effort teardown
            logger.warning("openclaw browser close failed: {}", exc)

    def _page(self) -> Any:
        if self._session is None:
            raise BrowserUnavailable("browser session not started")
        return self._session.page

    async def snapshot(self) -> list[ElementHandle]:
        tree = await self._page().accessibility.snapshot()
        return parse_a11y_tree(tree or {})

    async def navigate(self, url: str) -> dict[str, Any]:
        target = check_url(url)
        if target is None:
            raise ValueError(f"refused browse target: {url!r}")
        await self._page().goto(target)
        return {"ok": True, "url": target}

    async def click_by_role(self, role: str, name: str | None = None) -> dict[str, Any]:
        await self._page().get_by_role(role, name=name).first.click()
        return {"ok": True, "role": role, "name": name or ""}

    async def type_into(self, role: str, name: str | None, text: str) -> dict[str, Any]:
        """Non-commit typing only: fill() never submits — the breaker gates
        any submit-shaped op before this lane is ever reached."""
        await self._page().get_by_role(role, name=name).first.fill(text)
        return {"ok": True, "role": role, "name": name or "", "chars": len(text)}

    async def scroll(self, direction: str = "down") -> dict[str, Any]:
        delta = -SCROLL_STEP_PX if direction.strip().casefold() in ("up", "top") else SCROLL_STEP_PX
        await self._page().mouse.wheel(0, delta)
        return {"ok": True, "direction": direction, "dy": delta}


def _default_factory(headless: bool) -> Callable[[str], Awaitable[Any]]:
    """Real Playwright binding (PC only): persistent isolated profile."""

    async def _launch(profile_dir: str) -> Any:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserUnavailable(
                "playwright wheels not installed (requirements-bridge.txt)"
            ) from exc

        pw = await async_playwright().start()
        context = await pw.chromium.launch_persistent_context(profile_dir, headless=headless)
        page = context.pages[0] if context.pages else await context.new_page()

        class _LiveSession:
            async def aclose(self) -> None:
                try:
                    await context.close()
                finally:
                    await pw.stop()

        session = _LiveSession()
        session.page = page  # type: ignore[attr-defined]
        return session

    return _launch
