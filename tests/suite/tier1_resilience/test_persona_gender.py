"""Tier 1 — persona gender consistency (Phase-5 JODA slice). Hermetic.

Rule: Sara speaks feminine first-person (أنا + ة-form predicate); Omar is
addressed masculine. Second-person-feminine forms (انتِ، عملتي، بدكِ…)
anywhere in the exemplars fail loudly — gender drift never ships silently.
"""

import re

from src.persona import JODA_EXEMPLARS_AR, build_persona, build_persona_joda

FEM_2ND_RE = re.compile(r"انتِ|\S+تي\b|\S+كِ[\s.,!؟…]|لكِ|عندكِ")
SARA_ANCHOR_RE = re.compile(r"أنا")
SARA_FEM_RE = re.compile(r"\S+ة\b")
MASC_ADDR_RES = (
    re.compile(r"شوف\w*|اعمل|ذكرني|ساعدني|طمني"),
    re.compile(r"رأيك|شغلك|يومك|عمر"),
)


def test_exemplars_present_and_paired():
    assert len(JODA_EXEMPLARS_AR) >= 5
    for omar, sara in JODA_EXEMPLARS_AR:
        assert omar.strip() and sara.strip()


def test_sara_lines_feminine_first_person():
    for _, sara in JODA_EXEMPLARS_AR:
        assert SARA_ANCHOR_RE.search(sara), f"missing first-person anchor: {sara!r}"
        assert SARA_FEM_RE.search(sara), f"missing ة-form predicate: {sara!r}"


def test_omar_lines_masculine_address():
    for omar, _ in JODA_EXEMPLARS_AR:
        assert any(rx.search(omar) for rx in MASC_ADDR_RES), f"no masculine marker: {omar!r}"


def test_no_second_person_feminine_anywhere():
    for omar, sara in JODA_EXEMPLARS_AR:
        assert not FEM_2ND_RE.search(omar), f"feminine address in Omar line: {omar!r}"
        assert not FEM_2ND_RE.search(sara), f"feminine address in Sara line: {sara!r}"


def test_joda_builder_composes():
    full = build_persona_joda()
    assert full.startswith(build_persona([]))
    assert "عمر:" in full and "سارة:" in full
    assert len(full) <= len(build_persona([])) + 2000  # prompt-budget bound
