"""Phase-6 live end-to-end canary (owner-authorized, single turn).

Flow: RAG lookup on the real vault -> posture check -> ReAct decision loop
with a REAL gateway + read-only ToolRegistry (whitelist path bound; all other
backends None, so every other tool degrades honestly) -> Amman-dialect reply
-> Fish synthesis with voice-side tag sanitizer.

Budgets: one FAST router turn + loop stages + one HEAVY narration + one Fish
synthesis. Any stage may report THROTTLED/FAIL loudly — the scorecard, not an
exception, is the deliverable. No secrets printed, ever.

Usage (repo root):
    .venv/Scripts/python.exe scripts/live_canary_phase6.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CANARY_PROMPT = "شو البرامج المعتمدة عندك؟"
RAG_PROBE = "وين صرفنا مصاري هالشهر؟"
STAGE_TIMEOUT_S = 240.0


async def main() -> int:
    from src.associative import inject
    from src.config import get_settings
    from src.decision_loop import LoopBudget, run_decision_loop
    from src.fish_voice import FishFirstVoice, FishVoice
    from src.gateway import OmniRouteClient, Tier
    from src.situational import SituationalState, apply_posture
    from src.tools import ToolRegistry

    settings = get_settings()
    score: dict[str, str] = {}
    t_all = time.perf_counter()

    # 1. RAG lookup on the real vault -------------------------------------
    t0 = time.perf_counter()
    block = inject(RAG_PROBE, settings.vault_local_path)
    score["rag_ms"] = f"{(time.perf_counter() - t0) * 1000:.0f}"
    score["rag_hit"] = "yes" if block else "miss (honest empty)"
    print(f"[1/5] RAG lookup: {score['rag_hit']} in {score['rag_ms']}ms", flush=True)
    if block:
        print(f"      block head: {block[:120]}", flush=True)

    # 2. Posture on a fresh ring ------------------------------------------
    state = SituationalState()
    posture = state.posture()
    score["posture"] = posture
    assert apply_posture("SYS", posture) == "SYS", "fresh ring must be a no-op"
    print(f"[2/5] posture: {posture} (fresh ring, envelope untouched)", flush=True)

    # 3. ReAct decision loop, live gateway, read-only registry -------------
    gateway = OmniRouteClient(
        settings.omniroute_base_url,
        settings.omniroute_api_key,
        chains={
            Tier.FAST: settings.fast_chain,
            Tier.MEDIUM: settings.medium_chain,
            Tier.HEAVY: settings.heavy_chain,
        },
    )
    tools = ToolRegistry()
    tools.bind_whitelist_path("config/whitelist.json")
    deltas: list[str] = []
    tools_seen: list[str] = []
    orig_call = tools.call

    async def _spy(tool: str, arg: str = ""):
        tools_seen.append(tool)
        return await orig_call(tool, arg)

    tools.call = _spy  # type: ignore[method-assign] — canary observation only
    t0 = time.perf_counter()
    try:
        async for delta in run_decision_loop(
            gateway=gateway,
            tools=tools,
            user_text=CANARY_PROMPT,
            system="أنت سارة — مساعدة عمر التنفيذية. ردي بعامية عمانية دافئة.",
            budget=LoopBudget(max_iterations=4, max_tool_calls=4, max_wall_s=200.0),
        ):
            deltas.append(delta)
            print(f"      delta: {delta[:100]}", flush=True)
        score["loop"] = "OK"
    except Exception as exc:  # noqa: BLE001 — scorecard over stacktrace
        score["loop"] = f"FAIL: {type(exc).__name__}: {exc}"[:160]
    finally:
        await gateway.aclose()
    score["loop_ms"] = f"{(time.perf_counter() - t0) * 1000:.0f}"
    score["loop_tools"] = ",".join(tools_seen) or "none"
    reply = "".join(deltas[1:] if deltas else [])
    print(
        f"[3/5] loop: {score['loop']} in {score['loop_ms']}ms tools=[{score['loop_tools']}]",
        flush=True,
    )
    print(f"      reply: {reply[:220]}", flush=True)

    # 4. Fish synthesis (voice-side sanitizer rides along) -----------------
    if reply.strip():
        fish = FishFirstVoice(fish=FishVoice.from_settings(settings))
        t0 = time.perf_counter()
        try:
            opus = await asyncio.wait_for(fish.synthesize(reply[:160]), timeout=120.0)
            ok = opus[:4] == b"OggS"
            score["fish"] = "OK" if ok else "BAD_HEADER"
            score["fish_bytes"] = str(len(opus))
        except Exception as exc:  # noqa: BLE001
            score["fish"] = f"FAIL: {type(exc).__name__}"
            score["fish_bytes"] = "0"
        score["fish_ms"] = f"{(time.perf_counter() - t0) * 1000:.0f}"
    else:
        score["fish"] = "SKIPPED (empty reply)"
        score["fish_bytes"] = "0"
        score["fish_ms"] = "0"
    print(
        f"[4/5] fish: {score['fish']} bytes={score['fish_bytes']} ms={score['fish_ms']}", flush=True
    )

    # 5. Scorecard ----------------------------------------------------------
    print("[5/5] SCORECARD", flush=True)
    for key in (
        "rag_hit",
        "rag_ms",
        "posture",
        "loop",
        "loop_ms",
        "loop_tools",
        "fish",
        "fish_bytes",
        "fish_ms",
    ):
        print(f"      {key}: {score.get(key, '?')}", flush=True)
    print(f"      total_s: {time.perf_counter() - t_all:.1f}", flush=True)
    print(f"      SARA SAYS: {reply[:300]}", flush=True)
    bad = score["loop"].startswith("FAIL") or score["fish"] not in ("OK", "SKIPPED (empty reply)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
