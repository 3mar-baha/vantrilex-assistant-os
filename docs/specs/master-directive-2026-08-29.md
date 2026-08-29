# Master Directive Spec — 2026-08-29 Overhaul (new capabilities)

Implements the owner's MASTER ARCHITECTURAL DIRECTIVE (2026-08-29). Binding contract for the
capabilities absent from `sprint-{1..4}.md`. Per-sprint spec files are refreshed at each
sprint's entry gate from this file. Invariants live in CLAUDE.md + `docs/03-DECISIONS.md`
(ADR-15 hosting, ADR-16 dual brain). All pytest targets below are the TDD contract.

## M1 — Adaptive Jordanian Dialect Engine (Sprint 1, task 1.3b)
- `src/dialect.py`: `normalize(text, notes) -> str` — phonetic normalization of written
  colloquial Jordanian to `ar-JO-SanaNeural`-compatible pronunciation BEFORE Edge-TTS.
- Ingestion loop: owner corrections/slang in natural chat -> parsed -> appended to
  `Dialect_Notes.md` (YAML list entries: term, phonetic, context, date). Never blocks a reply.
- `Dialect_Notes.md` snapshot loads at session start and injects into the system prompt.
- Tests (`tests/test_dialect.py`): `test_normalize_applies_note_mapping`,
  `test_ingestion_appends_note_and_never_blocks`, `test_snapshot_injection_into_prompt`.

## M2 — Speaker Verification & Guest Mode (Sprint 2)
- `src/biometrics.py`: local zero-cost speaker verification (SpeechBrain ECAPA-TDNN;
  Resemblyzer fallback), <50 ms/chunk on CPU; cosine similarity vs the owner's enrolled
  embedding (5-10 s clean sample -> encrypted vector persisted in the vault).
- Two auth layers compose: Telegram-ID allowlist (unchanged, silent drop for foreign
  accounts) + voiceprint on voice input within the owner's account.
- Guest Mode (owner-account, non-owner voice, similarity < threshold `VOICE_SIMILARITY_THRESHOLD`):
  1. Warm greeting: "يا هلا، الصوت مش صوت عمر... مين بيحكي معي؟"
  2. Zero-trust lockdown: PC control, Gmail triage, Calendar, private vault = hard-blocked.
  3. Message-taking offered; recordings filed to `Voice_Memos/` or `Contacts/`.
- Tests (`tests/test_biometrics.py`): `test_owner_voice_passes_threshold`,
  `test_guest_voice_enters_lockdown_no_tools`, `test_guest_message_taken_and_filed`,
  `test_embedding_encrypted_at_rest`. Floor: guest lockdown test joins the sacred floor.

## M3 — Daily Activity Ledger & Evening Check-in (Sprint 2)
- `src/journal.py`: aggregates milestones/tasks/meetings/calls/events ->
  `Daily_Logs/YYYY-MM-DD.md` (chronological, YAML frontmatter).
- Evening proactive check-in (`skill-evening-proactive-journaler`): fires once daily,
  randomized 18:00-19:30 local, ONLY if the day's ledger is thin (< N entries, config);
  Google-Calendar-conflict-guarded (never during meetings/focus blocks); warm storytelling
  probes; results update `Daily_Logs/` + `User_Info.md`.
- Tests (`tests/test_journal.py`): `test_ledger_aggregates_chronologically`,
  `test_evening_trigger_randomized_and_once`, `test_calendar_conflict_suppresses_checkin`,
  `test_thin_ledger_prompts_probing`.

## M4 — Dynamic Capability Expansion (Sprint 4)
- `src/expansion.py`: on owner-supplied API credentials -> validates -> registers a new
  async task (fetch/transform/store-to-vault) WITHOUT redeploy; natural-language cron
  ("كل صباح 7") parses into the asyncio scheduler; tasks run in free-tier budgets; any
  failure logs loudly and disables the task (no silent loops).
- Secrets per task go to `.env` via owner action — never inline in chat logs.
- Tests (`tests/test_expansion.py`): `test_nl_cron_parses_arabic_schedule`,
  `test_task_registers_without_redeploy`, `test_invalid_credential_rejected_loudly`,
  `test_task_failure_disables_and_logs`.

## M5 — Dynamic Vault Taxonomy Expansion (Sprint 3)
- `src/vault_expand.py`: Sara creates new vault sub-directories/tag ontologies/semantic
  links as new projects/domains emerge; every structural change is a git commit on the
  vault repo (auditable); PARA backbone never deleted — expansion only.
- Tests (`tests/test_vault_expand.py`): `test_new_domain_creates_dir_and_tags`,
  `test_structure_change_is_git_commit`, `test_para_backbone_immutable`.

## M6 — Mandatory Vault Directories (Sprint 3, replaces §6 layout additions)
`Contacts/` · `Call_Transcripts/` (v1.1 writes, dir from Sprint 3) · `Studies/` (top-level;
`02_Areas/Studies/` migrates) · `Voice_Memos/` · `Daily_Logs/` + dynamic files
`User_Info.md`, `Dialect_Notes.md` (under `02_Areas/Profile/`, symlink-free canonical paths
documented in RUNBOOK). Vault guard test asserts all exist on first boot.

## M7 — Triage Token Compaction (Sprint 2, TokenJuice pattern)
- Before LLM classification: strip signatures/disclaimers/tracking boilerplate/quoted
  chains; cap body to classification budget. Reduces free-pool token burn (OpenHuman-
  pattern borrow; no upstream code — GPL boundary per `docs/reports/OPENHUMAN-ASSESSMENT.md`).
- Tests (`tests/test_triage_compaction.py`): `test_signature_and_quotes_stripped`,
  `test_body_capped_at_budget`, `test_classification_unchanged_on_compacted_input`.

## M8 — Voice Calls: VAD + Barge-in (v1.1, PyTgCalls)
- Full-duplex WebRTC; VAD gates incoming audio; owner speech instantly cancels Sara's
  playback (barge-in) — mid-stream TTS is dropped, never restarted (consistent with 1.2
  no-restart rule); biometrics runs per utterance (M2).
- Tests (`tests/test_call_bargein.py`): `test_bargein_cancels_playback_within_budget`,
  `test_vad_gates_silence`, `test_biometrics_gates_call_tools`.

## M9 — Polymath Tutor (`skill-polymath-tutor`, continuous)
- First-principles deconstruction across sciences + 10 languages; every study artifact
  filed to `Studies/` with YAML (topic, level, links). No new engine — chat + brain + vault.

## KPI additions
- Test coverage gate: **>=85%** enforced in Sprint 4 (`pytest-cov` in `make gate`).
- Biometric verification latency: <50 ms/chunk (CPU). Guest-mode tool leakage: 0.
