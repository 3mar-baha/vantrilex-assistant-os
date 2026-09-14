"""Tier 1 — persona extraction lock (Phase-1 foundations, re-pinned Phase-6).

The identity core moved verbatim bot.py -> src/persona.py; this file locks
that move three ways: alias identity (all existing importers keep working),
composer purity (empty extras return the core byte-identical), and a sha256
pin (any silent drift fails loudly — edits need owner sign-off).

Re-pin history: 4485/7cf6b475 (extraction) → 4638/3c43aa04 (owner-ordered
intuitive-expression rewrite of the emoji paragraph, 2026-09-13) →
4763/efa39690 (owner-ordered masculine-address anchor, 2026-09-13) →
4782/ec6acc69 (owner-ordered 6-emoji hygiene cap, 2026-09-14).
"""

import hashlib

from src.bot import SYSTEM_PROMPT_AR
from src.persona import SARA_PERSONA_AR, build_persona

CORE_SHA256 = "ec6acc69cf84fb48945f1439da24af15ab26b43352b40dc157a746b1b7c56235"
CORE_LEN = 4782


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
