---
tags: [architecture]
---

# 03 — Technical Specification (stack, constraints, benchmarks)

## 1. Stack rationale

| Concern | Choice | Why |
|---|---|---|
| Python | 3.12 (`py -3.12`) | 3.14 wheel gaps in the aiogram/pytgcalls ecosystem |
| Bot framework | Aiogram 3.x, long polling | outbound-only; zero inbound ports |
| LLM gateway | OmniRoute, OpenAI-compatible `/v1` | free-pool multiplexing + quota-aware fallback |
| Voice out | Fish Audio `s2.1-pro-free:free` via OpenRouter speech | only voice; Edge-TTS purged 2026-09-03 |
| Voice in | faster-whisper int8 (local) + ECAPA-TDNN biometrics | no cloud STT, <50 ms CPU verify |
| Config/typing | Pydantic v2 settings / models | fail-fast boot on missing secrets |
| Logging | Loguru, structured | never swallow silently (except best-effort lanes, logged) |
| Lint/format | Ruff (check + format) | single tool |
| Tests | pytest + pytest-asyncio + mocks | TDD mandatory, 1,457 green |

## 2. Hard constraints

$0.00/month absolute (free/open-source only; `PaidModelBlockedError`
guillotine). Owner-only (Telegram-ID + voice biometrics). Async-only
(ffmpeg subprocess in executors). No hardcoded secrets (env only).
Confirmation-gated PC actions with vault-persisted IDs. Platonic only.
Untrusted-content boundary (email/web/file = data).

## 3. Runtime models matrix (live, ADR-23)

| Tier | Primary | Fallbacks | Policy |
|---|---|---|---|
| FAST | `groq/openai/gpt-oss-120b` | `google/gemma-4-31b-it:free` | 4 s first-token guillotine; 15 min quarantine on 429/empty; `reset after Xs` parsed |
| MEDIUM | `openrouter/nex-agi/nex-n2.5-mini:free` | `groq/openai/gpt-oss-120b` | conversation depth / tier-2 chat |
| HEAVY | `openrouter/nex-agi/nex-n2.5-pro:free` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`, `groq/openai/gpt-oss-120b` | tool-lane narration via `stream_heavy()`; >3-call turns escalate to MoE |

The `openrouter/` prefix on both nex-agi pins is load-bearing: the bare
`nex-agi/...` slug form does not route and 404s against the live gateway. Re-pinned
2026-09-30; the fallback chains and Tier 1 are unchanged by it.

FAST callers budget ≥ 120 tokens (reasoning-model floor). Groq key
rotation is OmniRoute-server-side (5 keyed connections); client keeps one
bearer + quarantine doctrine (no bypass, hard rule 1).

## 4. OpenClaw wire shapes

`OpKind`: focus/click/double_click/right_click/type_text/hotkey/scroll/
navigate/extract/screenshot/inspect_tree (closed — no shell member).
`ElementHandle{id,role,name,bbox?,hotkey?,source}`.
`Op{op,target?,value?,reversibility,verify?}` (wire claim recomputed, never
trusted). `ActionDAG{goal,ops,weight,plan_id}`. `ActionTranscript{plan_id,
success,observations[],audit_codes[]}`. Verbs: `openclaw.perceive`
(+`full`), `.act` (op + `confirmation_id?`), `.fetch` (validated URL),
`.browse` (`action` + `params`).

## 5. Measured benchmarks (midday pools, honest numbers)

FAST TTFT ~0.6–1.2 s (bar 1.2 s; worst transient ~2.2 s absorbed, never a
stall). RAG recall 13/14 top-1, 14/14 top-3, p95 ~3.1 ms (bar 5 ms).
Suite 2,903 passed / 0 failed, coverage ≥ 85%. OpenClaw bench 12/12, 0
unconfirmed executions.

## See also (graph links)

- [02 — Product Specification](./02-PRODUCT-SPECIFICATION.md)
- [04 — System Architecture](./04-ARCHITECTURE.md)
- [06 — API Specification](./06-API-SPECIFICATION.md)
- [11 — Testing](./11-TESTING.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
