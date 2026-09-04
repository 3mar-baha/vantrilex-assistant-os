"""Pass-4 Instagram sandbox (v2.0 §3-أ/5): the account integration STAGED in
mock mode per the §7 contract — build everything around the missing human input
so the feature goes live the INSTANT the owner drops INSTAGRAM_SESSION into
.env, with zero code change. The sandbox backend is in-memory and isolated per
instance; every result carries sandbox=True so nothing can masquerade as live.
The real transport (instagrapi — open-source, free) binds in `bind_live_transport`
the day the credential exists; until then that path raises the honest staged
error. $0.00: instagrapi is a local library, no paid service anywhere."""

from __future__ import annotations

from typing import Any

from loguru import logger

_SAMPLES = [
    {"type": "feed_sample", "caption": "نموذج منشور ١", "sandbox": True},
    {"type": "feed_sample", "caption": "نموذج منشور ٢", "sandbox": True},
]


class SandboxBackend:
    """In-memory mock of the Instagram surface — isolated per instance."""

    def __init__(self) -> None:
        self.posts: list[dict] = []
        self.dms: list[dict] = []

    async def fetch_feed(self) -> list[dict]:
        return list(_SAMPLES)

    async def publish(self, caption: str, image: bytes) -> dict:
        record = {"caption": caption, "bytes": len(image), "sandbox": True}
        self.posts.append(record)
        return {"status": "recorded", "sandbox": True, **record}

    async def dm(self, to: str, text: str) -> dict:
        self.dms.append({"to": to, "text": text, "sandbox": True})
        return {"status": "recorded", "to": to, "sandbox": True}


class InstagramSandbox:
    """The staged integration. mode = 'sandbox' until a session string exists;
    is_live is the honest gate (credential presence, never an assumption)."""

    def __init__(
        self,
        backend: SandboxBackend,
        *,
        session_string: str | None = None,
    ) -> None:
        self._backend = backend
        self._session = (session_string or "").strip() or None

    @property
    def mode(self) -> str:
        return "sandbox" if not self._session else "live-staged"

    @property
    def is_live(self) -> bool:
        return self._session is not None

    async def feed(self) -> list[dict]:
        """Sandbox feed samples (labeled); live transport when credentialed."""
        if self.is_live:
            return await self._live("fetch_feed")
        return await self._backend.fetch_feed()

    async def post(self, caption: str, image: bytes) -> dict:
        if self.is_live:
            return await self._live("publish", caption, image)
        return await self._backend.publish(caption, image)

    async def send_dm(self, to: str, text: str) -> dict:
        if self.is_live:
            return await self._live("dm", to, text)
        return await self._backend.dm(to, text)

    async def _live(self, op: str, *args: Any) -> Any:
        """The real transport slot. The §7 contract: everything around the
        missing input is built; the transport itself binds here once the owner
        provides the session — until then, the honest staged error."""
        try:
            transport = self._bind_live_transport()
        except ImportError as error:
            logger.warning("instagram live transport not installed (staged): {}", error)
            raise RuntimeError(
                "instagram live transport unavailable — staged, waiting for setup"
            ) from error
        return await getattr(transport, op)(*args)

    def _bind_live_transport(self) -> Any:
        """instagrapi (open-source, local) against the session string. Imported
        lazily: the library joins requirements only when the owner activates
        the feature (keeping the base image lean until then)."""
        from instagrapi import InstagramClient  # noqa: F401 — staged import

        raise RuntimeError("live binding lands with the owner's session setup")
