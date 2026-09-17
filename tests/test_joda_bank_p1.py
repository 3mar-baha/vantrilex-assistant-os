"""P1 pattern-bank gates (master transformation plan, Phase P1).

The bank (`04_Resources/Dialect_Encyclopedia/JODA_Pattern_Bank.md`, 500 rows:
5 acts x 80 + 100 wildcards) is consumed by DIRECT section read — never by
competitive VaultIndex retrieval. Measured evidence for that architecture:
self-query top-1 hits only 287/500 (shared dialect vocabulary lets sibling
files win legitimately), so a top-1 gate would force index gaming. These tests
lock quotas, dedupe, format, and deterministic section parsing instead.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BANK = REPO / "04_Resources" / "Dialect_Encyclopedia" / "JODA_Pattern_Bank.md"
ACTS = ("banter", "agreement", "deflection", "technical_empathy", "boundaries")


def _sections() -> dict[str, list[str]]:
    current: str | None = None
    out: dict[str, list[str]] = {}
    for line in BANK.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif line.startswith("- ") and current is not None:
            out[current].append(line[2:].strip())
    return out


def test_bank_exists_with_frontmatter():
    assert BANK.is_file()
    head = BANK.read_text(encoding="utf-8")[:200]
    assert head.startswith("---\ntags: [memory]\n---")


def test_categorical_floors_and_total():
    sections = _sections()
    for act in ACTS:
        assert len(sections.get(act, [])) >= 80, f"floor unmet: {act}"
    assert len(sections.get("wildcards", [])) == 100
    total = sum(len(v) for v in sections.values())
    assert total == 500, f"bank total {total} != 500"


def test_no_duplicates_and_generic_cap():
    sections = _sections()
    norms = [p for pats in sections.values() for p in pats]
    assert len(set(norms)) == len(norms), "duplicate patterns in bank"
    generic = {"تمام", "شو هاد", "والله", "يعني", "هيك", "هاد", "طيب", "أها"}
    assert sum(1 for p in norms if p in generic) <= 5


def test_patterns_are_conversational_shape():
    sections = _sections()
    for act, pats in sections.items():
        for pattern in pats:
            words = pattern.split()
            assert 3 <= len(words) <= 25, f"{act}: shape breach {pattern!r}"
            assert re.search(r"[\u0600-\u06FF]", pattern), f"{act}: no Arabic {pattern!r}"


def test_direct_section_read_covers_acts():
    """The P2 consumption path: deterministic act lookup, no retrieval gamble."""
    sections = _sections()
    for act in ACTS:
        assert len(sections[act]) >= 80
    assert sections["wildcards"]
