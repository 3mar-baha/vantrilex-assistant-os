"""Pass-4 Instagram sandbox (v2.0 §3-أ/5): the account integration is STAGED in
mock/sandbox mode — the full client surface exists (feed fetch, post, DM status)
against a local in-memory backend, so the day the owner drops INSTAGRAM_SESSION
into .env the real transport binds with zero code change (§7 contract). Until
then: sandbox data only, clearly labeled, never pretending to be live."""

from __future__ import annotations

from src.skills.instagram_sandbox import InstagramSandbox, SandboxBackend


def _sandbox() -> InstagramSandbox:
    return InstagramSandbox(SandboxBackend())


async def test_sandbox_is_explicitly_not_live():
    box = _sandbox()
    assert box.mode == "sandbox"
    assert not box.is_live


async def test_sandbox_feed_returns_mock_items_labeled():
    box = _sandbox()
    feed = await box.feed()
    assert isinstance(feed, list) and feed, "sandbox feed carries sample items"
    for item in feed:
        assert item["sandbox"] is True  # every item is labeled — never mistaken for live


async def test_sandbox_post_records_and_labels():
    box = _sandbox()
    result = await box.post("caption", b"image-bytes")
    assert result["sandbox"] is True
    assert result["status"] == "recorded"  # recorded in the sandbox, NOT published


async def test_sandbox_dm_records_recipient_and_text():
    box = _sandbox()
    result = await box.send_dm("user1", "مرحبا")
    assert result["sandbox"] is True
    assert result["to"] == "user1"


async def test_live_mode_flips_only_with_credentials():
    """is_live is True only when a session string exists — the honest gate."""
    box = InstagramSandbox(SandboxBackend(), session_string="fake-session")
    assert box.is_live
    assert box.mode == "live-staged"  # staged: real transport still mock in sandbox tests


async def test_sandbox_backend_isolated_per_instance():
    a = _sandbox()
    b = _sandbox()
    await a.post("caption", b"x")
    feed_b = await b.feed()
    assert feed_b == [] or all(i["type"] == "feed_sample" for i in feed_b)
