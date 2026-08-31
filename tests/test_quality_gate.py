"""Sprint-4 §4.4a: quality-gate hardening — the >=85% branch coverage threshold goes
live through addopts (every runner inherits it), pragmas/nosec need `-- <reason>`
justifications, the Makefile/CI/secret-scan guards are pinned, and the threshold
mechanism is proven to fail closed."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TESTS_DIR = REPO / "tests"


def _pyproject() -> dict:
    with (REPO / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_coverage_threshold_configured():
    """AC1 — [tool.coverage] parsed: fail_under=85, branch=true, three sources."""
    data = _pyproject()
    run = data["tool"]["coverage"]["run"]
    report = data["tool"]["coverage"]["report"]
    assert run["branch"] is True
    assert set(run["source"]) >= {"src", "bridge", "common"}
    assert report["fail_under"] == 85


def test_coverage_enforced_for_every_runner():
    """AC2 — the threshold lives in pytest addopts so make/bare-pytest/CI all inherit."""
    addopts = _pyproject()["tool"]["pytest"]["ini_options"]["addopts"]
    assert "--cov=src" in addopts
    assert "--cov=bridge" in addopts
    assert "--cov=common" in addopts
    assert "--cov-branch" in addopts
    assert "--cov-fail-under=85" in addopts


def test_pragmas_are_justified():
    """AC3 — every no-cover pragma and every suppression marker carries a
    `-- <reason>` justification; a bare one fails. (ffmpeg-binary fallbacks are
    NOT allowlisted — mock-test them instead.)"""
    offenders: list[str] = []
    for tree in ("src", "bridge", "common", "scripts", "tests"):
        for path in (REPO / tree).rglob("*.py"):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.search(r"pragma:\s*no cover\b(?!\s*--)", line):
                    offenders.append(f"{path.relative_to(REPO)}:{lineno} bare pragma")
                if re.search(r"#\s*nosec\b(?!\s+.*--)", line):
                    offenders.append(f"{path.relative_to(REPO)}:{lineno} bare nosec")
    assert offenders == [], "\n".join(offenders)


def test_makefile_gate_order():
    """AC4 — gate order pinned: lint -> test -> security -> docs-guard."""
    gate_line = re.search(r"^gate:\s*(.+)$", _read("Makefile"), re.MULTILINE)
    assert gate_line, "gate target missing"
    parts = gate_line.group(1).split()
    assert parts == ["lint", "test", "security", "docs-guard"]


def test_ci_runs_all_four_guards():
    """AC5 — CI invokes ruff, pytest, security_gate.py, docs_guard.py (one gate
    implementation everywhere: the bandit step is gone in favor of the script)."""
    ci = _read(".github/workflows/ci.yml")
    assert "ruff check ." in ci
    assert "ruff format --check ." in ci
    assert "pytest" in ci
    assert "scripts/security_gate.py" in ci
    assert "scripts/docs_guard.py" in ci
    assert not re.search(r"bandit\s+-q\s+-r", ci), (
        "CI must call the gate script, not bandit directly"
    )


def test_threshold_fails_closed(tmp_path):
    """AC6 — pinned mechanism: a mini project with fail_under=100 and uncovered code
    makes pytest exit 1 with a coverage-failure message."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "mod.py").write_text(
        "def covered():\n    return 1\n\n\ndef uncovered():\n    return 2\n",
        encoding="utf-8",
    )
    test_file = tmp_path / "test_cov.py"
    test_file.write_text(
        "import src.mod\n\n\ndef test_it():\n    assert src.mod.covered() == 1\n", encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--cov=src",
            "--cov-branch",
            "--cov-fail-under=100",
            str(test_file),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    blob = (result.stdout + result.stderr).lower()
    assert "coverage" in blob and "100" in blob


def test_secret_scan_in_gate(tmp_path):
    """AC7 — the vendored pre-commit scanner runs inside make gate (security_gate.py
    wires secret_scan) and fails on a planted credential."""
    gate_src = _read("scripts/security_gate.py")
    assert "secret_scan" in gate_src, "security gate must run the secret scanner"
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "module.py").write_text("value = compute_total(42)\n", encoding="utf-8")
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "module.py").write_text(
        'SECRET_KEY = "Zx91Kd8wQ2pLnR7vBc4Md6sHf0jY3ePaTq5WbUzC"\n',
        encoding="utf-8",
    )
    scanner = REPO / "scripts" / "secret_scan.py"
    ok = subprocess.run(
        [sys.executable, str(scanner), str(clean)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = subprocess.run(
        [sys.executable, str(scanner), str(planted)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert bad.returncode == 1
    assert "SECRET_KEY" in bad.stdout or "secret" in bad.stdout.lower()
