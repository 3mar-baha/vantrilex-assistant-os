---
tags: [testing]
---

# Autonomous Coach Drill Report — 2026-09-16

> Harness: `tests/test_autonomous_coach_drill.py` (19 tests, hermetic — no
> gateway, no microphone, no live-vault writes; tmp vaults only).
> Drill notes written during the run target `tmp_path` mirrors, never the
> owner's live vault.
> RBAC honesty note: production Sara gates binary owner/guest (allowlist +
> Guest Mode). The tiered RBAC below is a DRILL-LOCAL policy defining the
> target tiers; the drill verifies biometric attribution feeds it exactly and
> denials leak zero content.

## Voice discrimination — 10/10 correct

| Profile | Cosine vs owner | Verdict | Mode |
|---|---|---|---|
| Owner | 1.000 | owner | Full autonomy |
| sibling-near (boundary) | 0.564 | unknown | Guest |
| child-high | 0.432 | unknown | Guest |
| elder-quiet | 0.409 | unknown | Guest |
| friend-casual | 0.227 | unknown | Guest |
| caller-echo | 0.078 | unknown | Guest |
| tts-impostor | ~0.05 | unknown | Guest |
| noise-floor | ~0.0 | unknown | Guest |
| silence (zero-vector) | 0.000 | unknown | Guest |
| stranger-far / colleague-phone / guest-roam | < 0.0 | unknown | Guest |

Gate: threshold 0.60 (calibrated 2026-09-03); diarizer attributes owner vector
to owner, silence/strangers to the unknown speaker; Fish lane verified pure
(`assert_no_edge`, 429 → `FishVoiceError` → honest text, unconfigured → loud
failure — never a foreign voice).

## RAG retrieval — 15/15 seeds self-retrieve top-1 (read-only)

Every `04_Resources/` seed rebuilds its own deterministic query (filename stem
+ longest body tokens) and retrieves itself first; drill write-back notes cite
back by path. Citations are file paths + excerpts via `build_injection_block`.

## Tool & skill matrix — 46/46 honest degradation + composition

All 46 `ToolRegistry` handlers answer with honest Arabic lines on zero
backends (no crash, no silence, no raw exceptions). Composition chain verified:
`gmail` (ليلى/عزومة) → `calendar` (عشا عائلي) → `telemetry` (12%) → vault note
→ content tokens propagate into the indexed note → voice leg stays Fish-pure.

## Cognitive trace — friction math + self-correction verified

Natural prompts map without tool names (`gmail`, `calendar`, `telemetry`,
`launch`, `none`); `ReflectiveTrace` penalties follow the 0.30/failure scale
capped at 0.60; a failed turn demotes the tool and a clean retry clears the
ledger; horizon adjacency falls back to `web_search`/`brief`.

## See also (graph links)

- [11 — Testing](./11-TESTING.md)
- [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md)

## Stage 5 — Multi-speaker enrollment & RBAC (19-test suite)

Identities enrolled in a tmp registry (Fernet-sealed, threshold 0.75; pairwise
voice separation ≤ 0.26): Owner (root admin), drill-sib (Family),
drill-colleague (Colleagues), drill-friend (Friends).

| Voice | Cosine | Tier |
|---|---|---|
| 1 Owner | 1.000 | Owner — all 46 tools, private vault, credentials |
| 2 Family | 1.000 | Family — calendar, bridge telemetry; finance/email denied |
| 3 Colleague | 1.000 | Work — project RAG, tasks; personal/banking/logs denied |
| 4 Friend | 1.000 | Friend — banter, web search, media; Guest-Plus sandbox |
| 5–10 stranger/child/elder/TTS/noise/silence | < 0.60 | Zero-trust Guest — informational tools only |

RAG filtering: owner reads private/shared/family/public with citations;
colleague reads shared only; friend/guest read public only — every denial is
the polite Arabic boundary with the secret tokens asserted absent. Tool gates:
destructive + private tools owner-only (denied launch never reaches the
coordinator); calendar owner+Family; project tools owner+Colleague; guests the
safe informational subset. Diarized dialogue (owner → colleague → owner)
attributes every turn correctly with per-speaker context isolation proven in
`ReflectiveTrace`.
