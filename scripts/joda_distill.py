"""Phase-5: JODA dialect distillation (offline, derive-once-locally).

Mines the cached Gheith-Abandah/JODA pair corpus (data/joda/*.xlsx,
gitignored, GPL-3.0 raw) into a committed derived knowledge artifact:
04_Resources/Dialect_Encyclopedia/JODA_Jordanian_Patterns.md.

Deterministic (Counter sorts, no randomness), stdlib + openpyxl only, zero
network, zero LLM. Reruns are byte-identical given identical inputs.

Usage (repo root):
    .venv/Scripts/python.exe scripts/joda_distill.py

Output: 04_Resources/Dialect_Encyclopedia/JODA_Jordanian_Patterns.md
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.associative import STOPWORDS
from src.cognition import _normalize

DATA_DIR = Path("data/joda")
OUT_PATH = Path("04_Resources/Dialect_Encyclopedia/JODA_Jordanian_Patterns.md")
SETS = ("train_set.xlsx", "valid_set.xlsx", "test_set.xlsx")

TOP_BIGRAMS = 40
TOP_TRIGRAMS = 20
TOP_STARTERS = 20
TOP_MARKERS = 20
TOP_POLYSEMY_DISCOVERED = 15
MIN_COUNT = 5

# Polysemy seeds from the mandate (normalized forms; phrases matched raw).
POLYSEMY_SEEDS: tuple[str, ...] = ("شغال", "ماشي", "فضيت", "فاضي", "ع راسي", "يا دوب")

# MSA function words excluded from gloss evidence (they swamp co-occurrence
# counts without sense-distinguishing power).
MSA_STOPS: Final = frozenset(
    {
        "أن",
        "ان",
        "لا",
        "لكن",
        "لم",
        "لن",
        "ليس",
        "لست",
        "أنا",
        "انا",
        "نحن",
        "وأنا",
        "هذا",
        "هذه",
        "ذلك",
        "الذي",
        "التي",
        "الذين",
        "ما",
        "من",
        "في",
        "على",
        "علي",
        "إلى",
        "الي",
        "إن",
        "إذا",
        "اذا",
        "أي",
        "هو",
        "هي",
        "كان",
        "ثم",
        "عندما",
        "بعد",
        "قبل",
        "مع",
        "بين",
        "غير",
        "كل",
        "قد",
        "نعم",
        "بلى",
        "هكذا",
        "بل",
        "أم",
        "أو",
        "و",
        "ف",
    }
)

# Gender audit patterns (corpus-level counts grounding the encyclopedia).
FEM_FIRST = ("أنا جاهزة", "أنا بقدر", "رح أعمل", "أنا سارة", "بدي أحكي")
MASC_ADDR = ("بدك", "شو رأيك", "عمر", "شغلك", "يومك")


def load_pairs() -> tuple[list[tuple[str, str]], dict]:
    """(JO, MSA) rows from the three sets. Raises loud on schema drift."""
    import openpyxl

    pairs: list[tuple[str, str]] = []
    stats: dict = {"rows": 0, "skipped": 0, "files": {}}
    for name in SETS:
        path = DATA_DIR / name
        if not path.exists():
            raise FileNotFoundError(
                f"missing cached corpus file: {path} (run joda_schema_probe.py)"
            )
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        header = [str(c) if c is not None else "" for c in next(it)]
        if "Text" not in header or "Text Corrected" not in header:
            raise ValueError(f"{name}: unexpected columns {header}")
        jo_i, msa_i = header.index("Text"), header.index("Text Corrected")
        n = 0
        for row in it:
            jo, msa = row[jo_i] if len(row) > jo_i else "", row[msa_i] if len(row) > msa_i else ""
            if isinstance(jo, str) and jo.strip() and isinstance(msa, str) and msa.strip():
                pairs.append((jo.strip(), msa.strip()))
                n += 1
            else:
                stats["skipped"] += 1
        stats["files"][name] = n
        stats["rows"] += n
        wb.close()
    return pairs, stats


def toks(text: str, *, keep_stops: bool = False) -> list[str]:
    out = [t for t in _normalize(text).split() if t]
    if not keep_stops:
        out = [t for t in out if t not in STOPWORDS]
    return out


def top_ngrams(pairs: list[tuple[str, str]], n: int, top: int) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for jo, _ in pairs:
        t = toks(jo, keep_stops=True)
        for i in range(len(t) - n + 1):
            counts[" ".join(t[i : i + n])] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(g, c) for g, c in ranked if c >= MIN_COUNT][:top]


def starters(pairs: list[tuple[str, str]], top: int) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for jo, _ in pairs:
        t = toks(jo, keep_stops=True)
        if len(t) >= 2:
            counts[" ".join(t[:2])] += 1
        elif t:
            counts[t[0]] += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]


def initial_markers(pairs: list[tuple[str, str]], top: int) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for jo, _ in pairs:
        t = toks(jo, keep_stops=True)
        if t:
            counts[t[0]] += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]


def msa_glosses(
    pairs: list[tuple[str, str]], seed_norm: str, top: int = 8
) -> list[tuple[str, int]]:
    """Distinct MSA-side content tokens co-occurring with a JO seed phrase."""
    counts: Counter[str] = Counter()
    for jo, msa in pairs:
        if seed_norm in _normalize(jo):
            jo_toks = set(toks(jo))
            for tok in toks(msa):
                if tok not in jo_toks and tok not in MSA_STOPS:
                    counts[tok] += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]


def discover_polysemy(pairs: list[tuple[str, str]], top: int) -> list[tuple[str, int, list[str]]]:
    """JO content tokens (freq≥20, len≥3, non-stop) with the widest distinct
    MSA-gloss spread."""
    per_token: dict[str, Counter[str]] = {}
    for jo, msa in pairs:
        jo_toks = {t for t in set(toks(jo)) if t not in STOPWORDS}
        msa_toks = {t for t in set(toks(msa)) - jo_toks if t not in MSA_STOPS}
        for tok in jo_toks:
            if len(tok) >= 3:
                per_token.setdefault(tok, Counter()).update(msa_toks)
    scored = []
    for tok, counter in per_token.items():
        gloss = [g for g, c in counter.most_common() if c >= 3]
        freq = sum(counter.values())
        if len(gloss) >= 2 and freq >= 20:
            scored.append((tok, len(gloss), [g for g, _ in counter.most_common(5)]))
    scored.sort(key=lambda r: (-r[1], r[0]))
    return scored[:top]


def gender_audit(pairs: list[tuple[str, str]]) -> dict:
    fem = sum(1 for jo, _ in pairs for pat in FEM_FIRST if pat in jo)
    masc = sum(1 for jo, _ in pairs for pat in MASC_ADDR if pat in jo)
    return {"fem_first_person_hits": fem, "masc_address_hits": masc, "rows": len(pairs)}


def main() -> int:
    t0 = time.perf_counter()
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

    pairs, stats = load_pairs()
    print(f"loaded {stats['rows']} pairs ({stats['skipped']} skipped)", flush=True)

    bigrams = top_ngrams(pairs, 2, TOP_BIGRAMS)
    trigrams = top_ngrams(pairs, 3, TOP_TRIGRAMS)
    starts = starters(pairs, TOP_STARTERS)
    markers = initial_markers(pairs, TOP_MARKERS)
    seed_rows = [(s, msa_glosses(pairs, _normalize(s))) for s in POLYSEMY_SEEDS]
    discovered = discover_polysemy(pairs, TOP_POLYSEMY_DISCOVERED)
    gender = gender_audit(pairs)

    lines = [
        "# JODA Jordanian Patterns — distilled dialect encyclopedia (Phase-5)",
        "",
        f"Date: {time.strftime('%Y-%m-%dT%H:%M:%S%z')} · commit: {commit}",
        (
            f"Corpus: Gheith-Abandah/JODA train+valid+test = **{stats['rows']}** pairs "
            f"({', '.join(f'{k}:{v}' for k, v in stats['files'].items())}; {stats['skipped']} skipped)."
        ),
        "Method: deterministic stdlib mining (Counter sorts, no randomness, no LLM).",
        "License: raw corpus GPL-3.0, gitignored under `data/joda/` — this file is",
        "derived original expression. Cite Abandah et al., JJCIT 2025; diacritized",
        "credit R. Otoum, MSc thesis, Univ. of Jordan 2025.",
        "Tiers: VERIFIED (count≥threshold) vs SINGLETON (below threshold, excluded).",
        "",
        "## 1. High-frequency collocations",
        "",
        "### Bigrams (min count 5)",
        "",
        "| Collocation | Count |",
        "|---|---|",
    ]
    lines += [f"| {g} | {c} |" for g, c in bigrams]
    lines += ["", "### Trigrams (min count 5)", "", "| Collocation | Count |", "|---|---|"]
    lines += [f"| {g} | {c} |" for g, c in trigrams]
    lines += [
        "",
        "## 2. Sentence starters (first-2-token patterns)",
        "",
        "| Starter | Count |",
        "|---|---|",
    ]
    lines += [f"| {g} | {c} |" for g, c in starts]
    lines += [
        "",
        "## 3. Colloquial discourse markers (position-initial)",
        "",
        "| Marker | Count |",
        "|---|---|",
    ]
    lines += [f"| {g} | {c} |" for g, c in markers]
    lines += ["", "## 4. Polysemy matrix (JO form → distinct MSA glosses)", ""]
    lines += ["### Mandate seeds", ""]
    for seed, glosses in seed_rows:
        gloss_str = (
            ", ".join(f"{g}({c})" for g, c in glosses) or "— (no divergent glosses attested)"
        )
        lines.append(f"- **{seed}** → {gloss_str}")
    lines += ["", "### Discovered candidates (freq≥20, ≥2 glosses @count≥3)", ""]
    lines += ["| JO token | #glosses | top MSA glosses |", "|---|---|---|"]
    lines += [f"| {t} | {n} | {', '.join(g)} |" for t, n, g in discovered] or ["| — | — | — |"]
    lines += [
        "",
        "## 5. Gender markers (corpus audit grounding persona exemplar tests)",
        "",
        (
            f"- Feminine first-person attestations: **{gender['fem_first_person_hits']}** "
            f"(`{'` `'.join(FEM_FIRST)}`)"
        ),
        (
            f"- Masculine address attestations: **{gender['masc_address_hits']}** "
            f"(`{'` `'.join(MASC_ADDR)}`)"
        ),
        "- Persona rule (enforced by unit test, not by corpus majority): Sara speaks",
        "  feminine first-person (أنا جاهزة/رح أعمل); Omar is addressed masculine",
        "  (بدك/عمر) — second-person-feminine forms are rejected in exemplar lines.",
        "",
        f"_Mined in {time.perf_counter() - t0:.1f}s; content deterministic given identical inputs (header date excluded)._",
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
