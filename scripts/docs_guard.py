"""Docs Guard: verify the canonical documentation set is present.

Exit 0 when all canonical files exist; exit 1 listing what is missing.
Run: python scripts/docs_guard.py  (wired into `make gate` and CI)
"""

from pathlib import Path

CANONICAL_FILES = [
    "CLAUDE.md",
    "README.md",
    ".gitignore",
    ".env.example",
    "LICENSE",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "Makefile",
    ".github/workflows/ci.yml",
    "docs/00-VISION.md",
    "docs/01-ARCHITECTURE.md",
    "docs/02-BACKLOG.md",
    "docs/03-DECISIONS.md",
    "docs/04-RUNBOOK.md",
    "docs/05-TEST-PLAN.md",
]


def missing_files(root: Path | None = None) -> list[str]:
    root = root if root is not None else Path(__file__).resolve().parent.parent
    return [f for f in CANONICAL_FILES if not (root / f).is_file()]


if __name__ == "__main__":
    missing = missing_files()
    if missing:
        print("Docs Guard FAILED — missing canonical files:")
        for f in missing:
            print(f"  - {f}")
        raise SystemExit(1)
    print(f"Docs Guard OK — {len(CANONICAL_FILES)} canonical files present.")
