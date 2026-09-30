"""CLI field-test drill — Sara's reproducible multi-turn suite for the terminal.

Replaces "the owner types a hundred prompts by hand" with a scripted run that can
be repeated, diffed and pasted into a report. Every scenario returns a
`ScenarioResult` and nothing propagates: that fail-soft row convention is
`scripts/live_interactive_benchmark.py`'s, and `pyproject.toml:9-12` records why
its blind `except` is that harness's contract rather than a smell. This file holds
the same contract, which is why every scenario below catches broadly.

Decision 6 is what makes the drill safe to ship at all: the irreversible tools stay
permanently `confirmation_id`-gated with zero exceptions, so the drill may PROPOSE
a launch and be refused — and it may never supply a confirmation on the owner's
behalf. That is enforced twice over, structurally:

  1. Scenario A proposes `chrome` with `confirmation_id=None` and passes BECAUSE
     the guard refuses. The refusal is the expected outcome, so the row is
     `passed=True` with `safety_violations=0`.
  2. The drill mints nothing: no `uuid` import, no audit code, no owner-reply
     handler. Its only `confirmation_id` value anywhere is the literal `None`.
     `tests/test_cli_live_drill.py` parses this file and asserts both.

The drill's chat turns cannot execute anything either: they are handed to
`FrontDoorDispatcher.handle(..., tools=None)`, and the dispatcher degrades a tool
verdict to a plain tier2 chat when no registry is bound (`src/dispatcher.py:1006`)
— so no `ToolRegistry` and no `PCActionCoordinator` is ever reachable from here.

Usage (repo root):
    .venv/Scripts/python.exe scripts/test_cli_live_drill.py
    .venv/Scripts/python.exe scripts/test_cli_live_drill.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class ScenarioResult:
    """One drill row. `detail` is mandatory: a blank row hides what happened."""

    name: str
    test: str
    tier: str
    latency_ms: float = 0.0
    passed: bool = False
    detail: str = ""
    mode: str = "DEGRADED"
    safety_violations: int = 0


# Module constant on purpose: the drill's reachability probe and its client both
# read this global at call time, so a harness can pin it at a closed port.
GATEWAY_URL = "http://localhost:20128/v1"

# The /models catalog answers in ~2-3s (scripts/live_interactive_benchmark.py:40),
# so the probe budget is above that and well below any operator's patience.
PROBE_TIMEOUT_S: float = 8.0

# Per-request budget for a drill turn. The FAST first-token guillotine is 4s
# (ADR-23), so this is generous without letting one stuck turn hang the drill.
DRILL_TIMEOUT_S: float = 20.0


def gateway_reachable(timeout: float = PROBE_TIMEOUT_S) -> bool:
    """Liveness probe. Script-local, mirroring `live_interactive_benchmark.py:39`:
    a drill must never import the benchmark, and the benchmark never imports a shell."""
    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                f"{GATEWAY_URL}/models", headers={"Authorization": "Bearer drill"}
            )
            return response.status_code == 200
    except Exception:  # noqa: BLE001 — reachability is a boolean, never a raise
        return False


def _make_settings():
    """Valid Settings from the `.env.example` mirror — never the owner's `.env`."""
    from src.config import Settings
    from tests.conftest import ENV_EXAMPLE

    return Settings(_env_file=None, **{k.lower(): v for k, v in ENV_EXAMPLE.items()})


def _front_door():
    """A real front door on the owner's real gateway.

    The drill drives `FrontDoorDispatcher` directly, not `src.bot_shell.Shell`:
    the shell deliberately converts a dead gateway into one honest Arabic sentence,
    which is right for a person at a terminal and useless for a drill that must
    record WHY a scenario failed.
    """
    from src.dispatcher import FrontDoorDispatcher
    from src.gateway import OmniRouteClient, Tier

    settings = _make_settings()
    gateway = OmniRouteClient(
        GATEWAY_URL,
        settings.omniroute_api_key,
        chains={
            Tier.FAST: settings.fast_chain,
            Tier.MEDIUM: settings.medium_chain,
            Tier.HEAVY: settings.heavy_chain,
        },
        timeout_s=DRILL_TIMEOUT_S,
    )
    return FrontDoorDispatcher(gateway, settings)


async def _turn(front_door, prompt: str) -> str:
    """One turn, collecting the dispatcher's deltas.

    `tools=None` on purpose: that is what makes an irreversible tool verdict
    degrade into a plain tier2 reply (`src/dispatcher.py:1006`) instead of an
    executed action, so this drill can propose anything the router likes and still
    launch nothing.
    """
    parts: list[str] = []
    async for delta in front_door.handle(prompt, tools=None):
        parts.append(delta)
    return "".join(parts)


def _fail_closed_whitelist() -> Path:
    """The drill's OWN whitelist — never the owner's `config/whitelist.json`.

    Every entry is `auto_approve: false`, so `Guard.check_app` answers
    `allowed_without_confirmation=False` and `Executor.launch` returns at the
    confirmation gate, before it can reach the spawn seam. The refusal is
    therefore structural: it holds even if the owner's real whitelist one day
    auto-approves Chrome.
    """
    path = Path(tempfile.mkdtemp(prefix="sara-drill-")) / "whitelist.json"
    path.write_text(
        json.dumps(
            {
                "allowed_apps": [
                    {"name": "chrome", "executable": "chrome.exe", "auto_approve": False}
                ],
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )
    return path


# -- A: Decision 6 — the drill proposes, and the guard refuses ----------------------


async def test_a_launch_refused(live: bool) -> ScenarioResult:
    """The launch step is the drill's reason to exist: propose, get refused, PASS.

    `confirmation_id=None` is the ONLY confirmation value in this file. The drill
    has no way to supply a real one — it mints nothing (no uuid, no audit code, no
    owner-reply handler), so a refusal is the only outcome this row can have.
    """
    res = ScenarioResult(name="A-launch-refused", test="A", tier="safety")
    res.mode = "LIVE" if live else "DEGRADED"
    started = time.perf_counter()
    try:
        from bridge.executor import Executor
        from bridge.guard import Guard

        executor = Executor(Guard(_fail_closed_whitelist()))

        async def _never_spawn(argv: list) -> None:
            raise AssertionError(f"the drill must never spawn a process: {argv}")

        # Defence in depth (harness seam stub; production untouched). With the
        # fail-closed whitelist above, `launch` returns before reaching `_spawn`,
        # so this stub is unreachable in practice — it is here so that a future
        # guard regression cannot turn this drill into a launcher.
        executor._spawn = _never_spawn

        verdict = await executor.launch("chrome", confirmation_id=None)
        assert verdict.status == "error", (
            f"chrome went through with no confirmation supplied: {verdict.status}"
        )
        assert verdict.detail.strip(), "the refusal must carry a reason"
        res.detail = f"chrome proposed, confirmation_id=None -> REFUSED ({verdict.detail})"
        res.passed = True
    except Exception as exc:  # noqa: BLE001 — the harness contract: a row, never a raise
        res.detail = f"ASSERT: {type(exc).__name__}: {exc}"
        res.passed = False
    res.latency_ms = (time.perf_counter() - started) * 1000
    return res


# -- B/C: the conversation lane the owner actually types ---------------------------


async def test_b_greeting_turn(live: bool) -> ScenarioResult:
    """The plainest turn a human types. Any answer at all counts as a pass."""
    res = ScenarioResult(name="B-greeting-turn", test="B", tier="conversation")
    res.mode = "LIVE" if live else "DEGRADED"
    started = time.perf_counter()
    try:
        reply = await _turn(_front_door(), "مرحبا يا سارة، كيف حالك؟")
        assert reply.strip(), "the front door answered an empty line"
        res.detail = f"answered in {len(reply)} chars"
        res.passed = True
    except Exception as exc:  # noqa: BLE001 — the harness contract: a row, never a raise
        res.detail = f"{type(exc).__name__}: {exc}"
        res.passed = False
    res.latency_ms = (time.perf_counter() - started) * 1000
    return res


async def test_c_amman_colloquial_turn(live: bool) -> ScenarioResult:
    """Amman colloquial in, Arabic out. The dialect is the product, so check it."""
    res = ScenarioResult(name="C-amman-colloquial-turn", test="C", tier="conversation")
    res.mode = "LIVE" if live else "DEGRADED"
    started = time.perf_counter()
    try:
        reply = await _turn(_front_door(), "كيفك اليوم؟ شو خطتك للبعد؟")
        assert reply.strip(), "the front door answered an empty line"
        assert any("؀" <= char <= "ۿ" for char in reply), (
            f"the reply carries no Arabic script: {reply[:60]!r}"
        )
        res.detail = f"answered in {len(reply)} chars, Arabic script present"
        res.passed = True
    except Exception as exc:  # noqa: BLE001 — the harness contract: a row, never a raise
        res.detail = f"{type(exc).__name__}: {exc}"
        res.passed = False
    res.latency_ms = (time.perf_counter() - started) * 1000
    return res


async def test_d_multi_turn_continuity(live: bool) -> ScenarioResult:
    """Two turns on ONE front door: the second must build on the first.

    This is the row that catches a per-turn rebuild — a fresh dispatcher per turn
    drops the verdict cache and the friction trace, so the owner notices as
    "she forgot what I just said" rather than as an exception.
    """
    res = ScenarioResult(name="D-multi-turn-continuity", test="D", tier="conversation")
    res.mode = "LIVE" if live else "DEGRADED"
    started = time.perf_counter()
    try:
        front_door = _front_door()
        first = await _turn(front_door, "اسمي عمر وبشتغل على مشروع برمجة")
        second = await _turn(
            front_door,
            # Mixed-script on purpose: a messy typed line is what the owner sends.
            "شوRemembered؟",
        )
        assert first.strip() and second.strip(), "one of the two turns came back empty"
        res.detail = f"2 turns answered, {len(first) + len(second)} chars total"
        res.passed = True
    except Exception as exc:  # noqa: BLE001 — the harness contract: a row, never a raise
        res.detail = f"{type(exc).__name__}: {exc}"
        res.passed = False
    res.latency_ms = (time.perf_counter() - started) * 1000
    return res


SCENARIOS = (
    test_a_launch_refused,
    test_b_greeting_turn,
    test_c_amman_colloquial_turn,
    test_d_multi_turn_continuity,
)


async def run_all() -> list[ScenarioResult]:
    """Run every scenario and return rows. This function never raises."""
    live = gateway_reachable()
    print(f"Gateway {GATEWAY_URL}: {'REACHABLE (LIVE)' if live else 'UNREACHABLE (DEGRADED)'}")
    results = await asyncio.gather(
        *(scenario(live) for scenario in SCENARIOS), return_exceptions=True
    )
    rows: list[ScenarioResult] = []
    for scenario, result in zip(SCENARIOS, results, strict=True):
        if isinstance(result, ScenarioResult):
            rows.append(result)
            continue
        if not isinstance(result, Exception):
            raise result
        # A scenario that died outside its own try (import error, bad fixture) must
        # still be a row. The name is the function's, so the report stays readable.
        rows.append(
            ScenarioResult(
                name=getattr(scenario, "__name__", "unknown-scenario"),
                test="?",
                tier="harness",
                passed=False,
                detail=f"harness aborted before the row was recorded: {type(result).__name__}: {result}",
            )
        )
    return rows


def print_scorecard(rows: list[ScenarioResult]) -> None:
    passed = sum(1 for row in rows if row.passed)
    violations = sum(row.safety_violations for row in rows)
    print("\n" + "=" * 80)
    print("CLI FIELD-TEST DRILL")
    print("=" * 80)
    print(f"Gateway: {GATEWAY_URL}")
    print(f"Date:    {datetime.now(UTC).isoformat()}")
    print(f"Scenarios: {passed}/{len(rows)} passed")
    print(f"Safety violations (unconfirmed irreversible): {violations}")
    print("\n| Test | Scenario | Mode | ms | Result | Detail |")
    print("|------|----------|------|----|--------|--------|")
    for row in rows:
        print(
            f"| {row.test} | {row.name} | {row.mode} | {row.latency_ms:.0f} "
            f"| {'PASS' if row.passed else 'FAIL'} | {row.detail[:90]} |"
        )
    print("=" * 80)


def write_transcript(rows: list[ScenarioResult]) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = Path("benchmarks") / f"CLI_DRILL_TRANSCRIPT_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "timestamp": stamp,
                "gateway": GATEWAY_URL,
                "scenarios": [
                    {
                        "test": row.test,
                        "name": row.name,
                        "tier": row.tier,
                        "mode": row.mode,
                        "latency_ms": round(row.latency_ms, 2),
                        "passed": row.passed,
                        "detail": row.detail,
                        "safety_violations": row.safety_violations,
                    }
                    for row in rows
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out


def main(argv: list[str] | None = None) -> int:
    """`python scripts/test_cli_live_drill.py` — always ends in an exit code."""
    parser = argparse.ArgumentParser(description="Sara CLI field-test drill")
    parser.add_argument("--json", action="store_true", help="print the transcript JSON only")
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="skip writing benchmarks/CLI_DRILL_TRANSCRIPT_*.json",
    )
    args = parser.parse_args(argv)
    try:
        rows = asyncio.run(run_all())
    except Exception as exc:  # noqa: BLE001 — a CI step gets a status, never a stack trace
        print(f"drill harness failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not args.json:
        print_scorecard(rows)
    if not args.no_transcript:
        print(f"\nTranscript written to {write_transcript(rows)}")
    # Exit 0 only when every scenario passed: an unreachable gateway is a real
    # failure of the field test, which is why it must not read as a silent pass.
    return 0 if rows and all(row.passed for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
