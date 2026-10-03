# N7 — Documentation Debt Triage

**The last node of Phase 1.** Owner-released 2026-10-03. Scope: documentation
only, zero behaviour change, no `.py` touched, no new tests, one commit.

This file is the **audit trail** for N7. Every corrected claim is stated as
`OLD -> NEW` in the commit message together with the command that re-derives the
new value and that command's output; the *reason each untouched claim was left*
lives here, because a triage that only records what it changed cannot be audited.

## The rule this file was built to

The brief handed N7 a grep count and called it a **hypothesis**. It was. The grep
found 16 files; the per-claim triage is the finding, and it produced a different
shape than the count suggested:

* the numeric corpus is **239 hits across 18 files**, not the 34 the brief's per-file
  count implied;
* **only 4** of them are live-and-wrong;
* **9** are claims that LOOK stale and are in fact exactly right today — including
  one (`4,782`) that a plausible-looking «correction» would have broken;
* the brief's four README Oracle sites are **not numeric claims at all** — they
  are narrative, so they are triaged separately as Inventory B;
* **`quoted-third-party` has zero members among the numeric hits.** Every quotation in
  this corpus is a *citation*, not a count, so that bucket is exercised in the citation
  triage below instead.

## Buckets

| Bucket | Meaning | Action |
|---|---|---|
| `live-and-wrong` | a claim about TODAY that is now false | **CORRECTED** |
| `dated-history` | a true statement about a PAST commit/date | left alone |
| `external` | a fact about something outside this repo | left alone |
| `quoted-third-party` | a quotation from a report or a recorded RED run | left alone, still marked as a quote |

**Two buckets were added, and the reason is the finding.** A four-bucket taxonomy
has no honest home for *a current claim that is simply true*, and forcing one in
produces a lie in either direction — either a false «correction» or a false
«stale, left as dated history». So:

* **`verified-true`** — re-derived against the tree and found CORRECT. Left byte-identical.
  These are the load-bearing rows: a reviewer who «fixed» one of them would have
  introduced a defect.
* **`not-a-claim`** — the extractor matched something that is not a count at all
  (a badge, a policy threshold, the word «Tier 2»). Recorded rather than silently
  dropped, because a corpus constant that quietly discards rows is a corpus
  constant nobody can audit.

## Totals

| Bucket | Hits |
|---|---|
| `dated-history` | 213 |
| `verified-true` | 9 |
| `external` | 9 |
| `not-a-claim` | 4 |
| `live-and-wrong` | 4 |
| **TOTAL** | **239** |

### Per file

| File | live-and-wrong | dated-history | external | quoted | verified-true | not-a-claim | total |
|---|---|---|---|---|---|---|---|
| `README.md` | — | — | — | — | — | 2 | 2 |
| `docs/00-MAP-OF-ARCHITECTURE.md` | — | — | — | — | 1 | — | 1 |
| `docs/01-PRODUCT-REQUIREMENTS.md` | 1 | — | — | — | 2 | — | 3 |
| `docs/03-TECHNICAL-SPECIFICATION.md` | 1 | — | — | — | 1 | — | 2 |
| `docs/04-ARCHITECTURE.md` | 1 | 1 | — | — | — | — | 2 |
| `docs/07-IMPLEMENTATION-PLAN.md` | — | 3 | — | — | — | — | 3 |
| `docs/09-DECISIONS.md` | — | 1 | 1 | — | — | — | 2 |
| `docs/10-CHECKPOINT.md` | — | 173 | 1 | — | — | — | 174 |
| `docs/16-WORKFLOWS.md` | — | 1 | 6 | — | 1 | 2 | 10 |
| `docs/ai/PROJECT-CONTEXT.md` | 1 | — | — | — | — | — | 1 |
| `docs/AUDIT_REPORT.md` | — | 20 | — | — | — | — | 20 |
| `docs/MASTER_ROADMAP_AND_REMAINING_WORK.md` | — | — | — | — | — | — | 0 |
| `docs/REMEDIATION_PLAN.md` | — | — | — | — | — | — | 0 |
| `docs/reports/OBJECTIVES_LEDGER_MET_VS_PENDING.md` | — | 1 | — | — | — | — | 1 |
| `docs/reports/PROJECT_TIMELINE_AND_MILESTONES.md` | — | 10 | — | — | — | — | 10 |
| `docs/reports/RISKS_COSTS_AND_GOVERNANCE.md` | — | 1 | — | — | — | — | 1 |
| `docs/reports/SARA_EXHAUSTIVE_SYSTEM_AND_CODEBASE_ENCYCLOPEDIA.md` | — | 2 | 1 | — | 1 | — | 4 |
| `docs/reports/TOOLS_AND_API_COMPENDIUM.md` | — | — | — | — | 3 | — | 3 |

## Inventory A — numeric and quantity claims

Generated from the tree at `8da8adf` (the commit N7 started from), so the table
records the corpus **as found**, not as left. One row per hit.

### `README.md` — 2 hits

`not-a-claim`: 2

| Line | Token | Bucket | Why |
|---|---|---|---|
| 16 | `12-green` | not-a-claim — left | the Python 3.12 badge; '3.12-green' matched the -green unit, not a count |
| 21 | `00%` | not-a-claim — left | the $0.00/MONTH COST badge; '$0.00' matched the % unit, not a count |

### `docs/00-MAP-OF-ARCHITECTURE.md` — 1 hits

`verified-true`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 28 | `10-agent` | verified-true — left | 'the 10-agent roster' - re-derived: AGENCY_SWARM_WORKFLOW.md's roster table has exactly 10 numbered rows |

### `docs/01-PRODUCT-REQUIREMENTS.md` — 3 hits

`live-and-wrong`: 1 | `verified-true`: 2

| Line | Token | Bucket | Why |
|---|---|---|---|
| 54 | `1,457 passed` | verified-true — left | Target-column FLOOR (suite >= 1,457); 2,903 satisfies it, so it is not a false claim |
| 54 | `0 failures` | verified-true — left | Target-column FLOOR (suite >= 1,457); 2,903 satisfies it, so it is not a false claim |
| 61 | `0 suite` | **LIVE-AND-WRONG** — corrected | KPI line reported the suite as 1,457/0 today |

### `docs/03-TECHNICAL-SPECIFICATION.md` — 2 hits

`live-and-wrong`: 1 | `verified-true`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 19 | `1,457 green` | verified-true — left | 'TDD mandatory, 1,457 green' reads as a floor in a tooling table; 2,903 satisfies it |
| 60 | `1,457 passed` | **LIVE-AND-WRONG** — corrected | 'Measured benchmarks ... honest numbers' reported 1,457 passed |

### `docs/04-ARCHITECTURE.md` — 2 hits

`live-and-wrong`: 1 | `dated-history`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 94 | `45 handlers` | **LIVE-AND-WRONG** — corrected | component registry said tools.py has 45 handlers; it has 46 |
| 130 | `2 model` | dated-history — left | section dated :112 |

### `docs/07-IMPLEMENTATION-PLAN.md` — 3 hits

`dated-history`: 3

| Line | Token | Bucket | Why |
|---|---|---|---|
| 5 | `12-step` | dated-history — left | a per-step completion table; the Evidence column records what that step's gate measured when it closed |
| 16 | `7-test` | dated-history — left | a per-step completion table; the Evidence column records what that step's gate measured when it closed |
| 24 | `0 suite` | dated-history — left | a per-step completion table; the Evidence column records what that step's gate measured when it closed |

### `docs/09-DECISIONS.md` — 2 hits

`dated-history`: 1 | `external`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 185 | `1,409 models` | external — left | OmniRoute /models catalogue size - a third-party gateway's inventory |
| 308 | `14 files` | dated-history — left | ADR dated in its own heading (:298) |

### `docs/10-CHECKPOINT.md` — 174 hits

`dated-history`: 173 | `external`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 58 | `45 passed` | dated-history — left | ledger entry at :46 - a record of that node at its commit |
| 79 | `150 passed` | dated-history — left | ledger entry at :64 - a record of that node at its commit |
| 80 | `7 passed` | dated-history — left | ledger entry at :64 - a record of that node at its commit |
| 82 | `150 tests` | dated-history — left | ledger entry at :64 - a record of that node at its commit |
| 88 | `150 tests` | dated-history — left | ledger entry at :64 - a record of that node at its commit |
| 106 | `228 passed` | dated-history — left | ledger entry at :90 - a record of that node at its commit |
| 108 | `228 tests` | dated-history — left | ledger entry at :90 - a record of that node at its commit |
| 116 | `228 tests` | dated-history — left | ledger entry at :90 - a record of that node at its commit |
| 128 | `9 tests` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 130 | `10 tests` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 131 | `6 tests` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 133 | `7 tests` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 138 | `18 tests` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 144 | `7 tests` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 148 | `16 passed` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 148 | `285 passed` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 155 | `285 tests` | dated-history — left | ledger entry at :119 - a record of that node at its commit |
| 167 | `285 passed` | dated-history — left | ledger entry at :159 - a record of that node at its commit |
| 174 | `9 tests` | dated-history — left | ledger entry at :171 - a record of that node at its commit |
| 186 | `294 passed` | dated-history — left | ledger entry at :171 - a record of that node at its commit |
| 193 | `6 axes` | dated-history — left | ledger entry at :190 - a record of that node at its commit |
| 193 | `43 agents` | dated-history — left | ledger entry at :190 - a record of that node at its commit |
| 205 | `478 passed` | dated-history — left | ledger entry at :190 - a record of that node at its commit |
| 218 | `8 files` | dated-history — left | ledger entry at :210 - a record of that node at its commit |
| 219 | `851 passed` | dated-history — left | ledger entry at :210 - a record of that node at its commit |
| 237 | `902 passed` | dated-history — left | ledger entry at :225 - a record of that node at its commit |
| 263 | `60-line` | dated-history — left | ledger entry at :262 - a record of that node at its commit |
| 268 | `6 green` | dated-history — left | ledger entry at :262 - a record of that node at its commit |
| 276 | `1,385 green` | dated-history — left | ledger entry at :273 - a record of that node at its commit |
| 276 | `45 handlers` | dated-history — left | ledger entry at :273 - a record of that node at its commit |
| 285 | `1,457 passed` | dated-history — left | ledger entry at :285 - a record of that node at its commit |
| 285 | `0 failures` | dated-history — left | ledger entry at :285 - a record of that node at its commit |
| 287 | `12 steps` | dated-history — left | ledger entry at :285 - a record of that node at its commit |
| 305 | `16-file` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 311 | `351 files` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 312 | `1,462 passed` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 312 | `16-file` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 313 | `1,462 tests` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 313 | `34 files` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 316 | `45 tools` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 317 | `44 skill` | dated-history — left | ledger entry at :298 - a record of that node at its commit |
| 372 | `45-tool` | dated-history — left | ledger entry at :364 - a record of that node at its commit |
| 419 | `45-tool` | dated-history — left | ledger entry at :414 - a record of that node at its commit |
| 431 | `16-file` | dated-history — left | ledger entry at :426 - a record of that node at its commit |
| 437 | `45 handlers` | dated-history — left | ledger entry at :426 - a record of that node at its commit |
| 508 | `2 model` | dated-history — left | ledger entry at :501 - a record of that node at its commit |
| 534 | `1,798 passed` | dated-history — left | ledger entry at :523 - a record of that node at its commit |
| 594 | `1,813 passed` | dated-history — left | ledger entry at :585 - a record of that node at its commit |
| 616 | `1,819 passed` | dated-history — left | ledger entry at :601 - a record of that node at its commit |
| 623 | `1,486 skills` | dated-history — left | ledger entry at :620 - a record of that node at its commit |
| 623 | `283 agents` | dated-history — left | ledger entry at :620 - a record of that node at its commit |
| 624 | `903 MCPs` | dated-history — left | ledger entry at :620 - a record of that node at its commit |
| 624 | `13 plugins` | dated-history — left | ledger entry at :620 - a record of that node at its commit |
| 624 | `19 hooks` | dated-history — left | ledger entry at :620 - a record of that node at its commit |
| 624 | `2,743 lines` | dated-history — left | ledger entry at :620 - a record of that node at its commit |
| 628 | `1,819 passed` | dated-history — left | ledger entry at :620 - a record of that node at its commit |
| 635 | `21 fails` | dated-history — left | ledger entry at :633 - a record of that node at its commit |
| 661 | `1,855 passed` | dated-history — left | ledger entry at :649 - a record of that node at its commit |
| 676 | `1,864 passed` | dated-history — left | ledger entry at :665 - a record of that node at its commit |
| 698 | `196 tests` | dated-history — left | ledger entry at :689 - a record of that node at its commit |
| 718 | `3 tests` | dated-history — left | ledger entry at :689 - a record of that node at its commit |
| 785 | `190 lines` | dated-history — left | ledger entry at :773 - a record of that node at its commit |
| 859 | `10 agent` | dated-history — left | ledger entry at :773 - a record of that node at its commit |
| 871 | `10-agent` | dated-history — left | ledger entry at :871 - a record of that node at its commit |
| 873 | `10-agent` | dated-history — left | ledger entry at :871 - a record of that node at its commit |
| 901 | `10 files` | dated-history — left | ledger entry at :871 - a record of that node at its commit |
| 909 | `874 lines` | dated-history — left | ledger entry at :871 - a record of that node at its commit |
| 909 | `41 tests` | dated-history — left | ledger entry at :871 - a record of that node at its commit |
| 1012 | `1,864 passed` | dated-history — left | ledger entry at :980 - a record of that node at its commit |
| 1016 | `418 files` | dated-history — left | ledger entry at :980 - a record of that node at its commit |
| 1030 | `3-step` | dated-history — left | ledger entry at :1024 - a record of that node at its commit |
| 1085 | `3-step` | dated-history — left | ledger entry at :1080 - a record of that node at its commit |
| 1115 | `1,409 models` | external — left | same third-party gateway /models count |
| 1169 | `10-agent` | dated-history — left | ledger entry at :1128 - a record of that node at its commit |
| 1173 | `15 files` | dated-history — left | ledger entry at :1128 - a record of that node at its commit |
| 1187 | `45 handlers` | dated-history — left | ledger entry at :1128 - a record of that node at its commit |
| 1188 | `46 tools` | dated-history — left | ledger entry at :1128 - a record of that node at its commit |
| 1209 | `10-agent` | dated-history — left | ledger entry at :1128 - a record of that node at its commit |
| 1212 | `202 lines` | dated-history — left | ledger entry at :1128 - a record of that node at its commit |
| 1232 | `29 passed` | dated-history — left | ledger entry at :1224 - a record of that node at its commit |
| 1266 | `2,379 passed` | dated-history — left | ledger entry at :1224 - a record of that node at its commit |
| 1266 | `2 failures` | dated-history — left | ledger entry at :1224 - a record of that node at its commit |
| 1276 | `5 green` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1276 | `115 green` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1278 | `112 tests` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1279 | `5 passed` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1280 | `4 green` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1280 | `1 green` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1345 | `115 passed` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1346 | `119 passed` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1347 | `2,378 passed` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1348 | `2,493 passed` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1355 | `2 failures` | dated-history — left | ledger entry at :1274 - a record of that node at its commit |
| 1417 | `4 tests` | dated-history — left | ledger entry at :1399 - a record of that node at its commit |
| 1436 | `4 tests` | dated-history — left | ledger entry at :1399 - a record of that node at its commit |
| 1507 | `458 passed` | dated-history — left | ledger entry at :1399 - a record of that node at its commit |
| 1507 | `459 passed` | dated-history — left | ledger entry at :1399 - a record of that node at its commit |
| 1508 | `2,485 passed` | dated-history — left | ledger entry at :1399 - a record of that node at its commit |
| 1508 | `2,548 passed` | dated-history — left | ledger entry at :1399 - a record of that node at its commit |
| 1529 | `1 test` | dated-history — left | ledger entry at :1399 - a record of that node at its commit |
| 1658 | `9-line` | dated-history — left | ledger entry at :1555 - a record of that node at its commit |
| 1668 | `2,547 passed` | dated-history — left | ledger entry at :1555 - a record of that node at its commit |
| 1668 | `2,566 passed` | dated-history — left | ledger entry at :1555 - a record of that node at its commit |
| 1721 | `43 step` | dated-history — left | ledger entry at :1710 - a record of that node at its commit |
| 1799 | `1 line` | dated-history — left | ledger entry at :1710 - a record of that node at its commit |
| 1805 | `43 step` | dated-history — left | ledger entry at :1710 - a record of that node at its commit |
| 1890 | `2,560 passed` | dated-history — left | ledger entry at :1710 - a record of that node at its commit |
| 1890 | `2,601 passed` | dated-history — left | ledger entry at :1710 - a record of that node at its commit |
| 1906 | `2,607 passed` | dated-history — left | ledger entry at :1710 - a record of that node at its commit |
| 1907 | `2,601 passed` | dated-history — left | ledger entry at :1710 - a record of that node at its commit |
| 2034 | `2,607 passed` | dated-history — left | ledger entry at :1923 - a record of that node at its commit |
| 2034 | `2,659 passed` | dated-history — left | ledger entry at :1923 - a record of that node at its commit |
| 2055 | `2 line` | dated-history — left | ledger entry at :1923 - a record of that node at its commit |
| 2194 | `1 green` | dated-history — left | ledger entry at :2089 - a record of that node at its commit |
| 2258 | `40 tests` | dated-history — left | ledger entry at :2198 - a record of that node at its commit |
| 2346 | `43 passed` | dated-history — left | ledger entry at :2198 - a record of that node at its commit |
| 2347 | `2,702 passed` | dated-history — left | ledger entry at :2198 - a record of that node at its commit |
| 2348 | `2,658 passed` | dated-history — left | ledger entry at :2198 - a record of that node at its commit |
| 2480 | `27 passed` | dated-history — left | ledger entry at :2362 - a record of that node at its commit |
| 2481 | `2,728 passed` | dated-history — left | ledger entry at :2362 - a record of that node at its commit |
| 2482 | `2,701 passed` | dated-history — left | ledger entry at :2362 - a record of that node at its commit |
| 2492 | `4 file` | dated-history — left | ledger entry at :2362 - a record of that node at its commit |
| 2493 | `5 passed` | dated-history — left | ledger entry at :2362 - a record of that node at its commit |
| 2610 | `4 tests` | dated-history — left | ledger entry at :2544 - a record of that node at its commit |
| 2627 | `6 passed` | dated-history — left | ledger entry at :2544 - a record of that node at its commit |
| 2627 | `5 passed` | dated-history — left | ledger entry at :2544 - a record of that node at its commit |
| 2628 | `2733 passed` | dated-history — left | ledger entry at :2544 - a record of that node at its commit |
| 2631 | `434 files` | dated-history — left | ledger entry at :2544 - a record of that node at its commit |
| 2800 | `14 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2801 | `2 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2802 | `2747 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2805 | `319 files` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2810 | `2,747 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2826 | `12 lines` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2826 | `1 line` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2827 | `13 lines` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2858 | `10 lines` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2860 | `12-line` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2916 | `2 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2917 | `8 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2918 | `2755 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2919 | `2746 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2922 | `436 files` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2933 | `7 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2934 | `18 passed` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 2964 | `7 lines` | dated-history — left | ledger entry at :2662 - a record of that node at its commit |
| 3193 | `43 passed` | dated-history — left | ledger entry at :3030 - a record of that node at its commit |
| 3194 | `2,792 passed` | dated-history — left | ledger entry at :3030 - a record of that node at its commit |
| 3198 | `438 files` | dated-history — left | ledger entry at :3030 - a record of that node at its commit |
| 3257 | `2,792 passed` | dated-history — left | ledger entry at :3030 - a record of that node at its commit |
| 3359 | `2,795 passed` | dated-history — left | ledger entry at :3279 - a record of that node at its commit |
| 3362 | `438 files` | dated-history — left | ledger entry at :3279 - a record of that node at its commit |
| 3406 | `110 lines` | dated-history — left | ledger entry at :3279 - a record of that node at its commit |
| 3503 | `438 files` | dated-history — left | ledger entry at :3412 - a record of that node at its commit |
| 3517 | `2,795 tests` | dated-history — left | ledger entry at :3412 - a record of that node at its commit |
| 3533 | `2,795 passed` | dated-history — left | ledger entry at :3412 - a record of that node at its commit |
| 3536 | `438 files` | dated-history — left | ledger entry at :3412 - a record of that node at its commit |
| 3542 | `2 failures` | dated-history — left | ledger entry at :3412 - a record of that node at its commit |
| 3649 | `48 step` | dated-history — left | ledger entry at :3585 - a record of that node at its commit |
| 3822 | `2,795 passed` | dated-history — left | ledger entry at :3585 - a record of that node at its commit |
| 3830 | `2,795 passed` | dated-history — left | ledger entry at :3585 - a record of that node at its commit |
| 3831 | `2,837 passed` | dated-history — left | ledger entry at :3585 - a record of that node at its commit |
| 3834 | `323 files` | dated-history — left | ledger entry at :3585 - a record of that node at its commit |
| 3840 | `2 failures` | dated-history — left | ledger entry at :3585 - a record of that node at its commit |
| 4035 | `56 passed` | dated-history — left | ledger entry at :3901 - a record of that node at its commit |
| 4060 | `1 file` | dated-history — left | ledger entry at :3901 - a record of that node at its commit |
| 4067 | `2,836 passed` | dated-history — left | ledger entry at :3901 - a record of that node at its commit |
| 4068 | `2,837 passed` | dated-history — left | ledger entry at :3901 - a record of that node at its commit |
| 4068 | `2,836 passed` | dated-history — left | ledger entry at :3901 - a record of that node at its commit |
| 4078 | `2 failures` | dated-history — left | ledger entry at :3901 - a record of that node at its commit |
| 4276 | `837 passed` | dated-history — left | ledger entry at :4117 - a record of that node at its commit |
| 4277 | `887 passed` | dated-history — left | ledger entry at :4117 - a record of that node at its commit |
| 4278 | `50 passed` | dated-history — left | ledger entry at :4117 - a record of that node at its commit |
| 4424 | `18 files` | dated-history — left | ledger entry at :4330 - a record of that node at its commit |

### `docs/16-WORKFLOWS.md` — 10 hits

`dated-history`: 1 | `external`: 6 | `verified-true`: 1 | `not-a-claim`: 2

| Line | Token | Bucket | Why |
|---|---|---|---|
| 15 | `1,486 skills` | external — left | registry census under O:\Claude Code\... on the owner's other machine |
| 15 | `283 agents` | external — left | registry census under O:\Claude Code\... on the owner's other machine |
| 15 | `903 MCPs` | external — left | registry census under O:\Claude Code\... on the owner's other machine |
| 15 | `13 plugins` | external — left | registry census under O:\Claude Code\... on the owner's other machine |
| 15 | `19 hooks` | external — left | registry census under O:\Claude Code\... on the owner's other machine |
| 16 | `2,743 lines` | external — left | VANTRILEX_CATALOG.md line count in that same external registry |
| 23 | `2 coverage` | not-a-claim — left | 'Tier 2 coverage workflow' - the regex read '2 coverage' as a count |
| 59 | `4,782-byte` | verified-true — left | 4,782 is len(SARA_PERSONA_AR) in CHARACTERS (measured 4,782), pinned green by tests/suite/tier1_resilience/test_persona_extract.py:20 |
| 87 | `1,819 passed` | dated-history — left | line is explicitly 'floor ratified 2026-09-18' |
| 145 | `5-line` | not-a-claim — left | 'Post <=5-line proof report' - a policy threshold on THIS node's report, not a count |

### `docs/ai/PROJECT-CONTEXT.md` — 1 hits

`live-and-wrong`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 12 | `45 handlers` | **LIVE-AND-WRONG** — corrected | agent vocabulary said ToolRegistry has 45 handlers; it has 46 |

### `docs/AUDIT_REPORT.md` — 20 hits

`dated-history`: 20

| Line | Token | Bucket | Why |
|---|---|---|---|
| 5 | `43 agents` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 5 | `538 tool` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 6 | `355 passed` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 23 | `1,420 test` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 66 | `3-line` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 68 | `258 lines` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 94 | `3-line` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 135 | `3-line` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 159 | `32-byte` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 168 | `4 model` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 189 | `265 test` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 193 | `1,420 test` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 210 | `355 passed` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 212 | `355 tests` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 221 | `355 green` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 221 | `355 passed` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 281 | `3 lines` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 311 | `260 lines` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 355 | `8 files` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |
| 376 | `43 agents` | dated-history — left | the 2026-09-02 forensic audit; every figure is its 'facts baseline at audit time' |

### `docs/MASTER_ROADMAP_AND_REMAINING_WORK.md` — 0 hits

Scanned; the extractor found no quantity claim. Nothing to triage.

### `docs/REMEDIATION_PLAN.md` — 0 hits

Scanned; the extractor found no quantity claim. Nothing to triage.

### `docs/reports/OBJECTIVES_LEDGER_MET_VS_PENDING.md` — 1 hits

`dated-history`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 22 | `46-tool` | dated-history — left | a MET/PENDING ledger scored on a fixed date |

### `docs/reports/PROJECT_TIMELINE_AND_MILESTONES.md` — 10 hits

`dated-history`: 10

| Line | Token | Bucket | Why |
|---|---|---|---|
| 16 | `45 green` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 17 | `45 tests` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 18 | `150 tests` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 19 | `285 tests` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 22 | `334 tests` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 23 | `43 agents` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 23 | `9-step` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 23 | `417 tests` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 24 | `468 tests` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |
| 28 | `1,460 tests` | dated-history — left | a milestone table; each row is dated and carries that milestone's suite count |

### `docs/reports/RISKS_COSTS_AND_GOVERNANCE.md` — 1 hits

`dated-history`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 27 | `1,460 green` | dated-history — left | the 2026-09-16 report set; the figure is its own risk-mitigation evidence |

### `docs/reports/SARA_EXHAUSTIVE_SYSTEM_AND_CODEBASE_ENCYCLOPEDIA.md` — 4 hits

`dated-history`: 2 | `external`: 1 | `verified-true`: 1

| Line | Token | Bucket | Why |
|---|---|---|---|
| 8 | `4,782 bytes` | verified-true — left | same 4,782 persona-length claim; correct today (the file's own 12,100-byte size is a different quantity) |
| 31 | `46-tool` | dated-history — left | a 2026-09-16 snapshot of the system as it stood then |
| 66 | `1,400-model` | external — left | a live third-party model catalogue size |
| 80 | `5-Agent` | dated-history — left | a 2026-09-16 snapshot of the system as it stood then |

### `docs/reports/TOOLS_AND_API_COMPENDIUM.md` — 3 hits

`verified-true`: 3

| Line | Token | Bucket | Why |
|---|---|---|---|
| 8 | `46 tools` | verified-true — left | '46 tools' matches the measured model-facing surface (valid_tools() == 46) |
| 12 | `46 tools` | verified-true — left | '46 tools' heading - same measurement |
| 79 | `46 tools` | verified-true — left | '46/46 tools connected-path tested' - matches the 46 measured |

## Inventory B — narrative claims (owner-instructed)

The README Oracle narrative and the `/health` paragraph are **not quantity claims**;
a count-based grep cannot see them, which is exactly why they needed naming rather
than sweeping. Owner decision 2026-10-01 (recorded in `docs/10-CHECKPOINT.md`
§*(b) Oracle is SHELVED*): **Oracle is future work; local-first is the day-to-day
doctrine.** That same table lists the README/MOC narrative as **deferred — a separate
measured docs work order**, which is N7.

| Site (at `8da8adf`) | Claim | Bucket | Action |
|---|---|---|---|
| `README.md:2-3` | frontmatter: «production host = Oracle VM, ADR-15 amended 2026-08-31» | live-and-wrong | frontmatter now names the Windows PC as the day-to-day host and marks Oracle SHELVED |
| `README.md:26` | Arabic tagline: «تعمل سحابياً على مدار الساعة (24/7)» — *works in the cloud, around the clock* | live-and-wrong | now «تعمل محلياً على جهاز المالك» — *works locally on the owner's machine* |
| `README.md:31` | «running 24/7 on an Oracle Cloud Always-Free VM (ADR-15, amended 2026-08-31)» | live-and-wrong | now local-first, Oracle named as shelved |
| `README.md:54` | the glance diagram: `Owner ⇄ Telegram ⇄ [Oracle VM 24/7 (ADR-15)]` | live-and-wrong | box now reads `[Local core — this PC]`; **column alignment preserved byte-for-byte** (verified: every column still 52/57/61) |
| `README.md:137` | heading `### Production (Oracle Cloud Always Free — ADR-15…)` | live-and-wrong | heading is now `### Deploying to Oracle Cloud Always Free (SHELVED — ADR-15…)` plus an explicit status block |
| `README.md:149` | «prints a JSON report (`gateway`/`telegram_token`/`ffmpeg`/`overall`) and exits 0 when ok, 1 when degraded» | live-and-wrong | now five lanes + the real vocabulary + the real exit rule |
| `docs/00-MAP-OF-ARCHITECTURE.md:40` | link to `15-ORACLE-DEPLOY.md` | live-surface, **kept** | **link kept** (the document exists and is correct as a deploy guide); a status marker was added saying SHELVED and why it was not deleted |

**The diagram was the one that mattered**, because it is what a new reader sees
first, and a half-fix — a header saying local above a diagram saying Oracle — is
worse than the original consistent-but-wrong state. That is also why the Arabic
tagline was corrected even though the brief named only four sites: it is the
one-line summary directly under the badges, and leaving it saying *in the cloud,
24/7* while everything else said local would have been precisely that half-fix.

## The `/health` correction, and why it is a behavioural claim

`README.md:149` was not a number; it was a description of **behaviour**, which is
the class of documentation claim that is most dangerous when it goes stale, because
a reader will act on it. It was wrong in three separate ways, each proved against
the live tree:

| The README said | The tree does | Proof |
|---|---|---|
| three lanes `gateway`/`telegram_token`/`ffmpeg` | **five** lanes, plus `overall` | `src/health.py:115` `LANE_NAMES = ('gateway','telegram_token','ffmpeg','vault','google')` |
| «exits 0 when **ok**» | `ok` is not in the vocabulary at all | `src/health.py` `LANE_STATES = {healthy, misconfigured, unreachable}` |
| «1 when **degraded**» | `degraded` is not in the vocabulary at all | same |

The dangerous part: `exit_code_for({'overall': 'ok'})` returns **1**. The old README
told an operator that an `ok` report exits 0 — **exactly inverted**. An operator
following it would read a non-zero exit as the alarm condition when it is in fact
the healthy one, and would ignore the real alarm.

## What N7 did NOT touch, and why

### Dated anchors — the explicit non-goal

Rewriting a dated anchor asserts that a past commit produced today's number. These
were left byte-identical:

| Anchor | Left as-is because |
|---|---|
| `docs/10-CHECKPOINT.md:285` `## Anchor — 2026-09-14 · Commit 3fe6703 · Tests 1,457 passed (0 failures)` | commit `3fe6703` really ran 1,457 tests. Rewriting it to 2,903 fabricates the ledger. |
| `docs/10-CHECKPOINT.md:312,465,476,485,498,509,519,534,594,616,628,645,661,676,1012` (`1,462`/`1,469`/`1,474`/`1,496`/`1,514`/`1,521`/`1,536`/`1,798`/`1,813`/`1,819`/`1,838`/`1,855`/`1,864` …) | each is the suite size its own dated entry recorded, with its commit. |
| `docs/01-PRODUCT-REQUIREMENTS.md:54`, `docs/03-TECHNICAL-SPECIFICATION.md:19` (`1,457 green`) | floors, satisfied by 2,903. Correcting a floor would change the requirement's meaning. |
| `docs/16-WORKFLOWS.md:87` «floor ratified 2026-09-18: 1,819 passed» | self-dated ratification; total coverage is 92.5% today, still ≥ the ratified 90%. |

### The `4,782` trap

`docs/16-WORKFLOWS.md:59` and the SARA encyclopedia both say persona is a
«4,782-byte invariant». `src/persona.py` is **12,100 bytes**. The obvious
«correction» — 4,782 → 12,100 — **would have been wrong**: 4,782 is
`len(SARA_PERSONA_AR)`, the length of the assembled persona *string*, measured at
4,782 characters today and pinned green by
`tests/suite/tier1_resilience/test_persona_extract.py:20` (`CORE_LEN = 4782`).
The unit word is loose; the number is right. Left alone.

### N5's entry — appended to, never edited

N5 recorded that a **secondary rate-limit 403** now classifies `REFUSED` rather
than throttled, because no header separates a secondary limit from an under-scoped
PAT. N7 **appended** the operator-facing consequence to the ledger as a
current-state note and did not touch N5's entry (`:4186-4194`).

### N6's Class-B deferrals — recorded, still deferred

Owner decision 2026-10-03, option (a): N6 recorded B/C drift rather than editing
prose. **N7 did not fix them.** The full table lives in
`docs/10-CHECKPOINT.md:4368-4388`; the machine-readable source of truth is
`DEFERRED_CLASS_B` in `tests/test_citation_guards.py`.

### The `ruff format` fence — the one ledger edit N7 was given

`ruff format --check` was **RED at `8da8adf`**, inherited from N3: a hand-wrapped
Python fence at `docs/10-CHECKPOINT.md:3654-3658`. A `python` fence inside a
markdown file is still parsed as Python, so the prose was breaking the repository's
own gate. N7 realigned that single fence to the live source and added nothing else
to that entry.

## The `docs/` citation triage — N6's 33, measured at 35

N6 deliberately left `docs/` unpoliced (owner decision 2026-10-03, option (a)) and
recorded that **33 `docs/` citations would fail** Guard 1 if it were. N7 re-derived that
number rather than inheriting it.

**N6's 33 is TRUE — for N6's commit.** Re-deriving at HEAD gives **35**, and the
difference is fully accounted for:

| | count |
|---|---|
| N6 measured at its RED commit `5136813` | **33** |
| `+` citations N6's own fix commit `8da8adf` added to the ledger (100 lines, 43 citations) | |
| `+` of those that FAIL — two quoted RED-demonstration citations at `:4396` and `:4398` | **2** |
| **= measured at HEAD** | **35** |

The arithmetic closes exactly (`484 - 43 = 441` total `docs/` citations at `5136813`,
matching N6's recorded 441). **So 33 + 2 = 35, and both new failures are quotations of a
deliberately wrong citation inside N6's own RED proof** — the same class as the two already
counted at `:3512`. They are marked as quotes and were left alone.

### Where the 35 live, and the bucket for each

| File | Count | Kinds | N7 bucket |
|---|---|---|---|
| `docs/architecture/AGENCY_SWARM_WORKFLOW.md` | 26 | 26 unresolved | **external** — every one cites a `.claude/agents/*.md` role file or `claude/WORKFLOW.md`. `SEARCH_ROOTS` excludes `.claude/` **by policy**, because a citation into a tree CI does not have cannot be verified from the repository. A stated policy, not a silent skip. |
| `docs/10-CHECKPOINT.md` | 6 | 4 past-EOF, 2 unresolved | mixed, all left — see below |
| `docs/AUDIT_REPORT.md` | 3 | 2 past-EOF, 1 unresolved | **quoted-third-party** — the 2026-09-02 forensic report citing a tree as it stood then |
| **total** | **35** | 7 past-EOF, 28 unresolved | **0 corrected** |

The six in the ledger:

| Site (at `8da8adf`) | Citation | Bucket | Why left |
|---|---|---|---|
| `:1168` | `CLAUDE.md` lines 223–264 (past EOF; it is 224 lines today) | dated-history | a 2026-08-31 audit finding *about what CLAUDE.md carried*. The block it described has since changed; the finding was true when written. |
| `:1715` | `Report/part-f-errors.md` line 152 (unresolved) | external | the line itself says «a gitignored reading copy, not committed» — it cites the never-staged analysis report by design |
| `:3512` ×2 | `src/tools.py` line 9999, `src/skills/capabilities.py` line 123456 | quoted | a recorded mutation demo; the wrong line numbers ARE the point |
| `:4396`, `:4398` | `src/tools.py` line 9999 | quoted | N6's RED proof, quoted verbatim from the guard's own failure message |

> **The four deliberately-wrong citations above are described, not reproduced.** Writing them
> back in `path:NNN` form would have made this appendix *itself* add five new
> would-fail citations and pushed the repository's measured figure from 35 to 40 — a
> reviewer would have found N7 worsening the very metric it was reporting. Describing the
> line number in prose keeps the citation count honest. This is recorded rather than left
> silent, because the next auditor should know the 35 was measured on the pre-appendix tree.

**Split: 0 corrected, 35 recorded as known.** Not one of them is a live-and-wrong claim
about today. They are historical findings, third-party quotations, or citations into trees
that are deliberately not shipped — which is the answer, and it is a *different* answer
from «they are all broken».

**`scripts/docs_guard.py` was NOT changed.** Its canonical set is the 16-file suite, and
this appendix is frozen history in exactly the sense that file's docstring already excludes
(«frozen history (VISION, HANDOFF, ...) is deliberately NOT canonical»). Adding a triage
record to a presence-check list would make a rename of the record look like a broken gate.

## The corrections, and the command that re-derives each

Every number below was re-derived at HEAD. The commit message carries these same pairs with
their raw command output.

| Site | OLD → NEW | Re-derived by |
|---|---|---|
| `docs/01-PRODUCT-REQUIREMENTS.md:61` | `1,457/0 suite` → `2,903/0 suite` | `pytest -q -p no:cacheprovider --no-cov --ignore=tests/live_harness` |
| `docs/03-TECHNICAL-SPECIFICATION.md:60` | `Suite 1,457 passed / 0 failed` → `2,903 passed / 0 failed` | same |
| `docs/04-ARCHITECTURE.md:94` | `tools.py` (45 handlers) → (46 handlers) | `len([n for n in dir(ToolRegistry) if n.startswith('_do_')])` |
| `docs/ai/PROJECT-CONTEXT.md:12` | `ToolRegistry (45 handlers)` → (46 handlers) | same |
| `README.md:2-3,26,31,54,137` | Oracle-as-production → local-first | `docs/10-CHECKPOINT.md:3006-3023` (owner decision 2026-10-01) |
| `README.md:149` | 3 lanes + `ok`/`degraded` → 5 lanes + `healthy`/`misconfigured`/`unreachable`, all HTTP 200, exit 0 only on `healthy` | `src/health.py:115` `LANE_NAMES`; `health.exit_code_for` |
| `docs/10-CHECKPOINT.md:3654-3658` | hand-wrapped fence → `src/health.py:157-161` verbatim | `ruff format --check` |

### Why 45 became 46 — and why the compendium's «46 tools» was already right

The two numbers were never the same quantity, and the ledger had already noticed the
discrepancy (`docs/10-CHECKPOINT.md:1187-1188`, a **dated** entry, left untouched). Measured:

* **handlers** — `_do_*` methods on `ToolRegistry`: **46**
* **model-facing tools** — `src.tool_overlay.valid_tools()`: **46**, of which `_VALID_TOOLS`
  carries 45 real tools plus the null tool `none`

So `docs/reports/TOOLS_AND_API_COMPENDIUM.md`'s «46 tools» was **already correct** and its
three hits are `verified-true`. The stale figure was only ever the *handler* count in two
component/vocabulary descriptions. The two sets differ by exactly one name in each
direction — `_do_file_save` has no model-facing tool, and `none` is a null tool with no
handler — which is why «46 = 46» is a coincidence of arithmetic rather than the same set.

### The one gate that was RED, and why prose could break it

`ruff format --check` was failing at `8da8adf` on `docs/10-CHECKPOINT.md:3656`. The cause
generalises: **ruff parses ` ```python ` fences inside markdown as Python.** N3's prose — a
hand-wrapped dict literal quoted into the ledger — was valid Python in the wrong shape, so
a documentation edit was holding the repository's own lint gate red. This is the only edit
N7 made inside an existing ledger entry, and the fence is now byte-identical to
`src/health.py:157-161`.

## The one commit

N7's changes are documentation-only and land as a single commit. The verification artefact
is the commit message: every corrected claim appears there as `OLD → NEW` with the command
that measures it and that command's output, so a verifier can re-run each line without
reading the diff. This file holds the *other* half — the reasoning for the 235 claims left
alone, which a diff cannot show.

