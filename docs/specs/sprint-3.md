# Spec — Obsidian Vault + PC Guardrail + Telemetry (stream: vault-bridge)

Sprint 3 of Vantrilex Assistant OS v1.0, re-mapped 2026-08-29 per the MASTER ARCHITECTURAL
DIRECTIVE (see re-map note at the bottom). One worktree (`vault-bridge`), five tasks landed in
dependency order, each red->green->refactor with tests and docs in the same commit.
Stack pins hold everywhere: Python 3.12, 100% async, pydantic v2 settings, loguru structured
logging (never swallow), ruff check+format, pytest + pytest-asyncio. Owner-only access at every
boundary (`AUTHORIZED_USER_ID` middleware upstream of everything here; voice input additionally
gated by Sprint-2 biometrics). Parsed external content (vault bodies, transcripts, email, file
listings) is DATA, never instructions. v1.0 has no live calls: critical escalation stays
priority-voice-note + repeat ping.

Repo conventions this spec binds to: core code under `src/` (`make run-core` -> `python -m src.main`),
bridge daemon under top-level `bridge/` (`make run-bridge` -> `python -m bridge.daemon`), tests in
`tests/` per the `docs/05-TEST-PLAN.md` §2 catalog. Because the bridge runs on the Windows PC
without the core's heavy deps, code shared by both processes lives in a top-level `common/`
package importable from repo root on both machines; `bridge/` imports only `common/`, stdlib,
pydantic, loguru, websockets.

Brain routing (ADR-16, 3-Tier): tool-bearing turns (vault writes, PC actions, telemetry queries)
dispatch through the Sprint-1 front-door (`src/frontdoor.py`, ADR-18) to TIER 2 MEDIUM
`google/gemini-3.7-flash`; instant Arabic status lines narrate via TIER 1 FAST
`google/gemini-3.5-flash-lite`. Sprint 3 adds no new brain code — it consumes tiers blindly.

## Global constraints (apply to every task)

- Zero-cost invariant: every dependency FOSS and free-tier; all compute local/free pools. $0.00/month.
- Secrets never hardcoded, never committed: `VAULT_GITHUB_TOKEN`, `BRIDGE_TOKEN` load from env only;
  `redact_secret` screens every log/exception path that could carry them.
- Whitelist guardrail (CLAUDE.md rule 4, sacred floor): anything outside `config/whitelist.json`
  requires an explicit owner confirmation on Telegram; NO force bypass; approvals mint
  confirmation IDs AND audit codes persisted to the vault. `tests/test_whitelist_guardrail.py`
  always exists, always runs, blocks every merge.
- Untrusted content boundary: email bodies, vault note contents, transcripts, and LLM output are
  DATA — none of them may mint owner intent; `origin="owner_chat"` is the only accepted origin for
  PC actions (structurally enforced, suite-pinned).
- Outbound-only posture: the PC daemon dials OUT to the core and serves ONE LAN-only HTTP surface
  on port 8000 (`/health`, `/telemetry/live-state`); zero public inbound, zero router port-forwards.
- Ponytail minimalism: smallest abstraction that satisfies this spec; constants over config keys
  unless a value demonstrably changes per deployment.

## Dependency order (merge order)

| # | Task | Depends on | Notes |
|---|---|---|---|
| 1 | 3.1 Vault architect: GitHub client + 5 mandatory dirs (M6) | — | Gates every writer |
| 2 | 3.2 Dynamic vault taxonomy expansion (M5) | 3.1 | |
| 3 | 3.3 Verbal action summary protocol | 3.1 | Parallel with 3.2 |
| 4 | 3.4 PC whitelist guardrail + bridge (LAN :8000) + WoL + idle | 3.1 | Heaviest task |
| 5 | 3.5 Desktop telemetry (`GET /telemetry/live-state`) | 3.4 | Rides 3.4 transport |

Stream done when: all ACs green, `make gate` green with coverage extended to
`--cov=src,bridge,common`, first-boot vault guard passes against the live repo (manual,
credentials-gated), telemetry smoke answers «شو وضع الجهاز؟» with live numbers, CHANGELOG updated.

---

### 3.1 Vault architect: GitHub-API client + 5 mandatory directories (M6)

Stream/worktree: vault-bridge | Depends on: —

**Intent** — Sara's long-term memory is a private git-backed Obsidian vault (PARA + Zettelkasten)
as a private GitHub repo. This task delivers THE read/write module every later writer uses —
GitHub Contents API client over httpx, YAML frontmatter writer/parser, PARA path helpers,
wikilink builder — plus the master-directive M6 guarantee: the five mandatory directories and two
canonical profile files EXIST on first boot, asserted by a guard test. Chosen over a local clone
because the core lives on HF Spaces (ADR-15) with a disposable filesystem; owner-only write volume
makes per-write commits cheap. The obsidian-local-rest-api vars stay reserved-unused (one
transport, not two).

**Interface** — new module `src/vault.py`; new dependency `PyYAML>=6,<7`; env via Settings:
`VAULT_GITHUB_REPO: str`, `VAULT_GITHUB_TOKEN: SecretStr`, `VAULT_BRANCH: str = "main"` (new).

```python
PARA = {"projects":"01_Projects","areas":"02_Areas","resources":"03_Resources",
        "archives":"04_Archives","contacts":"Contacts","memos":"Voice_Memos"}

# M6 mandatory set (created on first boot, asserted by guard test):
MANDATORY_DIRS   = ("Contacts/", "Call_Transcripts/", "Studies/", "Voice_Memos/", "Daily_Logs/")
CONTACTS_SUBDIRS = ("Contacts/Family/", "Contacts/Friends/", "Contacts/Colleagues/",
                    "Contacts/Ignored/", "Contacts/Unknown/")   # social-graph taxonomy (2026-08-29 addendum)
MANDATORY_FILES  = ("02_Areas/Profile/User_Info.md", "02_Areas/Profile/Dialect_Notes.md")
# Studies/ is TOP-LEVEL (02_Areas/Studies/ migrates once, if present — structural commit).

class Note(BaseModel):        path: str; frontmatter: dict[str, Any]; body: str
class WriteResult(BaseModel): path: str; commit_sha: str; created: bool

def para_path(category: str, title: str, *, ext: str = ".md") -> str
def daily_log_path(day: date) -> str                       # "Daily_Logs/YYYY-MM-DD.md"
def write_frontmatter(meta: dict, body: str) -> str
def split_frontmatter(text: str) -> tuple[dict, str]
def zettel_link(title: str, *, alias=None, block=None, embed=False) -> str

class VaultClient:
    def __init__(self, repo: str, token: str, branch: str = "main", session: httpx.AsyncClient | None = None)
    async def read(self, path: str) -> str                       # FileNotFoundError if absent
    async def upsert(self, path: str, content: str, *, message: str) -> WriteResult
    async def upsert_note(self, note: Note, *, message: str) -> WriteResult
    async def append_section(self, path, heading, lines, *, commit_prefix) -> WriteResult
    async def ensure_mandatory_dirs(self) -> list[WriteResult]   # idempotent first-boot bootstrap
    async def aclose() -> None
def redact_secret(s: str) -> str     # reused by 3.4/3.5 logs
```

Canonical path constants (used by 3.3/3.4): `PROFILE_USER_INFO`, `PROFILE_DIALECT`,
`CONVERSATIONS_DIR = "04_Archives/Conversations"`, `CONFIRMATIONS_DIR = "04_Archives/Confirmations"`,
`AUDIT_DIR = "04_Archives/Audit"`.

**Behavior** — `upsert`: GET contents API (?ref=branch, Bearer + versioned headers); 404 -> PUT
create; 200 -> PUT with sha; one 409 retry of GET->PUT then raise. Size cap: client-side refusal
above 1,000,000 bytes is a defensive note-shaped-content bound, NOT an API limit (documented).
Sanitizer — ONE deterministic transform: replace `/` and `\` separators with spaces, collapse
whitespace runs, strip forbidden chars `\ / : * ? " < > | # ^ [ ]` and leading dots, reject
empty / `.` / `..` / any residual separator; Arabic preserved verbatim
(`"ملاحظة: اجتماع/الأسبوع؟"` -> `"ملاحظة اجتماع الأسبوع"`). Frontmatter via
`yaml.safe_dump(allow_unicode=True, sort_keys=False)` in `---` fences; split accepts only leading
fences, safe_load only. `ensure_mandatory_dirs` upserts a one-line `.gitkeep`-style index note per
missing dir (real note content: frontmatter + purpose line) and both profile files; re-run makes
zero writes. Legacy migration: if `02_Areas/Studies/` exists with content, its notes MOVE to
`Studies/` and the move lands as ONE structural commit (`sara: migrate Studies to top-level`).
All logs pass through redact_secret.

**Acceptance criteria**

1. AC1 — create-then-update roundtrip on mocked backend (sha semantics, created flag). → `tests/test_obsidian_para.py::test_note_create_update_roundtrip`
2. AC2 — frontmatter roundtrip byte-identical body, Arabic intact, insertion order kept. → `test_frontmatter_writer_and_splitter`
3. AC3 — zettel_link renders `![[Obsidian|التطبيق#^abc]]` / bare `[[Obsidian]]`. → `test_zettelkasten_link_builder`
4. AC4 — sanitizer table-driven incl. separators-to-spaces, traversal refusals (`..`, embedded separators post-transform, empty). → `test_para_path_routing_and_sanitization`
5. AC5 — token never appears in exception text, logs, or outgoing URLs (caplog + transport inspection). → `test_no_token_in_logs_or_errors`
6. AC6 — 1,000,001-byte payload refused pre-flight. → `test_oversize_payload_refused`
7. AC7 — first-boot guard: empty repo -> `ensure_mandatory_dirs` creates all 5 dirs + 2 profile files; second run makes ZERO writes (idempotent). → `tests/test_vault_dirs.py::test_first_boot_creates_mandatory_tree_idempotent`
8. AC8 — legacy `02_Areas/Studies/` with notes -> single migration commit to top-level `Studies/`; absent legacy -> no migration commit. → `test_studies_dir_migrated_to_top_level`
9. AC9 — `daily_log_path` renders `Daily_Logs/YYYY-MM-DD.md` for a known date; guard test file itself is importable without credentials (pure constants). → `test_daily_log_path_dated_and_guard_importable`
10. AC10 — guard runs inside `make gate` (part of default testpaths) so a missing-dir regression fails CI before any writer depends on it. Evidence: gate output in PR. → `test_vault_dirs_in_default_gate`

**3.1b Social graph: Contacts taxonomy + story extractor** (same directive skill as 2.3b,
`skill-social-graph-and-voice-enrollment`; vault-side touchpoint)

```python
# src/skills/social_graph.py
CONTACT_CATEGORIES = ("Family", "Friends", "Colleagues")   # + Ignored/Unknown (system-managed)
class ContactDossier(BaseModel):
    name: str; category: str; relation_tags: list[str] = []
    voiceprint_ref: str | None = None                  # State/voiceprints/<id>.enc
    created: date; last_interaction: date | None = None
class EntityMention(BaseModel):
    name: str; action_summary: str; mentioned_at: datetime
    category_inferred: str | None = None               # None => ask owner before filing
class SocialGraph:
    async def dossier(self, category: str, name: str) -> ContactDossier | None
    async def create_dossier(self, d: ContactDossier, *, voiceprint: bytes | None) -> WriteResult
    async def extract_entities(self, narration: str) -> list[EntityMention]   # FAST-tier, JSON schema
    async def file_action(self, m: EntityMention) -> list[WriteResult]
        # appends timestamped section to Contacts/{Category}/{Name}.md AND Daily_Logs/YYYY-MM-DD.md
```

Dossier template — frontmatter `name/category/relation_tags/voiceprint_ref/created/
last_interaction`; body sections append-only (## Interaction Log — dated entries). `Ignored/`
dossiers carry `tracking: false` and NEVER receive appends; `Unknown/` carries
`security_flag: true` + anonymous embedding ref + timestamped transcripts.

**Behavior** — owner narrates the day -> `extract_entities` (one FAST-tier call, entities +
inferred category per mention) -> ambiguous/changed category => verbal confirm with owner
BEFORE filing -> `file_action` appends the timestamped summary to the person's dossier and the
day's `Daily_Logs` note (one vault commit per source note). Unmatched name with no dossier =>
propose creating one (Case B flow from 2.3b).

11. AC11 — taxonomy first-boot: `ensure_mandatory_dirs` also creates all five `Contacts/`
    subdirs (guard extended, idempotent). → `tests/test_vault_dirs.py::test_contacts_taxonomy_created`
12. AC12 — story extractor: fixture narration -> entities filed as dated sections in BOTH the
    correct dossiers and `Daily_Logs/YYYY-MM-DD.md`; ambiguous category holds for owner
    confirmation; `Ignored/` mention produces NO dossier write.
    → `tests/test_story_extractor.py::test_daily_narration_files_actions_to_contacts_and_log`

**Error modes** — auth errors propagate loudly (no retry); 409 after retry -> VaultConflictError WARN; timeouts propagate after ERROR; malformed YAML wrapped ValueError naming path; missing read -> FileNotFoundError; oversize pre-flight ValueError. Nothing swallowed.

**Zero-cost check** — PyYAML (MIT) only new dep; GitHub free-tier PAT quota ample. $0.00.

**Docs impact** — `.env.example` VAULT_BRANCH; ARCHITECTURE §6 + §6b (GitHub Contents API
transport + M6 mandatory tree + social-graph taxonomy + canonical constants); RUNBOOK
first-boot vault bootstrap; DATA-MODEL frontmatter conventions; CHANGELOG; BACKLOG tick 3.1.

---

### 3.2 Dynamic vault taxonomy expansion (M5)

Stream/worktree: vault-bridge | Depends on: 3.1

**Intent** — The vault taxonomy is DYNAMIC (master directive M5): as new projects/domains emerge
in conversation, Sara grows new sub-directories and tag ontologies herself, every structural
change landing as an auditable git commit on the vault repo. The PARA backbone is expansion-only —
nothing under the backbone is ever deleted or renamed by this module. No redeploy, no manual
 Obsidian re-org; the owner reviews structure through git history.

**Interface** — new module `src/vault_expand.py`; consumes `VaultClient` from 3.1.

```python
class ExpansionResult(BaseModel):
    created_dirs: list[str]; created_files: list[str]; commit_sha: str

class VaultExpander:
    def __init__(self, vault: VaultClient, *, backbone: frozenset[str] = PARA_BACKBONE)
    async def expand(self, domain: str, *, dirs: list[str], tags: list[str]) -> ExpansionResult
    # domain: Arabic or Latin domain name ("دراسة", "fitness"); dirs relative under it;
    # tags: YAML tag ontology written to <domain>/_tags.yaml; semantic links optional via body.
```

**Behavior** — `expand` creates `para_path("projects", domain)`-rooted sub-directories (or under
the category the caller names), writes `_tags.yaml` (safe_dump, `tags:` list + `domain:` +
`created:` ISO), writes an index note per dir, and lands ALL of it as ONE structural commit
(`sara: expand vault — {domain}`). Backbone immutability: the PARA top-level set
(`01_Projects/ 02_Areas/ 03_Resources/ 04_Archives/ Contacts/ Call_Transcripts/ Studies/
Voice_Memos/ Daily_Logs/`) is protected — any requested change touching (renaming, deleting,
moving) a backbone path raises `BackboneImmutableError` before any API call. Idempotent: existing
dirs/notes are left untouched, result reports only the delta. Deletion is structurally
impossible: the module has no delete/move code path. LLM-proposed structure is DATA: the
orchestrator validates proposals through this typed interface only.

**Acceptance criteria**

1. AC1 — new domain creates its dir, index note, and `_tags.yaml` on a mocked backend. → `tests/test_vault_expand.py::test_new_domain_creates_dir_and_tags`
2. AC2 — the whole expansion lands as exactly ONE vault commit with the `sara: expand vault —` prefix. → `test_structure_change_is_git_commit`
3. AC3 — request touching a backbone path (rename/delete/move) raises `BackboneImmutableError` with zero API calls made. → `test_para_backbone_immutable`
4. AC4 — re-expanding an existing domain makes zero writes, returns empty delta. → `test_expansion_idempotent`
5. AC5 — empty domain / empty dirs+tags / residual-separator path components refused pre-flight. → `test_invalid_expansion_refused`
6. AC6 — `_tags.yaml` parses back (safe_load) to the same tag list, Arabic intact, `created` ISO-UTC. → `test_tag_ontology_yaml_roundtrip`
7. AC7 — index notes cross-link with zettel wikilinks to the domain root. → `test_index_notes_link_domain_root`
8. AC8 — expansion result is derivable from vault state alone (re-read reconstructs created_dirs/files) — no local memory. → `test_state_derives_from_vault`
9. AC9 — backend failure mid-expansion -> error propagates; next successful run completes the delta (no partial-state corruption claimed). → `test_failure_then_retry_completes`
10. AC10 — vault token never in logs/exceptions on any expansion path. → `test_expansion_logs_redacted`

**Error modes** — backbone violation loud pre-flight; backend auth/conflict propagate per 3.1 error modes; invalid proposals refused with owner-readable reason. Nothing swallowed.

**Zero-cost check** — rides 3.1's PyYAML/httpx; no new dependency. $0.00.

**Docs impact** — ARCHITECTURE §6 (dynamic taxonomy paragraph + backbone list); RUNBOOK "reviewing
vault structure via git log"; DATA-MODEL `_tags.yaml` schema; CHANGELOG; BACKLOG tick 3.2 (M5).

---

### 3.3 Verbal action summary protocol

Stream/worktree: vault-bridge | Depends on: 3.1

**Intent** — Task-bearing turns close with Sara asking «هل بتحب ألخص لك شو رح أعمل هسا؟» — owner
approval recites and files the summary; casual turns suppress everything. Extraction of
actionable tasks rides the TIER 2 MEDIUM brain (ADR-16: tool executor tier); LLM output is
strictly data to validate, never instructions. Consent grammar is shared with 3.4's confirmation
flow via `common/consent.py` (hoisted so the bridge side imports the same rules — dependency
direction fixed).

**Interface** — `src/summary.py`; `common/consent.py`; test module `tests/test_post_call_summary.py`.

```python
class ActionTask(BaseModel): description: str; due: str | None
class PendingSummary(BaseModel): id: str; tasks: list[ActionTask]; asked_at: datetime
class TaskExtractor:
    def __init__(self, brain: OmniRouteClient)          # dispatched at TIER 2 MEDIUM
    async def extract(self, user_text: str, sara_reply: str) -> list[ActionTask]
        # strict JSON -> pydantic; garbage -> []
class ConversationSummary:
    def __init__(self, vault: VaultClient, extractor: TaskExtractor, notifier)
    async def process_turn(self, user_text, sara_reply) -> PendingSummary | None
    async def resolve_pending(self, pending, owner_reply) -> str | None
# common/consent.py
AFFIRMATIVES: Final[tuple[str, ...]] = ("نعم","ايه","إيه","أيوه","ايوه","أكيد","اكيد","تمام","ok","yes")
def is_affirmative(text: str) -> bool
SUMMARY_PROMPT: Final[str] = "هل بتحب ألخص لك شو رح أعمل هسا؟"
```

One pending per turn; newer turn supersedes unanswered older one (INFO). In-memory pendings lost
on restart — accepted ceiling (`# ponytail:` comment documents the vault-scratch-note upgrade
path). Arbitration rule: when BOTH a PendingSummary AND a 3.4 pending confirmation are active, the
CONFIRMATION consumer owns the next owner message (safety > convenience); the summary question is
re-asked after resolution — deterministic, tested. Consent binding: approval requires the
affirmative to FOLLOW the explicit prompt in the same conversational window — bare prefix match
against an unrelated topic does not mint consent; ambiguous reply = decline (never guessed as
consent).

**Acceptance criteria**

1. AC1 — 2-task turn triggers prompt exactly once + returns PendingSummary; zero-task turn returns None, no prompt. → `tests/test_post_call_summary.py::test_prompt_only_when_actionable_tasks_exist`
2. AC2 — chitchat fixture («شلونك اليوم؟») produces ZERO vault writes. → `test_casual_turn_suppressed`
3. AC3 — «ايه سوّيها» after prompt files note under `04_Archives/Conversations/` with numbered tasks + `[action-summary]` tag + zettel links. → `test_approval_files_action_summary`
4. AC4 — decline discards; unrelated later message doesn't resurrect. → `test_decline_discards_pending_summary`
5. AC5 — arbitration: active confirmation consumes next message; summary re-asked after. → `test_confirmation_arbitration_deterministic`
6. AC6 — affirmative immediately after an UNRELATED topic is NOT treated as summary consent. → `test_consent_binding_requires_followup_affirmative`
7. AC7 — filed note frontmatter carries `id`, `asked_at`, `resolved_at`, `task_count`; body numbered tasks. → `test_summary_note_frontmatter_schema`
8. AC8 — extractor garbage (malformed JSON, prompt-injection-shaped output) contained: empty task list, no writes, no raise, hash logged not content. → `test_extractor_garbage_is_contained`
9. AC9 — brain failure -> turn completes without capture (learning loss acceptable, breakage not). → `test_brain_failure_never_breaks_reply`
10. AC10 — task extraction requests route through the TIER 2 MEDIUM dispatch (model field asserted = medium tier). → `test_extraction_dispatches_tier2_medium`

**Error modes** — brain failure -> no capture, reply unaffected; vault write failure retains pending for one retry then drops bounded; ambiguous reply declines safely. Nothing swallowed.

**Zero-cost check** — rides existing MEDIUM-tier free pool. $0.00.

**Docs impact** — ARCHITECTURE §6 formats + exact prompt string; BACKLOG tick 3.3; CHANGELOG.
(The retired-name ingest draft is superseded per Q1 ruling — no import of its examples.)

---

### 3.4 PC whitelist guardrail + outbound bridge (LAN :8000) + WoL + idle monitor

Stream/worktree: vault-bridge | Depends on: 3.1

**Intent** — Sara controls the owner's PC through an outbound-only bridge: the daemon dials OUT
to the core (zero public inbound, zero port-forwards — the PC may sleep, Sara stays up per
ADR-15), serves exactly ONE LAN-only HTTP surface on port 8000 (`/health`,
`/telemetry/live-state` for 3.5), executes whitelisted apps/paths, power actions, and WoL, and
watches idle. Safety STRUCTURAL: whitelist governs friction-free execution; anything outside —
and EVERY power action — needs an owner confirmation on Telegram; approvals mint a confirmation
ID plus a human-quotable AUDIT CODE, both persisted to the vault; the daemon refuses unconfirmed
non-whitelisted commands. NO force bypass (CLAUDE.md rule 4). "Windows-MCP" realized as a small
async executor on the daemon — one hop, one trust boundary.

**Interface** — `common/protocol.py` (shared); `common/consent.py` (from 3.3); `src/bridge_server.py`;
`src/pc_actions.py`; `bridge/{daemon,server,guard,executor,wol,idle,__main__}.py`;
committed `config/whitelist.json` (canonical keys: `requires_confirmation`, sleep=true);
dep `websockets>=13,<16`. Env: `BRIDGE_TOKEN`, `BRIDGE_SERVER_URL` (core WSS), `BRIDGE_LAN_PORT=8000`,
`TARGET_PC_MAC_ADDRESS`, `TARGET_PC_IP`, `TARGET_PC_WOL_PORT=9`, `IDLE_SHUTDOWN_MINUTES=20`.

```python
# common/protocol.py
PROTOCOL_VERSION = 1; HEARTBEAT_INTERVAL_S = 15; DEAD_PEER_MULTIPLIER = 3
AUTH_TIMEOUT_S = 10; MAX_FRAME_BYTES = 1_048_576; BACKOFF_CAP_S = 30.0
CmdName = Literal["exec.launch", "exec.open", "power", "wol", "telemetry.state"]
class Hello(BaseModel):   v=1; token: str; hostname: str      # first frame within AUTH_TIMEOUT_S
class HelloAck(BaseModel): v=1; ok: bool; reason: str | None
class Envelope(BaseModel): id: str; type: Literal["heartbeat","cmd","result","event"]; ts: datetime
                           cmd: CmdName|None; args: dict = {}; status: Literal["ok","error"]|None
                           payload: dict = {}
def encode(msg) -> bytes; def decode_frame(raw) -> Hello | HelloAck | Envelope
class ProtocolError(Exception): ...

# bridge/guard.py
class Verdict(BaseModel): allowed_without_confirmation: bool; executable: str | None
                          requires_confirmation: bool = False; reason: str
class Guard:
    def check_app(self, name: str) -> Verdict          # case-insensitive
    def check_power(self, action: str) -> Verdict      # ALWAYS requires confirmation

# bridge/executor.py
class ExecResult(BaseModel): status: Literal["ok","error"]; detail: str; audit_code: str
class Executor:
    async def launch(self, name: str, *, confirmation_id: str | None) -> ExecResult
    async def open_path(self, path: str, *, confirmation_id: str | None) -> ExecResult
    async def power(self, action: str, *, confirmation_id: str) -> ExecResult   # id mandatory

# src/pc_actions.py
class LaunchStatus(StrEnum): EXECUTED; CONFIRMATION_REQUIRED; FAILED
class PCActionCoordinator:      # composes BridgeServer + VaultClient + Notifier
    async def request_launch(self, app_name, *, origin: Literal["owner_chat"]) -> LaunchStatus
    async def request_power(self, action: str, *, origin) -> LaunchStatus
    async def handle_owner_reply(self, reply: str) -> str | None

# bridge/wol.py + bridge/idle.py
def magic_packet(mac: str) -> bytes            # b"\xff"*6 + mac*16; ValueError on bad MAC
async def send_wol(mac, ip, port=9) -> int     # UDP datagram, SO_BROADCAST, one sendto
def windows_last_input_seconds() -> float      # ctypes GetLastInputInfo (win only)
class IdleMonitor(threshold_minutes, on_idle, *, source=None, poll_seconds=30.0)
IDLE_OFFER_TEXT_AR = "صرت مدة طويلة بدون استخدام، بدهني أفعل وضع النوم أو إطفاء الجهاز؟"
```

**Audit codes (directive requirement)** — `audit_code = "PC-" + YYYYMMDD + "-" + HHMMSS + "-" + 4hex`
minted by the EXECUTOR for every command attempt (launch/open/power/wol), returned in every
`ExecResult`, persisted by the coordinator as a frontmatter field in
`04_Archives/Confirmations/{date}_{id8}.md` (for confirmed actions — alongside the full
confirmation ID) and appended to `04_Archives/Audit/pc-ledger.md` (for refusals and failures:
one line per event — ts, audit_code, action, outcome, reason). Sara quotes the audit code in
owner-facing messages. Vault-write failure during confirmation recording => confirmation NOT
minted and command never executes — approval without audit is void.

**Behavior** — Handshake: daemon dials `BRIDGE_SERVER_URL` (outbound), first frame Hello with
token equal under `hmac.compare_digest`; ack ok and register (single session — second concurrent
Hello gets ok=False/"another_session_active", close 4400). Wrong/missing/late -> close 4401,
WARNING with peer IP (never token), rate-limited. Liveness: bare heartbeats + transport ping;
core drops after 45 s silence. Commands: uuid Envelope.id -> future -> result resolves ->
TimeoutError on expiry. Reconnect: backoff min(cap, 2^(n-1)) ±20% jitter, reset on success.

LAN surface (`bridge/server.py`): binds `BRIDGE_LAN_PORT=8000` on the machine's LAN/loopback
addresses ONLY (never a second public listener), routes `GET /health` and
`GET /telemetry/live-state` (Bearer `BRIDGE_TOKEN` required — 401 otherwise); stdlib
`http.server` behind `asyncio.to_thread` (ponytail — no new dep).

Happy path: «شغلي الآلة الحاسبة» -> `request_launch("calculator", origin="owner_chat")` ->
send_cmd exec.launch -> Guard auto_approve -> spawn via CREATE_NEW_PROCESS_GROUP detached,
shell=False -> ok + audit_code -> «فتحته لك (رمز التدقيق PC-…)».

Non-whitelisted: daemon refuses WITHOUT executing -> coordinator prompts «هاد البرنامج مش
بالقائمة المعتمدة، هل بتأكدلي صراحة إنه بدك تشغله هسا؟», parks pending (TTL 10 minutes — expired
= dropped with INFO). Owner affirmative (consent binding rules from `common/consent.py`) mints
`confirmation_id = uuid4().hex` + audit_code, records to Confirmations/, re-sends WITH id; daemon
sees not_whitelisted + valid id -> executes. Power actions ALWAYS require a confirmation ID
regardless of whitelist flags (fail-closed even if whitelist wrongly marks them auto-approved).
Idle-offer integration: replies map via choice grammar — «نوم»/sleep, «اطفاء»/shutdown variants,
anything else = decline; offer routed through `request_power`; not repeated while latch held.

`open_path` — BLOCKER FIX (structural, carried from the 2026-08-26 Guide pass): open_path routes
THROUGH THE GUARD. Allowed WITHOUT confirmation: regular documents/media inside allowed roots with
safe extensions. Anything executable/script/shortcut (`.exe/.bat/.cmd/.lnk/.ps1/...`) is treated
AS AN APP LAUNCH: whitelist entry with auto_approve, or valid confirmation_id, else refused.
Traversal/UNC refusals stay.

WoL topology (settled ruling): the daemon's packets reach OTHER LAN machines / a second NIC; a
sleeping PC cannot be woken by its own daemon — documented known ceiling, env comments honest.
Idle events ride event envelopes; latch clears below half-threshold; tunnel-down keeps latch SET
(deliver on reconnect, no spam).

Untrusted containment: `origin` required literal `"owner_chat"` — email triage/vault
parsers/LLM output can NEVER invoke PC actions without an architectural change; suite pins it.
Whitelist re-read on every check; invalid JSON -> fail CLOSED (confirm-everything) + CRITICAL.
`bridge/__main__.py`: installs loguru sink, starts daemon + LAN surface, runs.

**Acceptance criteria**

1. AC1 — whitelisted auto_approve launches immediately. → `tests/test_whitelist_guardrail.py::test_whitelisted_app_executes`
2. AC2 — non-whitelisted -> refusal, coordinator CONFIRMATION_REQUIRED + Arabic prompt sent. → `test_nonwhitelisted_blocked_pending_confirmation`
3. AC3 — daemon-side: non-whitelisted launch with confirmation_id=None refused even from compromised core. → `test_bridge_refuses_unconfirmed_execution`
4. AC4 — full round-trip: block -> affirm -> confirmation note with SAME id + audit_code -> executed. → `test_confirmation_roundtrip_persists_and_executes`
5. AC5 — `power("shutdown", confirmation_id=None)` refused regardless of whitelist content (even wrongly-marked auto-approved entries); valid ID proceeds. → `test_restricted_power_always_requires_confirmation`
6. AC6 — `open_path` on a whitelisted-safe document inside C:/ succeeds; `open_path("C:/Windows/notepad.exe")` outside whitelist is REFUSED pending confirmation; `../../etc/passwd` and UNC refused with `outside_allowed_roots`. → `test_open_path_confined_and_guarded`
7. AC7 — `origin != "owner_chat"` raises RefusedOrigin. → `test_non_owner_origin_intent_refused`
8. AC8 — corrupt whitelist flips guard fail-closed + CRITICAL. → `test_corrupt_whitelist_fails_closed`
9. AC9 — every ExecResult carries a well-formed audit_code (`PC-YYYYMMDD-HHMMSS-xxxx`); refusals append exactly one ledger line to `04_Archives/Audit/pc-ledger.md`. → `test_audit_code_minted_and_ledger_appended`
10. AC10 — real websockets pair over localhost: Hello/HelloAck + heartbeats; daemon's ONLY listener is the LAN :8000 surface (bind asserted LAN/loopback-scoped, zero other listening sockets; outbound dial patched-socket test proves no inbound accept path). → `tests/test_bridge_protocol.py::test_auth_success_flow_and_lan_only_surface`
11. AC11 — WoL packet bytes exact 102-byte classic frame; malformed MACs raise ValueError; single UDP sendto on port 9 spied. → `tests/test_wol_idle.py::test_magic_packet_bytes_and_udp9_send`
12. AC12 — idle offer fires EXACTLY once per 20-min window despite continued polling; sub-half-threshold activity clears latch and re-arms; choice reply routes through confirmation flow producing one confirmation + one power command with same ID. → `test_idle_offer_once_rearm_and_choice_roundtrip`

**Error modes** — missing executable -> «البرنامج مش موجود عالجهاز» + ERROR; bridge offline at
send_cmd -> owner told unreachable, pending dropped (stale PC actions dangerous); daemon
exceptions -> error envelopes (tunnel survives); scanner log spam rate-limited; handler failures
never leak the token. Nothing swallowed.

**Zero-cost check** — websockets BSD-3 only new dep; LAN HTTP stdlib; $0 TLS not required on the
LAN surface (token auth; the tunnel to HF Spaces rides the Space's own TLS termination). Bandit-clean, shell=False everywhere.

**Docs impact** — `config/whitelist.json` defaults; ARCHITECTURE §2/§5 (outbound dial, LAN :8000
surface, audit-code flow, WoL ceiling); RUNBOOK (daemon autostart via Task Scheduler/NSSM, token
setup, whitelist editing, audit ledger location); `docs/06-API-SPECIFICATION` formalization
(launch_desktop_app/save_obsidian_note; force semantics DROPPED, confirmation_id + audit_code
documented); DATA-MODEL schemas; CHANGELOG; BACKLOG tick 3.4.

---

### 3.5 Desktop telemetry: `GET /telemetry/live-state`

Stream/worktree: vault-bridge | Depends on: 3.4

**Intent** — The master directive's live-state endpoint: the owner asks «شو وضع الجهاز؟» and Sara
answers with real numbers. The daemon serves a token-authenticated snapshot on its LAN :8000
surface (direct LAN diagnostics) AND relays the same payload through the outbound tunnel when the
core asks (Sara on HF Spaces cannot reach the LAN directly). Ponytail: one psutil snapshot
function, one core-side client, one Arabic narration — no dashboards, no history.

**Interface** — `bridge/telemetry.py`; `src/telemetry.py`; dep `psutil>=5.9` (BSD).

```python
# bridge/telemetry.py
class LiveState(BaseModel):
    cpu_percent: float; ram_used_gb: float; ram_total_gb: float
    disk_c_used_gb: float; disk_c_total_gb: float; disk_d_used_gb: float | None
    uptime_hours: float; top_process: str; top_process_cpu: float
    captured_at: datetime
def live_state() -> LiveState                       # psutil snapshot, <2 s
# bridge/server.py route: GET /telemetry/live-state (Bearer BRIDGE_TOKEN) -> live_state() JSON

# src/telemetry.py
class TelemetryClient:
    def __init__(self, bridge: BridgeServer, brain: OmniRouteClient)
    async def fetch_state(self, *, timeout_s: float = 20.0) -> LiveState   # via tunnel cmd telemetry.state
    async def narrate(self, state: LiveState) -> str                       # TIER 1 FAST, ar-JO line
```

**Behavior** — Snapshot: psutil cpu_percent(interval=None), virtual_memory, disk_usage("C:/") and
("D:/") (None when absent), boot_time uptime, top-CPU process name+percent (one
`process_iter` pass). Tunnel path: core sends `telemetry.state` cmd envelope -> daemon executes
`live_state()` -> result envelope -> pydantic-validated. Narration: ONE Arabic sentence via TIER
1 FAST (instant status line per ADR-16/ADR-18), numbers verbatim from the state — the LLM never
invents values and its output is display-only text. psutil absent/failed -> degraded snapshot
(fields None where unmeasurable) — never a crash. Offline bridge -> honest «الجسر مو متصل هسا»,
no fabricated numbers.

**Acceptance criteria**

1. AC1 — `live_state()` returns a fully-typed LiveState on the test host (fields in range, captured_at ISO-UTC). → `tests/test_desktop_telemetry.py::test_live_state_snapshot_shape`
2. AC2 — LAN endpoint without Bearer token -> 401; with token -> 200 JSON validating as LiveState. → `test_lan_endpoint_token_gated`
3. AC3 — full tunnel roundtrip: core cmd -> daemon result -> validated LiveState (mocked transport). → `test_telemetry_via_tunnel_roundtrip`
4. AC4 — Arabic narration contains the actual cpu/ram numbers passed in; LLM unreachable -> deterministic fallback line with raw numbers (owner still answered). → `test_narration_contains_real_numbers_and_fallback`
5. AC5 — missing D: drive -> `disk_d_used_gb is None`, narration omits D:. → `test_missing_second_disk_degrades`
6. AC6 — bridge offline -> honest Arabic offline message, no raise to the chat layer. → `test_offline_bridge_reported_honestly`
7. AC7 — payload carries no secrets (no token, no hostname beyond the daemon's own, no file paths). → `test_payload_free_of_secrets`
8. AC8 — telemetry.state is in `CmdName` and the daemon handler map; unknown-id results WARN+drop (reuses 3.4 correlation). → `test_cmd_registered_and_correlated`

**Error modes** — psutil failure -> degraded snapshot + WARN; tunnel timeout -> TimeoutError -> honest offline message; narration brain failure -> numeric fallback line. Nothing swallowed.

**Zero-cost check** — psutil BSD; narration rides the FAST-tier free pool. $0.00.

**Docs impact** — ARCHITECTURE §2 (telemetry node + endpoint); RUNBOOK «شو وضع الجهاز؟» smoke +
psutil note; CHANGELOG; BACKLOG tick 3.5.

---

## Sprint-3 skill rotation

Per the master directive, skills are loaded per-sprint into `.claude/skills/` and WIPED at sprint
exit (teardown protocol below) — code and tests persist, skills do not. Sprint 3 ingests:

| Skill | Source repo | Purpose this sprint |
|---|---|---|
| `tdd` | mattpocock/skills | red->green->refactor discipline across all five tasks |
| `git-guardrails` | 3mar-baha/universal-agentic-os | one structural change = one auditable vault commit (3.2), clean worktree hygiene |
| `test-guard` | amElnagdy/guard-skills | guards the sacred-floor + guard tests from silent weakening during refactors |
| `systems-architect` | worldflowai/everything-claude-code | bridge/protocol/executor decomposition of 3.4 |

Skills adapt the TDD/Guide workflow to vault-structure changes; they never loosen the whitelist
guardrail, the untrusted-content boundary, or the zero-cost invariant.

**Teardown protocol (sprint exit, binding)**:
1. All five tasks green, `make gate` green, docs + CHANGELOG synced.
2. Delete `.claude/skills/*` (sprint-3 set). Code/tests/docs are NEVER touched by teardown.
3. Record the teardown (skills removed, date, sprint outcome) in `docs/10-CHECKPOINT.md`.
4. Post the stream report (completed / remaining / risks / next action) for owner review; merge
   to main only after owner approval.

---

## Guide Review — Verdict: FIX (dispositions below)

Reviewer: independent Guide agent, adversarial pass, 2026-08-26. *(Drafted during classifier
degradation — Leader personally re-audited draft + findings line-by-line before acceptance.)*

- 🔴 **BLOCKER — open_path bypassed whitelist entirely**: RESOLVED structurally — guard-routed open_path, executable-as-app-launch rule, rewritten AC6 (now within AC6 of 3.4), daemon-side negative test.
- 🟠 **MAJOR — confirmation safety gaps (no TTL, loose prefix consent, no arbitration)**: RESOLVED — 10-min TTL, consent binding rules (AC6 3.3), confirmation-wins arbitration (AC5 3.3).
- 🟠 **MAJOR — AFFIRMATIVES dependency drift**: RESOLVED — hoisted to `common/consent.py`.
- 🟠 **MAJOR — idle-offer handoff underspecified**: RESOLVED — choice grammar + request_power + AC12 round-trip.
- 🟠 **MAJOR — para_path sanitizer self-contradiction**: RESOLVED — one deterministic transform, AC4 recomputed.
- **MINOR ×8 — TLS-fingerprint requirement · heartbeat telemetry removal · 1MB-cap rationale correction · Whisper language detection (now owned by Sprint-2 voice-to-vault task) · AC5 signature fix · coverage scope extension (`--cov=src,bridge,common`) · WoL topology canonical ruling · env-comment honesty**: ALL RESOLVED inline.

### Open questions carried into implementation

1. Whitelist key drift resolved: canonical = `requires_confirmation`, sleep=true.
2. WoL topology ruling recorded; second always-on LAN sender = optional future hardware decision for owner.
3. `04_Archives/Conversations/` confirmed as summary filing location; `04_Archives/Audit/pc-ledger.md` as audit ledger.
4. Pendings in-memory only for v1.0; vault-scratch persistence documented as upgrade path.
5. LAN surface auth = Bearer BRIDGE_TOKEN (no TLS on LAN; tunnel TLS rides the Space's WSS endpoint).
6. OBSIDIAN_REST_* vars stay reserved-unused (GitHub API sole transport).

---

## Re-map note (2026-08-29, MASTER ARCHITECTURAL DIRECTIVE)

The 2026-08-26 six-task layout (3.1 client · 3.2 voice-memo ingestion · 3.3 conversation capture
· 3.4 bridge protocol :8443 · 3.5 executor · 3.6 WoL/idle) is SUPERSEDED by the five-task
directive layout above: 3.1 vault architect + M6 mandatory dirs · 3.2 M5 taxonomy expansion ·
3.3 verbal action summary · 3.4 merged guardrail + bridge (LAN :8000, outbound-only, audit codes)
+ WoL (UDP 9) + 20-min idle · 3.5 desktop telemetry. Voice-memo ingestion moved to Sprint 2 as
the voice-to-vault transcriber (local Whisper — decided by directive, superseding the old
"decide at task entry" note). All 2026-08-26 Guide dispositions and rulings remain binding where
not superseded. ADR cross-references: ADR-15 (HF Spaces), ADR-16 (3-Tier brain), ADR-21 (5-dir
vault).
