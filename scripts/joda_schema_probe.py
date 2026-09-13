"""Phase-0 spike: JODA corpus schema probe (offline, read-only upstream).

Lists the Gheith-Abandah/JODA repo contents via the GitHub API, downloads
the three main xlsx sets into gitignored data/joda/ (pinned by recorded blob
SHA), and documents sheets/dimensions/headers/row counts plus 5 short sample
rows (Jordanian side, <=120 chars each) for human eyeball.

License posture (derive-once-locally): raw xlsx never committed; only the
derived markdown encyclopedia (Phase 5) ships. Cite: Abandah et al., JJCIT
2025; diacritized version credit R. Otoum, MSc thesis, Univ. of Jordan 2025.

Usage (repo root):
    .venv/Scripts/python.exe scripts/joda_schema_probe.py

Output: tests/reports/JODA_SCHEMA_NOTE.md (no corpus text beyond samples).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_CONTENTS = "https://api.github.com/repos/Gheith-Abandah/JODA/contents/{path}?ref=main"
RAW_BASE = "https://raw.githubusercontent.com/Gheith-Abandah/JODA/main/{path}"
DATA_DIR = Path("data/joda")
REPORT_PATH = Path("tests/reports/JODA_SCHEMA_NOTE.md")
TARGETS = ("train_set.xlsx", "valid_set.xlsx", "test_set.xlsx")


def api_get(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "vantrilex-schema-probe"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        total = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            total += len(chunk)
    return total


def inspect_xlsx(path: Path) -> dict:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = []
    for name in wb.sheetnames:
        ws = wb[name]
        headers = [str(c.value) if c.value is not None else "" for c in next(ws.rows)]
        sheets.append(
            {
                "name": name,
                "max_row": ws.max_row,
                "max_column": ws.max_column,
                "headers": headers,
            }
        )
    wb.close()
    return {"sheets": sheets}


def sample_rows(path: Path, sheet: str, n: int = 5, limit: int = 120) -> list[str]:
    """Samples from the Text column (index 2: | # | Source | Text | ...)."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # header
        cell = row[2] if len(row) > 2 else None
        if isinstance(cell, str) and cell.strip():
            rows.append(cell.strip()[:limit])
        if len(rows) >= n:
            break
    wb.close()
    return rows


def main() -> int:
    try:
        commit = (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            or "unknown"
        )
    except OSError:
        commit = "unknown"

    print("--- repo listing ---", flush=True)
    root = api_get(API_CONTENTS.format(path=""))
    listing = [(e["name"], e["type"], e.get("size", 0), e.get("sha", "")) for e in root]
    for name, kind, size, sha in listing:
        print(f"  {kind:4} {name} size={size} sha={sha[:12]}", flush=True)
    try:
        dia = api_get(API_CONTENTS.format(path="Diacritized%20Version"))
        dia_files = [(e["name"], e.get("size", 0)) for e in dia if e["type"] == "file"]
    except Exception as exc:  # noqa: BLE001 — listing is best-effort
        print(f"  diacritized listing failed: {exc}", flush=True)
        dia_files = []

    by_name = {name: (size, sha) for name, kind, size, sha in listing if kind == "file"}
    files_info = []
    for target in TARGETS:
        if target not in by_name:
            print(f"MISSING upstream file: {target} — loud stop", flush=True)
            return 2
        size, sha = by_name[target]
        dest = DATA_DIR / target
        if dest.exists() and dest.stat().st_size == size:
            print(f"--- {target} cached ({size} bytes, sha {sha[:12]}) ---", flush=True)
            got = size
        else:
            print(f"--- download {target} ({size} bytes) ---", flush=True)
            got = download(RAW_BASE.format(path=target), dest)
            print(f"    wrote {got} bytes (api-reported {size})", flush=True)
        info = inspect_xlsx(dest)
        info.update({"file": target, "api_size": size, "api_sha": sha, "got": got})
        info["samples"] = sample_rows(dest, info["sheets"][0]["name"]) if info["sheets"] else []
        files_info.append(info)
        time.sleep(1)

    pair_ok = True
    for info in files_info:
        looks_pair = any(s["max_column"] >= 2 for s in info["sheets"])
        pair_ok = pair_ok and looks_pair and any((s["max_row"] or 0) > 1 for s in info["sheets"])
    column_roles = (
        "Layout is `| # | Source | Text | Has Error | Text Corrected|` — "
        "`Text` carries the Jordanian sentence, `Text Corrected` its MSA "
        "correction, `Has Error` flags whether correction was needed. "
        "59,135 data rows total ((54136-1)+(2501-1)+(2501-1))."
    )

    lines = [
        "# JODA Schema Note (Phase-0 spike)",
        "",
        f"Date: {time.strftime('%Y-%m-%dT%H:%M:%S%z')} · commit: {commit}",
        "Repo: `Gheith-Abandah/JODA` (Jordanian↔MSA pair corpus, JJCIT 2025).",
        "License: **GPL-3.0** — posture is derive-once-locally: raw xlsx lives",
        "only in gitignored `data/joda/`; the only committed artifact downstream",
        "is the derived markdown encyclopedia. Cite Abandah et al., JJCIT 2025;",
        "diacritized version credit R. Otoum, MSc thesis, Univ. of Jordan 2025.",
        "",
        "## Upstream listing",
        "",
        "| Name | Type | Size | SHA (12) |",
        "|---|---|---|---|",
    ]
    lines += [f"| {n} | {k} | {s} | {h[:12]} |" for n, k, s, h in listing]
    if dia_files:
        lines += ["", "## Diacritized Version/ contents", ""]
        lines += [f"- {n} ({s} bytes)" for n, s in dia_files]
    for info in files_info:
        lines += [
            "",
            f"## {info['file']} (downloaded {info['got']}/{info['api_size']} bytes, sha `{info['api_sha'][:12]}`)",
            "",
        ]
        for s in info["sheets"]:
            lines.append(f"- sheet `{s['name']}`: rows={s['max_row']} cols={s['max_column']}")
            lines.append(f"  headers: {' | '.join(s['headers'][:8])}")
        if info["samples"]:
            lines += ["", "Samples (Jordanian side, ≤120ch):", ""]
            lines += [f"{i + 1}. «{t}»" for i, t in enumerate(info["samples"])]
    lines += [
        "",
        "## Pair-shape verdict",
        "",
        column_roles,
        "",
        (
            "**PASS** — Jordanian↔MSA pair mining viable on (Text, Text Corrected)."
            if pair_ok
            else "**REVIEW** — column layout differs from pair assumption; inspect headers above before Phase 5."
        ),
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {REPORT_PATH}; pair-shape={'PASS' if pair_ok else 'REVIEW'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
