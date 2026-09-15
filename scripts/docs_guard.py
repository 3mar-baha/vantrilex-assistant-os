"""Docs Guard: verify the canonical documentation set is present.

Canonical = the 16-file suite (README + .env.example + CLAUDE.md + docs/01-13)
plus docs/ai/. Renames tracked in git; frozen history (VISION, HANDOFF, ...) is
deliberately NOT canonical. Run: python scripts/docs_guard.py (wired into
`make gate` and CI).
"""

from pathlib import Path

CANONICAL_FILES = [
    "README.md",
    ".env.example",
    "CLAUDE.md",
    "docs/01-PRODUCT-REQUIREMENTS.md",
    "docs/02-PRODUCT-SPECIFICATION.md",
    "docs/03-TECHNICAL-SPECIFICATION.md",
    "docs/04-ARCHITECTURE.md",
    "docs/05-DATA-MODEL.md",
    "docs/06-API-SPECIFICATION.md",
    "docs/07-IMPLEMENTATION-PLAN.md",
    "docs/08-ROADMAP.md",
    "docs/09-DECISIONS.md",
    "docs/10-CHECKPOINT.md",
    "docs/11-TESTING.md",
    "docs/12-SECURITY.md",
    "docs/13-DEPLOYMENT.md",
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
