"""Tier 1 — persona extraction lock (Phase-1 foundations).

The identity core moved verbatim bot.py -> src/persona.py; this file locks
that move three ways: alias identity (all existing importers keep working),
composer purity (empty extras return the core byte-identical), and a sha256
pin (any silent drift fails loudly — edits need owner sign-off).
"""

import hashlib

from src.bot import SYSTEM_PROMPT_AR
from src.persona import SARA_PERSONA_AR, build_persona

CORE_SHA256 = "7cf6b4759b3031e52f74de66559e4d5073a4c0a69f279ec53e06389dec856aac"
CORE_LEN = 4485


def test_alias_identity():
    assert SYSTEM_PROMPT_AR is SARA_PERSONA_AR


def test_core_hash_pinned():
    assert len(SARA_PERSONA_AR) == CORE_LEN
    assert hashlib.sha256(SARA_PERSONA_AR.encode()).hexdigest() == CORE_SHA256


def test_composer_pure_on_empty():
    assert build_persona([]) == SARA_PERSONA_AR
    assert build_persona(None) == SARA_PERSONA_AR


def test_composer_appends_blocks():
    assert build_persona(["x", "  ", "y"]) == SARA_PERSONA_AR + "\n\nx\n\ny"
