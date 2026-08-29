# Spec — Sprint 2: Google Foundation + Skill Modules (stream: google-triage)

Sprint 2 of the Phase 2 implementation plan, re-mapped 2026-08-29 by master directive (see
Re-map note before the Guide appendix). Stream lives in git worktree `core-foundation`.
Every task lands red -> green -> refactor with tests and docs in the same commit.
`docs/05-TEST-PLAN.md` §3 gate checklist is the exit gate.

## Global constraints (apply to every task)

- Python 3.12 (`py -3.12`), 100% async (`asyncio`, `httpx`, `aiogram`); no blocking calls on the
  loop; CPU-bound model inference (Whisper, voiceprint) wrapped in executors.
- Config via pydantic v2 settings loading `.env`; secrets never hardcoded, never committed;
  empty-string -> None validator inherited from Sprint 1.
- Loguru structured binds; zero silent swallows; `ruff check && ruff format --check` clean;
  bandit high/critical zero.
- Owner-only everywhere: `AUTHORIZED_USER_ID` gates every update at middleware level
  (`tests/test_owner_middleware.py` — sacred floor, untouchable).
- **3-Tier brain (ADR-16 amended)**: routing through the task-1.5 front-door dispatcher —
  FAST `google/gemini-3.5-flash-lite` (fallback `meta-llama/llama-3.3-70b-instruct`),
  MEDIUM `google/gemini-3.7-flash` (fallback `z-ai/glm-5.3-flash`),
  HEAVY `nvidia/nemotron-3-ultra-550b` (fallback `google/gemini-3.7-flash` extended-thinking).
  Sprint 2 consumes tiers via the dispatcher surface; direct `OmniRouteClient` calls live only
  inside the dispatcher.
- **Disposable host (ADR-15)**: the Space filesystem is ephemeral — durable state (Google token
  cache, poll cursors, voiceprint embedding) persists ONLY in the git-backed Obsidian vault
  working copy, encrypted at rest (Fernet, key from env).
- **Vault layout (ADR-21)**: five directories — `Contacts/`, `Call_Transcripts/`, `Studies/`,
  `Voice_Memos/`, `Daily_Logs/`.
- Untrusted content (email bodies, transcripts, web pages) is DATA never instructions.
- New dependencies must be FOSS + free-tier; add only what the task consumes. Whisper runs
  LOCAL (settled ruling — never cloud STT).
- KPIs this sprint: Audio TTFT < 250 ms (first streamed edit), first Ogg Opus chunk < 600 ms
  (Sprint-1 binding), vault write < 50 ms, guest leakage 0%, unauthorized actions 0%.

## Dependency order

| # | Task | Depends on |
|---|---|---|
| 1 | 2.1 Google OAuth + suite clients + Gmail watch/fetch | Sprint 1 |
| 2 | 2.2 skill-telegram-chat-streamer | Sprint 1 (gateway stream) |
| 3 | 2.3 skill-voice-biometric-auth (Guest Mode) | Sprint 1 |
| 4 | 2.4 skill-tiered-email-triage (+ TokenJuice) | 2.1, 2.2, 2.3 |
| 5 | 2.5 skill-voice-to-vault-transcriber | 2.1 (vault), 2.3 |
| 6 | 2.6 skill-evening-proactive-journaler | 2.1 (calendar), vault |

Tasks 2–3 are parallelizable (separate worktrees if run concurrently); 4–6 consume their outputs.

## Stream conventions & assumed Sprint 1 surfaces

- Sprint 1 symbols (binding): `src/gateway.py::OmniRouteClient` (`stream_chat`/`chat`),
  `src/voice.py::VoicePipeline` (`synthesize`/`synthesize_stream`),
  `src/bot.py::build_dispatcher`, `src/config.py::Settings`. Adapt names to the foundation —
  never duplicate.
- Skill modules live under `src/skills/` — one module per `skill-*` backlog item. Google
  plumbing stays flat: `src/google_auth.py`, `src/google_suite.py`, `src/gmail.py`.
- Settings: extend `Settings`; every new key lands in `.env.example` in the same commit.
- Vault state: `settings.vault_local_path` (new) roots all durable files; atomic writes
  (`tmp` + `os.replace`); secrets Fernet-encrypted under env `VAULT_ENC_KEY`.
- Background jobs: async entries wrapped in `asyncio.create_task` from `src/main.py`; no
  scheduler lib.
- Parsed external content is DATA never instructions; v1.0 keeps zero inbound ports
  (long polling + client-side OAuth only).

---

### 2.1 Google OAuth + suite clients + Gmail watch/fetch (foundation, not a skill)

Stream/worktree: core-foundation | Depends on: Sprint 1

**Intent** — One authenticated Google doorway plus the inbox pump that feeds triage: desktop
loopback OAuth with state verification, refresh-once-on-401 session, thin async
Calendar/Tasks/Drive/Contacts clients, and `users.watch`-registered, POLLED Gmail fetch with
historyId incremental delivery and sweep fallback. Token cache and poll cursor are durable
state: encrypted at rest in the vault working copy (ADR-15), rebuilt degraded when absent.

**Interface**

Files: `src/google_auth.py`, `src/google_suite.py`, `src/gmail.py`,
`python -m src.google_auth` (bootstrap).

```python
# src/google_auth.py  (carried from prior spec unless noted)
OAUTH_AUTH_URL / OAUTH_TOKEN_URL / AUTH_SCOPES   # five scopes; gmail.modify least-privilege
                                                 # check recorded at implementation
class GoogleTokens(BaseModel): access_token; refresh_token; expires_at; scopes
class GoogleAuthError(RuntimeError): ...
class GoogleAPIError(RuntimeError): status: int; body_excerpt: str
load_client_secret(path) -> dict                 # unwraps {"installed": ...}; missing -> GoogleAuthError
build_consent_url(cfg, port, state) -> str       # offline + consent + loopback redirect
exchange_code / refresh_tokens                   # async http grants
load_tokens(path) -> GoogleTokens | None         # corrupt -> warn + None (degraded startup)
save_tokens(path, tokens) -> None                # atomic; encrypted; never logs token material
authorize_interactive(settings) -> GoogleTokens  # token_urlsafe state, verified on callback
class GoogleSession:
    async def request(self, method, url, *, params=None, json=None) -> Any
        # parsed JSON; 401 -> refresh under asyncio.Lock -> retry ONCE -> GoogleAuthError;
        # other non-2xx -> GoogleAPIError(status, excerpt[:300])
```

**Vault-state rule (ADR-15)** — token cache at
`{vault_local_path}/State/google_token.json.enc`: JSON encrypted Fernet under env `VAULT_ENC_KEY`
(never plaintext on disk, never committed, never logged). Poll cursor + seen ids at
`{vault_local_path}/State/gmail_state.json` (no secrets; atomic writes; seen_ids truncated to
newest 2000). Missing/corrupt state -> warn + degraded rebuild via sweep. Inherited helper
contract: load/save are the ONLY state IO this sprint touches for Google.

`src/google_suite.py` (carried verbatim): `CalendarEvent`, `TaskItem`, `DriveFile`, `Contact`
models; `GoogleSuite(session, calendar_id="primary")` with `list_events`, `create_event`,
`list_tasks`, `add_task`, `list_drive_files`, `search_contacts`.

```python
# src/gmail.py
class EmailMessage(BaseModel):
    id: str; thread_id: str; from_email: str; from_name: str; subject: str
    body_text: str                      # capped at triage_body_max_chars
    received_at: datetime; labels: list[str]
    has_attachments: bool = False
    list_unsubscribe: bool = False      # set by parse_message from headers
class GmailState(BaseModel): seen_ids: list[str] = []; history_id: str | None = None
class GmailInbox:
    async def watch(self) -> bool       # topic configured ? register : False (info)
    async def fetch_new(self) -> list[EmailMessage]   # Lock-serialized
    async def unread_digest(self) -> tuple[int, int]
    @staticmethod parse_message(payload: dict, max_chars: int) -> EmailMessage  # PURE
async def run_gmail_poll(inbox, dispatcher, classifier, settings) -> None
```

Settings keys (new): `vault_local_path: Path = ./vault`; RETIRED: `google_token_json`,
`google_state_json` (superseded by vault paths). Carried: `gmail_pubsub_topic=""`,
`gmail_poll_seconds=120`, `gmail_sweep_days=2`, `triage_body_max_chars=8000`.

**Behavior** — OAuth: consent URL carries all five scopes + offline + consent + loopback
redirect; `state` generated via `secrets.token_urlsafe` and verified on callback; proactive
refresh single-flight under `asyncio.Lock`; bootstrap documented for the owner PC (RUNBOOK),
token file then synced into the vault State dir. Gmail: watch registered when topic configured
(free; keeps the v1.1 webhook option open), delivery is POLLING — historyId incremental
(messagesAdded minus SENT) with `is:unread newer_than:{N}d` sweep fallback on missing cursor or
historyIdNotFound; dedupe on message id. **Dispatch-then-mark**: seen state persists ONLY after
dispatch completes — a crash between fetch and dispatch re-delivers next cycle instead of
losing mail. `parse_message`: recursive parts walk, text/plain preferred, HTML strip fallback,
urlsafe_b64decode, truncation marker, safe defaults for missing Date/From/Subject
(«بدون عنوان»), `list_unsubscribe` from headers.

**Acceptance criteria**

1. AC1 — Consent URL carries all five scopes + offline + consent + loopback, AND cryptographic
   state verified on callback. → `tests/test_google_clients.py::test_consent_url_contains_scopes`
   (+ `::test_oauth_state_verified`)
2. AC2 — 401 -> refresh grant used, retried exactly once, cache rewritten; token cache
   round-trips ENCRYPTED at rest (no plaintext bytes on disk, Fernet under VAULT_ENC_KEY).
   → `test_refresh_on_401_reuses_refresh_token_and_retries_once` (+ `::test_token_cache_encrypted_at_rest`)
3. AC3 — historyId incremental then sweep fallback (historyIdNotFound simulated); overlapping
   fetches dedupe on message id. → `tests/test_gmail_watch.py::test_history_incremental_then_sweep_fallback`
   (+ `::test_fetch_new_dedupes_on_message_id`)
4. AC4 — Dispatch-then-mark crash window: simulated dispatch failure => next fetch_new
   re-delivers the message. → `test_dispatch_failure_redelivers_next_cycle`

**Error modes** — corrupt secret -> loud abort; corrupt token cache -> warn + degraded rebuild
(re-consent via RUNBOOK); revoked grant -> GoogleAuthError instructing re-bootstrap, no infinite
retry; network errors wrapped in GoogleAPIError chained; poll-loop API errors logged, loop
continues (Retry-After honored); unparseable payload -> safe defaults + marked seen; watch
failure -> warning, polling unaffected.

**Zero-cost check** — Google REST over installed `httpx`; free consumer quotas; watch free.
New dep: `cryptography` (BSD, Fernet only). $0.00.

**Docs impact** — `.env.example` vault-state block (VAULT_ENC_KEY, VAULT_LOCAL_PATH) + revised
Google block; RUNBOOK bootstrap + vault-state sections; ARCHITECTURE §4 (watch+polled delivery,
webhook deferred v1.1); TEST-PLAN catalog rows `test_google_clients.py` / `test_gmail_watch.py`;
CHANGELOG.

---

### 2.2 skill-telegram-chat-streamer

Stream/worktree: core-foundation | Depends on: Sprint 1 (gateway `stream_chat`)

**Intent** — Replace the Sprint-1 one-shot aggregated reply with progressive delivery: the owner
sees words as they generate — a placeholder send immediately, first real edit fired on the first
streamed delta (<250 ms Audio TTFT KPI), then coalesced edits until the final text. A new owner
message cancels the in-flight stream so the front door never queues behind a long answer.

**Interface**

```python
# src/skills/telegram_chat_streamer.py
PLACEHOLDER_AR: Final[str]   # «…»
class ChatStreamer:
    def __init__(self, bot, chat_id, *, edit_interval_ms: int = 750)
    async def stream_reply(self, deltas: AsyncIterator[str],
                           cancel: asyncio.Event) -> str   # returns final text
```

Settings keys (new): `stream_edit_interval_ms=750`, `stream_placeholder` (constant, not config).

**Behavior** — On invocation: send the placeholder once. First non-empty delta -> immediate
`edit_message_text` (TTFT measured stream-start -> first edit). Deltas coalesce on the interval
(≈1.3 edits/s max — never a flood limit); if generation completes before the first interval
elapses, skip intermediate edits entirely and send the final text as one edit. Final edit uses
the completed text verbatim. `parse_mode` unset — plain-text ruling from Sprint 1 holds;
MarkdownV2 lives only in triage templates. Owner interjection: the dispatcher signals `cancel`;
the streamer stops consuming, leaves received text in the bubble, and the newer update is
handled normally. Mid-stream gateway failure -> APOLOGY_AR + error log; already-delivered text
stays.

**Acceptance criteria**

5. AC5 — Scripted deltas: first edit lands <250 ms after stream start; subsequent edits coalesced
   within the interval; final bubble text exact. →
   `tests/test_chat_streamer.py::test_first_edit_within_250ms_ttfb`; owner interjection cancels
   cleanly with partial text preserved. → `::test_owner_interjection_cancels_stream`

**Error modes** — edit rate-limited -> warn + double the interval for the rest of the stream;
placeholder send failure -> fall back to Sprint-1 aggregate behavior; stream exception ->
apology, delivered text preserved, no silent swallow.

**Zero-cost check** — native Bot API sends/edits; zero new deps. $0.00.

**Docs impact** — ARCHITECTURE §1 progressive-streaming wording + TTFT KPI; RUNBOOK latency
smoke extended (first-edit timing); TEST-PLAN row `test_chat_streamer.py`; CHANGELOG.

---

### 2.3 skill-voice-biometric-auth (Guest Mode)

Stream/worktree: core-foundation | Depends on: Sprint 1

**Intent** — Voice notes get a second trust factor beyond the ID gate: an ECAPA-TDNN-class
speaker embedding matched on CPU in <50 ms. Owner voice -> normal service. Non-owner voice ->
Guest Mode: warm Jordanian lockdown with zero privileged side effects. Hardens the
"guest leakage 0%" KPI without weakening middleware (the owner ID gate stays authoritative).

**Interface**

```python
# src/skills/voice_biometric_auth.py
class VoiceprintError(RuntimeError): ...
class VoiceBiometrics:
    def __init__(self, *, embedding_path: Path, threshold: float = 0.75, executor) -> None
    @property enrolled -> bool
    async def enroll(self, ogg_opus: bytes) -> None   # owner /enroll-voice flow; Fernet-persist
    async def verify(self, ogg_opus: bytes) -> bool   # <50 ms CPU via executor
GUEST_LOCKDOWN_AR: Final[str]   # «يا هلا، الصوت مش صوت عمر... مين بيحكي معي؟»
```

Settings keys (new): `voiceprint_threshold=0.75`, `voiceprint_model` (FOSS speaker-verification
model; exact lib pinned at implementation, py3.12 wheel-verified), embedding file at
`{vault_local_path}/State/owner_voiceprint.enc` (Fernet under VAULT_ENC_KEY).

**Behavior** — Verify: Ogg Opus -> PCM via ffmpeg (in-memory) -> embedding on the CPU executor
(model loaded once at startup) -> cosine similarity vs stored owner embedding. Rulings:
- Unenrolled -> middleware-only trust (info log); enrollment is opt-in hardening via
  `/enroll-voice` (one owner voice note).
- Enrolled + match >= threshold -> owner-voice path.
- Enrolled + below threshold, OR verification exception when enrolled -> Guest Mode (fail-closed).

Guest Mode: reply `GUEST_LOCKDOWN_AR`, store exactly ONE staging note
`{vault_local_path}/State/guest_inbox/YYYY-MM-DDTHHMM.json` (raw transcript placeholder + timestamps)
and NOTHING else — no gateway calls carrying personal context, no whitelist, no PC actions, no
vault writes beyond staging. `tests/test_guest_lockdown.py` JOINS the sacred floor
(`test_owner_middleware.py`, `test_whitelist_guardrail.py`).

**Acceptance criteria**

6. AC6 — Enrolled + mismatched voice: lockdown reply sent, exactly one staging note, ZERO
   privileged calls (gateway/whitelist/subprocess/vault-CRUD spies assert uncalled).
   → `tests/test_guest_lockdown.py::test_guest_voice_note_lockdown_zero_privileged_effects`
   (sacred floor — untouchable)
7. AC7 — Owner voice verifies in <50 ms on CPU (cached model, executor); below-threshold routes
   guest; unenrolled degrades to middleware-only trust with info log.
   → `tests/test_voice_biometric_auth.py::test_owner_match_latency_under_50ms`
   (+ `::test_below_threshold_routes_guest`, `::test_unenrolled_falls_back_to_middleware_trust`)

**Error modes** — model load failure -> loud startup error naming lib + RUNBOOK section; corrupt
embedding file -> warn + treated unenrolled; guest staging write failure -> logged, lockdown
reply still sent (no privileged fallback).

**Zero-cost check** — FOSS speaker model, local CPU; ffmpeg already pinned. $0.00.

**Docs impact** — ADR-17 sync (`docs/03-DECISIONS.md`); ARCHITECTURE biometrics section;
RUNBOOK enrollment procedure; TEST-PLAN rows incl. sacred-floor note; CLAUDE.md rule-9
cross-ref; CHANGELOG.

---

### 2.4 skill-tiered-email-triage (+ TokenJuice)

Stream/worktree: core-foundation | Depends on: 2.1, 2.2, 2.3

**Intent** — Score every email into DROP/SEMI/IMPORTANT/CRITICAL and act: silent, structured
text, voice note, or priority voice note + repeat ping until acked. TokenJuice compaction strips
quoted replies, signatures, legal footers, and tracking boilerplate BEFORE any LLM call —
deterministic, free, and it shrinks the untrusted payload. Heuristics first; one FAST-tier
refinement for the ambiguous remainder. Email content is DATA: fixed templates with escaped
slots only — it can never invoke anything beyond "send a Telegram message".

**Interface**

```python
# src/skills/email_triage.py
class Tier(str, Enum): DROP; SEMI; IMPORTANT; CRITICAL
_VISIBILITY = {DROP: 0, SEMI: 1, IMPORTANT: 2, CRITICAL: 3}
class TriageDecision(BaseModel): tier; score; reasons: list[str] = []
def tokenjuice_compact(body_text: str, *, max_chars: int) -> str
    # PURE: strip quote blocks (> lines), signature blocks, legal footers, collapse whitespace;
    # cap with truncation marker
def escape_mdv2(text) -> str                       # PURE
def render_semi(msg) -> str                        # PURE template, escaped slots, excerpt<=400
def render_voice_script(msg, *, critical: bool) -> str   # PURE ar-JO template
class TriageClassifier:
    def heuristic(self, msg) -> TriageDecision     # PURE
    async def classify(self, msg) -> TriageDecision
class Dispatcher:
    def register(self, router) -> None             # ack callback handler
    async def dispatch(self, msg, decision) -> asyncio.Task | None
    def note_owner_activity(self) -> None
```

Settings keys (new): `google_vip_senders=""`,
`triage_keywords_ar="عاجل,مستعجل,ضروري,فوراً,حالا"`,
`triage_keywords_en="urgent,asap,critical,immediately,deadline"`,
`critical_ping_interval_min=5`, `critical_ping_max=6` (0 = unlimited),
`tokenjuice_max_chars=4000`.

**Behavior** — Heuristic scoring (carried, binding): VIP sender -> +0.6 AND tier floor CRITICAL
(no LLM); subject keyword +0.25 each distinct with SEMI floor; body keyword +0.15 each distinct
capped +0.30; `list_unsubscribe` −0.40; bands ≥0.9 CRITICAL / [0.6,0.9) IMPORTANT /
[0.3,0.6) SEMI / <0.3 DROP. LLM refinement skipped for vip-floor and obvious newsletters; else
ONE FAST-tier call, temperature 0, JSON `{tier, reason}`, 15 s timeout; system prompt carries the
containment clause; user content wrapped between `<<<EMAIL_DATA>>>` and `<<<END_EMAIL_DATA>>>`.
Merge = higher visibility of heuristic vs LLM (rescue upward, never silence downward). Invalid
JSON/timeout/exception -> heuristic alone; brain outage -> heuristic-only dispatch (fail toward
visibility). TokenJuice output feeds BOTH heuristic scoring and the LLM call. Dispatch: DROP ->
info log; SEMI -> MarkdownV2 text; IMPORTANT -> voice script -> `VoicePipeline.synthesize` ->
`answer_voice` (text fallback on failure); CRITICAL -> priority voice note + ping loop every
`critical_ping_interval_min` with «تم الاطلاع» ack button, stopped by ack /
`note_owner_activity` / `critical_ping_max` (0 = unlimited). In-memory ping state; restart
cancels pings — digest still surfaces the mail (honest ceiling).

**Acceptance criteria**

8. AC8 — TokenJuice: fixture with quoted reply + signature + legal footer compacts while
   keywords survive; VIP floor CRITICAL with brain mock uncalled; injection body produces a
   byte-identical template outside the EMAIL_DATA markers and an AST scan of
   `src/skills/email_triage.py` finds NO bridge/subprocess/os.system/socket reference.
   → `tests/test_email_triage.py::test_tokenjuice_strips_before_llm`
   (+ `::test_heuristic_vip_sender_is_critical`,
   `::test_injection_body_cannot_trigger_pc_actions`)

Carried-over prior-spec internals remain binding and land in the TEST-PLAN catalog (not the
10-AC sprint frame): keyword weights/bands (`test_heuristic_keyword_weights_and_bands`),
newsletter drop (`test_bulk_newsletter_drops_without_llm`), merge rule
(`test_llm_merge_never_downgrades`), LLM failure fallback
(`test_llm_failure_falls_back_to_heuristics`), prompt containment
(`test_llm_prompt_wraps_body_as_data`), dispatch matrix (`test_dispatch_*`), ping lifecycle
(`test_ping_loop_stop_conditions`), Markdown escaping (`test_markdown_injection_escaped`).

**Error modes** — brain outage -> heuristic-only, mail still dispatched; out-of-schema LLM tier
-> parse failure -> fallback; Telegram send failure -> error log + single plain-text retry;
persistent failure leaves mail visible in digest; empty excerpts handled gracefully.

**Zero-cost check** — ≤1 FAST-tier call per non-obvious email via free pools; TokenJuice
pure-python; buttons/voice native-free. $0.00.

**Docs impact** — ARCHITECTURE §4 (TokenJuice step + tier matrix); `.env.example` VIP/keywords/
ping block; TEST-PLAN rows; RUNBOOK (edit VIP/keyword lists); CHANGELOG.

---

### 2.5 skill-voice-to-vault-transcriber

Stream/worktree: core-foundation | Depends on: 2.1 (vault), 2.3 (voice gate)

**Intent** — Inbound owner voice note -> LOCAL Whisper transcription (settled ruling — never
cloud STT) -> YAML-frontmatter markdown note filed to `Voice_Memos/` (ADR-21). Runs only after
the 2.3 biometric gate passes; guest voice never reaches this module.

**Interface**

```python
# src/skills/voice_to_vault_transcriber.py
class TranscriberError(RuntimeError): ...
class VoiceToVault:
    def __init__(self, *, model_size: str, compute_type: str, executor, vault_dir: Path) -> None
    async def transcribe(self, ogg_opus: bytes) -> str    # whisper on CPU executor
    async def file_note(self, text, *, received_at, duration_s: float,
                        source: str = "telegram-voice") -> Path
    # writes Voice_Memos/YYYY-MM-DD-HHMM.md: YAML frontmatter (date, source, duration_s) + body
```

Settings keys (new): `whisper_model_size="small"`, `whisper_compute_type="int8"`,
`voice_memos_dir="Voice_Memos"`. Dep: `faster-whisper` (MIT).

**Behavior** — Download via Bot API -> ffmpeg decode to 16 kHz mono WAV in-memory ->
faster-whisper inference on the CPU executor (model cached in the container layer; first-run
download is the RUNBOOK warmup step) -> Arabic/Latin text. Note frontmatter: `date` (ISO with
`+03:00`), `source`, `duration_s`. Atomic write to the vault working copy (<50 ms target after
transcription). Transcribed text then enters the standard owner-text pipeline — tier selection
(HEAVY for long memos) is the task-1.5 dispatcher's decision, never this module's.

**Acceptance criteria**

9. AC9 — Owner voice note -> stubbed-whisper deterministic text -> YAML-frontmatter note lands
   in `Voice_Memos/` with correct frontmatter; ZERO outbound STT network calls asserted.
   → `tests/test_voice_to_vault_transcriber.py::test_voice_note_transcribed_to_local_whisper_vault_note`
   (+ `::test_no_cloud_stt_calls`)

**Error modes** — model missing at startup -> loud error naming the RUNBOOK warmup command;
empty transcription -> note still filed with `(empty)` body + warn; ffmpeg decode failure ->
TranscriberError chained; vault write failure -> logged + retried once, never blocks the reply.

**Zero-cost check** — faster-whisper (MIT) local CPU; ffmpeg local. $0.00.

**Docs impact** — ARCHITECTURE voice-to-vault leg; RUNBOOK Whisper warmup; ADR note (local
Whisper settled); TEST-PLAN row; CHANGELOG.

---

### 2.6 skill-evening-proactive-journaler

Stream/worktree: core-foundation | Depends on: 2.1 (calendar), vault

**Intent** — Sara closes the owner's day: a daily activity ledger note plus ONE proactive
evening check-in inside a randomized 18:00–19:30 window (natural, never robotic), skipped or
degraded when the calendar shows the owner busy. Zero LLM in the hot path — template plus
collected facts.

**Interface**

```python
# src/skills/evening_journaler.py
class LedgerData(BaseModel): events; tasks_done; critical_mail_count; memos_filed
class EveningJournaler:
    def __init__(self, suite, bot, chat_id, settings, vault_dir: Path) -> None
    def pick_slot(self, now: datetime) -> datetime   # uniform-random in [18:00, 19:30) Asia/Amman
    async def collect(self, now: datetime) -> LedgerData
    def render_ledger(self, data: LedgerData) -> str  # PURE Arabic template
    async def run_forever(self) -> None               # sleep-loop; calendar-guarded; once/day
```

Settings keys (new): `journaler_window_start="18:00"`, `journaler_window_end="19:30"`,
`journaler_enabled=true`, `daily_logs_dir="Daily_Logs"`. State:
`{vault_local_path}/State/journaler.json` (`last_ledger_date`, `last_checkin_sent`).

**Behavior** — Slot rerolled daily via `random.uniform` over the window (Asia/Amman). At slot:
calendar busy-check — if the owner is booked through the window, skip the check-in message but
STILL write the ledger. Check-in: short Jordanian prompt referencing the day (tasks due, critical
mail count, memos filed) + one open question. Ledger `Daily_Logs/YYYY-MM-DD.md`: YAML frontmatter
(`date`, `checkin_sent`) + sections Calendar / Mail / Voice memos / Notes; written once per local
day — a same-day second run appends a corrigenda line instead of duplicating. Send failure does
NOT persist `last_checkin_sent` (retried next loop tick — at-most-once per successful send).

**Acceptance criteria**

10. AC10 — Slot lands inside [18:00, 19:30) local and is calendar-guarded (busy -> no message,
    ledger still written); ledger file created exactly once per local day.
    → `tests/test_evening_journaler.py::test_checkin_window_randomized_calendar_guarded`
    (+ `::test_daily_ledger_created_once`)

**Error modes** — section source failure -> «غير متوفر حالياً» degradation, ledger still lands;
invalid window strings -> loud settings failure; missing tz key -> UTC fallback + warning; loop
survives exceptions (logged, never wedged).

**Zero-cost check** — stdlib scheduling only (`zoneinfo` + `asyncio.sleep`); free quotas; one
Telegram message/day. $0.00.

**Docs impact** — `.env.example` journaler block; RUNBOOK schedule config; ARCHITECTURE
proactive section; TEST-PLAN row `test_evening_journaler.py`; CHANGELOG.

---

## Skill ingestion (Sprint 2)

Upstream skills ingested into `.claude/skills/` BEFORE implementation begins (they shape the
code; they never ship as runtime deps):

| Skill | Source | Purpose this sprint |
|---|---|---|
| tdd | mattpocock/skills | red->green->refactor discipline for every task above |
| diagnosing-bugs | mattpocock/skills | triage method for Gmail/poll and streaming edge failures |
| clean-code-guard | guard-skills (amElnagdy) | pre-gate review pass on each module |
| test-guard | guard-skills (amElnagdy) | AC->pytest mapping completeness check |
| selected dispatch/streaming helpers | everything-claude-code (worldflowai) | progressive-edit + cancellation patterns for 2.2 |

Binding rule: skills are consulted during implementation and wiped at sprint exit — never
imported by `src/`, never added to `pyproject.toml`, never referenced at runtime.

## Teardown protocol (sprint exit)

1. Wipe `.claude/skills/*` (the ingested set above; harness-level skills outside the repo stay).
2. Keep all code, tests, docs; zero skill residue in `src/`
   (gate: `grep -r "claude/skills" src/` -> empty).
3. Record sprint results in `docs/10-CHECKPOINT.md` ledger (ACs green, gate evidence, carried
   questions).
4. `make gate` green AFTER teardown — proves zero skill dependency.

## Stream exit checklist

- [ ] `make gate` green (ruff, pytest with branch coverage on `src/` measured, bandit,
      docs-guard).
- [ ] AC1–AC10 demonstrably satisfied by the mapped tests above; carried-over prior-spec tests
      green and catalogued in `docs/05-TEST-PLAN.md`.
- [ ] Sacred floor intact: `tests/test_owner_middleware.py`, `tests/test_whitelist_guardrail.py`,
      `tests/test_guest_lockdown.py` untouched and green.
- [ ] `.env.example`, RUNBOOK, ARCHITECTURE, TEST-PLAN, BACKLOG ticks, CHANGELOG updated in the
      landing commits.
- [ ] Vault state confirmed durable-only (`vault/State/` gitignored or synced per ADR-15),
      secrets Fernet-encrypted at rest, `data/`-style plaintext state files GONE.
- [ ] Teardown protocol executed; `docs/10-CHECKPOINT.md` entry written.
- [ ] Manual live smoke (credential-gated): real owner voice -> streamed reply; simulated guest
      voice -> lockdown; one real Gmail message triaged E2E; one evening check-in received.

## Re-map note (2026-08-29, master directive)

This spec supersedes the 2026-08-26 Google-suite-only sprint-2 layout. Old tasks 2.1–2.4
(OAuth / Gmail / triage / daily brief) merge into 2.1 + 2.4; the master directive adds the four
skill modules — 2.2 chat streamer, 2.3 voice biometrics + Guest Mode, 2.5 voice-to-vault
transcriber, 2.6 evening journaler. The daily brief (old 2.4) leaves sprint scope; its facts are
absorbed by the evening journaler ledger (2.6). The AC frame is now sprint-wide (AC1–AC10)
instead of per-task; prior-spec tests that lost their AC number stay binding as TEST-PLAN
catalog rows. Token cache/state persistence moves from `data/` to encrypted vault State per
ADR-15. Guide dispositions below were adjudicated against the OLD layout and carry over where
the underlying behavior is unchanged (OAuth state/CSRF, refresh single-flight,
dispatch-then-mark, containment mechanics — all preserved above).

## Guide Review — Verdict: FIX (dispositions below; adjudicated 2026-08-26, carried 2026-08-29)

Reviewer: independent Guide agent, adversarial pass, 2026-08-26.

- **MAJOR — keyword weights contradicted matrix** ('URGENT' subject could DROP): RESOLVED —
  subject-hit tier floor added to scoring (now in 2.4).
- **MAJOR — List-Unsubscribe field didn't exist**: RESOLVED — `list_unsubscribe` on
  EmailMessage, populated by parse_message (now in 2.1).
- **MAJOR — crash window lost mail**: RESOLVED — dispatch-then-mark ordering + AC4 redelivery
  proof (now in 2.1).
- **MAJOR — containment ACs not runnable**: RESOLVED — twin-trace + AST surface scan (AC8);
  prompt containment mechanical (carried test).
- **MINOR — watch() dead scaffolding + expiry**: RESOLVED ruling — keep registration WITH
  renewal note OR drop entirely at implementation; decision recorded in stream commit.
- **MINOR — GoogleAPIError undeclared**: RESOLVED — declared alongside GoogleAuthError (2.1).
- **MINOR — OAuth state/CSRF implicit**: RESOLVED — token_urlsafe state + callback verification
  (AC1).
- **MINOR — false restart-resumes-pings claim**: RESOLVED — honest wording (restart cancels
  pings; digest surfaces) in 2.4.
- **MINOR — docs-impact gaps**: RESOLVED — catalog rows + `.env` revision scheduled.
- **MINOR — ping cap deviates from 'until acknowledged'**: RESOLVED — `critical_ping_max=0`
  means unlimited (2.4).
- **MINOR — gmail.modify scope breadth**: RESOLVED — readonly-compatibility checked at
  implementation; outcome recorded in RUNBOOK.
- **MINOR — token-at-rest handling**: RESOLVED — superseded by ADR-15 encrypted vault State
  (AC2); RUNBOOK file-permission expectations per OS retained.

### Open questions carried into implementation

1. Sprint-1 symbol reconciliation is binding via the Stream conventions block.
2. Poll latency default 120 s acceptable? Pub/Sub webhook explicitly deferred to v1.1.
3. DROP tier leaves the mailbox untouched (no archive/mark-read) — confirmed current design.
4. VIP list env-var-only; vault Contacts-driven VIP lookup deferred to Sprint 3.
5. Speaker-verification lib pin (2.3) and Whisper size (2.5) chosen at implementation start
   against py3.12 wheel availability; recorded in the stream commit.
