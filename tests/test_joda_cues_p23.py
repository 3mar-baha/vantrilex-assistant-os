"""P2.3 JODA cues in the digest baseline (master transformation plan, Phase P2.3).

The unconditional `load_long_term` path gains a capped conversational-cues
block parsed deterministically from the P1 bank — short greetings carry live
dialect cues with zero retrieval gamble and zero extra model calls.
"""

from datetime import date

from src.memory import JODA_CUES_HEADER_AR, _load_long_term_uncached, joda_cues_block

BANK = """---
tags: [memory]
---

# JODA Pattern Bank — mined conversational Ammani (P1)

## banter

- ههههه والله ضحكتني
- يا زلمة شو هالحكي

## agreement

- تمام، من عيوني
- أكيد يا غالي
"""


class FakeVault:
    def __init__(self, reads=None):
        self.reads = dict(reads or {})

    async def read(self, path: str) -> str:
        if path not in self.reads:
            raise FileNotFoundError(path)
        return self.reads[path]


def _bank_path() -> str:
    from src.memory import JODA_BANK_REL_PATH

    return JODA_BANK_REL_PATH


async def test_short_greeting_digest_carries_cues():
    vault = FakeVault({_bank_path(): BANK})
    out = await _load_long_term_uncached(vault, today=date(2026, 9, 17))
    assert JODA_CUES_HEADER_AR in out
    assert "ههههه والله ضحكتني" in out
    assert "تمام، من عيوني" in out


async def test_missing_bank_no_crash_no_cues():
    vault = FakeVault({"02_Areas/Profile/User_Info.md": "Omar likes knafeh"})
    out = await _load_long_term_uncached(vault, today=date(2026, 9, 17))
    assert JODA_CUES_HEADER_AR not in out
    assert "knafeh" in out


async def test_malformed_bank_no_cues():
    vault = FakeVault({_bank_path(): "no sections here\njust prose\n"})
    out = await _load_long_term_uncached(vault, today=date(2026, 9, 17))
    assert JODA_CUES_HEADER_AR not in out


async def test_cues_block_capped():
    long_pat = "كلمة " * 100
    text = "## banter\n\n" + "\n".join(f"- {long_pat}{i}" for i in range(5))
    block = joda_cues_block(text)
    assert JODA_CUES_HEADER_AR in block
    assert len(block) <= 300


async def test_cues_deterministic_first_patterns():
    first = joda_cues_block(BANK)
    second = joda_cues_block(BANK)
    assert first == second
    assert first.index("ههههه والله ضحكتني") < first.index("تمام، من عيوني")
