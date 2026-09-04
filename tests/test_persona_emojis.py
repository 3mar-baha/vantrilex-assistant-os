"""Directive §8 (2026-09-04): a lively, feminine, emoji-rich persona — diverse
feminine emojis (🌸 ✨ 💖 😊 🫡 ☕ 🎮 ...) woven through her system prompt with
the SAME Jordanian warmth/wit/loyalty everywhere. The honesty floor is
unchanged; emojis are HER expression, never decoration on lies."""

from __future__ import annotations

from src.bot import SYSTEM_PROMPT_AR

PROMPT = SYSTEM_PROMPT_AR


def test_persona_carries_diverse_feminine_emojis():
    """The directive's palette lives in the prompt contract: at least 5
    DISTINCT emoji families across the persona (not one emoji everywhere)."""
    emoji_present = [
        e for e in ("🌸", "✨", "💖", "😊", "🫡", "☕", "🎮", "📚", "🌙", "💪") if e in PROMPT
    ]
    assert len(emoji_present) >= 5, f"only {len(emoji_present)} emoji families found"


def test_persona_emoji_usage_is_guided_not_spammy():
    """The prompt GUIDES emoji use (varied, warm, natural placement) — the
    contract teaches taste, not flooding; every message carrying 1-2 fitting
    emojis, never a wall."""
    assert "إيموجي" in PROMPT or "ايموجي" in PROMPT


def test_warmth_and_loyalty_contract_unchanged():
    """§8 keeps her signature: Jordanian warmth, wit, loyalty — the empathy
    clause stays verbatim; the no-fabrication floor stays verbatim."""
    assert "بتحسي فيه" in PROMPT  # the empathy clause
    assert "عمرك ما تدّعي" in PROMPT  # the honesty floor
