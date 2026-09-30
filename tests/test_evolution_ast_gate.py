"""P3-B: hardening the AST gate to all 5 rules (tests only — never touch src/ here).

Seam: ``src.evolution.verify_proposal_code`` / ``evaluate_proposal``.

Ground truth (read from ``src/evolution.py`` and the §3.3 table, not assumed):
two rules exist (import allow-list, forbidden calls); ambient authority and the
``importlib`` / ``pathlib`` bypasses do not. Tests are therefore split:

- PINNED (green on the current gate): existing rules, reason prefixes, the
  never-executes shape, and the ``noqa`` non-effect.
- SPECIFYING (RED on the current gate): the ambient-authority rule, the
  ``importlib`` denylist, the secret-path close, and the new reason prefixes.
- HOLE-DEMONSTRATION (xpassed pre-fix, xfailed post-fix, never red): the
  ``Path(".env").read_text()`` bypass, kept to document the hole.

Tests call ``evolution.verify_proposal_code`` through the module so a
throwaway reference implementation can be injected with ``pytest -p`` (see the
acceptance report); no test may import the reference. Reason-string contract
for the implementer: ``import not allowlisted: X``, ``forbidden call: X``,
``syntax error: …`` (existing), ``ambient authority: X`` and
``forbidden import: importlib`` (new). Multiple violations are joined with
``"; "`` so each names its rule.

Notes: ``.env`` has no name/attribute form (it is not a valid identifier), so
it is covered via string mentions only. Bare ``id`` is excluded: the §3.3
table names it but the tasking 8-token list governs, and rejecting ``id()``
would ban innocent builtins.
"""

from __future__ import annotations

import pytest

from src import evolution

ALLOWED_MODULES = [
    "re",
    "math",
    "json",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "pathlib",
]

NETWORK_IMPORTS = [
    "import socket",
    "import http.client",
    "import urllib.request",
    "import requests",
    "from requests import get",
]

FORBIDDEN_CALLS = [
    ("eval('1+1')", "eval"),
    ("exec('x = 1')", "exec"),
    ("compile('1', '', 'eval')", "compile"),
    ("__import__('os')", "__import__"),
    ("open('notes.txt')", "open"),
]

# ".env" excluded: not a valid identifier, so it has no name form.
AMBIENT_NAMES = [
    "confirmation_id",
    "_secrets",
    "getattr",
    "setattr",
    "__dict__",
    "globals",
    "locals",
]

# Full tasking list; ".env" is covered here (string form) only.
AMBIENT_STRING_TOKENS = [*AMBIENT_NAMES, ".env"]


@pytest.mark.parametrize("module", ALLOWED_MODULES)
def test_allowlisted_module_passes(module: str) -> None:
    ok, reason = evolution.verify_proposal_code(f"import {module}")
    assert ok is True
    assert reason == "ok"


def test_re_and_json_only_candidate_passes() -> None:
    ok, reason = evolution.verify_proposal_code("import re\nimport json\nx = json.dumps({'a': 1})")
    assert ok is True
    assert reason == "ok"


def test_from_import_of_allowlisted_module_passes() -> None:
    ok, reason = evolution.verify_proposal_code("from pathlib import Path")
    assert ok is True
    assert reason == "ok"


@pytest.mark.parametrize("statement", NETWORK_IMPORTS)
def test_network_import_rejected_structural(statement: str) -> None:
    ok, reason = evolution.verify_proposal_code(statement)
    assert ok is False
    assert reason.startswith("import not allowlisted: ")


@pytest.mark.parametrize(("call", "name"), FORBIDDEN_CALLS)
def test_forbidden_call_rejected(call: str, name: str) -> None:
    ok, reason = evolution.verify_proposal_code(call)
    assert ok is False
    assert reason.startswith(f"forbidden call: {name}")


@pytest.mark.parametrize("bad", ["def broken(:", "x = ("])
def test_invalid_syntax_returns_syntax_error_tuple_never_raises(bad: str) -> None:
    ok, reason = evolution.verify_proposal_code(bad)
    assert ok is False
    assert reason.startswith("syntax error: ")


@pytest.mark.parametrize("token", AMBIENT_NAMES)
def test_ambient_authority_name_use_rejected(token: str) -> None:
    ok, reason = evolution.verify_proposal_code(f"value = {token}")
    assert ok is False
    assert reason.startswith(f"ambient authority: {token}")


@pytest.mark.parametrize("token", AMBIENT_NAMES)
def test_ambient_authority_attribute_access_rejected(token: str) -> None:
    ok, reason = evolution.verify_proposal_code(f"value = holder.{token}")
    assert ok is False
    assert reason.startswith(f"ambient authority: {token}")


@pytest.mark.parametrize("token", AMBIENT_STRING_TOKENS)
def test_ambient_authority_string_mention_rejected(token: str) -> None:
    ok, reason = evolution.verify_proposal_code(f'value = "{token}"')
    assert ok is False
    assert reason.startswith(f"ambient authority: {token}")


def test_open_env_fails_on_both_rules() -> None:
    ok, reason = evolution.verify_proposal_code('open(".env")')
    assert ok is False
    assert "forbidden call: open" in reason
    assert "ambient authority: .env" in reason


def test_noqa_pragma_alone_is_not_a_reason() -> None:
    ok, reason = evolution.verify_proposal_code("import re  # noqa")
    assert (ok, reason) == (True, "ok")


def test_noqa_pragma_does_not_suppress_rejection() -> None:
    ok, reason = evolution.verify_proposal_code("eval('1+1')  # noqa")
    assert ok is False
    assert reason.startswith("forbidden call: eval")


def test_importlib_denied_with_named_reason() -> None:
    ok, reason = evolution.verify_proposal_code("import importlib")
    assert ok is False
    assert reason.startswith("forbidden import: importlib")


def test_importlib_from_import_bypass_rejected() -> None:
    code = "from importlib import import_module\nimport_module('os')"
    ok, reason = evolution.verify_proposal_code(code)
    assert ok is False
    assert "forbidden import: importlib" in reason


@pytest.mark.xfail(
    strict=False,
    reason="HOLE-DEMONSTRATION: passes the current gate; the companion test specifies the close.",
)
def test_pathlib_read_text_hole_demonstration() -> None:
    code = 'from pathlib import Path\ntext = Path(".env").read_text()'
    ok, reason = evolution.verify_proposal_code(code)
    assert ok is True and reason == "ok"


def test_pathlib_read_of_secret_path_rejected() -> None:
    code = 'from pathlib import Path\ntext = Path(".env").read_text()'
    ok, reason = evolution.verify_proposal_code(code)
    assert ok is False
    assert "ambient authority: .env" in reason


def test_gate_never_executes_top_level_raise() -> None:
    result = evolution.verify_proposal_code("raise RuntimeError('boom')")
    assert isinstance(result, tuple) and len(result) == 2
    ok, reason = result
    assert isinstance(ok, bool) and isinstance(reason, str)


def _overlay(tmp_path):  # mirrors tests/test_evolution.py: local harness, no import cycle
    import sys

    sys.path.insert(0, "tests/live_harness")
    from overlay import OverlayVault

    real = tmp_path / "real"
    real.mkdir()
    return OverlayVault(real, tmp_path / "shadow")


def test_evaluate_proposal_never_executes_candidate(tmp_path) -> None:
    overlay = _overlay(tmp_path)
    report = evolution.evaluate_proposal(
        {"chain": [["gmail", ""]], "occurrences": 3, "code": "raise RuntimeError('boom')"},
        overlay,
    )
    assert isinstance(report, evolution.PromotionReport)


@pytest.mark.parametrize(
    ("code", "prefix"),
    [
        ("import os", "import not allowlisted: "),
        ("eval('1+1')", "forbidden call: "),
        ("def broken(:", "syntax error: "),
        ("value = confirmation_id", "ambient authority: "),
        ("import importlib", "forbidden import: "),
    ],
)
def test_rejection_reasons_name_the_rule(code: str, prefix: str) -> None:
    ok, reason = evolution.verify_proposal_code(code)
    assert ok is False
    assert reason.startswith(prefix)
