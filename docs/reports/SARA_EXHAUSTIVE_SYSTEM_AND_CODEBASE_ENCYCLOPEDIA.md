---
tags: [architecture]
---

# SARA Exhaustive System & Codebase Encyclopedia (forensic audit 2026-09-16)

> Every claim below was verified against code, tests, or governor docs this
> session. Persona lock held (4,782 bytes, read-only check). `.env`, `vault/`,
> and `opencode.json` were never read, staged, or committed. Gates this
> session: security OK · benchmark 6/6 LIVE + 5/5 invariants · docs-guard OK.

## 1. Brain & OmniRoute matrix (`src/gateway.py`, `src/config.py`)

Three tiers walked per request behind the Fast Front-Door Dispatcher
(`src/dispatcher.py`, ADR-18): FAST `groq/openai/gpt-oss-120b` (router, Jordanian
ack, direct chat, memory narration) · MEDIUM `nex-agi/nex-n2.5-mini:free`
(depth) · HEAVY `nex-agi/nex-n2.5-pro:free` + nemotron/gpt-oss fallbacks (tool
narration, DAGs). Survival doctrine: 4 s first-token guillotine, 15 min
quarantine on 429/empty/stall, immediate cascade — never a retry burn.
`PaidModelBlockedError` kills non-free IDs pre-wire ($0.00 circuit breaker).
Key rotation is OmniRoute-side (owner-operated); the client holds one bearer +
model quarantine. No direct Anthropic/Gemini SDK exists anywhere (Gemini
retired 2026-08-30 over the Google 403).

## 2. ReAct decision loop (`src/decision_loop.py`, behind `SARA_REACT_LOOP`)

`LoopBudget` caps iterations, wall seconds, tool calls, and same-tool repeats;
`run_decision_loop` streams tool verdicts with a keep-alive pulse. Default path
remains byte-identical to `front.handle()`.

## 3. 46-tool catalog (entry: `ToolRegistry.call`, `src/tools.py:137`)

Workspace (Gmail/Calendar/Tasks/Drive/People/reminders/brief, OAuth sealed
token, polling-only) · PC bridge (telemetry/apps/launch/close/files/
screenshot/OCR/volume/media, guard + `confirmation_id`, needs daemon WSS) ·
vault/memory (knowledge_graph, create_folder, multi_task) · keyless web
(DDG, Open-Meteo, bundled endpoints) · key-gated staged (Places/Firecrawl/
Instagram adapters written, keys missing; YouTube/ExchangeRate keys set) ·
cloud (GCS backup adapter; Logging/BigQuery-family registered, no callers).
Full per-tool table: [Compendium](./TOOLS_AND_API_COMPENDIUM.md).

## 4. Vault & conversational RAG (`src/associative.py`, `src/memory*.py`)

Two tiers: 50-message rolling buffer + Obsidian envelope (digest ≤1,500 chars,
top-k injection ≤600). `VaultIndex`: lazy mtime-cached, skips `.obsidian/` +
`State/`, scoring alias+10 / title×3 / tags×2 / body×1. `inject()` gates on
routine intents (zero memory tokens) and short greetings (<3 tokens) — both by
contract; advisory turns carry digest + hits (verified 2,010 chars live).
Corpora: JODA dialect, two feminine style guides, four KB domains, Omar core
digest + living master digest (≤800 words, write-back capped).

## 5. Invariants & gender engine

ar-JO immersion · masculine address (107-rule morphological engine:
`rules_verbs` + `REGEX_RULES`, `rules_imperatives`, `rules_clitics` +
adjective/participle tables, `shield.py` first-person guard, aggregation-time
normalization against KV-cache drift) · Fish-only voice
(`fish-audio/s2.1-pro-free:free`, `assert_no_edge`, 429 → honest text) ·
confirmation-gated execution (whitelist + audit codes + breaker triple-check) ·
$0.00 (free pools + quota budgets).

## 6. Defect ledger (root cause → fix, all closed)

- Doubled bot cores (venv + system Python polling one token) → kill stale pair,
  single-pair relaunch via `sara.ps1`.
- Probe timeout misreporting DEGRADED on a live 1,400-model catalog → 15 s
  liveness probe (turn budgets untouched).
- Google 403 → Gemini retired, Groq/OpenRouter re-pinned.
- Owner biometric lockout (0.75 inside variance) → threshold 0.60; single-owner
  doctrine kept (multi-speaker drill pruned by directive).
- Microsoft-voice failover → Fish-only re-raise + honest text.
- Arabic app-name misses → alias table + basename/stem matching.
- Voice «نعم» bypass → coordinator-first consumption.
- Quiet-hours 08:00–23:30 end-inclusive (pinned by `test_bridge_online.py`).
- Proclitic root-blinding (3-letter roots, على→ع gluing) → remainder floors +
  colloquial stripping in `src/cognition.py`.
- **No repo footprint found**: "Port 20128 EADDRINUSE Node collision" appears
  in no doc, log, or test — recorded here as mission-stated only.
- **Unratified horizon** (absent from code, docs, and `08-ROADMAP`):
  "5-Agent Sovereign Society / 50-key matrix / 12-game suite" and v1.1
  VoIP/SIP calls beyond the HANDOFF one-liner — require owner ratification
  before admission; `08-ROADMAP.md` remains the sole scope authority.

## 7. Verification record (this session)

security_gate OK · `live_interactive_benchmark.py` 6/6 LIVE (A 0.9 · B 3290.4 ·
C 4.4 · D 5.8 · E 2918.9 · F 217.3 ms) + 5/5 invariants · docs-guard 16/16 ·
transcript refreshed in `benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json`.

## See also (graph links)

- [04 — System Architecture](../04-ARCHITECTURE.md)
- [09 — Decisions](../09-DECISIONS.md) · [08 — Roadmap](../08-ROADMAP.md)
- [Tools & API Compendium](./TOOLS_AND_API_COMPENDIUM.md)
- [Risks, Costs & Governance](./RISKS_COSTS_AND_GOVERNANCE.md)
- [Map of Architecture](../00-MAP-OF-ARCHITECTURE.md)
