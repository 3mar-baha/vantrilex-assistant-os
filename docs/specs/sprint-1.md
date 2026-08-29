# Spec — Foundation: Gateway + Voice Pipeline + Bot Shell (stream: core-foundation)

Sprint 1 of the Phase 2 implementation plan. Stream lives in git worktree `core-foundation`
(one concern per merge; merge order below). Every task lands red -> green -> refactor with
tests and docs in the same commit (`docs/05-TEST-PLAN.md` §3 gate checklist is the exit gate).

## Global constraints (apply to every task)

- Python 3.12 (`py -3.12`), 100% async (`asyncio`, `httpx`, `aiogram`); no blocking calls on the loop.
- Config via pydantic v2 settings loading `.env`; secrets never hardcoded, never committed.
- Logging via loguru, structured binds (`logger.bind(...)`); exceptions are logged with
  `logger.opt(exception=...)` or re-raised — zero silent swallows.
- Lint/format: `ruff check .` && `ruff format --check .` clean; bandit high/critical zero.
- Owner-only access everywhere: `AUTHORIZED_USER_ID` gates every update at middleware level.
- Parsed external content is DATA never instructions (this sprint: LLM output is display-only text).
- v1.0 scope: NO PyTgCalls live calls; critical triage (Sprint 2) = priority voice note + repeat ping.
- Zero-cost invariant: every dependency FOSS and free-tier compliant; all compute local/free pools.
- Ponytail minimalism: smallest abstraction that satisfies this spec; constants over config keys
  unless a value demonstrably changes per deployment.

## Dependency order (merge order)

| # | Task | Depends on | Notes |
|---|---|---|---|
| 1 | 1.1 Project skeleton: config, logging, health, entrypoint | — | Gates everything |
| 2a | 1.2 OmniRoute client | 1.1 | Parallelizable with 2b |
| 2b | 1.3 Voice pipeline (Edge-TTS -> Ogg Opus) | 1.1 | Parallelizable with 2a |
| 3 | 1.4 Aiogram bot shell + owner middleware | 1.1, 1.2, 1.3 | Wires the stream end to end |

Stream done when: `make setup && make gate` green from clean clone, live smoke checklist passes
(owner message -> brain reply; `/start` voice note plays in Telegram; time-to-first-encoded-chunk
< 600 ms measured once locally), CHANGELOG updated under `[Unreleased]`.

---

### 1.1 Project skeleton: config, logging, health, entrypoint

Stream/worktree: core-foundation | Depends on: —

**Intent** — Create the async Python package that every later module plugs into: `src/` package,
pydantic v2 `Settings` validating `.env`, one-function loguru setup, a small health probe used by
ops (`python -m src.main --health`) and by later sprints' self-checks, and an async entrypoint
behind the existing `make run-core` target. Also introduces tool configuration (ruff, pytest +
coverage floor) so `make gate` becomes meaningful the moment the first source line lands.

**Interface**

Module tree delivered by this task:

```
src/
  __init__.py
  config.py      # Settings, get_settings()
  logsetup.py    # configure_logging()
  health.py      # healthcheck()
  main.py        # run(argv) -> int, main() console entry
tests/
  conftest.py    # extended: make_settings factory fixture (env-dict based)
  test_config.py, test_logsetup.py, test_health.py   # new
  test_scaffold.py   # existing: owns the canonical-file manifest assertion
pyproject.toml   # NEW: [tool.ruff], [tool.pytest.ini_options]
```

Signatures (exact):

```python
# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Sprint-1 critical: no defaults -> boot fails fast without them
    omniroute_base_url: str          # OMNIROUTE_BASE_URL
    omniroute_api_key: str           # OMNIROUTE_API_KEY
    primary_model: str               # PRIMARY_MODEL
    fast_model: str                  # FAST_MODEL
    telegram_bot_token: str          # TELEGRAM_BOT_TOKEN
    authorized_user_id: int          # AUTHORIZED_USER_ID (coerced from string)

    # Declared now (validates every var in .env.example), consumed by later sprints:
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_user_session_string: str | None = None
    voice_name: str = "ar-JO-SanaNeural"     # VOICE_NAME
    voice_rate: str = "+0%"                  # VOICE_RATE
    voice_pitch: str = "+0Hz"                # VOICE_PITCH
    vault_github_repo: str | None = None
    vault_github_token: str | None = None
    obsidian_rest_api_url: str | None = None
    obsidian_api_key: str | None = None
    google_oauth_client_json: str = "./config/google_oauth_client.json"
    google_calendar_id: str = "primary"
    bridge_token: str | None = None
    bridge_server_url: str | None = None
    bridge_bind_port: int = 8443
    target_pc_mac_address: str | None = None
    target_pc_ip: str | None = None
    target_pc_wol_port: int = 9
    tz: str = "Asia/Amman"
    log_level: str = "INFO"
    idle_shutdown_minutes: int = 20

def get_settings() -> Settings  # functools.lru_cache(maxsize=1) wrapper around Settings()

# src/logsetup.py
def configure_logging(level: str = "INFO") -> None
    # logger.remove(); logger.add(sys.stderr, level=level.upper(),
    #   format="{time:YYYY-MM-DDTHH:mm:ssZZ} | {level: <8} | {name}:{function}:{line} | {message}")

# src/health.py
async def healthcheck(settings: Settings, *, probe_gateway: bool = True) -> dict[str, str]
    # returns {"gateway": "ok"|"unreachable"|"unchecked",
    #          "telegram_token": "set"|"missing",
    #          "ffmpeg": "found"|"missing",       # shutil.which("ffmpeg")
    #          "overall": "ok"|"degraded"}

# src/main.py
async def run(argv: list[str] | None = None) -> int
def main() -> None            # sys.exit(asyncio.run(run()))
```

Env vars touched: every var declared above (full `.env.example` enumeration). Consumed this
sprint: `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`, `PRIMARY_MODEL`, `FAST_MODEL`,
`TELEGRAM_BOT_TOKEN`, `AUTHORIZED_USER_ID`, `LOG_LEVEL`. Config file: `pyproject.toml` gets
`[tool.ruff]` (`line-length = 100`, `target-version = "py312"`) and
`[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`;
coverage threshold activation lands in Sprint 4 per its spec — measurement only here).

**Behavior**

1. Import-time behavior stays side-effect-free: constructing `Settings()` reads `.env` + process
   env; missing any of the six critical fields raises `pydantic.ValidationError` naming them.
   Later-sprint fields default `None`/example values and become required in the commit whose task
   first consumes them (documented rule, keeps boot green before Google/vault exist).
2. **Empty-string normalization (Guide amendment)**: a `field_validator(mode="before")` maps
   empty-string env values to `None` for EVERY Optional field, and rejects empty strings for the
   six required fields as missing. `.env.example` contains empty assignments; without this rule
   `telegram_api_id=""` fails int coercion and `bridge_token=""` reads as configured.
3. `configure_logging` is idempotent: removes existing sinks then installs exactly one stderr sink
   at the requested level; unknown level strings fail fast via loguru's own error.
4. `main.py` flow: parse args -> `Settings()` -> `configure_logging(settings.log_level)` ->
   if `--health` in argv: run `healthcheck`, print JSON report to stdout, exit 0 when
   `overall == "ok"` else 1, never start polling. Otherwise log "core starting" with bound
   fields (`owner_id`, base_url host only — never the API key or token) and hand off to the bot
   runner added by 1.4 (`run_bot(settings)` imported lazily so 1.1 alone boots standalone).
5. `healthcheck` probes the gateway with a one-shot `httpx.AsyncClient` GET `{base}/models`
   (5 s timeout): HTTP 200 -> `"ok"`, anything else/exception -> `"unreachable"` (warn-level log).
   Telegram check is presence-of-token, not network. ffmpeg check is `shutil.which`.
   Degraded components never crash the process — health reports, ops decide.
6. `Makefile` unchanged (`run-core` starts working here). Root `conftest.py` kept;
   `tests/conftest.py` gains a `make_settings(**overrides)` factory building valid `Settings`
   from an env dict mirroring `.env.example`.

**Acceptance criteria**

1. AC1 — A Settings built from a dict mirroring literal `.env.example` contents validates cleanly,
   exposes all fields, AND `settings.telegram_api_id is None` AND `settings.bridge_token is None`
   (empty-string normalization proven). Target: `tests/test_config.py::test_settings_accept_all_env_example_vars`.
2. AC2 — Dropping any of the six critical fields raises `ValidationError` naming the missing field(s).
   Target: `tests/test_config.py::test_settings_fail_fast_on_missing_core_vars`.
3. AC3 — `AUTHORIZED_USER_ID="123456789"` coerces to `int`. Target: `tests/test_config.py::test_owner_id_coerced_from_string`.
4. AC4 — After `configure_logging("DEBUG")`, exactly one sink exists at DEBUG; calling twice does not duplicate sinks.
   Target: `tests/test_logsetup.py::test_single_sink_at_configured_level_and_idempotent`.
5. AC5 — Mocked gateway 200 -> `{gateway: ok, overall: ok}`; connection refused -> `{gateway: unreachable, overall: degraded}` + warning, no raise. Gateway route and `shutil.which`/token checks stubbed so the AC is machine-independent.
   Target: `tests/test_health.py::test_healthcheck_reports_gateway_status`.
6. AC6 — `run(["--health"])` prints JSON report and returns 0/1 per status without invoking the polling runner (import site asserted uncalled).
   Target: `tests/test_health.py::test_main_dash_health_exits_without_polling`.
7. AC7 — Gate integrity from clean clone: `make setup && make gate` exits 0 including docs guard.
   Evidence: gate run pasted into PR (manual AC).

**Error modes**

- Missing/invalid critical env var -> `ValidationError` caught in `main()`, logged with field list, non-zero exit before any network activity. Never a partial start.
- Unknown extra env keys -> ignored (`extra="ignore"`), one debug line listing ignored names.
- Gateway probe failure during healthcheck -> warn log, status `"unreachable"`; no raise.
- Invalid `LOG_LEVEL` value -> loguru raises at sink creation; surfaced as loud startup failure.

**Zero-cost check** — No new dependencies: pydantic, pydantic-settings, loguru, httpx already pinned (MIT/BSD). $0.00 delta.

**Docs impact** (same commit) — `README.md`: `--health` usage; `docs/04-RUNBOOK.md`: health procedure;
`CHANGELOG.md` `[Unreleased]/Added`; `docs/02-BACKLOG.md`: tick 1.1.

---

### 1.2 OmniRoute client: streaming, PRIMARY->FAST fallback, quota/retry

Stream/worktree: core-foundation | Depends on: 1.1

**Intent** — The brain engine adapter: one small class that talks OpenAI-compatible
`/chat/completions` against `OMNIROUTE_BASE_URL` over httpx, streams SSE deltas as an async
iterator, and survives free-pool reality — quota exhaustion falls back immediately, transient
failures retry with capped backoff, fatal errors stop loudly. Only module that knows what an LLM
endpoint looks like; Sprint 2+ consume it blindly.

**Interface**

```python
# src/gateway.py
RETRY_ATTEMPTS: Final[int] = 3
BACKOFF_BASE_S: Final[float] = 0.5
BACKOFF_CAP_S: Final[float] = 8.0
REQUEST_TIMEOUT_S: Final[float] = 120.0

class GatewayError(RuntimeError): ...

class OmniRouteClient:
    def __init__(self, base_url: str, api_key: str, *, primary_model: str, fast_model: str,
                 timeout_s: float = REQUEST_TIMEOUT_S,
                 transport: httpx.AsyncBaseTransport | None = None) -> ...
    async def __aenter__(self) -> "OmniRouteClient": ...
    async def __aexit__(self, *exc_info) -> None: ...
    def stream_chat(self, messages: list[dict[str, str]], *, temperature: float = 0.7,
                    max_tokens: int = 2048) -> AsyncIterator[str]
    async def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.7,
                   max_tokens: int = 2048) -> str
    async def aclose(self) -> None
```

Module-private helpers: `_attempt(model, payload)` (one streaming attempt);
`_classify(status_code, body_snippet) -> Literal["fatal","quota","transient"]`.

**Behavior**

Request: `POST {base_url}/chat/completions`, Bearer header, `stream: true` JSON body.

Streaming semantics (per attempt):
1. Non-200: read body (first 500 chars), classify, raise classified failure.
2. 200: iterate `aiter_lines()`; `data:` lines stripped; empties/keep-alives skipped;
   `data: [DONE]` terminates; each chunk contributes `choices[0].delta.content` when non-empty.
   Malformed JSON line -> warning, continue.
3. Lazy generator; cancellation closes the httpx stream promptly.

Fallback engine: per model in `(primary, fast)`:
- `quota` (402, or 429/quota-marker body) -> zero retries, advance to next model immediately.
- `transient` (408/409/425, 429 w/o quota markers, 5xx, timeout/transport errors) -> up to
  RETRY_ATTEMPTS with capped exponential backoff, then advance.
- `fatal` (400/401/403/404/422) -> immediate `GatewayError`; no retry, no fallback.
Both exhausted -> `GatewayError` naming both models + last cause. Every transition logs binds.

Mid-stream failure after >=1 delta yielded: NO transparent restart (owner would see duplicated
half-reply) — error log + `GatewayError`; bot shell owns user-facing recovery.

**Missing-[DONE] guard (Guide amendment)**: stream ending without `data: [DONE]` and without a
transport error -> WARNING logging bytes/deltas received; chunks remain valid and are delivered.

`chat()` = join over `stream_chat`. Lifecycle: created once in `src/main.py`, async context manager.

**Acceptance criteria** (all via `httpx.MockTransport` scripts; request-order asserted via recorded model fields)

1. AC1 — Happy path deltas arrive in order; request carried stream=true + Bearer. → `test_stream_yields_deltas_with_stream_true_and_bearer`
2. AC2 — Primary 402/quota -> one primary attempt then FAST succeeds, zero retries burned. → `test_quota_on_primary_switches_to_fast_immediately`
3. AC3 — Primary 500 ×3 (backoff stubbed short) -> 3 attempts then FAST first-try success. → `test_transient_errors_retry_then_fallback`
4. AC4 — Primary 401 -> `GatewayError`; FAST never contacted. → `test_fatal_auth_error_raises_without_fallback`
5. AC5 — Both models 503 across attempts -> `GatewayError` naming both. → `test_both_models_exhausted_raises_gateway_error`
6. AC6 — SSE edges: early `[DONE]`; null-delta skip; malformed-line skip-with-warning. → `test_sse_edge_cases_done_null_and_malformed`
7. AC7 — Mid-stream disconnect after first delta raises immediately. → `test_midstream_failure_after_first_delta_raises`
8. AC8 — Stream ends WITHOUT `[DONE]`: warning logged binding received byte count, deltas still delivered. → `test_missing_done_marker_warns_and_delivers`
9. AC9 — `chat()` concatenates streamed deltas. → `test_chat_aggregates_deltas`
10. AC10 — Live-gateway criterion: manual smoke vs running OmniRoute recorded as PR evidence (Q5 ruling: CI proves ordering via MockTransport; live smoke is credential-gated manual evidence).

Targets prefixed `tests/test_omniroute_gateway.py::`.

**Error modes** — connect/DNS/timeout both models -> GatewayError after logged retries; quota -> info-level fallback log (normal free-pool life); fatals -> error log with status+body snippet (never the key); malformed frame -> warning, continue; consumer cancel -> stream closed in finalization. No silent swallows anywhere.

**Zero-cost check** — httpx pinned (BSD-4); traffic only to self-hosted OmniRoute free pools. $0.00.

**Docs impact** — ARCHITECTURE §1/§2 note `src/gateway.py`; RUNBOOK "brain down?" triage via GatewayError signature; CHANGELOG; BACKLOG tick 1.2.

---

### 1.3 Voice pipeline: Edge-TTS -> BytesIO -> ffmpeg -> Ogg Opus, first-chunk dispatch

Stream/worktree: core-foundation | Depends on: 1.1

**Intent** — Turn finalized reply text into a Telegram-native Ogg Opus voice bubble with
`ar-JO-SanaNeural`, fully in memory, structured as an async byte-chunk iterator whose first
encoded chunk surfaces immediately. Delivery mechanism for Important/Critical triage and spoken
replies; must fail loudly and reap its subprocess on every path.

**Interface**

```python
# src/voice.py
FFMPEG_BIN: Final[str] = "ffmpeg"
MAX_TTS_CHARS: Final[int] = 4000
OGG_READ_CHUNK: Final[int] = 4096

class VoicePipelineError(RuntimeError): ...

class VoicePipeline:
    def __init__(self, *, voice: str, rate: str, pitch: str, ffmpeg_bin: str = FFMPEG_BIN) -> None
    def synthesize_stream(self, text: str) -> AsyncIterator[bytes]
    async def synthesize(self, text: str) -> bytes
```

Sender shape (1.4 / Sprint 2): `await message.answer_voice(BufferedInputFile(ogg_bytes, filename="sara.ogg"))`.

**Behavior**

1. Pre-spawn validation: blank -> ValueError; > MAX_TTS_CHARS -> ValueError.
2. Native-async spawn: `asyncio.create_subprocess_exec(ffmpeg, -hide_banner -loglevel error
   -f mp3 -i pipe:0 -map_metadata -1 -fflags +nobuffer -flags +low_delay -c:a libopus -b:a 24k
   -ar 48000 -ac 1 -vbr on -frame_duration 20 -application voip -f ogg -flush_packets 1 pipe:1,
   stdin=PIPE, stdout=PIPE, stderr=PIPE)`. asyncio subprocess IS the non-blocking form — **the
   CLAUDE.md rule-8 parenthetical and ARCHITECTURE §3 step-3 wording change to "via asyncio
   subprocess (natively non-blocking)" in this task's commit (Guide amendment)**.
   FileNotFoundError at spawn -> VoicePipelineError("ffmpeg binary not found — install it (docs/04-RUNBOOK.md)").
3. Two concurrent tasks: producer streams Edge-TTS MP3 audio chunks into stdin (WordBoundary
   metadata skipped), half-closes stdin on completion; consumer reads stdout chunks and yields
   each immediately — first yield IS the first-chunk event.
4. Completion: await proc.wait(); non-zero -> stderr tail (<=500B) into VoicePipelineError.
5. Cleanup on EVERY path (finally + contextlib): terminate/kill child, close pipes, cancel producer. No orphan ffmpeg ever.
6. **Latency metric (binding, Q1 approved)**: measured as time-to-first-encoded-chunk from
   synthesize_stream (Telegram Bot API cannot progressively upload one bubble); ARCHITECTURE §3
   steps 3–4 reworded accordingly in this commit.
7. Untrusted boundary: only Sara/system-originated strings reach TTS (enforced structurally in 1.4).

**Acceptance criteria**

Real-transcode tests skip when ffmpeg absent (`shutil.which`).

1. AC1 — Canned MP3 fixture -> first bytes `b"OggS"`, aggregate contains `b"OpusHead"`. → `tests/test_audio_stream_opus.py::test_real_ffmpeg_emits_valid_ogg_opus`
2. AC2 — Slow fake producer: first chunk arrives strictly before producer completion and proc.wait(). → `test_first_chunk_arrives_before_completion`
3. AC3 — `builtins.open` + `tempfile.*` monkeypatched to raise: full round-trip completes, zero calls. → `tests/test_edge_tts_pipeline.py::test_no_disk_writes_end_to_end`
4. AC4 — Patched edge_tts.Communicate records kwargs equal to Settings voice/rate/pitch. → `test_voice_params_flow_from_settings`
5. AC5 — Blank/>max text rejected pre-spawn (spawn sentinel uncalled). → `test_blank_or_oversized_text_rejected_pre_spawn`
6. AC6 — Missing ffmpeg -> actionable VoicePipelineError. → `test_missing_ffmpeg_raises_actionable_error`
7. AC7 — Mid-stream synthesis failure: producer cancelled, ffmpeg reaped, error raised. → `test_synthesis_failure_cancels_and_reaps_ffmpeg`
8. AC8 — Metadata events never forwarded; audio bytes pass through unchanged. → `test_metadata_events_skipped_only_audio_forwarded`

**Error modes** — input guards loud; missing binary actionable; Edge-TTS network failure converts to VoicePipelineError after reaping, caller degrades to text-only (voice loss never kills chat reply); ffmpeg exit -> stderr tail captured; abandonment/cancellation -> same reap path. All failures loguru-bound, none swallowed.

**Zero-cost check** — edge-tts pinned (free Microsoft neural endpoint, no key); ffmpeg FOSS via apt/choco. No new Python packages. $0.00.

**Docs impact** — ARCHITECTURE §3 rewrite (metric + module path + asyncio-subprocess wording); RUNBOOK ffmpeg install + latency smoke; CHANGELOG; BACKLOG tick 1.3.

---

### 1.4 Aiogram 3.x shell: long polling, owner-ID silent-drop middleware, echo-through-brain

Stream/worktree: core-foundation | Depends on: 1.1, 1.2, 1.3

**Intent** — Transport layer: long-polling dispatcher that physically cannot hear anyone but the
owner (outer middleware drops every other account before filters/handlers/outbound calls exist),
plus minimal handlers proving the stream E2E: `/start` (text + synthesized greeting), `/help`,
owner text routed through `OmniRouteClient.stream_chat` with typing indicator and ONE aggregated
reply, static ack for inbound voice notes (transcription is 3.2). Structural enforcement point of
owner-only and of the display-only boundary.

**Interface**

```python
# src/middleware.py
def _extract_user_id(update: Update) -> int | None:
    """Iterate Update event fields (message, edited_message, callback_query, ...) and return
    .from_user.id of the first populated one; None when absent/anonymous."""
class OwnerOnlyMiddleware(BaseMiddleware):
    def __init__(self, owner_id: int) -> None
    async def __call__(self, handler, event: TelegramObject, data: dict) -> Any
        # uid = _extract_user_id(update); uid != owner_id -> logger.debug(drop), return None
        # else -> await handler(event, data)
```

(Guide amendment: the draft's `getattr(event, "event", None)` accessor does not exist on aiogram
3.x raw Updates — resolution MUST go through `_extract_user_id`, unit-tested on message AND
callback_query shapes.)

```python
# src/bot.py
SYSTEM_PROMPT_AR / WELCOME_AR / HELP_AR / VOICE_ACK_AR / APOLOGY_AR: Final[str]

def build_dispatcher(gateway, voice, settings) -> Dispatcher
    # OwnerOnlyMiddleware on dp.update.outer_middleware, then:
    # CommandStart -> welcome text + answer_voice(greeting)
    # Command("help") -> HELP_AR ; F.voice -> VOICE_ACK_AR (no gateway call)
    # F.text -> brain echo ; dp.errors -> global handler

async def run_bot(settings) -> None   # Bot(token) eager validation -> optional get_me() sanity
                                      # -> dp.start_polling(bot, skip_updates=True)
```

**Behavior**

Owner gate: OUTER middleware executes for EVERY update type before any filter/handler; returning
None ends propagation — dropped updates produce literally zero Telegram API traffic since handlers
are the sole outbound origin. Anonymous/no-user contexts drop. Drop logging debug-level with update id.

Handlers:
- `/start`: WELCOME_AR + synthesized greeting voice note (standing E2E proof of 1.3).
- `/help`: capability list (inbox/triage/vault noted as coming online Sprints 2–3).
- Owner voice note: static ack, zero gateway calls.
- Owner text: typing indicator; deltas aggregated into ONE buffer; **single plain-text reply**
  (`parse_mode` unset — v1 avoids MarkdownV2 breakage from model output; rich formatting deferred
  to Sprint 2 orchestrator; ARCHITECTURE §1 "Markdown chat" wording synced in this commit).
  Generated content rendered verbatim — never interpreted as command/whitelist entry/action.
- `GatewayError` in handler -> `APOLOGY_AR` sent, exception logged; owner never left hanging.
- **Empty-buffer guard (Guide amendment)**: aggregated whitespace-only buffer -> fixed Arabic
  fallback line instead of `message.answer("")` (Telegram rejects empty sends).
- Global `dp.errors`: traceback + update id, one apology, marks handled — polling never wedges.

Lifecycle: eager token-format validation; optional get_me() catches revoked tokens; skip_updates
drops reboot backlog deliberately; shutdown closes gateway client. Outbound-only posture preserved.

**Acceptance criteria** (middleware tested directly with fake handler spies + constructed Updates; shell via `build_dispatcher` + recording `fake_bot`; shared fixtures `make_settings/fake_bot/owner_update/stranger_update`)

1. AC1 — Stranger private text: zero handler invocations, zero outbound methods. → `tests/test_owner_middleware.py::test_non_owner_message_dropped_zero_outbound_calls`
2. AC2 — Stranger callback_query equally dropped. → `test_non_owner_callback_query_also_dropped`
3. AC3 — `_extract_user_id` resolves owner id from message AND callback_query shapes; returns None for anonymous contexts. → `test_extract_user_id_shapes`
4. AC4 — Owner update passes through exactly once untouched. → `test_owner_update_reaches_handler`
5. AC5 — Middleware registered at `dp.update.outer_middleware` (introspection). → `test_middleware_registered_at_update_outer_level`
6. AC6 — `/start`: welcome text + one answer_voice with non-empty buffered bytes. → `tests/test_bot_shell.py::test_start_sends_welcome_and_voice_greeting`
7. AC7 — `/help` replies with capabilities. → `test_help_lists_capabilities`
8. AC8 — Owner text + scripted deltas -> exactly one reply equal to concatenation, typing issued, gateway got system prompt + owner text ONLY. → `test_owner_text_streams_brain_into_single_reply`
9. AC9 — Empty/whitespace aggregation -> Arabic fallback line, not an empty send. → `test_empty_brain_buffer_sends_fallback_line`
10. AC10 — GatewayError -> APOLOGY_AR + logged, nothing escapes dispatcher. → `test_brain_failure_sends_apology_and_logs`
11. AC11 — Voice-note ack with zero gateway calls. → `test_voice_note_acknowledged_without_brain_call`
12. AC12 — Live smoke (manual, credentials-gated, recorded in PR): real owner message -> real streamed reply; `/start` voice plays audibly in Jordanian Arabic.

**Error modes** — invalid/revoked token -> loud startup exit (token value never printed); polling flaps absorbed by aiogram internals, sustained outage visible in logs; handler exceptions -> errors handler, apology, handled; voice synthesis failure on /start -> text still delivered.

**Zero-cost check** — aiogram pinned (MIT); long polling needs no webhook/public endpoint. $0.00.

**Docs impact** — TEST-PLAN §2 rows for `test_config/logsetup/health/bot_shell`; ARCHITECTURE §2 annotate Core node (`src/bot.py` chokepoint) and §1 plain-text wording; README prerequisites; RUNBOOK first-boot checklist; CHANGELOG; BACKLOG tick 1.4.

---

## Guide Review — Verdict: FIX (all findings resolved above)

Reviewer: independent Guide agent, adversarial pass, 2026-08-26. Dispositions:

- **MAJOR — owner-resolution API nonexistent** (`Update.event` accessor): RESOLVED — `_extract_user_id` helper specified with dedicated AC3 covering message/callback_query shapes.
- **MAJOR — empty-env validation unsatisfiable**: RESOLVED — empty-string→None validator added (Behavior §2), AC1 extended to assert `telegram_api_id is None` / `bridge_token is None`; staged-required-fields rule (Q2) APPROVED with this normalization attached.
- **MINOR — executor-wording conflict** (CLAUDE.md rule 8 / ARCH §3 vs native asyncio subprocess): RESOLVED — doc rewording scheduled inside 1.3's commit.
- **MINOR — plain-text vs "Markdown chat" drift**: RESOLVED — Q6 approved; ARCH §1 wording sync inside 1.4's commit.
- **MINOR — silent truncation / empty-reply edges**: RESOLVED — missing-[DONE] warning behavior added to 1.2 (AC8) and empty-buffer fallback added to 1.4 (AC9).
- **MINOR — test-target hygiene**: RESOLVED — `test_scaffold.py` declared in module tree; AC5 stubs machine-dependent probes; HealthReport alias dropped (plain dict).
- **Open questions — rulings**: Q1 APPROVED (<600ms = time-to-first-encoded-chunk; ARCH §3 rewording mandatory in 1.3 commit) · Q3 APPROVED (سارة wins; retired-name ingest drafts superseded; no legacy-persona social-hook examples this sprint) · Q4 APPROVED (ffmpeg hard dependency owned by RUNBOOK; NO raw-MP3 fallback) · Q5 APPROVED (CI proves fallback ordering via MockTransport; live smoke manual + recorded).

**Amendment (2026-08-29, task 1.3 implementation)**: `-analyzeduration 0 -probesize 32`
prepended to the specced ffmpeg input options. Measured: default probesize gates ALL output
until EOF on piped MP3 (first chunk at ~1.0s = producer close), violating binding Q1
(<600 ms time-to-first-encoded-chunk); with the tiny probe the first encoded chunk surfaces
in ~30ms while stdin is still open. All other args verbatim.
