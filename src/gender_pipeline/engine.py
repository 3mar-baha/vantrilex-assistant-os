"""Pipeline coordinator: shield -> ordered rewrite stages. O(N) regex passes.

Boundary discipline: every pattern is wrapped in whitespace/punctuation
anchors (not bare \\b — Arabic diacritics like kasra break \\b adjacency).
Punctuation-adjacent forms («خبريني،», «(خبريني)», «خبريني!») all convert;
glued forms («وخبريني») do NOT match the bare entry — the top-frequency
glued variants are explicit entries where attested. Within each stage,
longer sources apply first so exact phrases win over their parts.
"""

from __future__ import annotations

import re
from typing import Final

from src.gender_pipeline.rules_clitics import FEM_ADJ as _FEM_ADJ
from src.gender_pipeline.rules_clitics import PARTICIPLE_ANCHORS as _PART_ANCHORS
from src.gender_pipeline.rules_clitics import RULES as _CLITIC_RULES
from src.gender_pipeline.rules_clitics import STANDALONE_ADJ as _STAND_ADJ
from src.gender_pipeline.rules_imperatives import RULES as _IMP_RULES
from src.gender_pipeline.rules_verbs import REGEX_RULES as _VERB_REGEX
from src.gender_pipeline.rules_verbs import RULES as _VERB_RULES
from src.gender_pipeline.shield import mask, unmask

# Token edges: start/end, whitespace, or punctuation (Arabic + ASCII sets).
_PRE: Final[str] = r"(?:^|(?<=[\s«\"'(\[]))"
_POST: Final[str] = r"(?=[\s.,!؟…:;،»\"')\]}]|$)"


def _compile(pairs: tuple[tuple[str, str], ...]) -> list[tuple[re.Pattern[str], str]]:
    ordered = sorted(pairs, key=lambda kv: len(kv[0]), reverse=True)
    return [(re.compile(_PRE + re.escape(src) + _POST), dst) for src, dst in ordered]


def _participle_rules() -> list[tuple[re.Pattern[str], str]]:
    pairs = [
        (f"{anchor} {fem}", f"{masc_anchor} {masc_adj}")
        for anchor, masc_anchor in _PART_ANCHORS
        for fem, masc_adj in _FEM_ADJ
    ]
    return _compile(tuple(pairs))


def _stages() -> list[list[tuple[re.Pattern[str], str]]]:
    raw = [(re.compile(src), dst) for src, dst in _VERB_REGEX]
    return [
        _compile(_IMP_RULES),
        _compile(_VERB_RULES),
        _compile(_CLITIC_RULES),
        _compile(_STAND_ADJ),
        raw,
        _participle_rules(),
    ]


_STAGES: Final = _stages()


def normalize_masculine_address(text: str) -> str:
    """Rewrite 2nd-person-feminine address (Omar) to masculine; Sara's own
    feminine voice shielded first and restored verbatim. Total function."""
    if not isinstance(text, str) or not text:
        return text
    masked, vault = mask(text)
    for stage in _STAGES:
        for pattern, replacement in stage:
            masked = pattern.sub(replacement, masked)
    return unmask(masked, vault)
