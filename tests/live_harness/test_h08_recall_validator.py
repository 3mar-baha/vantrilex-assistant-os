"""H08 — Recall validator: 30-round rolling window keeps order and cap."""

from src.memory import ConversationMemory


def test_thirty_rounds_keep_last_fifty_in_order():
    memory = ConversationMemory()
    for i in range(30):
        memory.remember(1, "user", f"سؤال {i}")
        memory.remember(1, "assistant", f"جواب {i}")
    history = memory.history(1)
    assert len(history) == 50
    assert history[0] == {"role": "user", "content": "سؤال 5"}
    assert history[-1] == {"role": "assistant", "content": "جواب 29"}


def test_per_chat_isolation_across_speakers():
    memory = ConversationMemory()
    memory.remember(1, "user", "owner turn")
    memory.remember(2, "user", "guest turn")
    assert memory.history(1) == [{"role": "user", "content": "owner turn"}]
    assert memory.history(2) == [{"role": "user", "content": "guest turn"}]
