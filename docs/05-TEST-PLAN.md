# 05 — Test Plan & Quality Gates

## 1. Test Architecture

- **Framework**: pytest + pytest-asyncio + unittest.mock; no external test containers required.
- **Coverage target**: >= 85% branch coverage once `src/` exists (gate activates with the
  first Sprint 1 merge; scaffold-stage CI runs without the threshold).
- **Discipline**: TDD red -> green -> refactor per concern; tests are the contract.

## 2. Test Catalog

| Test module | Verifies |
|---|---|
| `test_omniroute_gateway.py` | Streaming completions; PRIMARY->FAST fallback ordering; quota/retry handling |
| `test_edge_tts_pipeline.py` | Jordanian Arabic synthesis into BytesIO; Ogg Opus output; no disk writes |
| `test_audio_stream_opus.py` | ffmpeg transcode produces valid Ogg Opus headers; first-chunk emission |
| `test_owner_middleware.py` | Non-owner updates dropped silently; owner passes through |
| `test_email_triage.py` | Heuristic weights/bands/floors (VIP, keywords, bulk); LLM refinement containment + never-downgrade merge + fallback; per-tier dispatch (drop/text/voice/priority-ping); ping stop conditions; MarkdownV2 escaping; AST import-surface scan |
| `test_google_clients.py` | Calendar/Tasks CRUD shapes; refresh-token reuse; fixture-driven parsing |
| `test_google_suite.py` | Calendar/Tasks/Drive/Contacts fixtures parse to typed UTC-normalized models |
| `test_gmail_watch.py` | Sweep/incremental fetch, dedupe, dispatch-then-mark redelivery, watch gating, corrupt-state recovery, lock serialization, parse catalog |
| `test_obsidian_para.py` | Note create/update; YAML frontmatter; Zettelkasten links; PARA path routing |
| `test_voice_memo_ingest.py` | Voice note -> transcription -> filed YAML-tagged memo |
| `test_post_call_summary.py` | Action-summary prompt fires only when actionable tasks exist |
| `test_bridge_protocol.py` | Envelope conformance, heartbeat, auth rejection, outbound-only assertion |
| `test_whitelist_guardrail.py` | Non-whitelisted blocks; confirmation round-trip; approval IDs persisted |
| `test_wol_idle.py` | Magic-packet bytes match MAC; single idle offer per window |

## 3. Quality Gate Checklist (every change)

- [ ] **Clean Code Guard**: `ruff check .` && `ruff format --check .` — zero findings (ADR-12).
- [ ] **Test Guard**: `pytest -v --cov=src` all green at threshold.
- [ ] **Security Scan**: `bandit -r src/` — zero high/critical issues.
- [ ] **Docs Guard**: canonical docs updated in the same commit as behavior they describe.
- [ ] Second-pass guards (Clean Code / Test / Docs) re-run as independent review passes at Phase 4.

## 4. Integration & E2E

- Live smoke (manual, gated on credentials): owner message -> brain reply -> voice note
  playback; triage fixture run against sandbox Gmail; whitelist confirmation round-trip
  against the real bridge.
- v1.1 additions: PyTgCalls call lifecycle suite lands with the calling engine.

## 5. Exit Criteria per Sprint

Sprint done = backlog AC checked + gate checklist green + docs synced + CHANGELOG entry.
