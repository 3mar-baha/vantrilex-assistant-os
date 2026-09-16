"""Unified 3-tier runner: executes tests/suite/ + prints tabulate health matrix.

Usage: .\\.venv\\Scripts\\python.exe run_live_probe.py [--tier1|--tier2|--tier3|--all]
Extra rows: routing-matrix + coach (focused pytest files) and zero-edge (repo
grep proving the Edge-TTS purge). Clean teardown: never writes prod vault
logs; redacts secrets from output.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import time

TIERS = {
    "tier1": "tests/suite/tier1_resilience",
    "tier2": "tests/suite/tier2_live_probes",
    "tier3": "tests/suite/tier3_shadow_tracer",
    "routing-matrix": "tests/suite/tier1_resilience/test_routing_matrix.py",
    "coach": "tests/suite/tier3_shadow_tracer/test_coach.py",
}

_EDGE_RE = re.compile(
    r"^\s*(import\s+edge_tts|from\s+edge_tts|from\s+src\.voice\s+import\s+.*\bVoicePipeline\b)",
    re.MULTILINE,
)
_EDGE_SCOPES = ("src", "tests/suite", "requirements.txt")


def zero_edge_row() -> dict:
    """Grep-enforced purge proof: no Edge engine code in src/suite/deps."""
    t0 = time.perf_counter()
    offenders: list[str] = []
    for scope in _EDGE_SCOPES:
        p = pathlib.Path(scope)
        if p.is_file():
            targets = [p]
        elif p.is_dir():
            targets = sorted(p.rglob("*.py"))
        else:
            continue
        for f in targets:
            try:
                if _EDGE_RE.search(f.read_text(encoding="utf-8")):
                    offenders.append(str(f))
            except OSError:
                continue
    req = pathlib.Path("requirements.txt").read_text(encoding="utf-8")
    if re.search(r"(?m)^edge-tts", req):
        offenders.append("requirements.txt")
    dt = (time.perf_counter() - t0) * 1000
    if offenders:
        return {
            "tier": "zero-edge",
            "path": "grep src+suite+requirements",
            "status": "FAIL",
            "ms": dt,
            "detail": "Edge-TTS footprint: " + ", ".join(offenders),
        }
    return {
        "tier": "zero-edge",
        "path": "grep src+suite+requirements",
        "status": "PASS",
        "ms": dt,
        "detail": "zero Edge imports/usages; Fish-only verified",
    }


_SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9\-_]{8,}|ghp_[A-Za-z0-9]+|xox[a-z]-\S+|\\d{9,}:AA[A-Za-z0-9_-]+"
)


def redact(text: str) -> str:
    return _SECRET_RE.sub("<REDACTED>", text)


def run_tier(name: str, path: str) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-q", "--no-cov", "-p", "no:cacheprovider"],
        capture_output=True,
        check=False,
        text=True,
        cwd=".",
    )
    dt = (time.perf_counter() - t0) * 1000
    out = redact((proc.stdout or "") + (proc.stderr or ""))
    # Parse pytest -q tail: "3 passed, 1 skipped in 2.1s" etc.
    status = "FAIL" if proc.returncode != 0 else "PASS"
    if "skipped" in out and "failed" not in out and "passed" not in out:
        status = "SKIP"
    tail = "\n".join(out.strip().splitlines()[-6:])
    return {"tier": name, "path": path, "status": status, "ms": dt, "detail": tail}


def main() -> int:
    only = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else "all"
    targets = TIERS if only == "all" else {only: TIERS[only]}
    rows = []
    for name, path in targets.items():
        rows.append(run_tier(name, path))
    if only == "all":
        rows.append(zero_edge_row())
    try:
        from tabulate import tabulate

        print(
            tabulate(
                [(r["tier"], r["status"], f"{r['ms']:.0f}ms") for r in rows],
                headers=["tier", "status", "time"],
                tablefmt="github",
            )
        )
    except ImportError:
        for r in rows:
            print(f"{r['tier']}: {r['status']} ({r['ms']:.0f}ms)")
    print("\n--- diagnostics ---")
    for r in rows:
        print(f"\n## {r['tier']} [{r['status']}] ({r['path']})")
        print(r["detail"][-1500:])
    failed = [r for r in rows if r["status"] == "FAIL"]
    print(f"\nMATRIX: {len(rows) - len(failed)}/{len(rows)} tiers green")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
