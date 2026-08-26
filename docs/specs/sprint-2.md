# Spec — Google Suite + Tiered Email Triage (stream: google-triage)

Stream/worktree: `google-triage` · Python 3.12 · 100% async · pydantic v2 settings · loguru
structured (no silent swallows) · ruff clean · TDD red→green→refactor · owner-only everywhere ·
parsed external content is DATA never instructions · v1.0 has NO live calls (critical triage =
priority voice note + repeat ping).

## Dependency order

| Order | Task | Depends on |
|---|---|---|
| 1 | 2.1 Google OAuth bootstrap + Calendar/Tasks/Drive/Contacts clients | Sprint 1 (`src/config.py`, `httpx`) |
| 2 | 2.2 Gmail watch + fetch | 2.1 |
| 3 | 2.3 Triage classifier + dispatcher | 2.1, 2.2, Sprint 1 TTS + brain clients |
| 4 | 2.4 Daily brief composer | 2.1, 2.2, 2.3 |

## Stream conventions & assumed Sprint 1 surfaces

- Settings: extend `src/config.py::Settings`; every new key lands in `.env.example` same commit.
- **Sprint 1 symbol contract (reconciled per Guide):** brain client is `src/gateway.py::OmniRouteClient`
  (`stream_chat`/`chat`), voice pipeline is `src/voice.py::VoicePipeline.synthesize(text) -> bytes`
  (Ogg Opus bytes), bot wiring via `src/bot.py::build_dispatcher`. Adapt names to the foundation
  spec — never duplicate.
- Background jobs: async entries wrapped in `asyncio.create_task` from `src/main.py`; no scheduler lib.
- Persistence: no database. Token/triage state are gitignored JSON under `data/`, atomic writes
  (`tmp` + `os.replace`). Single owner, single process.
- Library stance: **zero new dependencies** — Google REST over installed `httpx`. The synchronous
  `google-api-python-client` stack is rejected.

---

### 2.1 Google OAuth bootstrap + Calendar/Tasks/Drive/Contacts clients

Stream/worktree: `google-triage` | Depends on: Sprint 1

**Intent** — One authenticated doorway to the owner's Google account plus thin async clients for
the four services Sara needs. Desktop OAuth with loopback redirect; refresh token cached and
reused across restarts (proven by test); one `GoogleSession` that attaches the bearer token,
refreshes proactively under a lock, and silently refreshes once on 401 before retrying. Services
are flat method bags returning pydantic models — no SDK hierarchy.

**Interface**

Files: `src/google_auth.py`, `src/google_suite.py`, `python -m src.google_auth` (bootstrap).

```python
# src/google_auth.py
OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.modify",   # least-privilege check pending (see review)
]
class GoogleTokens(BaseModel):
    access_token: str | None = None; refresh_token: str | None = None
    expires_at: float = 0.0; scopes: list[str] = []
class GoogleAuthError(RuntimeError): ...
class GoogleAPIError(RuntimeError):            # declared (Guide amendment)
    status: int; body_excerpt: str
def load_client_secret(path) -> dict           # unwraps {"installed": {...}}; missing -> GoogleAuthError
def build_consent_url(cfg, port, state) -> str # offline access_type, prompt=consent, loopback redirect
async def exchange_code(http, cfg, code, port) -> GoogleTokens
async def refresh_tokens(http, cfg, tokens) -> GoogleTokens
def load_tokens(path) -> GoogleTokens | None   # corrupt -> warn + None (never raises into startup)
def save_tokens(path, tokens) -> None          # atomic tmp+os.replace; best-effort chmod 600; never logs token material
async def authorize_interactive(settings) -> GoogleTokens
class GoogleSession:
    def __init__(self, settings, http=None)
    async def request(self, method, url, *, params=None, json=None) -> Any
        # parsed JSON; 401 -> refresh -> retry ONCE -> GoogleAuthError; other non-2xx -> GoogleAPIError
```

Models in `src/google_suite.py`: `CalendarEvent(id, summary, start, end, location?, description?)`,
`TaskItem(id, title, due?, notes?, completed=False)`, `DriveFile(id, name, mime_type, modified_time?)`,
`Contact(resource_name, display_name, email?)`. `GoogleSuite(session, calendar_id="primary")` with
`list_events(start,end)`, `create_event(...)`, `list_tasks(...)`, `add_task(...)` ,
`list_drive_files(query?, page_size=25)`, `search_contacts(query, page_size=10)`.

New settings keys: `google_token_json: Path = ./data/google_token.json`.

**Behavior** — Bootstrap runs on a browser machine (VPS headless: runbook documents running it on
the owner PC and copying the token file). Ephemeral loopback listener; consent URL printed;
**`state` parameter generated via `secrets.token_urlsafe` and verified on callback (CSRF — Guide
amendment, folded into AC2)**; exchange yields access + refresh token; atomic save. Runtime:
proactive refresh when `expires_at - 60s < now` under an `asyncio.Lock` (single flight); any 401
mid-session refreshes and replays exactly once. Datetimes normalized to tz-aware UTC.

**Acceptance criteria**

1. AC1 — Missing client secret → actionable `GoogleAuthError` naming path + runbook section. → `tests/test_google_clients.py::test_load_client_secret_missing_raises_actionable`
2. AC2 — Consent URL carries all five scopes, offline, consent, loopback redirect, AND cryptographic state verified on callback. → `test_consent_url_contains_scopes` (+ `::test_oauth_state_verified`)
3. AC3 — 401 → refresh grant used, retried exactly once, cache rewritten with new expires_at. → `test_refresh_on_401_reuses_refresh_token_and_retries_once`
4. AC4 — Fixture responses parse into typed models incl. datetime normalization (calendar/tasks/drive/contacts). → `test_calendar_list_parses_fixture`, `::test_tasks_crud_shapes`, `::test_drive_list_parses_fixture`, `::test_contacts_search_parses_fixture`
5. AC5 — Non-2xx → `GoogleAPIError(status, excerpt[:300])`, nothing swallowed. → `test_non2xx_raises_google_api_error_with_excerpt`
6. AC6 — Proactive refresh single-flight (concurrent callers → exactly one token POST). → `test_proactive_refresh_single_flight`

**Error modes** — corrupt secret → loud abort; corrupt token cache → warn + treated absent (degraded startup continues); revoked grant → GoogleAuthError instructing re-bootstrap, no infinite retry; network errors wrapped in GoogleAPIError chained.

**Zero-cost check** — zero new deps; free consumer quotas only. $0.00.

**Docs impact** — `.env.example` GOOGLE_TOKEN_JSON block; RUNBOOK "Google OAuth bootstrap" section (console project, five APIs, consent screen test-user, download JSON, run module, copy token file); CHANGELOG.

---

### 2.2 Gmail watch + fetch

Stream/worktree: `google-triage` | Depends on: 2.1

**Intent** — Inbox → typed, deduplicated `EmailMessage` stream for triage. Gmail `users.watch`
registered once at startup (free; keeps push option open), consumed by POLLING — historyId
incremental with query-sweep fallback — so v1.0 keeps its zero-inbound-ports posture. Tiny JSON
state file prevents re-triage across restarts. True Pub/Sub webhook = public HTTPS = deferred to
v1.1 (recorded).

**Interface** — `src/gmail.py`

```python
class EmailMessage(BaseModel):
    id: str; thread_id: str; from_email: str; from_name: str; subject: str
    body_text: str                      # capped at triage_body_max_chars
    received_at: datetime; labels: list[str]
    has_attachments: bool = False
    list_unsubscribe: bool = False      # Guide amendment: real field, set by parse_message
class GmailState(BaseModel):
    seen_ids: list[str] = []            # truncated to newest 2000 on save
    history_id: str | None = None
class StateStore: ...                   # load (corrupt -> *.corrupt rename + fresh), save (atomic)
class GmailInbox:
    async def watch(self) -> bool       # topic configured ? register : False(info)
    async def fetch_new(self) -> list[EmailMessage]   # Lock-serialized
    async def unread_digest(self) -> tuple[int, int]
    @staticmethod parse_message(payload: dict, max_chars: int) -> EmailMessage  # PURE
async def run_gmail_poll(inbox, dispatcher, classifier, settings) -> None
```

Settings keys: `gmail_pubsub_topic=""`, `gmail_poll_seconds=120`, `gmail_sweep_days=2`,
`google_state_json=./data/google_state.json`, `triage_body_max_chars=8000`.

**Behavior** — `fetch_new`: history.list path when cursor exists (messagesAdded minus SENT);
historyIdNotFound/expiry or no cursor → sweep `is:unread newer_than:{N}d`. Dedupe on message id.
**Dispatch-then-mark (Guide amendment): per-message seen state persists ONLY after dispatch
completes — a crash between fetch and dispatch re-delivers next cycle instead of losing mail.**
`parse_message`: recursive parts walk preferring text/plain; HTML fallback strip; urlsafe_b64decode;
truncation with marker; safe defaults for missing Date/From/Subject («بدون عنوان»); sets
`list_unsubscribe` from headers.

**Acceptance criteria**

1. AC1 — plain-text fixture parses fully. → `tests/test_gmail_watch.py::test_parse_message_plain_text_fixture`
2. AC2 — HTML-only strips + truncates. → `test_parse_message_html_fallback_strips_and_truncates`
3. AC3 — overlapping sweeps yield message exactly once. → `test_fetch_new_dedupes_on_message_id`
4. AC4 — history incremental then sweep fallback (incl. historyIdNotFound simulation). → `test_history_incremental_then_sweep_fallback`
5. AC5 — watch topic gating. → `test_watch_topic_gating`
6. AC6 — corrupt state recovers fresh. → `test_corrupt_state_recovers_fresh`
7. AC7 — concurrent fetch serialized. → `test_fetch_serialized_under_lock`
8. AC8 — **crash-window recovery**: simulated dispatch failure ⇒ next fetch_new re-delivers the message. → `test_dispatch_failure_redelivers_next_cycle`

**Error modes** — poll-loop API errors logged, loop continues (Retry-After honored); unparseable payload → defaults + marked seen (cannot poison loop); base64 failure skips part; watch failure → warning, polling unaffected.

**Zero-cost check** — no deps; Gmail free quotas dwarf a 120 s poll; Pub/Sub topic inside always-free tier (unused in v1.0). $0.00.

**Docs impact** — `.env.example` Gmail block; TEST-PLAN catalog row `test_gmail_watch.py`; ARCHITECTURE §4 footnote (watch+polled delivery, webhook deferred v1.1); CHANGELOG.

---

### 2.3 Triage classifier + dispatcher

Stream/worktree: `google-triage` | Depends on: 2.1, 2.2, Sprint 1 (brain, TTS, bot router)

**Intent** — Score each email into four tiers per ARCHITECTURE §4 and act: DROP silently, SEMI →
structured text, IMPORTANT → voice note, CRITICAL → priority voice note + repeat ping until acked.
Deterministic-first heuristics (VIP + urgency keywords + bulk signal); one FAST_MODEL refinement
for ambiguous remainder. Core invariant: email content is untrusted DATA selecting fixed templates
with escaped slots — it can never invoke anything beyond "send a Telegram message".

**Interface** — `src/email_triage.py`

```python
class Tier(str, Enum): DROP; SEMI; IMPORTANT; CRITICAL
_VISIBILITY = {DROP:0, SEMI:1, IMPORTANT:2, CRITICAL:3}
class TriageDecision(BaseModel): tier; score; reasons=[]
def escape_mdv2(text) -> str                     # PURE
def render_semi(msg) -> str                       # PURE template, escaped slots, excerpt<=400
def render_voice_script(msg, critical: bool) -> str  # PURE Arabic ar-JO template
class TriageClassifier:
    def __init__(self, settings, brain: OmniRouteClient)
    def heuristic(self, msg) -> TriageDecision    # PURE
    async def classify(self, msg) -> TriageDecision
class Dispatcher:
    def __init__(self, bot, chat_id, tts: VoicePipeline, settings)
    def register(self, router) -> None            # ack callback handler
    async def dispatch(self, msg, decision) -> asyncio.Task | None
    def note_owner_activity(self) -> None         # cancels ping loops (one-line hook in owner gate)
```

Settings keys: `google_vip_senders=""`, `triage_keywords_ar="عاجل,مستعجل,ضروري,فوراً,حالا"`,
`triage_keywords_en="urgent,asap,critical,immediately,deadline"`, `critical_ping_interval_min=5`,
`critical_ping_max=6` (**Guide amendment: 0 = unlimited**, so behavior matches §4's "until
acknowledged" without a doc deviation).

**Behavior — heuristic scoring (pure, fully enumerated)**

- VIP sender ∈ vip_senders → +0.6 AND **tier floor CRITICAL** (matrix: VIP ⇒ Critical, no LLM).
- Urgency keyword in SUBJECT → +0.25 each distinct; in BODY → +0.15 each distinct capped +0.30.
  **Guide amendment — subject floor**: any single subject-keyword hit floors the tier at SEMI
  minimum (matrix wording preserved: subject urgency cannot land in DROP; combined
  direct-request/VIP context floors at CRITICAL).
- `msg.list_unsubscribe` → −0.40 (bulk signal).
- Bands: ≥0.9 CRITICAL · [0.6,0.9) IMPORTANT · [0.3,0.6) SEMI · <0.3 DROP.

LLM refinement: skipped for vip-floor and for obvious newsletters (bulk & score<0.3); else ONE
FAST_MODEL call, temperature 0, JSON schema `{tier, reason}`, 15 s timeout. System prompt carries
containment clause; user content wraps metadata+body between `<<<EMAIL_DATA>>> … <<<END_EMAIL_DATA>>>`.
Merge rule: final = higher-visibility of heuristic vs LLM (rescue upward, never silence downward).
Invalid JSON/timeout/exception → warning + heuristic alone; brain-down degrades to pure heuristics
(fail toward visibility).

Dispatch: DROP → info log only. SEMI → MarkdownV2 text. IMPORTANT → voice script → synthesize →
send_voice (+ one-line text fallback if voice send raises). CRITICAL → priority voice note then
ping-loop task every N minutes with inline ack button «تم الاطلاع», stopping on
note_owner_activity / ack callback / critical_ping_max (0=unlimited). Ping ack state in-memory;
restart cancels pending pings — message remains visible via unread digest/brief (honest ceiling,
`# ponytail:` noted).

Containment mechanics: untrusted strings reach Telegram ONLY through escape_mdv2 in fixed
templates; Dispatcher depends solely on Bot/VoicePipeline/Settings; injection bodies produce
byte-identical template structure differing only in escaped slots.

**Acceptance criteria**

1. AC1 — VIP ⇒ CRITICAL regardless of content. → `tests/test_email_triage.py::test_heuristic_vip_sender_is_critical`
2. AC2 — keyword weights, distinct caps, band boundaries, AND subject-floor rule pinned. → `test_heuristic_keyword_weights_and_bands`
3. AC3 — bulk newsletter drops without LLM (brain mock uncalled). → `test_bulk_newsletter_drops_without_llm`
4. AC4 — merge rule never downgrades. → `test_llm_merge_never_downgrades`
5. AC5 — LLM failure paths fall back to heuristic. → `test_llm_failure_falls_back_to_heuristics`
6. AC6 — prompt containment, mechanically asserted: captured request byte-equal to fixed template outside the EMAIL_DATA markers. → `test_llm_prompt_wraps_body_as_data`
7. AC7 — dispatch matrix (drop/semi/important/critical call counts). → `test_dispatch_*`
8. AC8 — ping lifecycle stop conditions + interval. → `test_ping_loop_stop_conditions`
9. AC9 — containment, runnable form (Guide amendment): (a) injection-body email produces identical tier/dispatch trace as benign twin; (b) AST import-surface scan of `src/email_triage.py` finds NO reference to bridge/whitelist/subprocess/os.system/socket. → `test_injection_body_cannot_trigger_pc_actions`
10. AC10 — Markdown injection renders inert. → `test_markdown_injection_escaped`

**Error modes** — brain outage → heuristic-only, mail still dispatched; out-of-schema tier → parse failure → fallback; Telegram send failures → error log + single plain-text retry, persistent failure leaves mail visible in digest/brief; empty excerpts handled gracefully.

**Zero-cost check** — ≤1 FAST_MODEL call per non-obvious email via free pools; buttons/voice native-free. $0.00.

**Docs impact** — ARCHITECTURE §4 confirm Critical wording + fail-visible merge rule + containment note + documented escalation cap semantics; `.env.example` VIP/keywords/ping block; TEST-PLAN row extension; RUNBOOK (edit VIP/keyword lists); CHANGELOG. Scope check pending at implementation: whether `users.watch` accepts gmail.readonly (least-privilege downgrade recorded in runbook either way).

---

### 2.4 Daily brief composer

Stream/worktree: `google-triage` | Depends on: 2.1, 2.2, 2.3

**Intent** — One warm Jordanian-Arabic digest per day at `BRIEF_LOCAL_TIME` (Asia/Amman): today's
events, tasks due today, mail picture (unread counts + triage highlights). Deterministic template,
no LLM in hot path. Restart-safe fire-once-per-day loop.

**Interface** — `src/daily_brief.py`: `BriefData(events, tasks, unread_total, important_items)`;
`BriefComposer(suite, inbox, classifier, bot, chat_id, settings)` with `collect(now) -> BriefData`
(event window now..now+24h UTC; task due-window today; highlight cap 3 via heuristic, IMPORTANT+
only), `render(data, now) -> str` (PURE MarkdownV2 Arabic template, Amman times), `fire_if_due(now)
-> bool` (due when past brief time AND last_brief_date != today; disabled → False, zero calls),
`run_forever()`. Settings: `brief_local_time="07:30"`, `brief_enabled=true`; state adds
`last_brief_date` to GmailState. Fixed template sketch:

```
☀️ صباح الخير! موجز يوم {weekday d MMM}
📅 مواعيد اليوم ({n}): • {HH:mm–HH:mm} {summary}
✅ مهام مستحقة اليوم ({m}): • {title}
📥 البريد: {unread} غير مقروءة · مهمة: {imp} — أبرزها: «{subject}» من {sender}
```

**Acceptance criteria**

1. AC1 — render emits exact template structure, Amman-localized times, escaped dynamics. → `tests/test_daily_brief.py::test_render_template_with_fixtures`
2. AC2 — collect assembles BriefData from mocked clients (window bounds, cap, threshold). → `test_collect_from_mocked_clients`
3. AC3 — fires exactly once per local day; second same-day call no-op; next day fires again. → `test_fire_if_due_once_per_day`
4. AC4 — `brief_enabled=false` → zero calls. → `test_brief_disabled_sends_nothing`
5. AC5 — source failure degrades section («غير متوفر حالياً»), brief still sends, error logged. → `test_source_failure_degrades_section_not_brief`

**Error modes** — per-section isolation; send failure does NOT persist last_brief_date (retry same day — at-most-once per successful send); invalid time string → loud settings failure; missing tz key → UTC fallback + warning; loop survives exceptions.

**Zero-cost check** — stdlib scheduling only (zoneinfo + sleep); same free quotas; one Telegram msg/day. $0.00.

**Docs impact** — `.env.example` brief block; RUNBOOK schedule config + verify-via-state-file; TEST-PLAN row `test_daily_brief.py`; BACKLOG tick 2.4; CHANGELOG.

---

## Stream exit checklist

- [ ] `make gate` green (ruff, pytest ≥85% branch on `src/`, bandit, docs-guard).
- [ ] All backlog ACs demonstrably satisfied by mapped tests above.
- [ ] `.env.example`, RUNBOOK, ARCHITECTURE §4, TEST-PLAN catalog, BACKLOG ticks, CHANGELOG updated in landing commits.
- [ ] `data/*.json` and `config/google_oauth_client.json` confirmed gitignored.
- [ ] Manual live smoke (credential-gated): sandbox Gmail fixture triaged E2E; one real brief delivered.

---

## Guide Review — Verdict: FIX (dispositions below)

Reviewer: independent Guide agent, adversarial pass, 2026-08-26.

- **MAJOR — keyword weights contradicted matrix** ('URGENT' subject could DROP): RESOLVED — subject-hit tier floor added to scoring + AC2.
- **MAJOR — List-Unsubscribe field didn't exist**: RESOLVED — `list_unsubscribe` added to EmailMessage, populated by parse_message (AC fixtures updated).
- **MAJOR — crash window lost mail**: RESOLVED — dispatch-then-mark ordering + AC8 redelivery proof.
- **MAJOR — containment ACs not runnable**: RESOLVED — AC9 rewritten as twin-trace + AST surface scan; AC6 made mechanical (byte-equal outside markers).
- **MINOR — watch() dead scaffolding + expiry**: RESOLVED ruling — keep registration WITH renewal note OR drop entirely at implementation; 'trivial swap' rationale removed; decision recorded in stream commit.
- **MINOR — GoogleAPIError undeclared**: RESOLVED — declared alongside GoogleAuthError.
- **MINOR — OAuth state/CSRF implicit**: RESOLVED — token_urlsafe state + callback verification in Behavior + AC2.
- **MINOR — false restart-resumes-pings claim**: RESOLVED — corrected honest wording (restart cancels pings; digest still surfaces).
- **MINOR — docs-impact gaps**: RESOLVED — test-catalog rows + stale .env comment revision scheduled.
- **MINOR — ping cap deviates from 'until acknowledged'**: RESOLVED — `critical_ping_max=0` means unlimited; doc deviation eliminated.
- **MINOR — gmail.modify scope breadth**: RESOLVED — readonly-compatibility checked during implementation; outcome recorded in runbook.
- **MINOR — token-at-rest handling**: RESOLVED — RUNBOOK file-permission expectations per OS + no-token fast path (log once, idle until tokens appear).

### Open questions carried into implementation

1. Sprint-1 symbol reconciliation is now binding via the Stream conventions block above.
2. Poll latency default 120 s acceptable? Pub/Sub webhook explicitly deferred to v1.1.
3. DROP tier leaves mailbox untouched (no archive/mark-read) — confirmed current design.
4. Brief is text-only in v1.0; spoken variant not planned until requested.
5. VIP list env-var-only in v1.0; vault Contacts-driven VIP lookup deferred (avoids Sprint-3 dependency inversion).
