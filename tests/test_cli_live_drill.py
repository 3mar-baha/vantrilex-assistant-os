"""Item C (plan §1) — `scripts/test_cli_live_drill.py`, the CLI field-test drill.

The drill replaces "Omar types a hundred prompts" with a reproducible multi-turn suite.
The one thing that makes it safe to ship is Decision 6: the six irreversible tools stay
permanently `confirmation_id`-gated, zero exceptions, so the drill may PROPOSE `launch`
and be refused — and may never supply a confirmation on the owner's behalf (plan §4).

The second thing that makes it safe to run is fail-soft. The repo's established
convention is `scripts/live_interactive_benchmark.py` — every scenario returns a
`ScenarioResult`, and no crash propagates; the pyproject comment at `:9-12` records
why its blind `except` is that harness's contract rather than a smell. This file
guards that contract for the drill, with the gateway pointed at a closed port so the
suite stays hermetic: no live-harness test calls the real gateway here.

Public seam this file pins (mirrors `scripts/live_interactive_benchmark.py:24`, `:384`):
    ScenarioResult: name, test, tier, latency_ms, passed, detail, mode, safety_violations
    GATEWAY_URL: module constant the reachability probe reads
    async def run_all() -> list[ScenarioResult]      # never raises
    def main(argv=None) -> int                       # never raises
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

DRILL_PATH = Path(__file__).resolve().parents[1] / "scripts" / "test_cli_live_drill.py"

# A closed port on loopback: nothing listens, every connect is refused immediately.
DEAD_GATEWAY_URL = "http://127.0.0.1:1/v1"

# The drill's own launch step, located by name so the label stays free to change.
LAUNCH_ROW = re.compile(r"launch|pc[-_ ]?action|exec\.launch", re.IGNORECASE)

# A recorded refusal, in either language the repo speaks.
REFUSAL_WORDS = re.compile(r"refus|confirm|denied|رفض|تأكيد", re.IGNORECASE)

# The three forging primitives in the tree: src/pc_actions.py:277 mints the id with
# uuid4, bridge/executor.py mints the audit code, and handle_owner_reply is the only
# path that turns an affirmative reply into an executed action. A drill that can reach
# any of them can confirm on the owner's behalf.
MINTING_SYMBOLS = ("mint_audit_code", "handle_owner_reply", "_confirm_and_execute")


def _load_drill():
    """Loaded from inside the test body, not at module scope.

    A module-scope load would report ONE collection error for all five guards and
    hide which contract is unmet. Called per test, each guard fails on its own.

    `sys.modules` is populated BEFORE `exec_module`, as `importlib` does it: a module
    that declares a dataclass under `from __future__ import annotations` — which
    `ScenarioResult` is — resolves its field types through `sys.modules[cls.__module__]`
    and raises `AttributeError: 'NoneType' object has no attribute '__dict__'` if the
    module is not registered while it executes. Caught by the break-run.
    """
    if not DRILL_PATH.exists():
        pytest.fail("scripts/test_cli_live_drill.py does not exist yet (item C, plan §1)")
    spec = importlib.util.spec_from_file_location("test_cli_live_drill", DRILL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def _offline_drill(monkeypatch, tmp_path: Path):
    """The drill with the gateway pinned unreachable and the vault pinned to tmp.

    Reaching the owner-real `.env` or the real vault from a unit test is the failure
    this helper exists to prevent; the drill is specified to mutate no vault state.
    """
    module = _load_drill()
    monkeypatch.setattr(module, "GATEWAY_URL", DEAD_GATEWAY_URL, raising=False)
    monkeypatch.setenv("OMNIROUTE_BASE_URL", DEAD_GATEWAY_URL)
    monkeypatch.setenv("VAULT_LOCAL_PATH", str(tmp_path))
    return module


def _launch_rows(rows) -> list:
    return [row for row in rows if LAUNCH_ROW.search(f"{row.name} {row.detail}")]


# --- Decision 6: the launch row demonstrates the refusal and never a launch ----------


async def test_launch_row_records_the_refusal_as_the_expected_outcome(
    monkeypatch, tmp_path
) -> None:
    """The launch step is the drill's whole point: it proposes, and it is refused.

    Red: the drill does not exist. Green: an OS-launch row is recorded, it passes
    BECAUSE the refusal is the correct outcome, its detail names the refusal, and it
    reports zero safety violations.
    """
    rows = await _offline_drill(monkeypatch, tmp_path).run_all()
    launches = _launch_rows(rows)
    assert launches, (
        "the drill must propose an OS-launch step so Decision 6 is demonstrated "
        f"(plan §4); rows were {[row.name for row in rows]}"
    )
    for row in launches:
        assert row.passed is True, (
            f"a refused launch is the expected outcome, not a failure: {row.name}: {row.detail}"
        )
        assert row.safety_violations == 0, f"{row.name} reported a safety violation: {row.detail}"
        assert REFUSAL_WORDS.search(row.detail), (
            f"{row.name} must record why it did not launch: {row.detail!r}"
        )


# --- fail-soft: an unreachable gateway is a row, never a traceback -------------------


async def test_unreachable_gateway_degrades_to_fail_rows_and_never_raises(
    monkeypatch, tmp_path
) -> None:
    """pyproject `:9-12` — the harness contract is that nothing propagates.

    Red: the drill does not exist. Green: with the gateway closed, every scenario
    still returns a row carrying an honest detail, at least one of them is a FAIL, and
    no detail carries a Python traceback.
    """
    rows = await _offline_drill(monkeypatch, tmp_path).run_all()
    assert rows, "an unreachable gateway must still produce recorded rows"
    for row in rows:
        assert isinstance(row.passed, bool), f"{row.name} has no boolean verdict"
        assert row.detail.strip(), (
            f"{row.name} recorded no detail — a blank row hides what happened"
        )
        assert "Traceback" not in row.detail, f"{row.name} leaked a traceback: {row.detail!r}"
    assert any(row.passed is False for row in rows), (
        "an unreachable gateway must surface as a FAIL row, never as a silent pass"
    )


def test_drill_main_returns_an_exit_code_instead_of_raising(monkeypatch, tmp_path) -> None:
    """`python scripts/test_cli_live_drill.py` must always end in an exit code.

    Red: the drill does not exist. Green: `main` returns a non-negative int with the
    gateway unreachable, so a CI step gets a status instead of a stack trace.
    """
    code = _offline_drill(monkeypatch, tmp_path).main([])
    assert isinstance(code, int) and not isinstance(code, bool)
    assert code >= 0, f"exit code must be a non-negative status, got {code!r}"


# --- Decision 6, structurally: the drill cannot confirm, because it cannot mint ------


def test_drill_never_supplies_a_confirmation_id() -> None:
    """The only `confirmation_id` the drill may pass is the literal `None`.

    Red: the drill does not exist. Green: every `confirmation_id=` keyword argument
    and every `confirmation_id` dict entry in the source is the constant None — the
    refusal is demonstrated by never supplying the id, never by supplying a fake one.
    """
    if not DRILL_PATH.exists():
        pytest.fail("scripts/test_cli_live_drill.py does not exist yet (item C, plan §1)")
    tree = ast.parse(DRILL_PATH.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            offenders += [
                f"confirmation_id={ast.unparse(keyword.value)} (line {keyword.value.lineno})"
                for keyword in node.keywords
                if keyword.arg == "confirmation_id"
                and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None)
            ]
        elif isinstance(node, ast.Dict):
            offenders += [
                f"dict entry confirmation_id={ast.unparse(value)} (line {value.lineno})"
                for key, value in zip(node.keys, node.values, strict=True)
                if isinstance(key, ast.Constant)
                and key.value == "confirmation_id"
                and not (isinstance(value, ast.Constant) and value.value is None)
            ]
    assert not offenders, f"the drill must never supply a confirmation_id: {offenders}"


def test_drill_cannot_mint_a_confirmation_id() -> None:
    """No minting primitive is reachable from the drill: uuid, audit code, or reply.

    Red: the drill does not exist. Green: the source imports no `uuid`, and never
    names `mint_audit_code` / `handle_owner_reply` / `_confirm_and_execute`.
    """
    if not DRILL_PATH.exists():
        pytest.fail("scripts/test_cli_live_drill.py does not exist yet (item C, plan §1)")
    tree = ast.parse(DRILL_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "uuid" not in imported, "the drill must not import uuid — that is the id minter"
    used = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forging = sorted(used & set(MINTING_SYMBOLS))
    assert not forging, f"the drill must not reach the confirmation-forging path: {forging}"
