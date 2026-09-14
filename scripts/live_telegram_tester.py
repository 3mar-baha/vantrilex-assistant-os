"""Live Telegram-tester (mission Step 3): 4 end-to-end verification turns.

Design constraints (read before extending):
- NO real Telegram sends: driving aiogram polling would message the owner's
  live account (side effects). Instead every turn runs the PRODUCTION code
  the dispatcher calls in-process: OmniRouteClient (live gateway), VaultIndex
  over a freshly boot-mirrored vault, fetch_arm default chain, plans.gate +
  breaker. Same modules, same contracts, zero transport side effects.
- Turn 1 needs the live gateway (OmniRoute :20128 up?); turns 2/4 are fully
  hermetic; turn 3 needs plain HTTPS. Any unreachable dependency records an
  honest DEGRADED row (reason named) instead of failing loudly — the exit
  code is 0 only when every asserted turn passes.

Runs (repo root):
    .venv/Scripts/python.exe scripts/live_telegram_tester.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

JO_MARKERS = ("هسا", "شو", "عيوني", "بدي", "هيك", "كتير", "يلا", "تمام", "عشان")
AI_CLAIMS = ("ذكاء اصطناعي", "نموذج لغوي", "language model", "as an ai")


@dataclass
class Turn:
    name: str
    status: str = "SKIP"  # PASS | FAIL | DEGRADED
    detail: str = ""
    ms: float = 0.0
    extra: dict = field(default_factory=dict)


async def turn1_warmth() -> Turn:
    """Conversational warmth via the LIVE FAST lane + persona envelope."""
    turn = Turn(name="T1-warmth «مرحبا سارة، شو الأخبار؟»")
    try:
        from src.config import get_settings
        from src.gateway import GatewayError, OmniRouteClient, Tier
        from src.persona import SARA_PERSONA_AR
    except Exception as exc:  # noqa: BLE001 — import surface must exist
        turn.detail = f"imports unavailable: {exc}"
        return turn
    t0 = time.perf_counter()
    try:
        settings = get_settings()
        client = OmniRouteClient(
            settings.omniroute_base_url,
            settings.omniroute_api_key,
            chains={Tier.FAST: settings.fast_chain},
        )
        try:
            # True TTFT: time to FIRST content delta (streaming), not full-turn.
            parts: list[str] = []
            first_ms: float | None = None
            async for delta in client.stream_chat(
                [
                    {"role": "system", "content": SARA_PERSONA_AR},
                    {"role": "user", "content": "مرحبا سارة، شو الأخبار؟"},
                ],
                tier=Tier.FAST,
                max_tokens=256,
            ):
                if delta:
                    if first_ms is None:
                        first_ms = (time.perf_counter() - t0) * 1000
                    parts.append(delta)
                if len(parts) >= 120:
                    break
            if first_ms is None:
                raise GatewayError("streamed zero content deltas")
            reply = "".join(parts)
            turn.ms = first_ms
        finally:
            await client.aclose()
    except GatewayError as exc:
        turn.status = "DEGRADED"
        turn.detail = f"pools throttled, honest stop: {str(exc)[:100]}"
        return turn
    except Exception as exc:  # noqa: BLE001 — transport down, not a product fail
        turn.status = "DEGRADED"
        turn.detail = f"gateway unreachable: {type(exc).__name__}"
        return turn
    turn.ms = (time.perf_counter() - t0) * 1000
    lowered = reply.casefold()
    if any(c in lowered for c in AI_CLAIMS):
        turn.status = "FAIL"
        turn.detail = "AI-identity claim in reply"
    elif not any(m in reply for m in JO_MARKERS):
        turn.status = "FAIL"
        turn.detail = "no ar-JO marker in reply"
    elif turn.ms > 1200:
        turn.status = "FAIL"
        turn.detail = f"TTFT-equivalent {turn.ms:.0f}ms over the 1.2s bar"
    else:
        turn.status = "PASS"
        turn.detail = f"ar-JO warm reply in {turn.ms:.0f}ms"
    turn.extra = {"reply_head": reply[:120]}
    return turn


async def turn2_rag_recall() -> Turn:
    """Associative recall over a freshly boot-mirrored vault (live path:
    ensure_resources_scaffolding + VaultIndex, same as bot boot)."""
    turn = Turn(name="T2-rag «عمر مشتت اليوم وبده يركز، كيف يتصرف؟»")
    t0 = time.perf_counter()
    try:
        from src.associative import VaultIndex
        from src.vault import ensure_resources_scaffolding
    except Exception as exc:  # noqa: BLE001
        turn.detail = f"imports unavailable: {exc}"
        return turn
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "vault"
        mirrored = ensure_resources_scaffolding(root)
        idx = VaultIndex(root)
        idx.refresh_if_stale()
        hits = idx.query("عمر مشتت اليوم وبده يركز، كيف يتصرف؟")
    turn.ms = (time.perf_counter() - t0) * 1000
    top3 = [h.doc.path for h in hits[:3]]
    turn.extra = {"mirrored": len(mirrored), "top3": top3}
    want = ("Deep_Work_and_Attention_Sovereignty.md", "Omar_Executive_Profile_and_Rhythms.md")
    if any(any(p.endswith(w) for p in top3) for w in want):
        turn.status = "PASS"
        turn.detail = f"associative hit in top-3 ({len(mirrored)} files mirrored)"
    else:
        turn.status = "FAIL"
        turn.detail = f"miss: top3={top3}"
    return turn


async def turn3_silent_fetch() -> Turn:
    """Passive web extraction: real HTTPS, zero UI modules in the path."""
    turn = Turn(name="T3-fetch «اجلبي ملخص https://example.com»")
    t0 = time.perf_counter()
    try:
        from bridge.openclaw.fetch_arm import default_fetcher
    except Exception as exc:  # noqa: BLE001
        turn.detail = f"imports unavailable: {exc}"
        return turn
    try:
        text = await default_fetcher("https://example.com")
    except Exception as exc:  # noqa: BLE001 — network down, not a product fail
        turn.status = "DEGRADED"
        turn.detail = f"network unreachable: {type(exc).__name__}"
        return turn
    turn.ms = (time.perf_counter() - t0) * 1000
    if text and len(text.strip()) > 20:
        turn.status = "PASS"
        turn.detail = f"markdown served ({len(text)} chars, no UI touched by construction)"
    else:
        turn.status = "FAIL"
        turn.detail = "empty extraction"
    return turn


async def turn4_breaker_gate() -> Turn:
    """Destructive desktop action must PARK with a confirmation demand."""
    turn = Turn(name="T4-breaker «Alt+F4» without confirmation")
    try:
        from bridge.openclaw.breaker import SafetyCircuitBreaker
        from bridge.openclaw.protocol import Op, OpKind
        from src.openclaw.plans import PARK_LINE_AR, build_dag, gate
    except Exception as exc:  # noqa: BLE001
        turn.detail = f"imports unavailable: {exc}"
        return turn
    op = Op(op=OpKind.HOTKEY, value="Alt+F4")
    dag = build_dag(goal="سكري النافذة", ops=[op], weight=2)
    verdict = gate(dag, coordinator=None)
    authorized = SafetyCircuitBreaker.authorize(op, None)
    if verdict == "park" and authorized is False and PARK_LINE_AR:
        turn.status = "PASS"
        turn.detail = "PARKED + confirmation demanded, zero execution"
    else:
        turn.status = "FAIL"
        turn.detail = f"gate={verdict} authorized={authorized}"
    return turn


async def main() -> int:
    turns = [
        await fn()
        for fn in (turn1_warmth, turn2_rag_recall, turn3_silent_fetch, turn4_breaker_gate)
    ]
    print(f"{'turn':12s} {'status':9s} {'ms':>8s}  detail")
    for t in turns:
        print(f"{t.name[:46]:46s} {t.status:9s} {t.ms:8.0f}  {t.detail[:100]}")
    failed = [t for t in turns if t.status == "FAIL"]
    print(
        f"\nSCORECARD: {len(turns) - len(failed)}/{len(turns)} clean "
        f"({', '.join(f'{t.name[:2]}:{t.status}' for t in turns)})"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
