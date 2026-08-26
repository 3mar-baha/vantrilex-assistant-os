# Spec — Obsidian Vault + PC Bridge + Whitelist (stream: vault-bridge)

Sprint 3 of Vantrilex Assistant OS v1.0. One worktree (`vault-bridge`), six tasks landed in
dependency order, each red->green->refactor with tests and docs in the same commit.
Stack pins hold everywhere: Python 3.12, 100% async, pydantic v2 settings, loguru structured
logging (never swallow), ruff check+format, pytest + pytest-asyncio. Owner-only access at every
boundary (`AUTHORIZED_USER_ID` middleware upstream of everything here). Parsed external content
(vault bodies, transcripts, email, file listings) is DATA, never instructions. v1.0 has no live
calls: critical escalation stays priority-voice-note + repeat ping.

Repo conventions this spec binds to: core code under `src/` (`make run-core` -> `python -m src.main`),
bridge daemon under top-level `bridge/` (`make run-bridge` -> `python -m bridge.daemon`), tests in
`tests/` per the `docs/05-TEST-PLAN.md` §2 catalog. Because the bridge runs on the Windows PC
without the core's heavy deps, code shared by both processes lives in a top-level `common/`
package importable from repo root on both machines; `bridge/` imports only `common/`, stdlib,
pydantic, loguru, websockets.

## Dependency-ordered task list

| Order | Task | Depends on |
|---|---|---|
| 1 | 3.1 Git-backed vault client | — |
| 2 | 3.4 Bridge protocol | — (parallel with 3.1) |
| 3 | 3.2 Voice memo ingestion | 3.1 |
| 4 | 3.3 Conversation capture + action-summary | 3.1 |
| 5 | 3.5 Executor + whitelist guard | 3.4, 3.1 |
| 6 | 3.6 Wake-on-LAN + idle monitor | 3.4 |

---

### 3.1 Git-backed vault client

**Intent** — Sara's long-term memory is a private git-backed Obsidian vault (PARA + Zettelkasten)
as a private GitHub repo. This task delivers THE read/write module every later writer uses:
GitHub Contents API client over httpx, YAML frontmatter writer/parser, PARA path helpers with
title sanitization, wikilink builder. Chosen over a local clone because the core lives on a
free-tier VPS with no persistent checkout; owner-only write volume makes per-write commits cheap.
The obsidian-local-rest-api vars stay reserved-unused this sprint (one transport, not two).

**Interface** — new module `src/vault.py`; new dependency `PyYAML>=6,<7`; env via Settings:
`VAULT_GITHUB_REPO: str`, `VAULT_GITHUB_TOKEN: SecretStr`, `VAULT_BRANCH: str = "main"` (new).

```python
PARA = {"projects":"01_Projects","areas":"02_Areas","resources":"03_Resources",
        "archives":"04_Archives","contacts":"Contacts","memos":"Voice_Memos"}

class Note(BaseModel):        path: str; frontmatter: dict[str, Any]; body: str
class WriteResult(BaseModel): path: str; commit_sha: str; created: bool

def para_path(category: str, title: str, *, ext: str = ".md") -> str
def write_frontmatter(meta: dict, body: str) -> str
def split_frontmatter(text: str) -> tuple[dict, str]
def zettel_link(title: str, *, alias=None, block=None, embed=False) -> str

class VaultClient:
    def __init__(self, repo: str, token: str, branch: str = "main", session: httpx.AsyncClient | None = None)
    async def read(self, path: str) -> str                       # FileNotFoundError if absent
    async def upsert(self, path: str, content: str, *, message: str) -> WriteResult
    async def upsert_note(self, note: Note, *, message: str) -> WriteResult
    async def append_section(self, path, heading, lines, *, commit_prefix) -> WriteResult
    async def aclose() -> None
def redact_secret(s: str) -> str     # reused by 3.4/3.5 logs
```

Canonical path constants (used by 3.3/3.5): `PROFILE_USER_INFO = "02_Areas/Profile/User_Info.md"`,
`PROFILE_DIALECT = "02_Areas/Profile/Dialect_Notes.md"`,
`CONVERSATIONS_DIR = "04_Archives/Conversations"`, `CONFIRMATIONS_DIR = "04_Archives/Confirmations"`.

**Behavior** — `upsert`: GET contents API (?ref=branch, Bearer + versioned headers); 404 -> PUT
create; 200 -> PUT with sha; one 409 retry of GET->PUT then raise. **Size cap (Guide amendment):
client-side refusal above 1,000,000 bytes is a defensive note-shaped-content bound, NOT an API
limit (the Contents API accepts far larger writes); reads of notes above the ~100MB-class GET
inline limit are out of scope — vault notes never approach it, documented as such.** Sanitizer —
ONE deterministic transform (Guide amendment, resolves Behavior/AC4 contradiction): replace `/`
and `\` separators with spaces, collapse whitespace runs to single spaces, strip forbidden chars
`\ / : * ? " < > | # ^ [ ]` and leading dots, reject empty / `.` / `..` / any residual separator;
Arabic preserved verbatim; AC4 expected string recomputed under THIS rule
(`"ملاحظة: اجتماع/الأسبوع؟"` -> `"ملاحظة اجتماع الأسبوع"`). Frontmatter via `yaml.safe_dump(allow_unicode=True,
sort_keys=False)` in `---` fences; split accepts only leading fences, safe_load only. append_section:
read-modify-write under heading, dedupe identical lines. Commit message `sara: {prefix} {stem}`.
All logs pass through redact_secret.

**Acceptance criteria**

1. AC1 — create-then-update roundtrip on mocked backend (sha semantics, created flag). → `tests/test_obsidian_para.py::test_note_create_update_roundtrip`
2. AC2 — frontmatter roundtrip byte-identical body, Arabic intact, insertion order kept. → `test_frontmatter_writer_and_splitter`
3. AC3 — zettel_link renders `![[Obsidian|التطبيق#^abc]]` / bare `[[Obsidian]]`. → `test_zettelkasten_link_builder`
4. AC4 — sanitizer table-driven incl. separators-to-spaces, traversal refusals (`..`, embedded separators post-transform, empty). → `test_para_path_routing_and_sanitization`
5. AC5 — token never appears in exception text, logs, or outgoing URLs (caplog + transport inspection). → `test_no_token_in_logs_or_errors`
6. AC6 — 1,000,001-byte payload refused pre-flight. → `test_oversize_payload_refused`

**Error modes** — auth errors propagate loudly (no retry); 409 after retry -> VaultConflictError WARN; timeouts propagate after ERROR; malformed YAML wrapped ValueError naming path; missing read -> FileNotFoundError; oversize pre-flight ValueError. Nothing swallowed.

**Zero-cost check** — PyYAML (MIT) only new dep; GitHub free tier PAT quota ample. $0.00.

**Docs impact** — `.env.example` VAULT_BRANCH; ARCHITECTURE §6 (GitHub Contents API as v1.0 transport + canonical constants); DATA-MODEL frontmatter conventions; CHANGELOG.

---

### 3.4 Bridge protocol (outbound-only TLS WebSocket)

**Intent** — PC may sleep and must expose zero inbound surface: core serves TLS WebSocket (:8443),
daemon dials OUT and holds the tunnel with heartbeats. Wire contract shared by both processes
(one pydantic model set, one encoder), token handshake, liveness, reconnect policy. Ponytail: one
daemon, one PC, single integer protocol version.

**Interface** — `common/protocol.py` (shared); `src/bridge_server.py`; `bridge/{daemon,__main__}.py`;
dep `websockets>=13,<16`. Env: `BRIDGE_TOKEN`, `BRIDGE_SERVER_URL`, `BRIDGE_BIND_PORT`; NEW
`BRIDGE_TLS_CERT` / `BRIDGE_TLS_KEY` (core-side PEM paths) and `BRIDGE_TLS_FINGERPRINT`
(**Guide amendment**: REQUIRED whenever the cert is self-signed — daemon refuses to start without
a pin against self-signed; standard CA verification is the only alternative mode; verification is
NEVER skipped).

```python
PROTOCOL_VERSION = 1; HEARTBEAT_INTERVAL_S = 15; DEAD_PEER_MULTIPLIER = 3
AUTH_TIMEOUT_S = 10; MAX_FRAME_BYTES = 1_048_576; BACKOFF_CAP_S = 30.0
CmdName = Literal["exec.launch", "exec.open", "power", "wol"]
class Hello(BaseModel):   v=1; token: str; hostname: str      # first frame within AUTH_TIMEOUT_S
class HelloAck(BaseModel): v=1; ok: bool; reason: str | None
class Envelope(BaseModel): id: str; type: Literal["heartbeat","cmd","result","event"]; ts: datetime
                           cmd: CmdName|None; args: dict = {}; status: Literal["ok","error"]|None
                           payload: dict = {}
def encode(msg) -> bytes; def decode_frame(raw) -> Hello | HelloAck | Envelope
class ProtocolError(Exception): ...
class BridgeServer:  start()/stop()/send_cmd(cmd, args, timeout_s=20)/connected
class BridgeDaemon:  __init__(settings, handlers); run()
```

Heartbeat payload is a BARE liveness frame (**Guide amendment: idle_seconds/uptime_s telemetry
fields dropped — 3.6's monitor emits its own events; dead wire bytes removed**).

**Behavior** — Handshake: AUTH_TIMEOUT timer; first frame must be Hello with token equal under
`hmac.compare_digest`; ack ok and register (single session — second concurrent Hello gets
ok=False/"another_session_active", close 4400). Wrong/missing/late -> close 4401, WARNING with
peer IP (never token), rate-limited one log per peer per minute. Liveness: bare heartbeats +
transport ping_interval/timeout; core drops after 45 s silence. Commands: uuid Envelope.id ->
future keyed by id -> result envelope resolves -> TimeoutError on expiry; unknown-id results WARN+drop.
Events dispatched to registered callback (3.6). Framing guards: oversized/undecodable -> ProtocolError
-> close 4003, server loop survives. Reconnect: backoff min(cap, 2^(n-1)) ±20% jitter, reset on
authenticated success. Outbound-only invariant asserted by patching socket.bind/listen to raise.
`bridge/__main__.py`: builds empty handler dict until 3.5/3.6 register, installs loguru sink, runs.

**Acceptance criteria**

1. AC1 — real websockets pair over localhost TLS: Hello/HelloAck + heartbeats both ways. → `tests/test_bridge_protocol.py::test_auth_success_flow`
2. AC2 — wrong token & late hello -> 4401, zero command processing. → `test_auth_rejection`
3. AC3 — encode/decode roundtrip all types; garbage/oversize raise ProtocolError. → `test_envelope_conformance`
4. AC4 — silent daemon disconnected within DEAD_PEER window (shortened knobs). → `test_heartbeat_timeout_disconnects`
5. AC5 — full cycle with bind/listen patched to raise: zero calls — zero listening ports. → `test_daemon_holds_zero_listening_ports`
6. AC6 — backoff sequence 1,2,4,8,16,30,30 ±jitter, resets on success. → `test_reconnect_backoff_sequence`
7. AC7 — cmd/result correlation; never-answering daemon -> TimeoutError, connection reusable. → `test_cmd_result_roundtrip_and_timeout`

**Error modes** — scanner log spam rate-limited; pinned-fingerprint mismatch surfaced to owner on next contact (queued event); handler exceptions become error envelopes (tunnel survives), traceback logged; core with no daemon -> BridgeOfflineError after timeout (owner told honestly).

**Zero-cost check** — websockets BSD-3 only new dep; $0 TLS via self-signed + SPKI pin (openssl one-liner in runbook; Let's Encrypt upgrade path noted). Bandit-clean.

**Docs impact** — `.env.example` TLS block + fingerprint generation instructions; ARCHITECTURE §2 wire-contract summary + direction-of-dial ruling; RUNBOOK (cert generation, systemd unit, Task Scheduler/NSSM autostart, outbound-8443 firewall note); CHANGELOG.

---

### 3.2 Voice memo ingestion -> transcription -> filed note

**Intent** — Owner's Telegram voice notes transcribed LOCALLY (faster-whisper, CTranslate2 CPU
int8) and filed as YAML-frontmattered notes in `Voice_Memos/`. No paid STT. Audio never touches
disk: Ogg Opus bytes -> BytesIO -> ffmpeg pipes -> 16 kHz mono WAV -> faster-whisper in
asyncio.to_thread -> note.

**Interface** — `src/voice_memos.py`; deps `faster-whisper>=1.0` (MIT; ctranslate2 Apache-2.0);
env `WHISPER_MODEL="base"` (RAM knob per VPS sizing — open question Q3). Handler wiring in
`src/main.py` for F.voice/F.audio (owner middleware upstream).

```python
class Transcript(BaseModel): text; duration_seconds; language
class Transcriber:
    async def transcribe_ogg(self, ogg: bytes) -> Transcript
        # lazy WhisperModel singleton; language auto-detect WITH documented ar-JO bias
class MemoResult(BaseModel): note_path; transcript_text; commit_sha
class VoiceMemoIngester:
    async def ingest(self, ogg: bytes, *, captured_at, caption, message_id) -> MemoResult
```

**Language handling (Guide amendment)**: hard-coded `language="ar"` replaced by detection with
ar-JO bias; DETECTED language stored in frontmatter `language:` field (an English memo is decoded
as English and labeled truthfully — Sara serves 10 languages).

Note shape: frontmatter `{id: uuid4, captured_at ISO UTC, duration_seconds, language: <detected>,
source_message_id, transcription_ok: true, tags:[voice-memo]}`; body `## التفريغ` transcript
paragraphs + `## التعليق` caption when present. Path `para_path("memos", "{YYYY-MM-DD_HHMMSS}")`
(collision-proof to second; same-second re-ingest updates).

**Acceptance criteria**

1. AC1 — fixture Ogg (`tests/fixtures/memo_ar.opus`) -> filed note with all frontmatter keys, known transcript substring present, `language == "ar"` for the Arabic fixture (detected value asserted generally). → `tests/test_voice_memo_ingest.py::test_fixture_ogg_files_yaml_tagged_note`
2. AC2 — returned transcript_text matches note body section. → `test_transcript_returned_to_caller`
3. AC3 — caption preserved verbatim / omitted cleanly. → `test_caption_preserved_in_body`
4. AC4 — corrupt audio -> flagged note `transcription_ok:false` + honest owner-facing error. → `test_failed_transcription_writes_flagged_note`
5. AC5 — model constructed exactly once across calls (lazy singleton). → `test_model_loaded_lazily_once`

**Error modes** — ffmpeg absent/failure -> MemoIngestError -> flagged-note path; empty transcript still filed («التفريغ فارغ») + INFO; model load failure propagates with owner told; Telegram download failures ride Sprint-1 error handler. Every path files OR raises-with-owner-told.

**Zero-cost check** — faster-whisper MIT / ctranslate2 Apache-2.0; compute = already-provisioned free VPS CPU; one-time HF download $0. $0.00/month delta.

**Docs impact** — `.env.example` WHISPER_MODEL block; ARCHITECTURE §6 Voice_Memos schema; DATA-MODEL memo frontmatter; RUNBOOK warm-cache + RAM sizing; BACKLOG tick 3.2; CHANGELOG.

---

### 3.3 Conversation capture (User_Info, Dialect_Notes) + action-summary protocol

**Intent** — Sara learns while chatting: preferences persist to `User_Info.md`, colloquialisms to
`Dialect_Notes.md` (adaptive ar-JO loop), task-bearing turns end with «هل بتحب ألخص لك شو رح أعمل
هسا؟» — approval recites + files the summary; casual turns suppress everything. Extraction on
FAST_MODEL; LLM output strictly data to validate, never instructions.

**Interface** — `src/capture.py`; test module `tests/test_post_call_summary.py`.

```python
class UserFact(BaseModel): category: str; fact: str
class DialectNote(BaseModel): expression; meaning; context
class ActionTask(BaseModel): description: str; due: str | None
class CaptureResult(BaseModel): facts; dialect; tasks
class CaptureExtractor:
    def __init__(self, brain: OmniRouteClient)
    async def extract(self, user_text, sara_reply) -> CaptureResult   # strict JSON -> pydantic
class PendingSummary(BaseModel): id; tasks; asked_at
class ConversationCapture:
    async def process_turn(self, user_text, sara_reply) -> PendingSummary | None
    async def resolve_pending(self, pending, owner_reply) -> str | None
AFFIRMATIVES = ("نعم","ايه","إيه","أيوه","ايوه","أكيد","اكيد","تمام","ok","yes")
SUMMARY_PROMPT = "هل بتحب ألخص لك شو رح أعمل هسا؟"
```

AFFIRMATIVES lives in `common/consent.py` (**Guide amendment: hoisted so 3.5 imports from common/,
not from this core-side module — dependency direction fixed**). One pending per turn; newer turn
supersedes unanswered older one (INFO). In-memory pendings lost on restart — accepted ceiling
(`# ponytail:` comment documents the vault-scratch-note upgrade path; open question Q7).

**Arbitration rule (Guide amendment)**: when BOTH a PendingSummary AND a pending confirmation are
active, the CONFIRMATION consumer owns the next owner message (safety > convenience); the summary
question is re-asked after resolution. Deterministic, tested.

**Affirmative binding (Guide amendment)**: approval requires the affirmative to FOLLOW the explicit
prompt in the same conversational window — bare prefix match against an unrelated topic does not
mint consent; ambiguous reply = decline (never guessed as consent).

**Acceptance criteria**

1. AC1 — 2-task turn triggers prompt exactly once + returns PendingSummary; zero-task turn returns None, no prompt. → `tests/test_post_call_summary.py::test_prompt_only_when_actionable_tasks_exist`
2. AC2 — chitchat fixture («شلونك اليوم؟») produces ZERO vault writes. → `test_casual_turn_suppressed`
3. AC3 — «ايه سوّيها» after prompt files note under `04_Archives/Conversations/` with numbered tasks + `[action-summary]` tag. → `test_approval_files_action_summary`
4. AC4 — decline discards; unrelated later message doesn't resurrect. → `test_decline_discards_pending_summary`
5. AC5 — fact lands grouped by category; identical replay dedupes. → `test_user_fact_append_and_dedupe`
6. AC6 — colloquialism becomes dated Dialect_Notes row. → `test_dialect_note_appended`
7. AC7 — extractor garbage contained (empty result, no writes, no raise). → `test_extractor_garbage_is_contained`
8. AC8 — arbitration: active confirmation consumes next message; summary re-asked after. → `test_confirmation_arbitration_deterministic`

**Error modes** — brain failure → turn completes without capture (learning loss acceptable, breakage not); malformed JSON contained (hash logged, not content); vault write failure retains pending for one retry then drops bounded; ambiguous reply declines safely.

**Zero-cost check** — rides existing FAST_MODEL path. $0.00.

**Docs impact** — ARCHITECTURE §6 formats + Conversations path + exact prompt string; BACKLOG tick 3.3; CHANGELOG. (Mona-named ingest draft superseded per Q1 ruling — no import of its examples.)

---

### 3.5 Windows executor + whitelist guard + confirmation IDs

**Intent** — Sara controls the owner's PC: launching apps, opening paths on C:/D:, restricted
power actions. Safety STRUCTURAL: whitelist governs friction-free execution; anything outside —
and EVERY power action — needs an owner confirmation issued on Telegram, minted as a confirmation
ID, persisted to the vault; the bridge refuses unconfirmed non-whitelisted commands. NO force
bypass (CLAUDE.md rule 4). "Windows-MCP" realized as a small async executor on the daemon — one
hop, one trust boundary.

**Interface** — `bridge/guard.py`, `bridge/executor.py` (PC side); `src/pc_actions.py` (core side);
committed `config/whitelist.json` (schema per ARCHITECTURE §5 canonical keys:
`requires_confirmation`, sleep=true — resolves the ingest-doc key drift, open question Q1).

```python
# bridge/guard.py
class Verdict(BaseModel): allowed_without_confirmation: bool; executable: str | None
                          requires_confirmation: bool = False; reason: str
class Guard:
    def check_app(self, name: str) -> Verdict          # case-insensitive
    def check_power(self, action: str) -> Verdict      # ALWAYS requires confirmation
# bridge/executor.py
class ExecResult(BaseModel): status: Literal["ok","error"]; detail: str
class Executor:
    async def launch(self, name: str, *, confirmation_id: str | None) -> ExecResult
    async def open_path(self, path: str, *, confirmation_id: str | None) -> ExecResult
    async def power(self, action: str, *, confirmation_id: str) -> ExecResult   # id mandatory
# src/pc_actions.py
class LaunchStatus(StrEnum): EXECUTED; CONFIRMATION_REQUIRED; FAILED
class PCActionCoordinator(BridgeServer, VaultClient, Notifier):
    async def request_launch(self, app_name, *, origin: Literal["owner_chat"]) -> LaunchStatus
    async def request_power(self, action: str, *, origin) -> LaunchStatus       # Guide amendment
    async def handle_owner_reply(self, reply: str) -> str | None
```

**Behavior**

Happy path: «شغلي الآلة الحاسبة» -> intent parser -> `request_launch("calculator", origin="owner_chat")`
-> send_cmd exec.launch -> Guard auto_approve -> spawn via CREATE_NEW_PROCESS_GROUP detached,
shell=False -> ok -> «فتحته لك».

Non-whitelisted: daemon refuses WITHOUT executing (`not_whitelisted`) -> coordinator prompts
«هاد البرنامج مش بالقائمة المعتمدة، هل بتأكدلي صراحة إنه بدك تشغله هسا؟», parks pending (app,
asked_at, TTL **10 minutes — expired = dropped with INFO**). Owner affirmative (per 3.3 binding
rules, from common/consent.py) mints `confirmation_id = uuid4().hex`, writes record note to
`04_Archives/Confirmations/{YYYY-MM-DD}_{id8}.md` (frontmatter: full id, action/app, requested_at,
approved_at, method telegram_text or transcribed voice-note), THEN re-sends WITH confirmation_id;
daemon sees not_whitelisted + valid id -> executes. **Vault-write failure during recording =>
confirmation NOT minted and command never executes — approval without audit is void.**

Power actions: ALWAYS require confirmation ID regardless of whitelist flags (fail-closed even if
whitelist wrongly marks them auto-approved). Idle-offer integration (Guide amendment): replies map
via choice grammar — «نوم»/sleep -> sleep action, «اطفاء»/shutdown variants -> shutdown, anything
else = decline; `request_power` mints/persists the SAME confirmation mechanism; offer not repeated
while latch held.

**open_path — BLOCKER FIX (structural)**: `open_path` routes THROUGH THE GUARD. Allowed WITHOUT
confirmation: regular documents/media inside allowed roots with safe extensions (documents, images,
folders). Anything executable/script/shortcut (`.exe/.bat/.cmd/.lnk/.ps1/...`) is treated AS AN APP
LAUNCH: whitelist entry with auto_approve, or valid confirmation_id, else refused. Traversal/UNC
refusals stay. The old behavior (AC6 launching notepad.exe with no lookup) is GONE — rewritten AC6
below. `confirmation_id` parameter is consumed by this flow, not ignored.

Untrusted containment: `origin` required literal `"owner_chat"` — email triage/vault parsers/web
scrapes can NEVER invoke PC actions without an architectural change; suite pins it. Whitelist
re-read on every check; invalid JSON -> fail CLOSED (confirm-everything) + CRITICAL.

**Acceptance criteria**

1. AC1 — whitelisted auto_approve launches immediately. → `tests/test_whitelist_guardrail.py::test_whitelisted_app_executes`
2. AC2 — non-whitelisted -> refusal, coordinator CONFIRMATION_REQUIRED + Arabic prompt sent. → `test_nonwhitelisted_blocked_pending_confirmation`
3. AC3 — daemon-side: non-whitelisted launch with confirmation_id=None refused even from compromised core. → `test_bridge_refuses_unconfirmed_execution`
4. AC4 — full round-trip: block -> affirm -> confirmation note with SAME id -> executed. → `test_confirmation_roundtrip_persists_and_executes`
5. AC5 — `power("shutdown", confirmation_id=None)` refused regardless of whitelist content (even wrongly-marked auto-approved entries); valid ID proceeds. → `test_restricted_power_always_requires_confirmation`
6. AC6 — **rewritten**: `open_path` on a whitelisted-safe document inside C:/ succeeds; `open_path("C:/Windows/notepad.exe")` outside whitelist is REFUSED pending confirmation (executable-as-app-launch rule); `../../etc/passwd` and UNC refused with `outside_allowed_roots`; daemon-side test proves exec.open without confirmation_id never invokes os.startfile for non-whitelisted targets. → `test_open_path_confined_and_guarded`
7. AC7 — `origin != "owner_chat"` raises RefusedOrigin. → `test_non_owner_origin_intent_refused`
8. AC8 — corrupt whitelist flips guard fail-closed + CRITICAL. → `test_corrupt_whitelist_fails_closed`
9. AC9 — expired confirmation (>10 min) refused with INFO; interstitial unrelated message does not mint an ID. → `test_confirmation_ttl_expiry`
10. AC10 — duplicate pendings: newest wins, superseded dropped INFO. → `test_newest_pending_wins`

**Error modes** — missing executable -> «البرنامج مش موجود عالجهاز» + ERROR; bridge offline at send_cmd -> owner told unreachable, pending dropped (stale PC actions dangerous); daemon exceptions -> error envelopes (tunnel survives).

**Zero-cost check** — stdlib only; whitelist committed JSON; confirmations ride 3.1 quota; shell=False bandit-clean. $0.00.

**Docs impact** — `config/whitelist.json` defaults; docs/06-API-SPECIFICATION formalization (launch_desktop_app/save_obsidian_note; force semantics DROPPED, confirmation_id documented); ARCHITECTURE §5 flow + fail-closed + WoL-topology ruling (see 3.6); RUNBOOK whitelist editing + confirmation locations; DATA-MODEL schemas; BACKLOG tick 3.5; CHANGELOG.

---

### 3.6 Wake-on-LAN sender + 20-minute idle monitor

**Intent** — (a) Daemon fires WoL magic packets toward TARGET_PC_MAC_ADDRESS — **topology ruling
(Guide amendment, recorded canonically in ARCHITECTURE §2): v1.0 WoL reaches OTHER LAN machines /
a second NIC only; a sleeping PC cannot be woken by its own daemon (documented known ceiling —
matches ADR-05/runbook). Env-var names unchanged but manifest comments state the scope honestly.**
(b) Idle monitor watches last-input; after IDLE_SHUTDOWN_MINUTES (default 20) emits an event and
Sara offers sleep/shutdown BY MESSAGE exactly once per idle window (hysteresis re-arm).

**Interface** — `bridge/wol.py`, `bridge/idle.py`; env all existing.

```python
def magic_packet(mac: str) -> bytes            # b"\xff"*6 + mac*16; ValueError on bad MAC
async def send_wol(mac, ip, port=9) -> int     # datagram endpoint, SO_BROADCAST, one sendto
def windows_last_input_seconds() -> float      # ctypes GetLastInputInfo (win only)
class IdleMonitor(threshold_minutes, on_idle, *, source=None, poll_seconds=30.0)
IDLE_OFFER_TEXT_AR = "صرت مدة طويلة بدون استخدام، بدهني أفعل وضع النوم أو إطفاء الجهاز؟"
```

Idle events ride 3.4 event envelopes; offer delivery routed through 3.5's restricted-action flow
(choice grammar + request_power). Latch clears below half-threshold (real activity).

**Acceptance criteria**

1. AC1 — packet bytes exact 102-byte classic frame. → `tests/test_wol_idle.py::test_magic_packet_bytes_match_mac`
2. AC2 — malformed MACs raise ValueError. → `test_invalid_mac_raises`
3. AC3 — UDP SO_BROADCAST single sendto spied. → `test_wol_sends_udp_broadcast`
4. AC4 — offer fires EXACTLY once per window despite continued polling. → `test_idle_offer_fires_once_per_window`
5. AC5 — sub-half-threshold activity clears latch and re-arms; hovering at threshold doesn't flap. → `test_activity_resets_latch_rearms_offer`
6. AC6 — E2E over 3.4: idle event reaches core callback with correct payload. → `test_idle_event_reaches_core_callback`
7. AC7 — owner choice reply routes through confirmation flow producing exactly one confirmation + one power command with same ID; ambiguous reply declines. → `test_idle_choice_confirmation_roundtrip`

**Error modes** — datagram failure WARNING + honest error result; non-Windows host running real source raises at construction (misconfiguration loud); tunnel-down keeps latch SET (deliver on reconnect, no spam); clean cancellation.

**Zero-cost check** — stdlib only. $0.00.

**Docs impact** — `.env.example` comment honesty pass; ARCHITECTURE §2/§5 flows; RUNBOOK BIOS/NIC WoL steps + ceiling note; BACKLOG tick 3.6; CHANGELOG.

---

## Stream gate

Done = all six tasks' AC green, `make lint` zero findings, `bandit -r src/ bridge/ common/` zero
high/critical, **coverage extended to `--cov=src,bridge,common` (Guide amendment — safety-critical
guard/executor code measured, TEST-PLAN §3 synced)**, docs synced per task, CHANGELOG entry.
Integration smoke (manual, credentials-gated): real voice note -> filed memo; whitelist miss ->
Telegram confirmation -> launch with persisted ID; daemon reconnect after core restart; idle offer
observed once after 20 untouched minutes.

---

## Guide Review — Verdict: FIX (dispositions below)

Reviewer: independent Guide agent, adversarial pass, 2026-08-26. *(Drafted during classifier
degradation — Leader personally re-audited draft + findings line-by-line before acceptance.)*

- 🔴 **BLOCKER — open_path bypassed whitelist entirely**: RESOLVED structurally — guard-routed open_path, executable-as-app-launch rule, rewritten AC6, daemon-side negative test.
- 🟠 **MAJOR — confirmation safety gaps (no TTL, loose prefix consent, no arbitration)**: RESOLVED — 10-min TTL (AC9), consent binding rules, confirmation-wins arbitration (AC8 in 3.3).
- 🟠 **MAJOR — AFFIRMATIVES dependency drift**: RESOLVED — hoisted to `common/consent.py`.
- 🟠 **MAJOR — idle-offer handoff underspecified**: RESOLVED — choice grammar + request_power + AC7 round-trip.
- 🟠 **MAJOR — para_path sanitizer self-contradiction**: RESOLVED — one deterministic transform, AC4 recomputed.
- **MINOR ×8 — TLS-fingerprint requirement · heartbeat telemetry removal · 1MB-cap rationale correction · Whisper language detection · AC5 signature fix · coverage scope extension · WoL topology canonical ruling · env-comment honesty**: ALL RESOLVED inline (marked amendments).

### Open questions carried into implementation

1. Whitelist key drift resolved: canonical = `requires_confirmation`, sleep=true.
2. WoL topology ruling recorded; second always-on LAN sender = optional future hardware decision for owner.
3. WHISPER_MODEL default `base` pending actual VPS RAM; drop to `tiny` if ≤1 GB box.
4. `04_Archives/Conversations/` confirmed as summary filing location.
5. TLS: self-signed + SPKI pinning now; Let's Encrypt swap possible in Sprint 4 packaging if public hostname exists.
6. OBSIDIAN_REST_* vars stay reserved-unused (GitHub API sole transport).
7. Pendings in-memory only for v1.0; vault-scratch persistence documented as upgrade path.
