"""P6 tiered coverage gate (master transformation plan, Phase P6).

Runs the full suite with branch coverage, then enforces two tiers:
  - CORE modules (safety, cost, gender, cadence, RAG, router, memory):
    >= 98.0% branch coverage each.
  - Overall (src + bridge + common): >= 90.0%.
Exits non-zero with the breach table when either tier fails.

Usage (repo root):
    .venv/Scripts/python.exe scripts/check_tiered_coverage.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CORE_THRESHOLD = 98.0
TOTAL_THRESHOLD = 90.0

CORE = [
    "src/gateway.py",
    # P3-C (2026-09-30): the registration merge layer. Chosen for this list
    # precisely because it fails SILENTLY -- a dropped name yields a quietly
    # unroutable tool, a replaced goal tuple yields a quietly shrunken detection
    # vocabulary, and neither raises. It also gates four modules (dispatcher,
    # cognition and decision_loop are CORE already; agent_manager and evolution
    # are not), so it is the only place a break in the latter pair is caught.
    "src/tool_overlay.py",
    "bridge/guard.py",
    "bridge/executor.py",
    "bridge/openclaw/breaker.py",
    "src/gender_pipeline/engine.py",
    "src/gender_pipeline/shield.py",
    "src/gender_pipeline/rules_verbs.py",
    "src/gender_pipeline/rules_imperatives.py",
    "src/gender_pipeline/rules_clitics.py",
    "src/pc_actions.py",
    "src/voice_policy.py",
    "src/turn_counter.py",
    "src/cadence.py",
    "src/associative.py",
    "src/dispatcher.py",
    "src/decision_loop.py",
    "src/cognition.py",
    "src/memory.py",
    "src/middleware.py",
    "src/openclaw/plans.py",
    "common/consent.py",
    "common/protocol.py",
]


def _key(path: str) -> str:
    return path.replace("/", "\\")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        report = str(Path(tmp) / "coverage.json")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--cov=src",
                "--cov=bridge",
                "--cov=common",
                "--cov-branch",
                f"--cov-report=json:{report}",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,  # return code interpreted below (0/1 -> evaluate, else crash)
        )
        print(proc.stdout[-2000:])
        if proc.returncode not in (0, 1):
            print("check_tiered_coverage: pytest crashed")
            return 2
        if not Path(report).exists():
            print("check_tiered_coverage: no coverage report (suite failed)")
            return 2
        data = json.loads(Path(report).read_text(encoding="utf-8"))
    breaches: list[str] = []
    files = data["files"]
    for path in CORE:
        summary = files[_key(path)]["summary"]
        pct = summary["percent_covered"]
        flag = "OK  " if pct >= CORE_THRESHOLD else "FAIL"
        print(f"[{flag}] {pct:5.1f}% {path}")
        if pct < CORE_THRESHOLD:
            entry = files[_key(path)]
            breaches.append(
                f"{path}: {pct:.1f}% < {CORE_THRESHOLD} (miss={entry.get('missing_lines')})"
            )
    total = data["totals"]["percent_covered"]
    flag = "OK  " if total >= TOTAL_THRESHOLD else "FAIL"
    print(f"[{flag}] {total:5.1f}% TOTAL")
    if total < TOTAL_THRESHOLD:
        breaches.append(f"TOTAL: {total:.1f}% < {TOTAL_THRESHOLD}")
    if breaches:
        print("\nTIERED COVERAGE GATE FAILED:")
        for breach in breaches:
            print(f"  - {breach}")
        return 1
    print("\nTIERED COVERAGE GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
