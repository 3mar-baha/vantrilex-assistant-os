"""H06 — JODA dialogues: bank patterns drive live turns (skip-soft, bounded)."""

import re

import pytest

from src.gateway import OmniRouteClient, Tier
from tests.live_harness.conftest import pace, require_gateway
from tests.test_dispatcher import CHAINS

AR_RE = re.compile(r"[\u0600-\u06FF]")


def _bank_sample(n: int = 10) -> list[str]:
    from pathlib import Path

    bank = Path("04_Resources/Dialect_Encyclopedia/JODA_Pattern_Bank.md")
    if not bank.exists():
        pytest.skip("pattern bank absent")
    patterns = [l[2:].strip() for l in bank.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    return patterns[:n]


async def test_bank_patterns_get_arabic_replies():
    require_gateway()
    sample = _bank_sample()
    client = OmniRouteClient("http://localhost:20128/v1", "harness", chains=CHAINS)
    async with client:
        for pattern in sample:
            pace()
            reply = await client.chat(
                [{"role": "user", "content": f"رد بلهجتك: {pattern}"}],
                tier=Tier.FAST,
                max_tokens=64,
            )
            assert reply and AR_RE.search(reply), pattern
