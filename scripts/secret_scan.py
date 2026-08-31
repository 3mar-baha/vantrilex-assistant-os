"""Secret scanner — the vendored .githooks/pre-commit battery over the working tree.

Same patterns as the hook (known API key formats, credential-like assignments with
the `your-*/changeme/example/placeholder` allowlist, Bearer-in-header literals,
committed .env files). `make gate` runs this over tracked files via
scripts/security_gate.py; a finding fails the gate exactly like a bandit high.

Usage: python scripts/secret_scan.py [paths...]
       no args -> scan git-tracked files (falls back to the runtime trees)
Exit 0 clean, 1 on any finding.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "htmlcov", "node_modules"}
BINARY_HINT = re.compile(rb"\x00")

API_KEY_RE = re.compile(
    r"\bsk-ant-[A-Za-z0-9_-]{20,}"
    r"|\bsk-or-v1-[A-Za-z0-9]{16,}"
    r"|\bgh[pousr]_[A-Za-z0-9]{36,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{22,}"
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"
    r"|\bAKIA[0-9A-Z]{16}"
)
ASSIGN_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)[_a-z0-9]*[\"']?\s*[:=]\s*[\"']?"
    r"[A-Za-z0-9+/_=-]{24,}"
)
PLACEHOLDER_RE = re.compile(
    r"(?i)your[_-]|changeme|example|placeholder|\$\{|<[^>]+>|xxxx"
)
BEARER_RE = re.compile(r"(?i)\"authorization\"\s*:\s*\"bearer [A-Za-z0-9+/_=-]{24,}\"")


def _default_files() -> list[pathlib.Path]:
    tracked = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=False
    )
    if tracked.returncode == 0 and tracked.stdout.strip():
        return [pathlib.Path(line) for line in tracked.stdout.splitlines() if line.strip()]
    # no git (fresh checkout oddity) — fall back to the runtime trees
    fallback: list[pathlib.Path] = []
    for tree in ("src", "bridge", "common", "scripts"):
        base = pathlib.Path(tree)
        if base.is_dir():
            fallback.extend(p for p in base.rglob("*.py"))
    return fallback


def _iter_targets(paths: list[str]):
    if paths:
        for raw in paths:
            base = pathlib.Path(raw)
            if base.is_dir():
                for p in base.rglob("*"):
                    if p.is_file() and not SKIP_DIRS & set(p.parts):
                        yield p
            elif base.is_file():
                yield base
        return
    yield from _default_files()


def scan(paths: list[str] | None = None) -> list[str]:
    findings: list[str] = []
    for path in _iter_targets(list(paths or [])):
        if path.name == ".env" or (path.name.startswith(".env.") and path.suffix not in (".example",)):
            findings.append(f"{path}: committed .env file (secrets live outside version control)")
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        if BINARY_HINT.search(blob[:4096]):
            continue
        text = blob.decode("utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if API_KEY_RE.search(line):
                findings.append(f"{path}:{lineno}: known API key format")
            elif ASSIGN_RE.search(line) and not PLACEHOLDER_RE.search(line):
                findings.append(f"{path}:{lineno}: credential-like assignment")
            elif BEARER_RE.search(line):
                findings.append(f"{path}:{lineno}: Bearer token literal in header")
    return findings


def main(argv: list[str]) -> int:
    findings = scan(argv)
    if findings:
        print(f"Secret scan FAILED — {len(findings)} finding(s):")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("Secret Scan OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
