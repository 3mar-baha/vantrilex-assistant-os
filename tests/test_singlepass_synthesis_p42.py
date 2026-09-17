"""P4.2 single-pass synthesis pins (master transformation plan, Phase P4.2).

The turn architecture is one verdict call + one answer stream — no chained
synthesis passes. These tests pin that shape: a direct turn touches the
brain exactly twice, and the transient placeholder/ack never reaches memory.
(Ack-transience on the ack-only path is pinned in test_bot_shell.py; here is
the full-turn-with-memory variant.)
"""

from src.memory import ConversationMemory
from tests.conftest import OWNER_ID, StreamProgram, make_update
from tests.test_bot_shell import _router, _run


async def test_direct_turn_two_model_touches_total(fake_bot, make_shell):
    """Verdict + answer, nothing else: chains would show up here first."""
    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[StreamProgram(deltas=("أهلين عمر",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "مرحبا"))
    assert len(shell.gateway.router_calls) == 1
    assert len(shell.gateway.stream_calls) == 1


async def test_placeholder_and_ack_never_reach_memory(fake_bot, make_shell):
    """Full turn with memory wired: history holds user + answer only."""
    memory = ConversationMemory()
    shell = make_shell(
        memory=memory,
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[StreamProgram(deltas=("أهلين عمر",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "مرحبا"))
    history = memory.history(OWNER_ID)
    assert {"role": "user", "content": "مرحبا"} in history
    assert {"role": "assistant", "content": "أهلين عمر"} in history
    blob = " ".join(turn["content"] for turn in history)
    assert "…" not in blob
    assert "أهلا" not in blob
