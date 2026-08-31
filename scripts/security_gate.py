"""Security gate: bandit over src/ + the vendored secret scanner over tracked files.

Exit 0 when both are clean; exit 1 otherwise (shell-agnostic, wired into `make gate`).
Run: python scripts/security_gate.py
"""

import pathlib
import subprocess
import sys

import secret_scan  # scripts/ is sys.path[0] when run as a script


def main() -> int:
    if not pathlib.Path("src").is_dir():
        print("Security Gate SKIPPED — no src/ yet (activates with first implementation).")
        return 0
    bandit = subprocess.run(
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
    if bandit.returncode:
        print("Security Gate FAILED — see bandit findings above.")
        return bandit.returncode

    findings = secret_scan.scan()
    if findings:
        print(f"Security Gate FAILED — {len(findings)} secret-scan finding(s):")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("Security Gate OK (bandit + secret scan).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
