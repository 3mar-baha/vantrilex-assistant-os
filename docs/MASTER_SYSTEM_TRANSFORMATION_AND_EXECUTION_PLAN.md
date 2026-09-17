---
tags: [architecture]
---

# Master System Transformation & Execution Plan (P0–P6)

> Ratified Tier-1 output of the Leader–Guide–Implementer governance loop.
> Doc-only deliverable: no production code is modified by this document.
> Persona lock held (4,782 bytes, untouched). All phase work below executes
> under `docs/16-WORKFLOWS.md` with atomic per-phase commits and the 3-strike
> circuit breaker. P0 code begins only on explicit `"التالي"`/`"next"`.

## 1. Executive Architecture & Protocol Governance

Vantrilex Assistant OS (Sara) is a single-owner, strictly-zero-cost executive
assistant: one Telegram transport (aiogram 3.x, owner-ID allowlist with silent
drop), a 3-tier OmniRoute brain (FAST conversation, MEDIUM depth, HEAVY tool
narration) behind the Fast Front-Door Dispatcher, a Fish-only voice lane with
local Whisper transcription, a git-backed Obsidian vault with two-tier memory
(50-message buffer + long-term envelope), and a whitelisted Windows PC bridge
with OpenClaw substrate. The five invariants are absolute: ar-JO immersion,
masculine address to Omar, zero Edge-TTS, zero unconfirmed destructive
execution, and $0.00 cost. The cost proof is structural rather than
promissory: every LLM call rides free pools (Groq gpt-oss + OpenRouter `:free`
slugs) guarded pre-wire by `PaidModelBlockedError`, which raises on any model
ID outside the free set before any request object exists; quota survival adds
a 4-second first-token guillotine, 15-minute quarantine on 429/empty/stall,
and immediate cascade to the next chain entry without retry burn; per-service
daily budgets in `google_cloud_suite.py` return do-not-call once spent; the
`quota_safety` tool reports headroom visibly. Measured lifetime spend is
$0.00 across all lanes. Governance runs Leader (Omar: intent, sign-off, halt
authority) → Guide (Gemini Spark: specification, adversarial review,
architecture) → Implementer (OpenCode: plans, TDD code, gates, commits).
Operating tiers are `/plan` (read-only discovery, default for any unspecified
request, ends in sign-off halt), `/code` (red-green-refactor, minimal
abstraction, full suite green), `/audit` (invariants, security gate,
benchmark, adversarial review), `/sync` (checkpoint entry, wikilink/tag sync,
clean direct-to-`main` commit with immediate push). Standing laws bind every
phase: `src/persona.py` stays byte-identical at 4,782 bytes; `.env`, `vault/`,
`opencode.json`, and debug dumps are never read for content into docs, never
staged, never committed; documentation lives only in authorized homes
(`docs/`, `archive/`, `benchmarks/`, `vault/`); `[[WikiLinks]]` resolve only
inside `vault/` while `docs/` uses portable relative links; zero deletions
without explicit human confirmation; the sacred floor
(`test_owner_middleware.py`, `test_whitelist_guardrail.py`,
`test_guest_lockdown.py`, `test_zero_paid_guard.py`) blocks every merge; three
failed fix attempts on one defect trips the circuit breaker into full halt
plus a decision-incident record. Each phase below carries exact file
boundaries, data structures, algorithms, and acceptance criteria so Tier-2
execution is mechanical rather than interpretive. The converged DAG order is
P0 shape-contracts → P1 pattern bank → P2 counter + rotation → P3 fused router
→ P4 directive templates → P5 verification matrices → P6 coverage certification,
each phase ending green, checkpointed, and committed before the next begins.

## 2. Phase Technical Specifications (P0–P6)

### P0 — Test-impact enumeration & shape contracts

Allowlist (presentation layer only): streamer acknowledgment/prose assertions
in chat-streamer tests, dispatcher ACK-guard assertions (`MAX_ACK_CHARS`,
identity-word and claim-word scans), voice-fallback wording assertions,
triage-template assertions, brief/journaler wording assertions. Denylist
(immutable): `test_owner_middleware.py`, `test_whitelist_guardrail.py`,
`test_guest_lockdown.py`, `test_zero_paid_guard.py`, every
`PaidModelBlockedError` assertion, every `confirmation_id`/breaker assertion,
quota-guard assertions, biometric threshold assertions. Transformation rules:
exact Arabic literal `assert x == "..."` becomes a shape contract — e.g.
`assert re.fullmatch(r"[\u0600-\u06FF\s….,!؟]+", text)` plus a ban-list scan
for forbidden substrings (identity claims, claimed actions, leaked IDs);
length assertions become bounded ranges (`100 <= len <= 400`) derived from the
current literal ±20%; JSON-verdict assertions become schema assertions (required
keys present, enums within closed vocabularies) rather than string equality.
AST pre-check enumerates every `assert ... ==` with an Arabic literal in the
allowlisted files and emits the contract table for review before any rewrite.
Acceptance: rewritten suite green, denylisted files byte-identical
(`git diff --stat` empty for all four), persona length still 4,782.

### P1 — Categorical speech-act pattern bank

Miner (dev layer only, `openpyxl` read-only over `data/joda/train_set.xlsx`,
54,136 rows, columns Source/Text/Has-Error/Text-Corrected; `openpyxl>=3.1`
already pinned in `requirements-dev.txt`, production requirements untouched):
normalize each Text (strip tashkeel/tatweel, collapse whitespace, drop
error-flagged rows only when the correction is empty), dedupe by normalized
form, then classify by speech act with transparent heuristics — banter/humor
(laughter markers `ههه/هه`, Source social, exclamation density), task agreement
(imperative verb stems + affirmation tokens `تمام/أكيد/من عيوني`), polite
deflection (apology/hedge markers `آسف/معلش/يمكن/بس`), technical empathy
(problem nouns + reassurance verbs + second-person masculine address),
boundary setting (refusal shapes `ما بقدر/ممنوع/خلينا` + reason clause).
Quota: 80 floor per act (400 guaranteed diverse) + 100 wildcards by
length-normalized rarity with generic collocations capped at 5 via dedupe
(`تمام`, `شو هاد`, `والله` compete only as wildcards). Output: one tracked
markdown bank under `04_Resources/Dialect_Encyclopedia/` (size-capped,
sentence-unit rows with act tags); raw xlsx never enters git. Recall harness:
each admitted pattern must top-1 retrieve its own bank file through
`VaultIndex` before the bank ships. Acceptance: 500 rows, all five floors met,
recall 500/500, suite green.

### P2 — Atomic counter, 10-message cadence & mobile rotation

State: `vault/State/turn_counter.txt` holding a bare integer (no content, no
timestamps beyond mtime — the situational ring's privacy doctrine extended:
content never persists). Write path mirrors the house idiom (`gmail.py:76`,
`google_auth.py:109`): write `.tmp`, flush + fsync, `os.replace`; read path
`try: int() except (ValueError, FileNotFoundError, OSError) → 0` with
corrupt-rename mirroring `StateStore`. Increment rule: exactly once per genuine
human user turn at the transport boundary (`on_text`/`on_voice` entry) — never
ReAct iterations, sub-agent cycles, or harness replays; a dedicated test fires
4 internal cycles and asserts zero increments. Starvation guard: refresh also
triggers on session-start when the persisted counter is stale-but-nonzero.
Cadence: every 10th turn re-injects the master digest plus one rotated domain
block (JODA cues → Ammani humor → Feminine Grace → KB spotlight), all sourced
from already-loaded vault text — zero extra model calls. Rotation key is
`(bridge_posture, telegram_active, last_domain)`: FOCUS forces the
technical-empathy/brevity lane and suppresses humor/grace; FRAGMENTED and
NORMAL allow the wheel; an active Telegram turn while the bridge ring reads
AWAY derives the MOBILE context (concise delivery, no IDE-oriented modes);
cold boot (no samples) defaults NORMAL, never AWAY-by-default. Posture itself
is never persisted. Acceptance: counter survives kill -9 mid-write in fault
tests; rotation matrix covered per posture × domain; short sessions refresh on
next start.

### P3 — Fused router, repair layer & adaptive slicing

Verdict schema gains one field in the same FAST forward pass (+0ms, ~15
tokens): `rag_domains`, closed vocabulary
`{dialect, humor, grace, kb, personal, none}`, ordered by relevance.
`repair_verdict()` runs before any fallback, non-throwing by contract:
fence-strip (```json blocks) → first-balanced-brace scan → trailing-comma
repair → `json.loads` → schema validation where unknown enum values degrade to
field defaults (never whole-verdict discard). Only total repair failure falls
to deduce/net, each firing a loud log plus a `ReflectiveTrace` friction entry
so fallback frequency is monitored. Budget slicing is closed arithmetic on the
ordered domain list against a 3,000 ceiling: single domain up to ceiling; two
domains 60/40 by router order; three 50/30/20; four or more equal shares with
a 400-char floor (sub-floor domains drop with a log line); the composer
asserts the sum fits. Sentence-boundary chunking (never mid-sentence cuts)
plus 429-coupling: while any lane is quarantined the ceiling halves to 1,500.
Digest rides outside the block budget as today. Acceptance: fenced/malformed
router fixtures all parse or degrade loudly; slicing property-tests hold over
random domain lists; quarantine-halving covered.

### P4 — Directive templates & token/prose separation

Offline/booting strings (`WOL_OFFLINE_AR`, core-offline warnings) stay frozen
literals. All live surfaces (acks, warnings, confirmations, errors) move to
envelope directive blocks synthesized in the single generation pass — no
chained calls, Fish TTFT structurally protected. Safety boundary:
`confirmation_id` is minted server-side (`uuid4().hex[:12}`), persisted to a
vault confirmation note, and verified structurally by the breaker; the
coordinator composes challenges with the token as an immutable substring while
the model wraps prose around it. New tests assert the token survives verbatim
in every rendered challenge and that tampered/omitted tokens fail closed.
Acceptance: P0 shape-contracts green, token-tamper matrix red-team clean,
TTFT bars held on the live smoke.

### P5 — Hermetic 30-seam matrix & sandboxed live harnesses

Thirty fault-injection seams, all doubles, all in-suite: router unparseable,
gateway 429/empty/stall per tier (FAST/MEDIUM/HEAVY), Fish 429 + unconfigured,
Whisper empty audio, biometric miss + guest lockdown, whitelist miss + corrupt
whitelist, executor spawn failure, breaker irreversible-without-id,
coordinator dead, Gmail 401 + corrupt state, calendar empty, vault missing
digest, RAG short-query + routine-intent bypass, persona intactness, gender
drift (feminine verb in reply, first-person slip), triage invalid-JSON +
timeout, brief disabled, journaler busy-day, voice-demand Fish-dead, pending
orphan tokens, OpenClaw daemon down, tunnel verb errors, unknown dispatcher
tool, memory write failure, confirmation tamper. Ten live harnesses under
`tests/live_harness/` (`@pytest.mark.live_harness`, skip-soft conftest mirroring
`tests/live_probe/`, marker registered in `pyproject.toml`): Telegram runner,
audio bitrate/Ogg analyzer, 429 exhaustion simulator, TTFT monitor (<2.0 s),
bridge reconnection chaos, JODA 100-scenario dialogues, prompt-injection probe,
30-round recall validator, TPM quota dashboard, Workspace roundtrip probe.
Sandbox contract (`SARA_HARNESS=1`): `OverlayVault` resolver (writes to shadow
root, reads shadow-first then real vault), journaler/summarizer writers
disabled, Telegram pacing ≥1.5 s, zero mtime movement under
`vault/Daily_Logs/` asserted per run; harness 5 and 7 run owner-present only.
Acceptance: hermetic-30 green in CI; live-10 green-or-skipped with diary
pristine.

### P6 — Tiered coverage & invariant certification

Check-script (coverage.py has no per-module `fail_under`): ≥98% branch on the
safety/cost/gender core (`gateway.py` guard paths, `bridge/guard.py`,
`bridge/executor.py`, `bridge/openclaw/breaker.py`, `gender_pipeline/`,
`pc_actions.py` confirmation paths, `voice_policy.py`) and ≥90% overall;
fails the phase otherwise. Gates in order: `security_gate.py`, `docs_guard.py`
(16 canonical files), `live_interactive_benchmark.py` 6/6 + 5/5, full pytest.
Acceptance: script green, all gates green, checkpoint entry, clean commit.

## 3. 16-WORKFLOWS Operational Binding (per phase)

Every phase runs the same lifecycle with phase-specific tooling. Tiers:
build phases P0–P5 implement under `/code`; verification moments (P5 matrix,
P6) run under `/audit`; each phase closes under `/sync`. Tooling fleet:
`architect` (phase scoping), `ponytail` + `tdd-workflow` + `pytest-skill`
(red-green-refactor), `clean-code-guard` + `test-guard` (review gates),
`securing-agentic-ai-tool-invocation` (P4/P5 safety surfaces + confirmation
flows), `pyright-lsp`/`ruff` (static hygiene), `commit-commands` (phase
commits). Exact commands, run from the repo root: `.venv/Scripts/python.exe -m
pytest -q -p no:cacheprovider --no-cov` (suite), `.venv/Scripts/python.exe -m
pytest tests/<phase-file> -q -p no:cacheprovider --no-cov` (phase slice),
`.venv/Scripts/python.exe -m ruff check .` + `.venv/Scripts/python.exe -m ruff
format --check .` (hygiene), `.venv/Scripts/python.exe scripts/security_gate.py`
(audit), `.venv/Scripts/python.exe scripts/docs_guard.py` (sync guard),
`.venv/Scripts/python.exe scripts/live_interactive_benchmark.py` (P5/P6 live
proof). Governing hooks and invariants every phase: `block-creation-of-random-
md-files` (new docs only under `docs/`, `archive/`, `benchmarks/`, `vault/`;
P1 bank under `04_Resources/` as curated knowledge, P5 harnesses under
`tests/live_harness/` as code); `src/persona.py` 4,782-byte lock verified by
byte-length assertion before each phase commit; git exclusions (`.env`,
`vault/`, `opencode.json`, dumps) checked via `git status` before every
commit; portable relative links in `docs/`, `[[WikiLinks]]` only in `vault/`;
zero deletions without confirmation. Phase exit gates, identical each time:
suite green, ruff clean, phase slice green, 3-strike circuit breaker honored
(three failed fixes on one defect = full halt + decision-incident record),
`docs/10-CHECKPOINT.md` entry appended, atomic phase commit direct to `main`
with immediate push, then HALT for phase review. P0 exits on contract-table
green; P1 on 500-row recall green; P2 on crash-matrix + rotation-matrix green;
P3 on repair-fixture + slicing-property green; P4 on token-tamper + TTFT green;
P5 on hermetic-30 green + live-10 green-or-skipped with pristine diary; P6 on
check-script + all-gates green.

## 4. Rollback & Circuit-Breaker Protocols

Failure handling is uniform: any red gate stops the phase — no partial
advances, no "fix forward" across phase boundaries. One failed fix attempt is
logged with the error, the hypothesis, and the diff tried; the second attempt
must change strategy (different seam, smaller scope, or reverted assumption);
the third failure trips the breaker: full halt, a decision-incident record
appended to `docs/10-CHECKPOINT.md` (symptom, attempts, evidence, suspected
root cause), working tree left intact and uncommitted, control yielded to the
owner with the exact resume command. Rollback per phase is the inverse of its
commits: each atomic phase commit reverts independently (`git revert`), and
because phases never share uncommitted state, reverting Pn never touches
P0..Pn-1. Diagnostic triggers mandating a halt (beyond test red): any sacred
denylist file modified, persona byte-length drift, a secret appearing in
`git status`, benchmark invariant flip to FAIL, or diary mtime movement during
a harness run. Recovery order after a halt: reproduce hermetically first, fix
at the smallest seam, re-run the phase slice, then the full suite, then resume
the DAG at the failed phase — never skip ahead. Escalation path is always
Leader → Guide → Implementer with the incident record as the handoff artifact,
and no new phase opens while an incident record is unresolved. The incident
record template is fixed: symptom (one line), phase and gate that caught it,
all three attempts with diffs, benchmark/invariant deltas if any, suspected
root cause with the file:line anchor, and the exact resume command for the
next session. Stale incident records older than one phase without owner review
escalate to the Leader explicitly rather than decaying silently.

## Appendix E — P0 contract transformations (allowlist only)

Before (brittle literal): `assert ack == "من عيوني هسا ببدأ"`. After (shape):
`assert 5 <= len(ack) <= 30 and re.fullmatch(r"[\u0600-\u06FF\s….,!؟]+", ack)`
plus `assert not any(w in ack for w in IDENTITY_WORDS + CLAIM_WORDS)`.
Before: `assert reply == "تم بنجاح"`. After: `assert "تم" in reply and
len(reply.split()) <= 12` with the ban-list scan attached. Before: triage
template equality on the full rendered semi-critical card. After: assertions
on required slots present (excerpt ≤400 chars, escaped name, ack callback id
matching `triage:ack:{id}`) independent of connective prose. Before: voice
fallback equality on `EMPTY_VOICE_AR`. After: single-surface assertion (exactly
one of voice-note-sent vs text-sent true) plus content-shape check. Denylist
confirmations: `PARK_LINE_AR` equality stays literal (protocol challenge);
`confirmation_id` round-trip asserts structure (`hex[:12]`, vault note exists,
breaker False without it, True with it) — never prose. Gender excerpt asserts
become rule-hit asserts (named rule from the 107 fires on the fixture) rather
than full-sentence equality. Every rewritten test keeps its original name with
a `_shape` suffix added alongside (not replacing) for one full phase, so the
old and new contracts overlap green before the literal is retired.

## See also (graph links)

- [16 — Operational Workflows](./16-WORKFLOWS.md)
- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [08 — Roadmap](./08-ROADMAP.md)
- [04 — System Architecture](./04-ARCHITECTURE.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)

## Appendix A — 30-seam fault inventory (P5 hermetic matrix)

| # | Seam | Injected fault | Expected outcome |
|---|---|---|---|
| 1 | Router unparseable | fenced/trailing-comma JSON | repair or loud deduce fallback |
| 2 | FAST 429 | streak throttle | quarantine + cascade, no retry burn |
| 3 | FAST empty stream | zero deltas | park model 15 min, cascade |
| 4 | FAST first-token stall | 4 s guillotine | abort + quarantine + cascade |
| 5 | MEDIUM 429 | throttled depth call | cascade to fallback chain |
| 6 | HEAVY 429 | throttled narration | MoE escalation path |
| 7 | Non-free model ID | paid slug dispatched | `PaidModelBlockedError` pre-wire |
| 8 | Fish 429 | quota hit mid-voice | `FishVoiceError` → honest text |
| 9 | Fish unconfigured | no key | loud failure, never foreign voice |
| 10 | Whisper empty audio | silent note | `EMPTY_VOICE_AR` single surface |
| 11 | Biometric miss | impostor vector | Guest Mode, zero privileged effects |
| 12 | Guest lockdown spy | guest turn | zero Gmail/calendar/PC/vault effects |
| 13 | Whitelist miss | unknown app | honest not-listed line, no pending state |
| 14 | Whitelist corrupt | unreadable JSON | fail closed (confirm everything) |
| 15 | Executor spawn failure | missing binary | honest Arabic error + audit code |
| 16 | Breaker irreversible w/o id | Alt+F4, no confirmation | `authorize` False |
| 17 | Coordinator dead | exception in `has_confirmation` | PARK, never pass |
| 18 | Gmail 401 | expired token | single-flight refresh + replay once |
| 19 | Gmail corrupt state | garbage JSON | `*.corrupt` rename + fresh |
| 20 | Calendar empty | no events | honest no-events line |
| 21 | Vault missing digest | absent master copy | empty block, reply proceeds |
| 22 | RAG short query | <3 tokens | empty block by contract |
| 23 | RAG routine intent | device turn | zero memory tokens |
| 24 | Persona intactness | any phase diff | length still 4,782 |
| 25 | Gender drift (reply) | feminine verb smuggled | aggregation normalization |
| 26 | Gender drift (self) | first-person slip | shield rewrite |
| 27 | Triage invalid JSON | garbage refinement | heuristic alone |
| 28 | Triage timeout | 15 s exceeded | heuristic alone |
| 29 | Brief disabled | flag off | silent skip, no send |
| 30 | Confirmation tamper | altered/omitted token | fail closed, no execution |

## Appendix B — Verdict schema and repair pipeline (P3)

```json
{"route": "direct|tier2|tier3", "tool": "<closed tool vocab>",
 "arg": "<free text>", "ack": "<≤30 chars>",
 "voice_reply": true,
 "rag_domains": ["dialect", "humor", "grace", "kb", "personal", "none"]}
```

`repair_verdict(reply)`: strip code fences → scan first balanced `{...}` →
remove trailing commas before `}`/`]` → `json.loads` → validate each field
against its closed vocabulary (unknown route → `"direct"`; unknown tool →
`"none"`; unknown domains dropped; ack over length → default ack) → return the
sanitized verdict. Raises nothing: total failure returns `None` and the caller
falls to deduce/net with a loud log plus a friction entry. Property tests:
every malformed fixture in the corpus either parses to schema or degrades
loudly; no fixture raises; no fixture yields an out-of-vocab tool.

## Appendix C — Rotation state machine (P2)

States are `(counter mod 10, bridge_posture, telegram_active, last_domain)`.
On a genuine human turn: counter += 1 (atomic persisted write). When counter
reaches a multiple of 10, or on session-start with a stale-but-nonzero
counter: emit refresh block = master digest + next domain by key — FOCUS →
technical-empathy lane only (humor/grace suppressed); MOBILE (Telegram-active
+ bridge AWAY) → concise lane, no IDE modes; FRAGMENTED/NORMAL → wheel advance
excluding `last_domain` (no immediate repeats); cold boot (no samples) →
NORMAL path. Counter reset to 0 only after a completed refresh. Internal
ReAct iterations, sub-agent cycles, and harness replays never touch the
counter; a dedicated test asserts 4 internal cycles leave it unchanged.

## Appendix D — Per-phase binding rows (P0–P6)

| Phase | Tier | Fleet | Commands | Exit gate |
|---|---|---|---|---|
| P0 contracts | `/code` → `/sync` | `architect`, `ponytail`, `tdd-workflow`, `test-guard`, `commit-commands` | phase slice + full `pytest` + `ruff` + `docs_guard.py` | contract table green, denylist byte-identical, checkpoint + commit |
| P1 bank | `/code` → `/sync` | `ponytail`, `pytest-skill`, `clean-code-guard`, `commit-commands` | miner + recall harness + full suite | 500 rows, floors met, 500/500 recall, commit |
| P2 counter | `/code` → `/sync` | `ponytail`, `tdd-workflow`, `test-guard`, `securing-agentic-ai-tool-invocation`, `commit-commands` | crash matrix + rotation matrix + suite | kill-proof counter, posture matrix green, commit |
| P3 router | `/code` → `/sync` | `ponytail`, `pytest-skill`, `clean-code-guard`, `commit-commands` | repair fixtures + slicing properties + suite | malformed corpus handled, sums closed, commit |
| P4 templates | `/code` → `/audit` → `/sync` | `ponytail`, `clean-code-guard`, `test-guard`, `securing-agentic-ai-tool-invocation`, `commit-commands` | tamper matrix + live smoke + `security_gate.py` | token verbatim, TTFT held, commit |
| P5 matrices | `/code` → `/audit` → `/sync` | `tdd-workflow`, `pytest-skill`, `test-guard`, `clean-code-guard`, `commit-commands` | hermetic-30 + live-10 + benchmark | CI green, diary pristine, commit |
| P6 coverage | `/audit` → `/sync` | `test-guard`, `clean-code-guard`, `commit-commands` | check-script + all gates | 98/90 green, commit |
