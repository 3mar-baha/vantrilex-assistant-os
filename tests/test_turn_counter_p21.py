"""P2.1 atomic turn counter (master transformation plan, Phase P2.1).

Crash-resilient human-turn tally in vault State: missing/garbage/empty reads
recover to 0 (corrupt-rename, never raise); increments are atomic tmp+replace;
only transport-boundary callers bump it — ReAct internals never import it.
"""

import ast
from pathlib import Path

import pytest

from src.turn_counter import COUNTER_NAME, bump_turn_counter, read_turn_count


@pytest.fixture(autouse=True)
def _real_disk(monkeypatch):
    """Most tests exercise real atomic writes; the skip test sets the marker itself."""
    monkeypatch.delenv("SARA_TURN_COUNTER_OFF", raising=False)


def _state(tmp_path: Path) -> Path:
    return tmp_path / "vault"


def test_missing_file_reads_zero_without_creating(tmp_path):
    assert read_turn_count(_state(tmp_path)) == 0
    assert not (_state(tmp_path) / "State" / COUNTER_NAME).exists()


def test_increment_persists_across_reads(tmp_path):
    root = _state(tmp_path)
    assert bump_turn_counter(root) == 1
    assert bump_turn_counter(root) == 2
    assert read_turn_count(root) == 2


def test_truncated_file_recovers_to_zero(tmp_path):
    target = _state(tmp_path) / "State" / COUNTER_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"")
    assert read_turn_count(_state(tmp_path)) == 0
    assert target.with_name(target.name + ".corrupt").exists()


def test_garbage_recovers_to_zero(tmp_path):
    target = _state(tmp_path) / "State" / COUNTER_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not-a-number\n", encoding="utf-8")
    assert read_turn_count(_state(tmp_path)) == 0
    assert bump_turn_counter(_state(tmp_path)) == 1


def test_react_internals_never_import_counter():
    """Human-turn-only isolation: no ReAct/dispatcher file may touch the counter."""
    repo = Path(__file__).resolve().parent.parent
    for rel in ("src/decision_loop.py", "src/dispatcher.py", "src/agent_manager.py"):
        tree = ast.parse((repo / rel).read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports |= {a.name for a in node.names}
        assert not any("turn_counter" in name for name in imports), rel


def test_pytest_env_skips_disk_write(tmp_path, monkeypatch):
    """Suite hermeticity: under pytest the transport hook never touches disk."""
    monkeypatch.setenv("SARA_TURN_COUNTER_OFF", "1")
    assert bump_turn_counter(_state(tmp_path)) == 0
    assert not (_state(tmp_path) / "State").exists()


def test_transport_hooks_present():
    """Both human entry points bump the counter (wiring guard)."""
    repo = Path(__file__).resolve().parent.parent
    tree = ast.parse((repo / "src" / "bot.py").read_text(encoding="utf-8"))
    bumped_in = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in (
            "on_text",
            "on_voice",
        ):
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and child.id == "bump_turn_counter":
                    bumped_in.add(node.name)
    assert bumped_in == {"on_text", "on_voice"}


def test_state_dir_created_on_bump(tmp_path):
    assert bump_turn_counter(_state(tmp_path)) == 1
    assert (_state(tmp_path) / "State" / COUNTER_NAME).is_file()


def test_whitespace_padded_value_reads(tmp_path):
    target = _state(tmp_path) / "State" / COUNTER_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("  7\n", encoding="utf-8")
    assert read_turn_count(_state(tmp_path)) == 7
    assert bump_turn_counter(_state(tmp_path)) == 8
