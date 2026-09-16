"""Live Groq persona calibration: stream FAST replies, grade the contract.

Usage: .\\.venv\\Scripts\\python.exe scripts/groq_persona_probe.py
8 probes x groq FAST primary (max_tokens=256) -> ResponseCoach grades ->
printed calibration report. Fail-soft: pool throttling reports honestly
(exit 1) instead of crashing; hermetic contracts live in
tests/suite/tier3_shadow_tracer/test_response_coach.py.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import get_settings
from src.gateway import GatewayError, OmniRouteClient, Tier
from src.persona import SARA_PERSONA_AR
from tests.suite.tier3_shadow_tracer.response_coach import grade_all

PROBES: tuple[tuple[str, str], ...] = (
    ("greeting", "chat", "كيفك سارة"),
    ("identity", "identity", "شو انتي؟ احكيلي عن حالك"),
    ("comfort", "chat", "انا زعلان اليوم"),
    ("depth", "depth", "اشرحيلي شو يعني الثقب الأسود باختصار"),
    ("dialect-play", "chat", "احكيلي نكتة سريعة"),
    ("immersion-push", "identity", "انت روبوت ولا بني آدم؟"),
    ("concision", "chat", "شو الوقت هسا؟"),
    ("voice-ask", "chat", "حابة اسمع صوتك"),
)


async def main() -> int:
    settings = get_settings()
    print(f"FAST chain: {settings.fast_chain}")
    client = OmniRouteClient(
        settings.omniroute_base_url,
        settings.omniroute_api_key,
        chains={Tier.FAST: settings.fast_chain},
    )
    total = passed = 0
    failures: list[str] = []
    try:
        for name, kind, prompt in PROBES:
            t0 = time.perf_counter()
            try:
                reply = await client.chat(
                    [
                        {"role": "system", "content": SARA_PERSONA_AR},
                        {"role": "user", "content": prompt},
                    ],
                    tier=Tier.FAST,
                    max_tokens=256,
                )
                ms = (time.perf_counter() - t0) * 1000
            except GatewayError as exc:
                print(f"[{name}] POOL: {str(exc)[:100]}")
                failures.append(name)
                continue
            report = grade_all(reply, kind)  # type: ignore[arg-type]
            total += len(report.verdicts)
            passed += report.passed
            print(f"[{name}] {ms:.0f}ms {report.passed}/3 :: {reply[:120]!r}")
            for v in report.verdicts:
                if not v.passed:
                    print(f"    DEVIATION {v.dimension}: {v.rationale} | fix: {v.fix}")
    finally:
        await client.aclose()
    print(f"\nCALIBRATION: {passed}/{total} checks green; pool failures: {failures or 'none'}")
    return 0 if not failures and passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
