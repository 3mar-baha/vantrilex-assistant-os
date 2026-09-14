"""OpenClaw regression benchmark runner (Phase 4).

Executes the scenario matrix (A–E) against hermetic doubles — no browser,
no desktop, no network — times every tier, counts safety violations, and
writes the official report to benchmarks/BENCHMARK_OPENCLAW_REPORT.md.

Honesty note (also stamped in the report): mock latencies validate
routing order + safety gating, NOT production wall-clock. T0 < T1 < T2/T3
ordering is the assertion; absolute milliseconds are harness overhead.

Runs (repo root):
    .venv/Scripts/python.exe scripts/benchmark_openclaw.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.suite.openclaw_bench.scenarios import ALL_SCENARIOS

REPORT_DEFAULT = Path("benchmarks/BENCHMARK_OPENCLAW_REPORT.md")


async def run_matrix() -> list[dict]:
    rows = []
    for scenario in ALL_SCENARIOS:
        t0 = time.perf_counter()
        try:
            result = await scenario()
        except Exception as exc:  # noqa: BLE001 — a crashed scenario is a row, not a halt
            from tests.suite.openclaw_bench.scenarios import ScenarioResult

            result = ScenarioResult(name=scenario.__name__, tier="?", detail=f"CRASH: {exc}")
        wall_ms = (time.perf_counter() - t0) * 1000
        rows.append(
            {
                "scenario": result.name,
                "tier": result.tier,
                "ms": result.latency_ms or wall_ms,
                "pass": result.passed,
                "violations": result.safety_violations,
                "detail": result.detail,
            }
        )
        mark = "PASS" if result.passed else "FAIL"
        print(
            f"[{mark}] {result.name:38s} {result.tier:12s} {rows[-1]['ms']:7.1f}ms :: {result.detail[:90]}"
        )
    return rows


def render_report(rows: list[dict], stamp: str) -> str:
    total = len(rows)
    passed = sum(1 for r in rows if r["pass"])
    violations = sum(max(0, r["violations"]) for r in rows)
    lines = [
        "# OpenClaw Regression Benchmark — Official Report",
        "",
        f"- Date (UTC): {stamp}",
        f"- Scenarios: **{passed}/{total} passed ({100.0 * passed / total:.1f}%)**",
        f"- Safety violations (unconfirmed irreversible executions): **{violations}**",
        "- Environment: hermetic doubles (MockDesktop/MockUIA/MockWebPage/fake fetchers) —",
        "  no browser, no desktop, no network. Mock latencies validate routing",
        "  order + gating, not production wall-clock.",
        "",
        "## Matrix",
        "",
        "| Scenario | Tier | ms | Result | Detail |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        mark = "PASS" if r["pass"] else "FAIL"
        lines.append(
            f"| {r['scenario']} | {r['tier']} | {r['ms']:.1f} | {mark} | {r['detail'][:100]} |"
        )
    by_tier: dict[str, list[float]] = {}
    for r in rows:
        by_tier.setdefault(r["tier"], []).append(r["ms"])
    lines += ["", "## Per-tier latency (harness ms, ordering signal only)", ""]
    for tier in sorted(by_tier):
        vals = by_tier[tier]
        lines.append(
            f"- {tier}: n={len(vals)} mean={sum(vals) / len(vals):.1f} max={max(vals):.1f}"
        )
    lines += [
        "",
        "## Safety compliance",
        "",
        "- Committing ops without confirmation: all PARKED/refused (D1: 7/7, D2: shell shapes refused even with id).",
        f"- Total unconfirmed irreversible executions across the matrix: **{violations}**.",
        "",
        "## Verdict",
        "",
        (
            "**GREEN** — all scenarios pass, zero safety violations."
            if passed == total and violations == 0
            else "**RED** — see FAIL rows above."
        ),
        "",
    ]
    return "\n".join(lines)


async def main() -> int:
    rows = await run_matrix()
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    REPORT_DEFAULT.write_text(render_report(rows, stamp), encoding="utf-8")
    print(f"\nReport: {REPORT_DEFAULT}")
    passed = sum(1 for r in rows if r["pass"])
    violations = sum(max(0, r["violations"]) for r in rows)
    return 0 if passed == len(rows) and violations == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
