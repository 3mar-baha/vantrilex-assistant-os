"""P1 pattern-bank miner (master transformation plan, Phase P1).

Dev-layer only: reads the LOCAL gitignored corpus (data/joda/*.xlsx) via
openpyxl read-only and emits a capped, categorized conversational pattern
bank into 04_Resources/Dialect_Encyclopedia/JODA_Pattern_Bank.md.
Raw dumps never enter git; the bank is recall-tested before admission.

Usage (repo root):
    .venv/Scripts/python.exe scripts/mine_joda_bank.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
CORPUS = [
    ROOT / "data" / "joda" / "train_set.xlsx",
    ROOT / "data" / "joda" / "valid_set.xlsx",
    ROOT / "data" / "joda" / "test_set.xlsx",
]
BANK_PATH = ROOT / "04_Resources" / "Dialect_Encyclopedia" / "JODA_Pattern_Bank.md"

FLOOR_PER_ACT = 80
CAP_PER_ACT = 80
WILDCARD_N = 100
GENERIC_CAP = 5
MIN_WORDS = 3
MAX_WORDS = 25

ACTS: dict[str, list[str]] = {
    "banter": ["ههه", "هههه", "ههههه", "نكتة", "ضحك", "مسخرة", "فرفشة", "يا زلمة"],
    "agreement": ["تمام", "أكيد", "من عيوني", "أبشر", "على راسي", "اتفقنا", "حاضر", "ابشر"],
    "deflection": ["آسف", "معلش", "يمكن", "بس ", "مش وقته", "بعدين", "خلص", "انسى"],
    "technical_empathy": ["مشكلة", "خطأ", "عطل", "صعب", "بسيطة", "ولا يهمك", "منحلها", "جرب"],
    "boundaries": ["ما بقدر", "ممنوع", "خلينا", "لازم", "ما بصير", "مستحيل", "حدود"],
}
GENERIC = {"تمام", "شو هاد", "والله", "يعني", "هيك", "هاد", "طيب", "أها"}


def _normalize(text: str) -> str:
    text = re.sub(r"[\u064b-\u0652\u0640\u200b]", "", text or "")
    return " ".join(text.split()).strip()


def _load_texts() -> list[tuple[str, str]]:
    """(source, corrected-or-raw text) pairs across the three splits."""
    out: list[tuple[str, str]] = []
    for path in CORPUS:
        if not path.exists():
            continue
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 5:
                continue
            _, source, text, _, corrected = row[:5]
            pick = corrected if corrected and str(corrected).strip() else text
            if pick and str(pick).strip():
                out.append((str(source or ""), str(pick).strip()))
        wb.close()
    return out


def _classify(text: str) -> list[str]:
    norm = _normalize(text)
    return [act for act, markers in ACTS.items() if any(m in norm for m in markers)]


def mine() -> dict[str, list[str]]:
    seen: set[str] = set()
    generic_used = 0
    bank: dict[str, list[str]] = {act: [] for act in ACTS}
    wildcards: list[tuple[float, str]] = []
    for _, text in _load_texts():
        norm = _normalize(text)
        words = norm.split()
        if not (MIN_WORDS <= len(words) <= MAX_WORDS):
            continue
        if norm in seen:
            continue
        seen.add(norm)
        acts = _classify(norm)
        if norm in GENERIC:
            if generic_used >= GENERIC_CAP:
                continue
            generic_used += 1
        if acts:
            bank[acts[0]].append(norm)  # first-act-wins: seen[] already guarantees
            # global uniqueness, so one row lands in exactly one act — deterministic
        else:
            rarity = sum(1.0 / max(1, len(w)) for w in words) / len(words)
            wildcards.append((rarity, norm))
    freq = Counter()
    for _, text in _load_texts():
        for w in _normalize(text).split():
            freq[w] += 1

    def _distinctiveness(norm: str) -> float:
        words = norm.split()
        rarity = sum(1.0 / max(1, len(w)) for w in words) / len(words)
        common = sum(freq[w] for w in words) / len(words)
        return rarity / max(1.0, common / 100.0)

    capped: dict[str, list[str]] = {}
    for act, patterns in bank.items():
        ranked = sorted(patterns, key=_distinctiveness, reverse=True)
        capped[act] = ranked[:CAP_PER_ACT]
    bank = capped
    scored = []
    for rarity, norm in wildcards:
        common = sum(freq[w] for w in norm.split()) / len(norm.split())
        scored.append((rarity / max(1.0, common / 100.0), norm))
    scored.sort(reverse=True)
    bank["wildcards"] = [norm for _, norm in scored[:WILDCARD_N]]
    return bank


def floors_met(bank: dict[str, list[str]]) -> dict[str, int]:
    return {act: len(bank.get(act, [])) for act in ACTS}


def emit(bank: dict[str, list[str]]) -> Path:
    lines = [
        "---",
        "tags: [memory]",
        "---",
        "",
        "# JODA Pattern Bank — mined conversational Ammani (P1)",
        "",
        "> Compiled from the local gitignored corpus (`data/joda/*.xlsx`) by",
        "> `scripts/mine_joda_bank.py`. Categorical floors per speech act +",
        "> rarity wildcards; generic collocations capped. Raw dumps never in git.",
        "",
    ]
    for act in list(ACTS) + ["wildcards"]:
        lines.append(f"## {act}")
        lines.append("")
        for pattern in bank.get(act, []):
            lines.append(f"- {pattern}")
        lines.append("")
    BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    BANK_PATH.write_text("\n".join(lines), encoding="utf-8")
    return BANK_PATH


def main() -> None:
    bank = mine()
    floors = floors_met(bank)
    print("FLOORS:", floors, "| wildcards:", len(bank.get("wildcards", [])))
    missing = [a for a, n in floors.items() if n < FLOOR_PER_ACT]
    if missing:
        raise SystemExit(
            f"P1 floors unmet for acts: {missing} — adjust markers, do not lower floors"
        )
    path = emit(bank)
    total = sum(len(v) for v in bank.values())
    print(f"BANK: {path} ({total} patterns)")


if __name__ == "__main__":
    main()
