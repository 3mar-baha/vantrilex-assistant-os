"""Tier 1 — Phase-6 integration contracts: RAG + posture + tag-stripped surfaces.

Hermetic shell tests (scripted gateway doubles, tmp vaults, preloaded posture
states, recorder transports). The live end-to-end turn is covered by the
Phase-6 canary script, not here.
"""

import json

from src.bot import _STREAMS
from src.situational import SituationalState
from tests.conftest import OWNER_ID, StreamProgram, drain, make_update


def _router(route: str, ack: str) -> str:
    return json.dumps({"route": route, "ack": ack}, ensure_ascii=False)


async def _run(shell, bot, update):
    await shell.dp.feed_update(bot, update)
    await drain(_STREAMS)
    _STREAMS.clear()


def _system_of(shell) -> str:
    messages, _tier = shell.gateway.stream_calls[0]
    assert messages[0]["role"] == "system"
    return messages[0]["content"]


def _write_note(root, rel: str, meta: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{meta}---\n{body}\n", encoding="utf-8")


async def test_assoc_block_injected(tmp_path, fake_bot, make_shell):
    """Leap 2 wired: a matching local note lands in the persona envelope."""
    vault = tmp_path / "vault"
    _write_note(
        vault,
        "02_Areas/Finance/Budget.md",
        "aliases: [مصاري, ميزانية]\ntags: [مالية]\n",
        "راتبي يغطي الإيجار والمصاريف الأساسية كل شهر",
    )
    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[StreamProgram(deltas=("تمام",))],
        VAULT_LOCAL_PATH=str(vault),
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "وين صرفنا مصاري هالشهر يا سارة؟"))
    system = _system_of(shell)
    assert "[سياق من خزينتك" in system
    assert "02_Areas/Finance/Budget.md" in system


async def test_no_assoc_block_without_match(tmp_path, fake_bot, make_shell):
    """No match / missing vault: envelope byte-identical to the core."""
    vault = tmp_path / "vault"
    _write_note(vault, "00_Inbox/plumbing.md", "aliases: [سباكة]\n", "سباكة ومواسير الحمام مسدودة")
    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[StreamProgram(deltas=("تمام",))],
        VAULT_LOCAL_PATH=str(vault),
    )
    # F-6: anchored to the BASE PROMPT, not to the bare identity core. The law
    # is "the associative block is not injected when nothing matches"; the base
    # prompt became `build_persona_joda()` when Telegram was unified with
    # Terminal 1 (owner decision 2026-10-01). The assertion is unchanged in
    # strength — any extra block still breaks it.
    from src.persona import build_persona_joda

    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "شو أخبار الطقس اليوم؟"))
    assert _system_of(shell) == build_persona_joda()


async def test_posture_focus_block(tmp_path, fake_bot, make_shell):
    """Leap 3 wired: a FOCUS ring modulates the envelope."""
    st = SituationalState()
    t = 200000.0
    for _ in range(9):
        st.push("code.exe", "IDE / Coding", 10.0, t=t)
        t += 200.0
    assert st.posture(now=t) == "FOCUS"
    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[StreamProgram(deltas=("تمام",))],
        VAULT_LOCAL_PATH=str(tmp_path / "empty-vault"),
        situational=st,
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "مرحبا سارة"))
    assert "تركيز عميق" in _system_of(shell)


async def test_posture_normal_noop(fake_bot, make_shell):
    """Empty ring (no sampler yet): system untouched."""
    # F-6: same re-anchor as `test_no_assoc_block_without_match` — the law is
    # "a NORMAL posture appends nothing", and the base prompt is now the
    # composed `build_persona_joda()`. The `[الوضع الحالي` absence check above
    # it is untouched and still the primary assertion.
    from src.persona import build_persona_joda

    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[StreamProgram(deltas=("تمام",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "مرحبا سارة"))
    assert "[الوضع الحالي" not in _system_of(shell)
    assert _system_of(shell) == build_persona_joda()


async def test_dp_exposes_situational_state(fake_bot, make_shell):
    """The future heartbeat transport's public handle."""
    st = SituationalState()
    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[],
        situational=st,
    )
    assert shell.dp["situational"] is st


async def test_streamer_edits_strip_tags(fake_bot, make_shell):
    """Leap 4 text surface: no bubble edit ever shows a literal tag."""
    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[
            StreamProgram(deltas=("[laughing] هههه يا زلمة، هاي نكتة حلوة كتير والله",))
        ],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "حكيلي نكتة"))
    texts = [c.method.text for c in bot.session.sent("EditMessageText")]
    texts += [c.method.text for c in bot.session.sent("SendMessage")]
    assert texts, "expected bubble traffic"
    assert not any("[laughing]" in t for t in texts)
    assert any("نكتة" in t for t in texts)  # prose survives


async def test_split_sends_strip_tags_keep_links(fake_bot, make_shell):
    """Long bubbles: tags stripped at the split seam, [[links]] preserved."""
    para1 = "المقدمة الطويلة جدا عن الموضوع " * 8 + "[laughing] ضحكة خفيفة هنا. "
    para2 = "التفاصيل الكاملة للموضوع " * 8 + "راجع [[Budget]] للمصاريف. "
    shell = make_shell(
        router_replies=[_router("direct", "أهلا")],
        stream_programs=[StreamProgram(deltas=(para1 + "\n\n" + para2,))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "اشرحلي الموضوع بالتفصيل"))
    edits = [c.method.text for c in bot.session.sent("EditMessageText")]
    sends = [c.method.text for c in bot.session.sent("SendMessage")]
    assert edits, "expected the split head edit"
    assert not any("[laughing]" in t for t in edits + sends)
    assert any("[[Budget]]" in t for t in edits + sends)
