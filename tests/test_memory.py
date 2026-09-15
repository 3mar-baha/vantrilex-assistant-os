"""Dual-tier memory (owner directive 2026-09-01): short-term rolling buffer + Obsidian
long-term context injection + background vault writers (Daily_Logs + User_Info)."""

import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from src.memory import (
    SECTION_CHAR_CAP,
    ConversationMemory,
    VaultMemoryWriter,
    build_messages,
    load_long_term,
    reset_context_cache,
)
from src.vault import PROFILE_USER_INFO

TZ = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 1, 15, 30, tzinfo=UTC)  # 18:30 Amman


@pytest.fixture(autouse=True)
def _clean_context_cache():
    """The C-10 envelope cache is process-global — every test starts and ends
    with it empty and a real clock."""
    import src.memory as memory_mod

    reset_context_cache()
    memory_mod._clock = memory_mod._time_mod.monotonic
    yield
    reset_context_cache()
    memory_mod._clock = memory_mod._time_mod.monotonic


class FakeVault:
    def __init__(self, reads: dict[str, str] | None = None) -> None:
        self.reads = dict(reads or {})
        self.appends: list[tuple] = []
        self.read_calls: list[str] = []

    async def read(self, path: str) -> str:
        self.read_calls.append(path)
        if path not in self.reads:
            raise FileNotFoundError(path)
        return self.reads[path]

    async def append_section(self, path, heading, lines, *, commit_prefix):
        self.appends.append((path, heading, tuple(lines), commit_prefix))
        return f"written:{path}"


class FakeBrain:
    def __init__(self, reply: str = "") -> None:
        self.reply = reply
        self.calls: list[list[dict]] = []

    async def chat(self, messages, **kwargs):
        self.calls.append(messages)
        return self.reply


# --- short-term rolling buffer -------------------------------------------------


def test_buffer_keeps_last_50_messages_and_drops_oldest():
    memory = ConversationMemory()
    for i in range(55):
        memory.remember(1, "user" if i % 2 == 0 else "assistant", f"msg{i}")
    history = memory.history(1)
    assert len(history) == 50  # deque(maxlen=50) of {role, content} dicts
    assert history[0]["content"] == "msg5"
    assert history[-1]["content"] == "msg54"
    assert all(set(m) == {"role", "content"} for m in history)


def test_buffer_isolated_per_chat_and_history_is_a_copy():
    memory = ConversationMemory()
    memory.remember(1, "user", "أ")
    memory.remember(2, "user", "ب")
    history = memory.history(1)
    history.append({"role": "user", "content": "تلاعب"})
    assert memory.history(1) == [{"role": "user", "content": "أ"}]
    assert memory.history(2) == [{"role": "user", "content": "ب"}]
    assert memory.history(3) == []


# --- context envelope ----------------------------------------------------------


def test_envelope_personas_history_and_current_message_in_order():
    persona = "أنت سارة"
    history = [
        {"role": "user", "content": "س1"},
        {"role": "assistant", "content": "ج1"},
    ]
    messages = build_messages(persona, None, history, "س2")
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == persona
    assert messages[-1]["content"] == "س2"


def test_envelope_injects_long_term_into_system_block():
    messages = build_messages("أنت سارة", "المالك عمر، مهندس", [], "مرحبا")
    system = messages[0]["content"]
    assert system.startswith("أنت سارة")
    assert "المالك عمر، مهندس" in system
    assert "بيانات" in system  # data-not-instructions boundary marker


# --- long-term vault context ----------------------------------------------------


async def test_load_long_term_joins_profile_dialect_and_today_log():
    vault = FakeVault(
        {
            "02_Areas/Profile/User_Info.md": "---\ntype: profile\n---\nاسمي عمر.",
            "02_Areas/Profile/Dialect_Notes.md": "---\n---\nيقول «هسا» كثيراً.",
            "Daily_Logs/2026-09-01.md": "---\n---\n## دردشة 10:00\n\n**المالك:** صباح",
        }
    )
    context = await load_long_term(vault, today=NOW.date())
    assert "اسمي عمر." in context
    assert "يقول «هسا»" in context
    assert "صباح" in context


async def test_load_long_term_reads_dialect_notes_header():
    """Remediation 2.5 (dead loop): the learned pronunciation pairs live in the
    Dialect_Notes FRONTMATTER (notes: list) — the header must reach the brain's
    envelope, not just the prose body. Previously the owner's teachings were
    invisible to every turn."""
    vault = FakeVault(
        {
            "02_Areas/Profile/Dialect_Notes.md": (
                "---\nnotes:\n  - term: كفيك\n    phonetic: كفايك\n---\nعمر يحكي أردني."
            )
        }
    )
    context = await load_long_term(vault, today=NOW.date())
    assert "كفيك" in context and "كفايك" in context  # the pair reached the envelope
    assert "عمر يحكي أردني." in context  # body still rides along


async def test_load_long_term_ttl_cache_serves_repeated_turns():
    """Audit C-10: three sequential GitHub GETs run before EVERY router call —
    the <250ms ack target is unreachable. A 60s TTL cache serves the envelope:
    back-to-back turns hit the cache (zero vault reads), a write invalidates
    it, and expiry re-reads."""
    import time as _time

    vault = FakeVault({"02_Areas/Profile/User_Info.md": "---\n---\nعمر"})
    from src.memory import reset_context_cache

    reset_context_cache()
    await load_long_term(vault, today=NOW.date())
    first = len(vault.read_calls)
    await load_long_term(vault, today=NOW.date())  # served from cache
    await load_long_term(vault, today=NOW.date())  # served again
    assert len(vault.read_calls) == first  # ZERO extra GitHub reads
    assert first >= 1

    # TTL expiry re-reads (the cache honors freshness)
    from src.memory import _bump_cache_clock

    _bump_cache_clock(_time.monotonic() + 61)
    await load_long_term(vault, today=NOW.date())
    assert len(vault.read_calls) > first  # expired -> fresh reads

    reset_context_cache()


async def test_vault_write_invalidates_context_cache():
    """The cache must never serve a stale just-written profile: a vault write
    (upsert path) clears it, so the NEXT turn reads fresh content."""
    vault = FakeVault({"02_Areas/Profile/User_Info.md": "---\n---\nنسخة أولى"})
    from src.memory import reset_context_cache

    reset_context_cache()
    first = await load_long_term(vault, today=NOW.date())
    assert "نسخة أولى" in first
    vault.reads["02_Areas/Profile/User_Info.md"] = "---\n---\nنسخة ثانية"
    from src.memory import invalidate_context_cache

    invalidate_context_cache()
    second = await load_long_term(vault, today=NOW.date())
    assert "نسخة ثانية" in second  # the fresh content arrived
    reset_context_cache()


async def test_load_long_term_skips_missing_notes_and_survives_vault_failure():
    class ExplodingVault(FakeVault):
        async def read(self, path):
            if path == "02_Areas/Profile/User_Info.md":
                return await super().read(path)
            raise RuntimeError("github down")

    context = await load_long_term(
        ExplodingVault({"02_Areas/Profile/User_Info.md": "---\ntype: profile\n---\nعمر فقط."}),
        today=NOW.date(),
    )
    assert context == "عمر فقط."  # degraded gracefully — chat never breaks


async def test_load_long_term_caps_each_section():
    vault = FakeVault(
        {"02_Areas/Profile/User_Info.md": "---\n---\n" + "ط" * (SECTION_CHAR_CAP + 500)}
    )
    context = await load_long_term(vault, today=NOW.date())
    assert len(context) == SECTION_CHAR_CAP


async def test_load_long_term_keeps_the_newest_tail():
    """Remediation 2.7 (head-vs-tail flaw): facts append to the END of
    User_Info — when the cap slices, the brain must see the NEWEST facts
    (the tail), not the stale head."""
    head = "حقيقة قديمة. " * 400  # ~5200 chars of old facts, well past the cap
    tail = "أحدث حقيقة تعلمتها اليوم عن عمر."
    vault = FakeVault({"02_Areas/Profile/User_Info.md": "---\n---\n" + head + tail})
    context = await load_long_term(vault, today=NOW.date())
    assert "أحدث حقيقة" in context  # the newest fact IS visible
    assert context.endswith(tail)  # the window ENDS on the newest fact
    assert len(context) <= SECTION_CHAR_CAP + len(tail)  # roughly the cap window


# --- background memory writer ----------------------------------------------------


def _writer(vault, brain) -> VaultMemoryWriter:
    return VaultMemoryWriter(vault, brain, tz=TZ)


async def test_log_exchange_appends_dated_chat_section():
    vault, brain = FakeVault(), FakeBrain()
    result = await _writer(vault, brain).log_exchange("شو الأخبار؟", "كل شي تمام", now=NOW)
    assert result == "written:Daily_Logs/2026/09/2026-09-01.md"
    path, heading, lines, prefix = vault.appends[0]
    assert path == "Daily_Logs/2026/09/2026-09-01.md"
    assert "18:30" in heading
    assert "**المالك:** شو الأخبار؟" in lines
    assert "**سارة:** كل شي تمام" in lines
    assert prefix.startswith("sara:")


async def test_log_exchange_caps_long_turns():
    vault, brain = FakeVault(), FakeBrain()
    await _writer(vault, brain).log_exchange("ك" * 900, "س" * 900, now=NOW)
    lines = vault.appends[0][2]
    assert all(len(line) < 900 for line in lines)


async def test_maybe_learn_persists_new_fact_to_user_info():
    vault = FakeVault()
    brain = FakeBrain(
        json.dumps({"learn": True, "fact": "المالك يحب القهوة التركية"}, ensure_ascii=False)
    )
    fact = await _writer(vault, brain).maybe_learn("خليني احكيلك اني بحب القهوة التركية", now=NOW)
    assert fact == "المالك يحب القهوة التركية"
    path, heading, lines, _ = vault.appends[0]
    assert path == PROFILE_USER_INFO
    assert "2026-09-01" in heading
    assert lines == ("المالك يحب القهوة التركية",)
    # the extraction call went to the conversation lane (FAST tier)
    assert brain.calls[0][0]["role"] == "user"


async def test_maybe_learn_ignores_transient_chat():
    vault, brain = (
        FakeVault(),
        FakeBrain(json.dumps({"learn": False, "fact": ""}, ensure_ascii=False)),
    )
    assert await _writer(vault, brain).maybe_learn("شو الأخبار؟", now=NOW) is None
    assert vault.appends == []


async def test_maybe_learn_survives_bad_json_and_brain_failure():
    vault = FakeVault()
    writer = _writer(vault, FakeBrain("مش JSON أبداً"))
    assert await writer.maybe_learn("شي", now=NOW) is None
    writer2 = _writer(vault, FailingBrain())
    assert await writer2.maybe_learn("شي", now=NOW) is None
    assert vault.appends == []


class FailingBrain:
    async def chat(self, messages, **kwargs):
        raise RuntimeError("gateway down")


async def test_maybe_learn_never_writes_empty_fact():
    vault, brain = (
        FakeVault(),
        FakeBrain(json.dumps({"learn": True, "fact": "  "}, ensure_ascii=False)),
    )
    assert await _writer(vault, brain).maybe_learn("شي", now=NOW) is None
    assert vault.appends == []


# --- daily conversation summary (owner directive 2026-09-01, 23:50 job) -------------


from src.memory import SUMMARY_MAX_MESSAGES, DailySummarizer, day_chat_lines

NOTE = (
    "---\ntype: daily\n---\n"
    "## دردشة 10:00\n\n**المالك:** صباح الخير\n**سارة:** صباح النور\n\n"
    "## دردشة 12:30\n\n**المالك:** ذكرني بالموعد\n**سارة:** سجلته\n"
)


def test_day_chat_lines_extracts_chat_turns_in_order():
    lines = day_chat_lines(NOTE)
    assert lines == [
        "**المالك:** صباح الخير",
        "**سارة:** صباح النور",
        "**المالك:** ذكرني بالموعد",
        "**سارة:** سجلته",
    ]


def test_day_chat_lines_ignores_prose_and_other_speakers():
    note = "ملاحظة يومية\n**عمر:** نص\n**المالك:** رسالة حقيقية\n**سارة:** رد"
    assert day_chat_lines(note) == ["**المالك:** رسالة حقيقية", "**سارة:** رد"]


def test_day_chat_lines_caps_to_last_150():
    body = "".join(f"**المالك:** رسالة{i}\n" for i in range(SUMMARY_MAX_MESSAGES + 50))
    lines = day_chat_lines(body)
    assert len(lines) == SUMMARY_MAX_MESSAGES
    assert lines[0] == "**المالك:** رسالة50"  # oldest dropped
    assert lines[-1] == "**المالك:** رسالة199"


def _summarizer(vault, brain) -> DailySummarizer:
    return DailySummarizer(vault, brain, tz=TZ)


async def test_summarize_day_appends_detailed_summary_section():
    vault = FakeVault(
        {
            "Daily_Logs/2026-09-01.md": NOTE,
            "02_Areas/Profile/User_Info.md": "---\ntype: profile\n---\nالمالك عمر مهندس.",
        }
    )
    brain = FakeBrain("ملخص اليوم: تحدثا عن الموعد والقهوة.")
    out = await _summarizer(vault, brain).summarize_day(NOW.date(), now=NOW)
    assert out == "ملخص اليوم: تحدثا عن الموعد والقهوة."
    path, heading, lines, prefix = vault.appends[0]
    assert path == "Daily_Logs/2026-09-01.md"
    assert "ملخص محادثة" in heading and "2026-09-01" in heading
    assert lines == ("ملخص اليوم: تحدثا عن الموعد والقهوة.",)
    assert prefix.startswith("sara:")
    # the model call carried the day's turns AND the Obsidian context
    prompt = brain.calls[0][0]["content"]
    assert "صباح الخير" in prompt and "سجلته" in prompt
    assert "المالك عمر مهندس." in prompt


async def test_summarize_day_caps_sent_messages_to_last_150():
    body = "---\n---\n" + "".join(f"**المالك:** رسالة{i}\n" for i in range(200))
    vault = FakeVault({"Daily_Logs/2026-09-01.md": body})
    brain = FakeBrain("ملخص")
    await _summarizer(vault, brain).summarize_day(NOW.date(), now=NOW)
    prompt = brain.calls[0][0]["content"]
    turns = prompt.split("[محادثة اليوم")[1]  # the CONTEXT block may quote the note head;
    assert "رسالة50\n" in turns and "رسالة49" not in turns  # the TURNS block is the last 150
    assert "رسالة199" in turns


async def test_summarize_day_skips_days_without_chat():
    vault, brain = FakeVault(), FakeBrain("ملخص")
    assert await _summarizer(vault, brain).summarize_day(NOW.date(), now=NOW) is None
    assert brain.calls == [] and vault.appends == []


async def test_summarize_day_skips_prose_only_note():
    vault = FakeVault({"Daily_Logs/2026-09-01.md": "---\n---\nملاحظات بدون دردشة"})
    brain = FakeBrain("ملخص")
    assert await _summarizer(vault, brain).summarize_day(NOW.date(), now=NOW) is None
    assert brain.calls == [] and vault.appends == []


async def test_summarize_day_is_idempotent_already_summarized():
    vault = FakeVault(
        {"Daily_Logs/2026-09-01.md": NOTE + "\n## ملخص محادثة اليوم 2026-09-01\n\nتم"}
    )
    brain = FakeBrain("ملخص جديد")
    assert await _summarizer(vault, brain).summarize_day(NOW.date(), now=NOW) is None
    assert brain.calls == [] and vault.appends == []


async def test_summarize_day_survives_brain_failure():
    vault = FakeVault({"Daily_Logs/2026-09-01.md": NOTE})
    assert await _summarizer(vault, FailingBrain()).summarize_day(NOW.date(), now=NOW) is None
    assert vault.appends == []


def test_summary_due_predicate_at_2350_local():
    summarizer = _summarizer(FakeVault(), FakeBrain())
    before = datetime(2026, 9, 1, 20, 49, tzinfo=UTC)  # 23:49 Amman
    at = datetime(2026, 9, 1, 20, 50, tzinfo=UTC)  # 23:50 Amman
    assert summarizer.due(before) is False
    assert summarizer.due(at) is True


async def test_summarize_day_multi_paragraph_summary_kept_verbatim():
    vault = FakeVault({"Daily_Logs/2026-09-01.md": NOTE})
    summary = "الفقرة الأولى.\n\nالفقرة الثانية."
    vault2 = vault
    await _summarizer(vault2, FakeBrain(summary)).summarize_day(NOW.date(), now=NOW)
    assert vault2.appends[0][2] == ("الفقرة الأولى.", "", "الفقرة الثانية.")
