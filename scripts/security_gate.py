"""Security gate: run bandit over src/ when it exists (shell-agnostic).

Exit 0 when no high/critical issues (or no src/ yet); exit 1 otherwise.
Run: python scripts/security_gate.py  (wired into `make gate`)
"""

import pathlib
import subprocess
import sys


def main() -> int:
    if not pathlib.Path("src").is_dir():
        print(
            "Security Gate SKIPPED — no src/ yet (activates with first implementation)."
        )
        return 0
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "bandit",
            "-q",
            "-lll",
            "-ii",  # fail only on high-confidence high/critical issues
            "-r",
            "src/",
        ],
        check=False,
    )
    if result.returncode:
        print("Security Gate FAILED — see bandit findings above.")
    else:
        print("Security Gate OK.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
