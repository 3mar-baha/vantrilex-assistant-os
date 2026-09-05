"""M5 (master directive 2026-09-05 §6): Sara's Obsidian SELF-AWARENESS
capabilities manifest.

Contract:
- The manifest document (02_Areas/Profile/Sara_Capabilities.md) is written
  into the VAULT at runtime (VaultClient.upsert — the live vault, not a
  repo copy), so it rides the same durable git-backed state as User_Info.
- load_long_term() injects it into the context envelope alongside
  User_Info / Dialect_Notes / the daily ledger — Sara's brain is primed
  with her exact operational powers on EVERY router call.
- The manifest is DATA: every tool name, trigger phrase, and the modality
  rules (the voice-demand law) — enough that she never claims inability or
  invents a capability that does not exist.
- The envelope cache (C-10) serves it without extra vault reads.
"""

from __future__ import annotations

from datetime import date


class _Vault:
    """In-memory vault double: read/upsert with a files dict."""

    def __init__(self, files: dict[str, str] | None = None):
        self.files = dict(files or {})
        self.upserts: list[str] = []

    async def read(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def upsert(self, path: str, content: str, *, message: str = "", merge=None) -> None:
        self.upserts.append(path)
        self.files[path] = content


def test_manifest_content_carries_every_capability():
    """The generated manifest: the identity block, every tool zone with its
    trigger phrasings, and the modality rules (the voice-demand law)."""
    from src.memory import build_capabilities_manifest

    manifest = build_capabilities_manifest()
    # identity
    assert "سارة" in manifest and "عمر" in manifest and ("عمان" in manifest or "عمّان" in manifest)
    # the tool zones the owner can name in one line (spot the critical ones)
    for needle in (
        "الآلة الحاسبة",  # launch
        "شو وضع الجهاز",  # telemetry
        "لقطة",  # screenshot
        "التطبيقات",  # running_apps + whitelist_apps
        "تذكير",  # schedule + list/cancel
        "الجيميل",  # gmail
        "الطقس",  # weather
        "يوتيوب",  # youtube
        "النت",  # web_search
        "الصوت",  # volume
        "الفيديو",  # media
        "الشاشة",  # screen_ocr + screenshot
        "الصلاة",  # prayer_times
        "البيتكوين",  # crypto
        "دولار",  # currency
        "التقنية",  # tech_trending
        "الايبي",  # network_status
        "الرابط",  # read_page
        "ملف",  # file_fetch
    ):
        assert needle in manifest, needle
    # the modality laws
    assert "صوتية" in manifest  # the voice-demand law
    assert "نص" in manifest


async def test_manifest_written_to_the_live_vault():
    """run-time write: the manifest lands at 02_Areas/Profile/
    Sara_Capabilities.md through VaultClient.upsert (the durable git-backed
    vault — not a repo file)."""
    from src.memory import SARA_CAPABILITIES_PATH, sync_capabilities_manifest

    vault = _Vault()
    wrote = await sync_capabilities_manifest(vault)
    assert wrote is True
    assert vault.upserts == [SARA_CAPABILITIES_PATH]
    assert "سارة" in vault.files[SARA_CAPABILITIES_PATH]


async def test_load_long_term_injects_the_manifest():
    """The envelope: Sara_Capabilities.md rides with User_Info +
    Dialect_Notes + the daily ledger; a missing manifest degrades silently
    (the chat never blocks on self-knowledge)."""
    from src.memory import (
        SARA_CAPABILITIES_PATH,
        load_long_term,
        reset_context_cache,
    )

    reset_context_cache()
    vault = _Vault(
        {
            "02_Areas/Profile/User_Info.md": "عمر الفياض من خريبة السوق.",
            SARA_CAPABILITIES_PATH: "# قدرات سارة\n\n- بفتح البرامج.",
        }
    )
    envelope = await load_long_term(vault, today=date(2026, 9, 5))
    assert "قدرات سارة" in envelope  # the manifest IS in the context
    assert "عمر الفياض" in envelope  # ...alongside the profile

    # missing manifest -> the rest still loads (honest degrade)
    reset_context_cache()
    vault2 = _Vault({"02_Areas/Profile/User_Info.md": "بيانات"})
    envelope2 = await load_long_term(vault2, today=date(2026, 9, 5))
    assert "بيانات" in envelope2
    assert "قدرات" not in envelope2
    reset_context_cache()


async def test_envelope_cache_serves_manifest_without_rereads():
    """C-10: the second load within the TTL serves from cache — the manifest
    does not double the envelope's vault traffic."""
    from src.memory import _CONTEXT_CACHE, load_long_term, reset_context_cache

    reset_context_cache()
    vault = _Vault(
        {
            __import__(
                "src.memory", fromlist=["SARA_CAPABILITIES_PATH"]
            ).SARA_CAPABILITIES_PATH: "قدرات"
        }
    )
    await load_long_term(vault, today=date(2026, 9, 5))
    reads_first = dict(_CONTEXT_CACHE)
    await load_long_term(vault, today=date(2026, 9, 5))
    assert len(_CONTEXT_CACHE) == len(reads_first)  # no new entries
    assert "قدرات" in (await load_long_term(vault, today=date(2026, 9, 5)))
