"""SACRED FLOOR — owner-ID silent drop (sprint-1 §1.4 AC1-AC5, carried into Sprint-2 2.2).

Untouchable safety floor: every future methodology amendment leaves this file green,
and it blocks every merge. Stranger updates produce literally zero outbound Telegram
traffic because handlers are the sole outbound origin.
"""

from src.bot import build_dispatcher
from src.middleware import OwnerOnlyMiddleware, _extract_user_id
from tests.conftest import OWNER_ID, FakeGateway, FakeVoice, make_callback_update, make_update


def _build(make_settings):
    return build_dispatcher(FakeGateway(), FakeVoice(), make_settings())


async def test_non_owner_message_dropped_zero_outbound_calls(
    fake_bot, stranger_update, make_settings
):
    """AC1: stranger private text -> zero handler invocations, zero outbound methods."""
    bot = fake_bot()
    dp = _build(make_settings)
    await dp.feed_update(bot, stranger_update)
    assert bot.session.calls == []


async def test_non_owner_callback_query_also_dropped(fake_bot, make_settings):
    """AC2: stranger callback_query equally dropped — no reply, no processing."""
    bot = fake_bot()
    dp = _build(make_settings)
    await dp.feed_update(bot, make_callback_update(3, 987654321))
    assert bot.session.calls == []


async def test_extract_user_id_shapes():
    """AC3: owner id resolved from message AND callback_query shapes; None when anonymous."""
    assert _extract_user_id(make_update(1, OWNER_ID, "hi")) == OWNER_ID
    assert _extract_user_id(make_callback_update(2, OWNER_ID)) == OWNER_ID
    assert _extract_user_id(make_update(3, None, "hi")) is None


async def test_owner_update_reaches_handler():
    """AC4: owner update passes through exactly once, untouched."""
    mw = OwnerOnlyMiddleware(OWNER_ID)
    seen: list[object] = []

    async def handler(event, data):
        seen.append(event)

    owner = make_update(1, OWNER_ID, "hi")
    await mw(handler, owner, {})
    assert seen == [owner]


def test_middleware_registered_at_update_outer_level(make_settings):
    """AC5: the owner gate sits on dp.update.outer_middleware (introspection)."""
    dp = _build(make_settings)
    assert any(isinstance(m, OwnerOnlyMiddleware) for m in dp.update.outer_middleware)
