# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning targets [Semantic Versioning](https://semver.org/) starting at v1.0.0.
("v1.1.0" in project branding names the Universal Agentic OS framework Sara is built on;
product release tags start independently at v1.0.0.)

## [Unreleased]

### Added — dual console: clean chat REPL, CLI field drill, 6th HUD marker (2026-09-30)
- **`src/bot_shell.py`** — Terminal 1. `build_shell(gateway, settings) -> Shell`, and
  `Shell.turn(text)` is an async generator yielding the dispatcher's deltas **verbatim**.
  The module imports none of `src.persona`, `src.gender_pipeline`, `src.voice_policy`,
  `src.tools`, `src.pc_actions` or `bridge.executor`; a guard parses it with `ast` and
  asserts it. Invariant preservation is structural — there is no second code path for a
  gender, dialect or confirmation rule to leak through. A failed turn yields one honest
  Amman line, never a traceback and never an empty string.
- **`sara.bat -Chat`** launches it; **`sara.bat --tracer`** is a new alias of the existing
  `-Trace`. Both flags are purely additive — 14 lines added, 0 removed, CRLF preserved,
  and `-Trace` / `-InstallAutoStart` are untouched.
- **`scripts/test_cli_live_drill.py`** — programmatic multi-turn CLI field testing. Its
  launch row records the **refusal** as the expected outcome (146 ms live), and a PID
  diff across a full run showed 73 Chrome processes before and 73 after. It never supplies
  a `confirmation_id`, carries its own fail-closed whitelist rather than reading
  `config/whitelist.json`, and calls the dispatcher with `tools=None`. Adds ~101 s to the
  suite — intrinsic to drilling the real gateway, not worked around.
- **`scripts/live_shadow_tracer.py`** — the sixth HUD marker. The `invariants` classifier
  group is **first** in `DOMAIN_RULES`, because `classify_record` is first-match-wins and a
  real invariant report collides with both `generation` (`$0.00 cost`) and `audio`
  (`Zero Edge-TTS`). Per-tool gateway counters added. **Measured limit, stated in the
  code:** only the tool lane's failure path emits a marker, so the counters count recorded
  tool-lane events, not total tool traffic.

### Resolved — Terminal 1 answers in ar-JO, not MSA (owner decision 2026-09-30)
This entry previously announced an MSA limitation. It was stale: the safety rule it named
as the cause has since been narrowed, and `src/bot_shell.py` binds EXACTLY ONE symbol from
`src.persona` — `build_persona_joda`, the builder — composing it into
`TERMINAL_SYSTEM_PROMPT` at import and into the `system` default of `_live_shell`
(`tests/test_bot_shell_dialect.py` asserts that binding). There is no second dialect path:
the builder composes the byte-locked identity core with the JODA ar-JO few-shot exemplars,
so the terminal and Telegram share one dialect and one masculine-address contract. What
remains banned is the other persona literals — the raw core and the exemplars — because a
copied literal is a second source of truth.
`tests/test_changelog_dialect_claims.py` now re-derives this binding from the source and
fails if the changelog re-announces the limitation the tree refutes.

### Added — 10-agent agency swarm + binding Precision Workflow (2026-09-30)
- **`.claude/skills/vantrilex-precision-workflow/SKILL.md`** — vendored
  byte-identical (hash-verified) into the repo. It previously existed only at the
  user level, so it loaded on one machine and for no sub-agent in a fresh checkout.
- **`CLAUDE.md` §5.1** — the skill is now the binding contract for the root agent,
  every role in `.claude/agents/`, and every dispatched sub-agent. All seven
  directives are named with their one-line tests. Scope clarified: concurrent
  read-only reconnaissance and review sub-agents are authorized; parallel
  **writers** are not, so the closed-loop rule at §5 stands.
- **10 Sara-bound agent roles** in `.claude/agents/`. Nine wrap a persona from
  [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents)
  (MIT, pinned `765be423`), vendored verbatim into `.claude/agents/agency/`.
  `github-ecosystem-miner` has no upstream counterpart and is authored locally.
- **`scripts/launch_parallel_scouts.py` + `tests/test_parallel_scouts.py`** —
  concurrent in-process runner for the two internal reconnaissance scouts on a
  `ThreadPoolExecutor`; the two external scouts return `deferred_to_harness` with a
  dispatch manifest and zero findings. Stdlib only, 41 tests.
- **`docs/architecture/AGENCY_SWARM_WORKFLOW.md`** — the roster, the four governance
  rules, and — for each — the mechanism that would enforce it, including the two
  rules whose enforcement is a convention rather than a gate.

### Fixed — two correctness defects in the scout detectors
- The unbounded-concurrency detector reported `src/agent_manager.py:247` as having no
  bound, when `_trim_lines` caps the iterable at `MAX_LINES` one call upstream. It now
  resolves the upstream cap and reports `bounded-fanout` with the citing line.
- The silent-swallow classifier read a handler's inline comment via `ast.unparse`,
  which strips comments — so the documented "handler comment marks it deliberate"
  signal could never fire, and two structurally identical handlers in
  `src/associative.py` received opposite verdicts. It now reads real source lines via
  a `tokenize`-based comment map with suppression pragmas stripped.

### Added — cross-framework analysis & self-evolution blueprint (2026-09-30)
- **`docs/architecture/CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md`** — a
  24-resource architectural matrix (orchestration, governance, memory, observability,
  System-1 decision layers), the five-stage self-evolution specification modelled on
  the [Mojito](https://github.com/TimeLovercc/mojito) self-rebuild loop, a comparative
  analysis against unconstrained self-rewriting, and the roadmap P3-A…P3-D with the
  exact assertions each phase must pass.
- **Documentation only — no runtime change.** Nothing in the blueprint is implemented.
  It also records three corrections to the source dossier (§8 of the document): Laya is
  a 33 ms non-autoregressive decision model rather than a sub-10 ms ModernBERT
  classifier; the Jev speed/cost figures are vendor-published; and
  `TOOL_CAPABILITIES` holds **42** capabilities, not 46.
- The document's central finding for the runtime: registering a new tool is **four**
  edits, not one — `ToolRegistry.call`'s `getattr` seam is runtime-bindable, but
  `_VALID_TOOLS` and `_TOOL_GOALS` are `Final` literals, so a tool that is not in both
  is silently unreachable. The roadmap therefore ships a registration-overlay refactor
  (P3-C) with an empty overlay before any dynamic tool is enabled.

### Fixed — live round 2026-09-07 (owner manual test)
- **Prayer times routing**: «شو اوقات الاذان للصلوات اليوم» fell to plain chat
  («ما عندي أداة لأوقات الأذان») because the net matched only «اوقات الصلاة».
  The `prayer_times` net now catches اذان/أذان/الآذان/صلوات/مواقيت + «وقت أذان»
  variants.
- **Voice Fish-ONLY identity (owner)**: a DEMANDED voice note no longer falls
  back to a foreign (Microsoft/Edge) voice when Fish fails — it lands the honest
  TEXT (owner: «لم يستخدم فيش اوديو بل مايكروسوف الذي قلنا لن نستخدمه»).
  `_speak_demanded` + the demanded tail dropped the Edge lane.
- **create_folder nested batch**: «انشئي فولدر Friends وضعي فيه المجلدات: أ، ب، ج»
  now creates the parent + each child (each an `_index.md`), strips a «اسمه»
  prefix, and no longer hallucinates the child names. `_extract_folder_names`
  parses comma/numbered lists per component (traversal dies).

### Added — Phase B: Tool Wiring & Operational Surface Completion (2026-09-06)
The full B1-B8 backlog from `AUDIT_AND_PLAN_40_FEATURES.md`, all wired into
`ToolRegistry`, routed in the keyword net, and given per-tool skill guides
(44 new tests expand the gate ceiling):
- **B1 `drive`** — Drive file list/search (name + id + link) via
  `GoogleSuite.list_drive_files`.
- **B2 `contacts`** — People directory lookup → compact card
  (name + phone + email).
- **B3 `create_event`/`create_task`** — Calendar/Tasks WRITE verbs via
  `GoogleSuite.create_event`/`add_task`.
- **B4 `places`** — Nearby Amman venues (rating + address + maps link) via a
  Places adapter behind the 7-day CacheEngine (key-gated, $0.00).
- **B5 `deep_search`** — Custom Search w/ a transparent keyless DDG fallback
  past the 80/day cap.
- **B6 `fitness`** — Daily steps + active minutes + calories (08:00/22:00 sync
  windows + 1h cache).
- **B7 `cloud_backup`/`analytics`** — Fernet-sealed vault snapshot to free
  Cloud Storage; life-analytics rows over local SQLite.
- **B8 `quota_safety`** — Free-tier headroom (QuotaGuard breaker; «آمن» under
  90%).
- New backend: `src/google_cloud_client.py::GoogleCloudClient` wraps the §7
  adapters + CacheEngine + QuotaGuard. New settings: `GOOGLE_PLACES_KEY`,
  `CUSTOM_SEARCH_CX`, `CUSTOM_SEARCH_KEY` (optional; empty = honest offline).

### Fixed — the 2026-09-05 live-defect round (defects A–G, commit `4bb212c`)
Seven production defects from the owner's real Telegram session of 2026-09-05,
each pinned by the regression floor `tests/test_live_defects_2026_09_05.py`
(39 collected items):
- **A — Calculator UWP close**: Windows 10/11 runs Calculator as
  `CalculatorApp.exe` while the whitelist says `calc.exe` — close() now hunts
  EVERY image via `close_images()` + `PROCESS_IMAGE_ALIASES` and reports the
  psutil-verified count («ما لقيت نسخة شغالة» while windows stayed open — dead).
- **B — Amman prayer times**: exact coordinates `31.9539, 35.9106` +
  `timezonestring=Asia/Amman` + Awqaf method 23 + explicit date segment
  (the date-less endpoint 302'd and the client never followed) — the Amman-vs-
  Oman geocode drift (30–40 min) is structurally impossible now.
- **C — Weather geocode crash**: an empty geocode `results` list raised
  IndexError on the NORMAL path, and the except-block's loguru named-placeholder
  raised `KeyError:'place'` masking it — honest named-place line now; a
  tree-wide structural test bans the mixed loguru format forever (also rooted G).
- **D — Dispatcher keyword collisions**: «اكتمي الصوت» closed an app literally
  named «الصوت» (volume beats close now), bare pasted URLs reach Jina Reader,
  crypto/network/prayer asks route to their real tools (priority-ordered net).
- **E — Demanded voice note on Fish 429**: the demand NEVER lands text-only —
  `_speak_demanded` fails over to the LOCAL Edge lane (same text), the honest
  apology only when BOTH engines die; ordinary turns keep the Fish-only law.
- **F — Google OAuth 400**: scopes ride ONE space-separated param
  (`" ".join(AUTH_SCOPES)`, RFC 6749 §3.3) — the consent screen renders again.
- **G — Vault folder crash**: `_do_create_folder` failures return the honest
  Arabic line (the loguru `KeyError:'name'` escaping the except block is dead).

### Fixed — the live-session production round (2026-09-04, owner transcript 3:18-4:04pm)
- **§1 Sender-ID-only voice authorization**: the owner's account NEVER falls
  to Guest Mode from any device/mic — `owner_voice_gate` replaces the old
  biometric gate in on_voice (the missed print stages a Pending_Speakers
  LABELING note; the turn proceeds with full permissions). The dead
  verify_or_lockdown path deleted; the guest floor re-anchored: non-owner
  chats stay False, dead staging never blocks the owner turn.
- **§2 Real process termination**: سكري/اغلقي/طفي/وقفي/close/kill route to
  the `close` tool (BEFORE launch in the net); the daemon runs
  taskkill /IM /F /T and VERIFIES via psutil — the owner line carries the
  real killed count; killed=0 gets its own honest line; CMD/DOS/PowerShell
  aliases land. (Live: a close spawned a SECOND copy, then hallucinated.)
- **§3 Real voice-note dispatch**: hallucinated external audio URLs
  (s3/cdn/mp3...) structurally stripped before any surface; the
  in-memory Ogg-Opus answer_voice lane unchanged. (Live: sara-voice.s3
  links + an invented no-audio-on-Telegram claim.)
- **§4 Screenshot as a real photo**: «بعثيلي السكرين شوت» routes to the
  screenshot tool; the captured JPEG dispatches as a REAL Telegram photo
  (answer_photo + caption) before the vision description. (Live: text only.)
- **app_sessions payload fix**: the daemon returns the raw day report —
  present `apps` is the ok marker (the live 3:36pm «عطل» root cause).

### Added
- **§5 Dual task engine** (`src/task_orchestrator.py`): timed reminders that
  FIRE (general delay/wallclock parsing — matrices, Arabic-Indic digits,
  12 صباح=midnight; state persists, restart re-arms, dispatch failure
  retries), sequential step-DAG (stops at failure, names it), parallel
  gather (one unified confirmation), composite timer→chain; rides the loop
  set. (Live: three reminders acknowledged then never fired.)
- **§6 Dynamic Obsidian folders**: `create_folder` — one sanitized `_index.md`
  commit creates the dir (contents API); idempotent; PARA backbone
  additive-only. (Live: RoutineTasks «عطل بسيط».)
- **§7 Google 41-API suite** (`src/google_cloud_suite.py`): the full registry
  (Workspace 7 + Health/Gaming 4 + Media/Search 8 + BigQuery/Storage 14 +
  Observability/Quota 8 = 41; **Gemini STRICTLY EXCLUDED**) behind the
  $0.00 caching engine — TTL rules (weather 6h/4-day, places 7d, custom
  search 24h + HARD 80/day, fitness 08:00/22:00 + 1h), QuotaGuard breaker
  (>90% free-tier = open; dead API fails conservative), cache-first call
  order proven by the custom_search lane (2 identical queries = 1 wire call).
- **§8 Persona emojis**: the feminine emoji palette (🌸✨💖😊🫡☕🎮📚🌙)
  woven into the prompt with guided taste (1-2 per message, from the
  sentence's heart, quiet on serious moments); warmth/loyalty/honesty
  floors verbatim.


### Added — v2.0 pass-4: web intelligence + staged integrations (2026-09-04, §3-هـ + §3-ب + §3-أ/5 + §3-ح)
- **`web_search` — keyless live web search**: DuckDuckGo HTML results (real
  titles + links, empty-on-failure, never fabricated); page reading strips to
  clean budgeted text; results wrapped DATA (untrusted boundary). No API key,
  $0.00 — the directive's live-web-intel intent without Firecrawl's key for
  the common case.
- **`weather` — spoken live weather via Open-Meteo**: free, keyless. Google's
  Weather API is PAID → excluded by the $0.00 invariant (ruling recorded in
  weather.py + docs). Static coordinates for Amman + Jordan's main cities
  (zero geocode latency on daily asks); unknown places geocode once per
  session; WMO codes map to Jordanian condition lines; numbers verbatim.
- **`youtube` — Data API v3 search** (staged per §7): real
  titles/channels/links; 10k units/day free quota; env-gated
  `YOUTUBE_API_KEY` — empty key = honest offline line until the owner fills it.
- **Instagram sandbox (§3-أ/5, staged per §7)**: the full client surface
  (feed/post/dm) against an isolated in-memory backend; every result labeled
  `sandbox=True`; `is_live` flips ONLY on credential presence; the real
  transport (instagrapi) binds lazily when `INSTAGRAM_SESSION` lands.
- **Civ6 fair-play contract core (§3-ح, staged per §7)**: TurnState wire
  schema (localhost:9871); **the Fog-of-War enforcer** — Sara's
  VisibleTurnView is built by structurally REMOVING every fogged item
  (anti-cheat by construction); voice-to-civilization binding (صوت خالد =
  روما); the staged Lua mod script (legal-visibility APIs only,
  contract-tested against fog-reveal identifiers); dossier/lessons vault
  paths.
- **Firecrawl REST client (§3-هـ/1, staged per §7)**: complex-page Markdown
  extraction, 4000-char budget; empty `FIRECRAWL_API_KEY` = the keyless
  WebIntel path serves page reads until the owner provides one.
- **Clip farming DEFERRED BY OWNER (2026-09-04)**: «تأجيلها كلياً إلى
  المستقبل... عندما ينضج المشروع الحالي» — the design stays in
  02-BACKLOG as the future spec; zero code, zero staging (this is the §2
  requirement to name dropped features with justification).

### Changed — v2.0 pass-3: hyper-humanization of the persona contract (2026-09-04, §3-أ/1+3+4)
- **Full tool self-knowledge**: the persona prompt now names every capability
  she owns — launches AND closes, live screen capture she SEES, per-minute
  app-session tracking, the Obsidian knowledge web, scheduled tasks (mirrored
  to Calendar+Tasks), the morning brief, her voice memo listening — so she
  invokes them with earned confidence and never denies her own powers.
- **Engaged-life partner stance**: on his university days, friends and daily
  situations she listens with genuine interest and asks real follow-up
  questions from the heart of the topic («وشو صار بعدين؟»), because she wants
  to know — never the service-desk fishing style.
- **Spontaneous human texture**: self-repair stutters («رح أفتح
  البرنامـ... قصدي اللعبة»), Jordanian thinking pauses («اممم شوف...»),
  relief sighs after long work, light laughs before teasing — prompt-contract
  for natural timing, explicitly not overdone.
- **Model-judgment preserved**: reply modality stays the ROUTER's call (round-2
  owner ruling); no hard regex substitutes for her judgment.
- The honesty floor is contract-tested unchanged: no fabricated actions, no
  robot admission, untrusted content stays DATA.

### Added — v2.0 pass-2: knowledge graph + scheduled tasks (2026-09-04, §3-و + §3-ج/2)
- **`src/skills/knowledge_graph.py` — the vault's wikilink web**: notes are
  nodes, `[[wikilinks]]` are directed edges (alias-aware, extension-less
  targets resolved onto real note paths, dangling links stay honest nodes).
  Pure local index — zero LLM, zero IO — answering backlinks («مين بيحكي عن
  هالموضوع؟»), neighbors, orphans, and an Arabic DATA brief for the tool lane.
  Exposed as the `knowledge_graph` tool (overview with no arg; a note's
  backlink web with one) + keyword net («مين بيحكي عن»، «شبكة المعرفة»،
  «خريطة المعرفة»).
- **`src/skills/scheduled_tasks.py` — the Obsidian↔Google task lane**: one task
  = ONE note in `01_Projects/Scheduled_Tasks/` with a `[sara:task:<id>]`
  tracking tag, mirrored to BOTH Google Calendar (event) and Google Tasks
  (checklist item). Idempotent by tag (re-syncs never duplicate); Google
  outage parks the note pending and a ~10-min catch-up loop (seventh
  background loop, journaler pattern) mirrors it when Google returns.
  Vault-first: the note ALWAYS lands before any cloud write.
- **`VaultClient.list_dir`**: directory scans over the GitHub contents API
  (missing dir = honest empty list) — shared by the graph snapshot and the
  task sync.
- **`schedule` tool + router/keyword-net routing**: «ذكرني بكرة أراجع
  الفيزياء» routes deterministically; بكرة/بعد بكرة/اليوم map onto the due
  time; the confirmation quotes title + time.
- Bot wiring: `ScheduledTasksEngine` constructed when Google is up, passed to
  the registry + the loop set.

### Added — v2.0 pass-1: the deep bridge tools (2026-09-04, master directive §3-د)
- **`exec.screenshot` — the live screen tool**: «شو عالشاشة؟» captures the
  owner's desktop ENTIRELY in memory (Pillow `ImageGrab`, ≤1600px JPEG,
  quality 70 — zero disk writes) and Sara's conversation lane SEES it
  natively (m3 `image_url` data-URI) and answers in her own words. Pillow
  joins requirements (MIT, free).
- **`telemetry.app_sessions` — minute-level usage tracking**: the daemon
  samples the foreground window once a minute; per-app minutes, session
  counts, first/last-seen, category roll-up (Games/Programming/Study/
  Productivity/Unknown from the whitelist `category` fields), screen hours,
  and a boot/shutdown session log — per local day, persisted under
  `data/app_sessions/` (machine-local, gitignored) so restarts keep the day.
  «كم استخدمت برامج اليوم؟» now answers with real numbers.
- **`exec.close` — programmatic app close**: «سكري <برنامج>» closes a
  running app via `taskkill /IM <image> /F` through the SAME whitelist gate
  as launching (auto_approve closes directly; everything else demands a live
  confirmation) — closing is destructive on the live session, audit code
  every time.
- **Router + keyword net extended**: `screenshot`/`app_sessions` are valid
  tool verdicts and the deterministic net catches «شو عالشاشة»، «كم
  استخدمت»، «ساعات الشاشة» behind a router miss.
- **Dialect lexicon (§3-أ/2)**: the owner-named phonetic pins land in the
  seed lexicon — «سارة» → «سارَا»، «كيفك» → «كِيفَك» (TTS whole-word,
  owner «تعلمي:» notes still override live).
- **Dispatcher router prompt** names the two new tools for tier2 routing.

### Fixed — the deferred audit queue cleared (2026-09-04, continuation mandate)
- **C-10 — envelope TTL cache**: the three sequential GitHub GETs that ran
  before EVERY router call (killing the <250ms ack target) are now served
  from a 60s TTL cache; any vault write invalidates it — a just-written
  profile never serves stale. Back-to-back turns cost ZERO GitHub reads.
- **V-1 — voice total wall**: a hung engine hits a 30s wall and dies
  honestly (`timed out` VoicePipelineError), the ffmpeg child reaped —
  never a silent hang eating the turn.
- **2.10 — vault 429/403 one-retry**: a rate limit with Retry-After is
  honored once (capped 30s); persistent limits surface loudly — no silent
  infinite retry loop.
- **Security batch (S-2/S-3/S-6)**: the bridge token compare is
  `hmac.compare_digest` (timing the reject can never leak the prefix);
  auth-failure logging is bounded; the daemon WARNS loudly when dialing a
  plaintext ws:// endpoint on the public internet.
- **§13 — /health honesty**: the report now carries the vault-token and
  Google-token-cache state — health never reads green while Gmail is
  actually failing (the absent OAuth cache is THE local cause per the
  audit).
- **M-4 — the run_bot boot test**: the REAL production wiring (gateway,
  voice, vault, memory, tools, coordinator, all six loops) assembles and
  shuts down cleanly — proven, not assumed.

### Added — the v1.1 intelligence suite (2026-09-04, owner overnight mission)
- **Universal multi-speaker diarization & separation**
  (`src/skills/speaker_diarization.py`): a conversation recording splits
  into per-speaker dialogue turns fully on CPU — ffmpeg in-memory decode →
  energy-window segmentation → ECAPA embedding per segment (the same local
  model as the biometric gate) → cosine clustering → attribution via the
  sealed owner print + the Contacts voiceprint registry (a voice in neither
  stays «متحدث غير معروف», never guessed) → local Whisper per turn.
  render(): «المتحدث (عمر): ... | (أحمد): ...». Transcripts are DATA — the
  module has zero tool/exec surface (AST-guarded).
- **Contextual affect & emotional trajectory engine**
  (`AffectiveStateTracker` in src/memory.py): ONE FAST micro-verdict per
  turn reads the last 6 turns + the User_Info baseline and judges the
  owner's state (banter/sarcasm/fatigue/stress/joy/neutral) — the model
  distinguishes playful mock-outrage from genuine anger via history, not a
  keyword table. The guide rides the envelope as subtle Arabic context;
  any failure injects nothing.
- **Acoustic & paralinguistic nuance pipeline**
  (`src/skills/acoustic_nuance.py`): deterministic local DSP (RMS energy
  windows — zero models, zero cost) profiles HOW he spoke (activity, pause
  ratio, energy); the subtle Arabic block rides every voice-turn envelope.
  Short notes (<1 s) yield an empty block — never a guess. ECAPA stays the
  ONLY authorization path (no verify/enroll surface here, AST-guarded).
- **Self-improvement & linguistic evolution engine**
  (`src/skills/self_evolution.py`, the SIXTH background loop): a nightly
  ~23:40 reflection reads the day's ledger + the current Dialect_Notes and
  proposes recurring Jordanian idioms she kept missing — filed as
  «مقترحات تعلم» PROPOSALS for the owner to adopt with «تعلمي:». NEVER
  silently learns; every failure skips.
- **Live-call lane scaffold** (`src/skills/live_calls.py` +
  `src/telegram_login.py` + `docs/OWNER_ACTION_REQUIRED.md`): the
  CallSession facade runs mock-complete now (dial/hang-up recorded +
  tested) and goes live the moment TELEGRAM_USER_SESSION_STRING lands in
  .env — one interface, zero code changes, honest owner-action lines.

### Fixed
- **Round-3 live fixes (owner test 2026-09-03 22:51–22:58)**:
  - **The owner's own ~2s voice note locked him out as a guest** (his note
    scored 0.388 vs his print; his genuine band is 0.67–0.72): clips shorter
    than ~2 s of PCM are now INCONCLUSIVE — they proceed on middleware
    trust (the Telegram-ID gate is the hard security boundary) with a loud
    log, never a guest lockdown. Enrollment requires a decisive-length note
    and RE-ENROLLMENT BLENDS with the existing print (running centroid) so
    every genuine note strengthens it. RUNBOOK: enroll with 8+ s of natural
    speech.
  - **A transient Fish rate-limit became «ما بقدرش ابعتلك صوت»**: voice
    synthesis now retries once after a 2 s burst window before falling back
    to text — a rate limit is never narrated as a capability loss (persona
    bans the phrasing by name).
  - **Tool results became support-desk lectures** («الجسر مو متصل» grew into
    a Windows/Mac/Linux manual): the tool-lane narration instructions now
    pin the tool result as the complete ground truth — a one-or-two-line
    warm relay, never steps, alternatives, or other-OS instructions.
  - **Long text replies are re-split into 2-3 short chat bubbles**: after
    streaming, a long multi-paragraph answer is edited down to its first
    paragraph and the rest arrive as short follow-up messages (the
    22:56 climate lecture class is dead).

### Fixed (earlier today)
- **Round-2 live fixes (owner test 2026-09-03 22:14–22:17)**:
  - **The router picks the reply channel**: `voice_reply` rides the same FAST
    verdict — the MODEL decides whether a turn deserves her voice (zero extra
    calls); his explicit «رد صوتي/رد نصي» still overrides everything; origin
    default (voice begets voice) otherwise. The 70/30 dice roll is retired
    and the regex keeps only unambiguous request patterns («بدي اسمع صوتك»
    fixed).
  - **Persona hardened** (contract-tested): she NEVER denies her voice
    («ما بقدر أبعت صوت»/«صوتي ميكانيكي» banned by name), NEVER admits being
    a robot — deflects humanly like a friend's joke; replies are 2-3 SHORT
    bubbles with no markdown/headings/numbered lists; she reads through his
    typos («جهاي»=«جهازي») and never corrects spelling out loud.
  - **Proactive outreach is VOICE**: Sara checks in with her own voice note
    (text only when synthesis is down).
  - **A dead bridge gets its own honest line**: launch with no bridge session
    says «الجسر مو متصل» (actionable) instead of the generic «عطل بسيط».
  - **Voice-reply text fallback splits into short bubbles** (the
    long-single-lecture class is dead on every surface).

### Fixed (earlier today)
- **Proactive failure backoff (live-test finding 2026-09-03 21:52–22:00)**:
  when the brain is unreachable (gateway down), the outreach loop no longer
  retries the full model chain every ~30 s tick — a verdict failure parks
  the engine for 30 minutes (`last_failure_at` in the state file); a
  recovered gateway ends the backoff on the next attempt. The live run
  burned 9 minutes × 6 calls/cycle against a dead OmniRoute.

### Removed
- **Dead code pruned (remediation 3.3, ~2,515 lines)**: `config/agents_config.json`
  (zero consumers, stale Gemini/Sana pins), `src/expansion.py`, `src/syllabus.py`
  + `src/tutor.py` (+ their tests), the sprint-3 trio `src/summary.py` +
  `src/skills/social_graph.py` + `src/vault_expand.py` (+ their tests), and
  **pypdf from requirements.txt** (~376KB wheel serving dead code only).
  Zero-consumption verified by grep before deletion; `common/consent.py` and
  `src/vault.py` stay (live consumers). Coverage ROSE to 87.09% after the cut.
- **Dead settings keys (remediation 3.4)**: obsidian_rest_api_url,
  obsidian_api_key, target_pc_mac_address/ip/wol_port, idle_shutdown_minutes
  (+ the never-present google_cloud_project) removed from config.py,
  .env.example, and the conftest mirror — zero keys feeding nothing.
  telegram_api_* stay as the documented v1.1 plan.

### Changed
- **OAuth consent slimmed to three scopes (remediation 3.4)**: the OS asks for
  Calendar + Tasks + Gmail.modify only — Drive/Contacts readonly left the
  consent screen (the OS never reads either API).
- **RUNBOOK live-loops table + OAuth path fix (remediation 3.6)**: §3 now
  documents the five active background loops (cadence/gates/OAuth needs) and
  the proactive tuning knobs; the §6 OAuth bootstrap no longer points at the
  retired `core-foundation` worktree — the main checkout is the path.
- **Memory reads the newest facts (remediation 2.7, head-vs-tail flaw)**:
  the per-section cap in `load_long_term` now slices from the TAIL
  (`body[-max_chars:]`) — learned facts append to the end of User_Info, so
  the brain sees the newest slice, not the stale head that pushed it out.

### Added
- **Proactive outreach engine (remediation 3.2 — Sara INITIATES, the heart of
  the initiative axis)**: a new ~45-min smart loop
  (`src/skills/proactive_outreach.py`) gathers real context (today's
  Daily_Logs tail + User_Info excerpt + local time) and asks the HEAVY model
  (nemotron) ONE question — does the state deserve a proactive message to
  the owner? A yes lands as ONE warm Jordanian check-in. Safety gates, all
  BEFORE any model call: `PROACTIVE_ENABLED`, window 08:00–22:30 local,
  cooldown between sends, hard cap 3/day, calendar-conflict guard (a booked
  owner is not pinged, the §2.6 pattern). Model failure or an unparsable
  verdict = a silent skip (free pools are bursty; silence is never wrong).
  The verdict prompt FORBIDS claiming actions — outreach is a check-in,
  never a fabricated accomplishment. Cadence state persists in
  `State/proactive.json` (the journaler pattern). Wired into
  `start_background_loops` as the fifth loop. New settings:
  `PROACTIVE_ENABLED/INTERVAL_MIN/MAX_PER_DAY/WINDOW_START/WINDOW_END/
  COOLDOWN_MIN` (+ .env.example + conftest mirror).
- **The three absent loops now run (remediation 3.1)**: `start_background_loops`
  — one testable stitch point in bot.py — launches the 07:30 morning brief
  (`BriefComposer.run_forever`), the evening check-in
  (`EveningJournaler.run_forever`, 18:00-19:30 window), the real Gmail watch
  (`run_gmail_poll` + triage dispatcher/classifier), and the existing 23:50
  daily summary. All four tasks are cancelled on shutdown;
  `BRIEF_ENABLED=false` suppresses only the brief; a degraded Google boot
  (no OAuth) keeps the chat loops alive and skips only the Gmail watch.
  First activation since these features were built.
- **Whisper pinned to Jordanian Arabic (remediation 2.6, mishear fix)**:
  every voice-note transcription now calls faster-whisper with
  `language="ar"`, `beam_size=5`, and an `initial_prompt` seeded with the
  dialect context (owner name + Jordanian colloquial marker + the learned
  «تعلمي:» pairs from boot) — the «كفيك»-class mishears are choked at the
  source instead of MSA-guessing. The prompt bias refreshes live when the
  owner teaches a new pair (`update_prompt_terms`), matching the 2.5
  synthesis-side loop; `run_bot` seeds both lanes from Dialect_Notes at boot.
- **Live dialect learning loop (remediation 2.5, audit dead-loop fix)**: «تعلمي:
  مصطلح -> نطق» now actually does something — a background task reads
  Dialect_Notes.md, merges the teaching (dedupe by term), upserts the vault,
  and refreshes the LIVE voice lexicon on both lanes (Edge VoicePipeline and
  the Fish lane) with no reboot. The learned pairs also reach the brain:
  `load_long_term` now reads the Dialect_Notes FRONTMATTER (`notes:` pairs)
  in addition to the prose body, so learned pronunciations ride every
  envelope. Best-effort per the M1 contract: a vault failure logs and skips,
  the reply is never blocked.
- **Confirmation memory (remediation 2.4, audit C-8)**: every PC-action
  exchange — the coordinator's prompt, the owner's «نعم»/«لا», the execution
  result or refusal line — now enters `memory.remember` under the owner's chat
  id (optional `memory=` injection; a dead memory never breaks a launch).
  The brain reads the real confirmation conversation in its rolling history,
  never a context-free orphan. Complement: after a rejected/failed
  confirmation, a BARE short consent/refusal token («نعم»/«لا»/«مش هلق»…,
  ≤3 tokens, no real content) no longer falls through to the brain — the
  blind contextual-reply class («نعم» → «أكيد سويتها!») is dead; real chat
  during a pending window streams normally.
- **Voice-confirmation guard (remediation 2.3, audit C-2, sacred floor)**:
  a pending PC confirmation answered with a VOICE «نعم» is now consumed by
  the coordinator right after transcription — mirroring on_text's pending
  check inside on_voice. Previously a voice «نعم» sailed past the
  coordinator into a normal chat answer while the confirmed launch silently
  never fired. The brain is never consulted for a confirmation reply.
- **Arabic app aliases (remediation 2.2, audit C-7)**: the owner can now launch
  apps by their natural Arabic names — «الآلة الحاسبة» resolves to `calculator`,
  «أوبسيديان» to `obsidian`, «المفكرة» to `Notepad` (+ الكروم، سبوتيفاي، واتساب،
  ديسكورد…). Resolution happens in the coordinator BEFORE any bridge
  round-trip; a name with no alias AND no whitelist hit gets the honest
  «مش موجود بالقائمة المعتمدة» line immediately — no confirmation round-trip
  for a name that can never resolve, no pending state left behind. The
  coordinator carries an optional core-side Guard (bot.py wires it,
  `config/whitelist.json`, re-read per check); unguarded construction keeps
  the legacy pass-through (the daemon-side Guard still guards every execution).
- **Anti-hallucination keyword net (remediation 2.1, audit C-1)**: a
  deterministic intent net in the dispatcher now runs BEHIND the router —
  colloquial tool words (جيميل/بريد → gmail، مواعيد/تقويم → calendar، مهام →
  tasks، وضع الجهاز/الرام/المعالج → telemetry، إحاطة → brief، افتحي/شغّل +
  اسم البرنامج → launch) force the REAL tool path whenever the router misses
  (`tool="none"`) or emits an unknown tool string. A valid router verdict is
  never overridden; every coercion is logged loudly (unknown tool strings too —
  previously sanitized silently). The launch pattern captures the clean app
  name (trailing «على جهازي/لو سمحت» clauses stripped) and keeps the noun
  الشغل out of the imperative match. 6 new tests; fixes the live
  «افتحي الآلة الحاسبة على جهازي» → «ما بقدر» failure class.

### Changed
- **Fish is Sara's ONLY voice — Microsoft fallback removed (owner directive
  2026-09-03 07:03, live retest)**: the 07:03 voice note came back in the
  Microsoft-Salma voice after a Fish failure («الرد عاد لمايكروسوفت») — a
  foreign voice broke identity. `FishFirstVoice` no longer falls back to Edge
  synthesis: a Fish failure (429/5xx/network) re-raises so the bot's honest
  TEXT reply lands; the owner never hangs, and the voice identity stays pure
  Fish. `build_voice()` wires no Edge lane when Fish is configured;
  unconfigured deployments remain pure Edge-TTS. Docs synced (CLAUDE.md
  invariant 1, .env.example voice block).
- **Explicit voice-ask forcing widened (live 07:03)**: «ابعثي رسالة صوتية» /
  «رسالة صوتية» / «ملاحظة صوتية» now force the voice channel like «رد صوتي» —
  the explicit ask never rides the 70/30 dice.

### Added
- **Media comprehension — photos & videos seen natively (owner directive 2026-09-03)**:
  a photo or video the owner sends on Telegram is understood automatically —
  downloaded, base64-encoded, and carried to minimax-m3 as an `image_url`/`video_url`
  content block (the caption is the prompt; no caption -> the default ask). The
  conversation lane answers naturally; >10MiB files get one honest size line and
  the brain is never called. Reply-awareness in the same directive: when the owner
  replies to a specific message, the quoted message rides the prompt («عمر ردّ على
  رسالة سابقة: …») so Sara knows exactly what he is responding to.
- **Reply-modality skill — 70/30 mirror + explicit forcing (owner directive
  2026-09-03)**: `src/skills/reply_modality.py` decides Sara's reply surface once
  per turn — his text -> 70% text / 30% voice note; his voice note -> the ratio
  flips (70% voice / 30% text); an explicit request («رد صوتي» / «رد نصي /
  اكتبي») is always honored. Exactly ONE surface either way (the remediation-1.4
  no-duplicates contract untouched). The shipped skill is the default; the shell
  tests inject a deterministic decider so legacy contracts stay unflakeable.

### Changed
- **Fish calm-tone: speed on the wire (owner directive 2026-09-03)**: the official
  `/audio/speech` schema carries NO temperature (a chat param, never a speech
  param) — the requested 0.7-temperature steadiness is emulated through the
  officially supported `speed` multiplier, default 0.9 (`FISH_AUDIO_SPEED`,
  tunable; a no-op if the provider drops it). Wire + settings + conftest mirror
  + tests pinned.
- **Two-tier architecture ratified in the remediation plan (owner directive 2026-09-03)**:
  TALKER_AND_MEMORY = `minimax-m3:free` (428B MoE / 23B active / 1M context / native
  image+video input confirmed from OpenRouter's schema; strongest free Jordanian
  Arabic — live-probed) + HEAVY_TOOL_MASTER = `nemotron-3-ultra-550b-a55b:free`
  (exclusive tool/bridge/whitelist executor, unchanged). Both draw from the shared
  50/day free pool — the proactive loop stays capped ≤3 HEAVY/day so neither lane
  starves the other. Voice-tone filter section (2.1b): the official `/audio/speech`
  schema carries NO temperature (a chat param, not a speech param); calm tone is
  controlled by the reference voice + the officially supported `speed` param —
  probe pending rate-limit relief. Discovered and recorded: `input_references`
  voice cloning (≤15MiB sample) — future free upgrade path to a Sara voice cloned
  from the owner's own sample. Media (photo/video) comprehension via m3 is
  technically available but NOT yet wired in bot.py — future directive work.
- **FAST model upgraded to minimax-m3 (owner directive 2026-09-03, live-retest feedback)**:
  the owner's live Phase-1 retest caught m2.7's conversation lane producing
  mixed-language garble («معكcepted», «بتقدرتفتحها») and leaked stage directions
  («[سارة تضيف معلومة تفضيل جديدة]» printed verbatim into the chat). `FAST_MODEL` is
  now `openrouter/minimax/minimax-m3:free` (also the MEDIUM fallback) — live-probed
  through OmniRoute before pinning: HTTP 200, clean Arabic «جاهزة», ~4.8s first token.
  Pins synced across `.env.example`, conftest mirror, test_config/test_dispatcher
  pins, CLAUDE.md §1, ARCHITECTURE §3 diagram, RUNBOOK probe row, OWNER-NEXT-STEPS
  env block, DECISIONS ADR-16 amendment (2026-09-03). m2.7 fully retired.
- **Voiceprint threshold live-calibrated 0.75 → 0.60 (2026-09-03)**: the same retest
  exposed the ADR-17 gate rejecting the OWNER's own voice notes right after a
  successful `/enroll-voice` (two consecutive guest lockdowns). Real ECAPA measurement
  on the sealed print: owner intra-speaker cosine 0.7637 vs TTS impostor control
  0.1071 — the old 0.75 default sat inside the owner's natural variance band and
  locked him out. 0.60 keeps every measured impostor 0.49 below while giving the
  owner's voice normal range. `VOICEPRINT_THRESHOLD` in `.env.example`/conftest +
  `config.py` default + RUNBOOK enrollment row + DECISIONS ADR-17 amendment synced.

### Added
- **Consent grammar hardening (remediation 1.8, 2026-09-03)**: an affirmative is a
  STANDALONE short yes — at most 3 tokens, opening with an affirmative, carrying no
  negation/reservation word (لا/بس/مش/مو/لسا/بعد شوي/بعدين/يمكن/وقف/ألغها). Sprint-3's
  first-token rule let «نعم بس استنى» launch guarded actions — a reservation is now
  structurally unable to execute (audit S-4 closed; 28-case contract test). The
  whitelist-guardrail sacred floor stays green («ايه سوّيها» remains a clean 2-token yes).
- **Real stream cancellation on interjection (remediation 1.7, 2026-09-03)**: a newer
  owner message now sets the cancel Event AND `task.cancel()`s the in-flight stream —
  the Event alone only landed between deltas, so a turn blocked mid-flight (slow model
  delta) lived on as a zombie able to fire late edits/voice from a dead turn (audit
  V-3 closed). The blocked-midstream test proves the abandoned task dies at its await
  point and its late delta never reaches the bubble.
- **Hardcoded-line cleanup + string contract (remediation 1.5/1.6, 2026-09-03)**: every
  owner-facing Arabic constant rewritten in Sara's register, mechanically enforced by a
  new AST-based contract test (`tests/test_persona_lines.py`) scanning EVERY string
  constant in src/: WELCOME «كيف فيني ساعدك اليوم؟» → «يا هلا عمر! شغّالة وجاهزة —
  ابعثلي أي شي.» (identity lives in ONE surface — the voice greeting); EMPTY_VOICE
  «وهسا القريب من الميك» (garbled) → honest, clear line; «انسمعت بصمتك» → «سجّلت
  بصمتك!»; «سمسعتك» → «سمعت بصوتك» (contact mode); EMPTY_REPLY desk-style → Sara's
  own voice; «لسأ» misspelling extinct with VOICE_ACK_AR (deleted in 1.4). Zero
  service-desk/garbled lines can ship — the contract test fails on any.
- **Voice-origin single modality (remediation 1.4, 2026-09-03)**: a voice note now
  begets exactly ONE surface. The voice-origin turn consumes the stream off the wire
  (record_voice action, NO text bubble) and delivers the answer as a single voice note;
  only when synthesis dies does the answer land as a single honest text fallback
  (audit C-3 closed: the text-bubble-plus-voice-note double delivery is dead).
  `_voice_fail_reply` (silent/failed transcription) is single-modality too — voice first,
  text only on synthesis failure. The stray unenrolled `VOICE_ACK_AR` static line
  («سمعت الملاحظة الصوتية، لسأ أعالجها...» — a lie: nothing was processed, and the
  comment claimed "ack only" with no return) is deleted; the unenrolled note flows to
  transcription under middleware-only trust like any owner note.
- **Transient ack, never glued (remediation 1.3, 2026-09-03)**: the Tier-1 ack now lives
  exactly as the owner demanded — it shows instantly in the bubble for reassurance, then
  is DELETED from the text the moment answer deltas start streaming. Memory, the daily
  ledger, and voice synthesis receive the answer ONLY (audit C-4 closed: «تمام، ببدأ»
  never again prefixes «سجّلت الموعد»). The router ack also gains a content guard beside
  the length guard: gateway identity (بوابة/مساعد/بوت/خدمة/برنامج) or claimed actions
  (تم فتح/فتحت/بعت/جدولت…) inside an ack → replaced with the default «من عيوني هسا ببدأ...»
  (audit C-5 closed), and the router prompt no longer introduces itself as «بوابة سارة
  الأمامية» — it just classifies. The silent tool lane (launch, which notifies the owner
  directly) now keeps the ack bubble without appending a fake empty-reply line, and the
  ack is never remembered as Sara's reply.
- **Fish Audio primary voice engine (remediation 1.9, owner directive 2026-09-03)**:
  Sara's voice is now Fish `s2.1-pro-free:free` with the «سمسم-بوس» reference voice
  (`56c2f0c2…`) via OpenRouter's `/api/v1/audio/speech`, borrowing the same
  `OPENROUTER_API_KEY` free pool that feeds OmniRoute — $0.00 held. New `src/fish_voice.py`
  (`FishVoice` wire client + `FishFirstVoice` fish-first wrapper): Fish MP3 → the existing
  ffmpeg 64k/audio-mode Opus chain; ANY Fish failure (402/429/5xx/timeout/JSON body)
  transparently falls back to Edge-TTS Salma — the owner is never left hanging.
  Unconfigured (no key) → pure Edge lane, zero behavior change. Wire note: the voice lane
  calls OpenRouter directly (OmniRoute's speech endpoint does not proxy `openrouter/*` slugs).
- **Creator-recognition persona contract (remediation 1.2, 2026-09-03)**: `SYSTEM_PROMPT_AR`
  now pins Sara's addressee as **عمر الفياض, صانعك ومهندسك الوحيد** — first-person feminine,
  identity bans BY NAME (بوابة/مساعد آلي/بوت/برنامج/خدمة عملاء), customer-service phrasing
  bans (كيف أساعدك/كيف فيني ساعدك اليوم/يسرني خدمتك/أعدك بأن), and the action-honesty clause
  (no claim without ناتج الأداة in the same turn). 5 contract tests enforce it.
- **Dialect TTS shaper (owner directive 2026-09-02, Path A)**: `shape_for_tts()` in
  `src/dialect.py` runs before every synthesis — emoji stripped (emoji read aloud or
  corrupted the stream), whole-word pronunciation lexicon (owner Dialect_Notes override
  the 10-word seed), and trailing-harakat تسكين الأواخر (shadda preserved) so Microsoft
  G2P stops forcing MSA tanween on unvocalized Jordanian endings. Never-blocking: any
  internal failure returns the input verbatim.
- **Two-strong-model brain (owner directive 2026-09-01)**: conversation lane FAST `minimax-m2.7:free` (fb `gpt-oss-120b`) + MEDIUM `gpt-oss-120b`; tool lane HEAVY `nemotron-3-ultra-550b` as the exclusive Gmail/Calendar/Tasks/bridge executor.
- **Dual-tier memory** (`src/memory.py`): 50-message rolling buffer per chat (owner directive — widened from 15), Obsidian long-term envelope (User_Info + Dialect_Notes + today's Daily_Logs) injected every turn, background writers persist each exchange to Daily_Logs and learn durable facts into User_Info.
- **Memory on every chat path (live-debug fix 2026-09-01)**: the ADR-18 `direct` route no longer answers from the history-less router call — simple chat acks at Tier 1 then streams the FAST conversation lane with the full envelope; the router only classifies.
- **Real tool execution loop** (`src/tools.py` ToolRegistry): gmail/calendar/tasks/telemetry/launch/brief with honest offline lines; launch notifies the owner directly with its audit code (no narration).
- **One-command local cycle** (`sara.bat`/`sara.ps1`): full stop->start — kills stale core/bridge processes, gateway preflight check, relaunches both windows (`-StopOnly` / `-Port` supported).
- **Daily conversation summary** (`DailySummarizer`): at 23:50 local the day's last 150 chat turns + Obsidian owner context go to the conversation lane; the detailed Arabic summary lands as a separate `## ملخص محادثة اليوم` section in the day's Daily_Logs note (idempotent, tick-loop like the brief/journaler).
- **Voice-out replies**: owner voice notes now get an ar-JO Ogg Opus voice note of Sara's streamed reply; pending PC-launch confirmations are consumed by the coordinator before the brain sees them.
- **Overlong router ack guard (live-debug fix 2026-09-01)**: minimax sometimes writes a mini-ANSWER into the router's `ack` field, so the owner saw a wrong reply followed seconds later by the real one in the same bubble. Acks over 30 chars are now discarded for the default «من عيوني هسا ببدأ...», and the router prompt forbids answering inside the ack.
- **Honest voice reply on silent/failed transcription (live-debug fix 2026-09-01)**: a 6-second silent voice note transcribed empty and left the owner with two static acks. Empty transcript or transcription failure now answers with the honest line «ما سمعت شي واضح بالملاحظة...» as text AND an ar-JO voice note; the memo is still filed.

### Changed
- **Voice encoding 24k voip -> 64k audio-mode Opus (Path A, 2026-09-02)**: the
  telephone-grade `voip` application mode choked every voice (live 2026-09-02, owner:
  «صوت رديء وغير بشري») — ffmpeg now encodes 64k VBR `-application audio` at 48 kHz
  mono. Voice default pin `ar-JO-SanaNeural` -> `ar-EG-SalmaNeural` (owner pick after
  the 6-voice A/B; larger Egyptian training data, still free; switchable via
  `VOICE_NAME`).
- **Injectable clock in ToolRegistry (2026-09-02)**: calendar/tasks/brief handlers
  take an optional `now_fn` (default: real clock) — the frozen-date test bomb
  (2026-09-01 -> 2026-09-02 midnight rollover) is structurally dead; tests pin their
  own clock.

## [1.0.2] — 2026-09-01

Owner-directed runtime enhancements ahead of the first cloud deploy (local test phase).

### Added
- **Start Menu app indexer** (`src/app_indexer.py`, `python -m src.app_indexer [--dry-run]`):
  discovers installed applications from both Windows Start Menu shortcut roots
  (`C:\ProgramData\...` + `%APPDATA%\...`), resolves each `.lnk` target through
  PowerShell WScript.Shell COM (batched EncodedCommand — no shell, no quoting hazards),
  categorizes apps (Coding / Gaming / Study / Productivity) and merges them into
  `config/whitelist.json` so the owner never hand-writes executable paths. Safety
  contract: only Start-Menu-installed desktop shortcuts enter the whitelist — anything
  resolving under `C:\Windows` (System32 included) is dropped; existing entries and
  `restricted_actions` are preserved verbatim; merging is idempotent (casefold dedupe);
  the whitelist Guard keeps re-reading the file per check. First live run: 223
  shortcuts discovered, 154 apps merged, 63 system binaries skipped.
- **Headless remote boot documentation** (RUNBOOK §5b): Windows Auto-Logon via
  Sysinternals Autologon (LSA secret, preferred) or netplwiz, so a Wake-on-LAN magic
  packet boots straight into the owner's desktop session; bridge daemon auto-start via
  Task Scheduler (ONLOGON preferred — runs in the user session after auto-logon;
  ONSTART alternative documented); end-to-end headless proof checklist.

## [1.0.1] — 2026-08-31

Patch release closing the two gaps discovered while preparing the first cloud deploy.

### Fixed
- **Container could never start the gateway**: OmniRoute is a Node/npm application
  (engines `node >=22.22`) while the image was `python:3.12-slim` — no Node runtime.
  The Dockerfile now installs Node 24 via NodeSource and installs the vendored
  OmniRoute clone globally (`npm install -g /app/scripts/omniroute` — the clone pins
  the gateway version), with `ENV OMNIROUTE_CMD="omniroute run"` as the zero-config
  default. Asserted by `tests/test_packaging.py::test_dockerfile_contract`.

### Changed
- **ADR-15 amended: Oracle Cloud Always Free replaces the HF Space as production host**
  (owner ruling 2026-08-31). HF made Docker/Gradio Spaces a paid PRO feature ($9/mo —
  breaks the $0.00 invariant); Render/Koyeb/Cloud-Run free tiers (512 MB) cannot carry
  the full stack. The container design is unchanged and host-agnostic; the
  disposable-filesystem rule stays as a design principle, and the OAuth client JSON may
  live on the VM (never git), resolving the Space-era Google gap. Owner deploy guide:
  `docs/09-ORACLE-DEPLOY.md`; RUNBOOK §4 re-anchored; keep-alive cron now optional
  (the VM never sleeps).

## [1.0.0] — 2026-08-31

First tagged release: **Sara (سارة)** — an owner-only, strictly-zero-cost executive
assistant speaking warm Jordanian Arabic over Telegram, reasoning through a 3-tier
multi-model brain behind a fast front-door dispatcher, running 24/7 in one free
Hugging Face Space with all durable state in a git-backed Obsidian vault.

### Added
- **Sprint 4 / task 4.4c — release v1.0.0**: single version source
  (`src/__version__`) with a consistency guard, and `scripts/make_release.py` —
  verifications (version == newest CHANGELOG heading naming both on mismatch; clean
  `git status --porcelain`; green `make gate`) then the annotated tag on the validated
  HEAD (`--tag` only; an existing tag means bump to 1.0.1, and there is deliberately
  NO --force flag — its absence is the safety feature). Publishing stays an owner step
  with the exact `gh release create` command printed by the dry run. Scope-lock test
  freezes the full settled v1.0 exclusion set (pytgcalls/telethon/pyrogram/mem0/
  firestore absent from artifacts and runtime imports).
- **Sprint 4 / task 4.4b — HF Spaces packaging (the ONE container, ADR-15)**:
  `Dockerfile` (python:3.12-slim, ffmpeg, non-root `sara` user, TZ=Asia/Amman) whose
  entrypoint is the new single-tree supervisor `scripts/supervise.py` — OmniRoute
  gateway child + core child (commands via `OMNIROUTE_CMD`/`CORE_CMD`; first child to
  exit tears down the tree and becomes the container exit, so the Space restarts whole,
  never half-alive). The core reads `$PORT` and serves `GET /health` + the authenticated
  bridge WSS on the single public port (`src.main.start_public_port`). `.dockerignore`
  keeps secrets/tests/docs/OAuth client/sessions out of the build context while
  re-including the two runtime needs. `.github/workflows/keepalive.yml` pings the Space
  `/health` every 10 minutes and fails loudly on any non-200 (shipped contract, not an
  ops footnote). `scripts/deploy_smoke.py` turns "is Sara alive?" into an exit code —
  five checks (gateway/telegram/vault/google_token_cache/space_health), per-check
  timeout bounds, all checks run even after one fails, and a Settings-aware masker
  screens EVERY failure detail (httpx errors embed full URLs carrying the bot token —
  nothing secret survives into logs; host + path class remain). Durable-state audit
  test locks every disk write in runtime code to ADR-15-justified stores; README gains
  Space metadata (sdk: docker, app_port) + HF Secrets policy; RUNBOOK §4 rewritten
  (Space deploy / keep-alive / Cloud Run fallback) with troubleshooting rows and a
  dated validation checklist ending in deploy_smoke exit 0.
- **Sprint 4 / task 4.4a — quality-gate hardening**: the >=85% branch coverage threshold
  is LIVE — `--cov=src --cov=bridge --cov=common --cov-branch --cov-fail-under=85` lives
  once in pytest `addopts` (85.86% measured at activation; Sprints 1-3 ran
  measurement-only, per Guide amendment note in TEST-PLAN §1). The vendored
  `.githooks/pre-commit` secret scanner now runs inside `make gate`
  (`scripts/secret_scan.py` — the hook's pattern battery over tracked files, placeholder
  allowlist intact) and a finding fails the gate exactly like a bandit high; CI's bandit
  step is unified onto `scripts/security_gate.py` (one gate implementation everywhere).
  Pragma policy enforced by test: every `pragma: no cover` / `# nosec` carries
  `-- <reason>` (`__main__` guards and OS-gated branches only; ffmpeg-binary fallbacks
  NOT allowlisted). The threshold mechanism is proven to fail closed (mini-project
  subprocess at fail_under=100).
- **Sprint 4 / task 4.3 — skill-polymath-tutor (M9)**: `src/tutor.py` — first-principles
  tutoring as a persona behavior of the existing chat+brain+vault loop, NO new engine:
  `study_artifact(topic, level, language, gateway, vault)` drives ONE `Tier.HEAVY`
  conversation (temperature 0.4, 4096-token budget) under `TUTOR_SYSTEM_PROMPT` —
  first-principles deconstruction (concept/why/how it's built), a graded learning
  path, 5 drills with answers, bilingual key terms, in the requested language
  verbatim (10 languages, Arabic-first). Artifacts file to
  `Studies/<topic>/Study Guide.md` with complete YAML frontmatter
  (type/topic/level/language/links/created/tags) and wikilinks; oversized topics cap
  at 120 chars. Boundaries: no provider or PC surface in the module (AST-scanned);
  generated content is DATA — imperative strings store verbatim and trigger nothing;
  vault failure logs ERROR + raises `StudyFilingError` carrying the FULL content with
  an Arabic apology so the reply never loses the guide.
- **Sprint 4 / task 4.2 — skill-dynamic-capability-expansion (M4)**:
  `src/expansion.py` — Sara gains capabilities at runtime, no redeploy (ADR-15 state
  re-derivation): the owner hands a credential env NAME in chat; `CapabilityScheduler`
  probes presence/format (>= 16 chars, no whitespace) with ONLY the NAME in errors and
  logs (the value never leaves `.env`), parses Arabic/English natural-language
  scheduling («كل صباح 7» → daily 07:00, «كل اثنين 9» → weekly, «كل ساعة» → hourly,
  gibberish → `ExpansionError`) with the clock zone pinned to `settings.tz`, and
  registers a background asyncio job (`register_capability` — reserved-name refusal,
  max-8 cap, single-lock serialization). Any failure or `wait_for` timeout DISABLES the
  task loudly (ERROR log with the task name + one owner notify, no silent retry loops);
  re-enable is an explicit owner action. Registry persists to `State/capabilities.json`;
  `restore(pipelines)` re-derives enabled tasks after a restart. Pipelines receive one
  ctx dict (`name`/`credential_env`/`vault`) — the secret VALUE never travels.
- **Sprint 4 / task 4.1 — module-syllabus-to-dag-parser**: `src/syllabus.py` turns a
  course syllabus PDF into an executable study plan — threaded `pypdf` extraction
  (length-capped untrusted input), ONE TIER3 `HEAVY_MODEL` call with strict-JSON output
  (one malformed retry, then loud `SyllabusError`; temperature 0, max_tokens 4096
  budget), nx-free DAG validation (cycles and orphan prereqs rejected with named
  offenders, deadlines parsed), weighted capped review schedule (60-min sessions
  backward from each deadline, daily cap, `[sara:syllabus:...]` idempotency tags on
  every Calendar event and Tasks entry), and the compiled plan filed to
  `Studies/<course>/` with YAML frontmatter. PDF text is DATA never instructions —
  the module has no PC-action surface (AST-scanned by AC7). New dep `pypdf>=5` (BSD-3).
- **Sprint 3 / task 3.5 — skill-desktop-telemetry-protocol**: one psutil snapshot
  (`bridge/telemetry.live_state()` — cpu, ram, C:/D: disks, uptime, top-CPU process,
  <2 s) that degrades unmeasurable metrics to None instead of crashing; served two
  ways: `GET /telemetry/live-state` on the LAN surface (Bearer BRIDGE_TOKEN — 401
  without it, 404 when unwired) and the tunnel cmd `telemetry.state` executed by the
  daemon. Core-side `TelemetryClient` (`src/telemetry.py`): pydantic-validated fetch,
  ONE Tier-1 FAST Arabic narration with the state numbers as verbatim DATA
  («شو وضع الجهاز؟»), deterministic numeric fallback when the brain is unreachable,
  honest «الجسر مو متصل هسا» when the bridge is offline. Payload carries no secrets.
- **Sprint 3 / task 3.4 — skill-pc-whitelist-safety-guardrail (M5)**:
  the PC control plane. `common/protocol.py` — v1 wire (JSON-per-frame, Hello/HelloAck
  token handshake: bad token closed 4401, second session 4400, token never logged);
  `bridge/guard.py` — whitelist re-read per check, fail-CLOSED on corrupt file
  (CRITICAL), power actions ALWAYS need a confirmation id; `bridge/executor.py` —
  detached `shell=False` spawns, audit codes `PC-YYYYMMDD-HHMMSS-4hex`, traversal/UNC
  refusal (`outside_allowed_roots`), missing exe «البرنامج مش موجود عالجهاز»;
  `bridge/wol.py` + `bridge/idle.py` — exact 102-byte magic packet (one UDP:9 sendto)
  and the latched idle monitor (one offer per window, sustained-activity re-arm);
  `src/bridge_server.py` — single-session acceptor, silence watchdog, honest
  `BridgeOffline`; `bridge/daemon.py` — outbound-only dialer (AST-asserted: never
  binds), heartbeat + capped exponential backoff; `src/pc_actions.py` — owner-origin
  gate (`RefusedOrigin`), confirmations-note-BEFORE-command, one audit code chaining
  note → cmd → ExecResult → Telegram, append-only `04_Archives/Audit/pc-ledger.md`;
  `docs/06-API-SPECIFICATION.md` formalizes the contracts (force semantics DROPPED).
- **Sprint 3 / task 3.3 — skill-verbal-action-summary-protocol**:
  `src/summary.py` + `common/consent.py` — task-bearing turns close with the exact
  Jordanian prompt «هل بتحب ألخص لك شو رح أعمل هسا؟»; `TaskExtractor` rides ONE TIER 2
  MEDIUM call per turn, strict-JSON validated (LLM output is DATA — garbage collapses to
  `[]` loudly, hashed not logged); one pending per turn (newer supersedes, casual turns
  capture nothing); consent grammar shared with 3.4 (`is_affirmative` first-token
  Jordanian match) with the structural binding rule — only an affirmative FOLLOWING the
  live prompt mints consent; approval files
  `04_Archives/Conversations/YYYY-MM-DD-HHMMSS-summary.md` (frontmatter `id`/`asked_at`/
  `resolved_at`/`task_count`/`tags: [action-summary]`, numbered tasks + daily-log
  wikilink); arbitration defers to 3.4's confirmation consumer and re-asks once after;
  brain failure never breaks the reply; bounded filing retries.
- **Sprint 3 / task 3.2 — skill-dynamic-vault-expander (M5)**:
  `src/vault_expand.py` — `VaultExpander.expand(domain, dirs, tags)` grows new domain
  trees under `01_Projects/<domain>` as structure emerges in conversation: sanitized
  sub-directories, an `_index.md` per directory (wikilinked to the domain root), and the
  tag ontology `<domain>/_tags.yaml` (`domain` / `created` ISO-UTC / `tags`, Arabic
  intact). Every expansion lands as ONE auditable commit (`sara: expand vault —
  <domain>`) through the Git Data API. PARA backbone (`01_Projects/ 02_Areas/
  03_Resources/ 04_Archives/ Contacts/ Call_Transcripts/ Studies/ Voice_Memos/
  Daily_Logs/`) is expansion-only — backbone-touching requests raise
  `BackboneImmutableError` pre-flight (zero API calls) and the module has no
  delete/move code path. Idempotent (vault state IS the memory — re-run = empty delta,
  no commit); invalid proposals refused pre-flight; token never in logs/exceptions.
- **Sprint 3 / task 3.1 — skill-obsidian-vault-architect (M6 / ADR-21)**:
  `src/vault.py` — THE read/write surface for Sara's git-backed Obsidian vault:
  `VaultClient` over the GitHub Contents API (Bearer + versioned headers, `?ref=VAULT_BRANCH`;
  upsert = sha lookup -> 404 create / 200 update, one 409 GET->PUT retry then
  `VaultConflictError`, auth errors loud with zero retries, >1,000,000-byte payloads refused
  pre-flight), Git Data API `commit_files` for ONE-commit structural changes (legacy
  `02_Areas/Studies/` -> top-level `Studies/` migration), `append_section` for append-only
  dossiers/logs, deterministic title sanitizer (Arabic preserved verbatim), YAML frontmatter
  writer/splitter (`safe_dump`, leading fences only, malformed -> ValueError naming the path),
  PARA path helpers + Zettelkasten wikilinks + canonical constants (PROFILE_USER_INFO,
  PROFILE_DIALECT, CONVERSATIONS/CONFIRMATIONS/AUDIT dirs), `redact_secret` screening every
  log/exception path, and the idempotent M6 first-boot `ensure_mandatory_dirs()` (index note
  per mandatory dir + contacts taxonomy + both profile files; re-run = zero writes).
  Settings: VAULT_GITHUB_REPO / VAULT_GITHUB_TOKEN (SecretStr) now required, VAULT_BRANCH
  (default main); new dep PyYAML>=6,<7. Plus **3.1b** `src/skills/social_graph.py` —
  `SocialGraph`: `dossier()`/`create_dossier()`, FAST-tier `extract_entities()` (strict JSON,
  LLM output is DATA — garbage -> [] loudly), `file_action()` (dated sections into the
  person's dossier AND `Daily_Logs/YYYY-MM-DD.md`; ambiguous category holds for owner
  confirmation; `Ignored/` never appends).
- **Sprint 2 / task 2.6 — skill-evening-proactive-journaler (§2.6)**:
  `src/skills/evening_journaler.py` — closes the owner's day: one Jordanian check-in at a
  `random.uniform` slot inside [18:00, 19:30) Amman (tasks done, critical mail, memos
  filed + one open question), calendar-guarded (booked -> no message, ledger still
  lands), plus the daily ledger `Daily_Logs/YYYY-MM-DD.md` (YAML frontmatter + Calendar/
  Mail/Voice memos/Notes sections, per-section «غير متوفر حالياً» degradation). Once per
  local day (corrigenda line on state-loss re-run); send failure never persists the
  check-in date (30 s retry tick); zero LLM in the hot path. Settings:
  JOURNALER_ENABLED, JOURNALER_WINDOW_START/END, DAILY_LOGS_DIR; state
  `{vault}/State/journaler.json`.
- **Sprint 2 / task 2.3b — skill-social-enrollment (multi-speaker registry, §2.3b)**:
  `src/skills/social_enrollment.py` — `VoiceprintRegistry` extends ADR-17 beyond the
  owner: per-contact Fernet-sealed vectors under `State/voiceprints/` with dossier
  frontmatter (`voiceprint_ref`), owner-first `match` (<50 ms cosine), running-centroid
  stability, transcript appends, and the three-way pending lifecycle — known contact ->
  warm `CONTACT_MODE_AR` message-taking reply (zero privileged calls, bot-wired through
  `verify_or_lockdown`); unknown owner-absent -> `Voice_Memos/Pending_Speakers/` staging;
  verdicts `confirm:{Category}` -> dossier+voiceprint, `ignore` -> `Contacts/Ignored/`
  (never matches again), `unknown` -> `Contacts/Unknown/` + security flag (re-matchable).
- **Sprint 2 / task 2.3 — skill-voice-biometric-auth + Guest Mode (ADR-17)**:
  `src/skills/voice_biometric_auth.py` — sealed single-owner ECAPA-TDNN voiceprint
  (speechbrain pinned, py3.12 wheel-verified; lazy model load, CPU executor, ffmpeg
  in-memory decode): `/enroll-voice` + one owner voice note Fernet-seals
  `{vault}/State/owner_voiceprint.enc`; every voice note then verifies — unenrolled
  -> middleware-only trust (info log), match >= VOICEPRINT_THRESHOLD -> owner path,
  below-threshold or ANY verification error -> Guest Mode (fail-closed): warm
  Jordanian lockdown reply + exactly ONE `Voice_Memos/Pending_Speakers/` staging
  note (transcript placeholder + encrypted embedding, ADR-15-durable, same-minute
  collisions never overwritten) and ZERO privileged effects — spy-proven no
  gateway/whitelist/subprocess/extra-vault calls. `tests/test_guest_lockdown.py`
  JOINS the sacred floor. Settings: VOICEPRINT_THRESHOLD=0.75,
  VOICEPRINT_MODEL=speechbrain/spkrec-ecapa-voxceleb.
- **Sprint 2 — Google integration + tiered email triage (tasks 2.1-2.4)**:
  `src/google_auth.py` (OAuth consent + Fernet-sealed token cache, proactive/401
  single-flight refresh), `src/google_suite.py` (Calendar/Tasks/Drive/Contacts typed
  clients, UTC-normalized), `src/gmail.py` (sweep/incremental fetch with dedupe and
  sweep fallback, dispatch-then-mark redelivery, watch registration, read-only
  peek_unread), `src/email_triage.py` (heuristic tiers + one FAST_MODEL refinement
  with untrusted-data containment and never-downgrade merge; dispatch matrix
  drop/text/voice/critical-ping with ack + owner-activity stops), `src/daily_brief.py`
  (fire-once-per-local-day Jordanian digest — events, due tasks, mail picture —
  deterministic template, per-section degradation). Settings: GOOGLE_VIP_SENDERS,
  TRIAGE_KEYWORDS_*, CRITICAL_PING_*, BRIEF_ENABLED, BRIEF_LOCAL_TIME.
- **Sprint 2 / task 2.4 remainder — TokenJuice compaction (ADR-19)**: pure
  `tokenjuice_compact` (quoted reply chains, signature blocks, legal footers and
  tracking boilerplate stripped; whitespace collapsed; body capped with a truncation
  marker) now feeds BOTH the heuristic body-keyword scan and the FAST refinement
  payload — less free-pool token burn, identical tier decisions. Settings:
  TOKENJUICE_MAX_CHARS=4000.
- **Sprint 2 / task 2.5 — skill-voice-to-vault-transcriber (ADR-22)**:
  `src/skills/voice_to_vault_transcriber.py` — owner voice notes (post-biometric-gate
  only) decode in-memory via ffmpeg to 16 kHz mono s16le and transcribe with LOCAL
  faster-whisper (MIT, CPU int8; cloud STT settled to never — ADR-22); notes file
  atomically to `Voice_Memos/YYYY-MM-DD-HHMM.md` (YAML frontmatter date/source/
  duration_s, same-minute numeric suffixes, empty transcripts filed as `(empty)`,
  write retried once and never blocking the reply). Bot wiring: enrolled owner voice →
  transcribe → file → transcript enters the standard streamed text pipeline; guest
  voice never reaches the transcriber. Settings: WHISPER_MODEL_SIZE=small,
  WHISPER_COMPUTE_TYPE=int8, VOICE_MEMOS_DIR=Voice_Memos.
- **Sprint 2 / task 2.2 — skill-telegram-chat-streamer + bot shell**: progressive delivery
  replaces the one-shot aggregated reply — `src/skills/telegram_chat_streamer.py`
  (`ChatStreamer.stream_reply`) sends the placeholder instantly, fires the first edit on the
  first delta (<250 ms Audio-TTFT), coalesces further deltas at `STREAM_EDIT_INTERVAL_MS`
  (750 ms), lands the final text verbatim, and honors a cancel event (owner interjection
  keeps the partial in the bubble). Error modes: edit rate-limit doubles the interval;
  placeholder failure falls back to the Sprint-1 aggregate send; mid-stream failure -> shell
  apology with delivered text preserved. Bot shell (`src/bot.py` + `src/middleware.py`,
  carried from old-1.4): owner-ID silent-drop middleware on `dp.update.outer_middleware`,
  /start welcome + Ogg voice greeting, /help, voice-note static ack (zero gateway calls),
  typing indicator, global `dp.errors` handler; `FrontDoorDispatcher.handle` now carries the
  persona system prompt into the tier stream. Settings: `STREAM_EDIT_INTERVAL_MS=750` in
  `.env.example`.
- **Sprint 1 / task 1.5 — 3-tier brain + Fast Front-Door Dispatcher** (`src/dispatcher.py`,
  `src/gateway.py` chains): per ADR-16/18 — `Tier` FAST/MEDIUM/HEAVY chains walked per
  request (quota -> immediate advance, transient -> capped retries, fatal -> loud stop,
  unchanged per-tier), one Tier-1 router call classifies (tiny JSON verdict) and yields the
  instant Jordanian ack («من عيوني هسا ببدأ...») as the first delta (<250 ms TTFT budget);
  simple chat answered fully at Tier 1, single/dual-tool intents stream Tier 2, multi-step
  DAGs stream Tier 3; unparsable/failed routing degrades safely to Tier 2 with a loud log.
  Settings carries the tier pins + comma-separated fallback lists (boot fails fast on gaps);
  `.env.example` and the runtime `.env` migrated to the `google/`-prefixed pins; the 2-slot
  PRIMARY/FAST chain retired.
- **Sprint 1 / task 1.4 — adaptive Jordanian dialect engine** (`src/dialect.py`): M1
  notes-driven pronunciation normalization before Edge-TTS (longest-term-first),
  never-blocking ingestion of owner teach-lines («تعلمي: term -> phonetic (context)»)
  into `Dialect_Notes.md` YAML entries (term/phonetic/context/date), and the compact
  system-prompt dialect snapshot; pure sync transforms, vault persistence wired at 3.1.
- **Sprint 1 / task 1.3 — voice pipeline** (`src/voice.py`): Edge-TTS -> ffmpeg -> Ogg Opus
  fully in memory as an async byte-chunk iterator; first encoded chunk surfaces immediately
  (time-to-first-encoded-chunk, <600 ms budget — binding Q1; tiny `-probesize 32` keeps the
  stream flowing from the first frames); blank/oversized text rejected pre-spawn; missing
  ffmpeg raises an actionable error; every failure path reaps the ffmpeg child; Edge-TTS
  metadata events never forwarded.
- **Sprint 1 / task 1.2 — OmniRoute client** (`src/gateway.py`): OpenAI-compatible SSE
  streaming as async text-delta iterator; PRIMARY->FAST model fallback; free-pool survival
  (quota -> immediate fallback, transient -> capped-backoff retries, fatal -> loud stop);
  mid-stream failures never restart a partially-yielded reply; missing-[DONE] guard; mid-stream SSE error events classified (never swallowed).
- **Sprint 1 / task 1.1 — project skeleton**: async `src/` package with pydantic v2
  `Settings` validating `.env` (fail-fast on the six critical vars, empty-string→unset
  normalization), one-sink loguru setup, ops health probe (`python -m src.main --health`),
  and the async entrypoint behind `make run-core`.
- Socratic discovery record and confirmed mission statement (persona: Sara سارة).
- Canonical documentation scaffold: CLAUDE.md, README, LICENSE, CONTRIBUTING,
  CHANGELOG, SECURITY, Makefile, CI workflow, and docs/00–05.
- **Phase 2 implementation specifications** (`docs/specs/sprint-{1..4}.md`): per-task
  interfaces, behaviors, testable acceptance criteria mapped to pytest targets,
  error modes, zero-cost checks — drafted by parallel agents and adversarially
  verified (Guide pass); every finding integrated with disposition appendix.
- Session-resume protocol baked into CLAUDE.md + checkpoint file.
- Native stage-gate hooks (`.claude/hooks/`) and resumable phase state
  (`.claude/PHASE-STATE.md`).
- Credential manifest (`.env.example`) covering core (VPS) and bridge (PC) processes.

### Changed
- **Second master-directive alignment (2026-08-29)**: ADR-16 amended in place to the
  3-tier multi-model brain (FAST/MEDIUM/HEAVY via OmniRoute) + ADR-17..21 appended
  (voice biometrics/Guest Mode, front-door dispatcher, TokenJuice, in-memory Opus,
  5-directory vault); Fast Front-Door Dispatcher specced as Sprint-1 task 1.5;
  per-sprint skill rotation with the teardown protocol (`docs/10-CHECKPOINT.md`);
  sprint specs 2-4 exhaustively re-mapped; `.env.example`/`agents_config.json`
  re-pinned to the tier models; `config/whitelist.json` seeded; KPIs add
  Tier-1 TTFT < 250 ms and biometric < 50 ms.
- Documentation consolidation (ADR-14): 22 docx drafts retired from the working tree
  (21 recoverable via git history; 1 via .ingest text); zero-tolerance persona naming
  enforced across all records; Future Scope parked without version numbers (PC Health
  Monitor, Voice Read-It-Later, Emotional Context Memory, Silent Vault Backup,
  on-demand YouTube/Weather/Maps APIs — per-request, free-tier, $0 preserved).
- **Branch directive (owner, 2026-08-31, binding)**: ALL commits land directly on
  `main` and push immediately; the per-stream worktree/branch merge pattern retired
  (the `core-foundation` worktree is a reference checkout only).
- **Quality gate hardened (4.4a)**: >=85% branch coverage enforced from 4.4a onward
  (Sprints 1-3 ran measurement-only — decided deviation, documented in TEST-PLAN §1);
  CI unified onto one gate script.

### Security
- **Owner-only access surface**: non-owner Telegram accounts dropped silently at
  middleware level; two-layer owner auth composes the allowlist with local voice
  biometrics (ECAPA-TDNN, fail-closed) — any verification error or below-threshold
  voice lands in Guest Mode: warm lockdown reply, message-taking only, ZERO
  privileged effects.
- **Secrets never travel**: all credentials load strictly from environment/HF
  Secrets; vault token redacted on every log/exception path (`redact_secret`);
  capability registration handles credential env NAMES only (the value never leaves
  the environment, never reaches ctx, never reaches logs); the bridge token travels
  only inside the first Hello frame and is never logged; deploy-smoke failures are
  screened through a Settings-aware masker (httpx errors embed full URLs carrying
  the bot token — nothing secret survives into logs).
- **Whitelist guardrail**: any PC action outside `config/whitelist.json` requires an
  explicit owner confirmation with the confirmation ID persisted to the vault BEFORE
  the command leaves the core; power actions always require it; the whitelist guard
  fails CLOSED on a corrupt file (CRITICAL); force semantics were dropped from the
  API specification entirely.
- **Untrusted content boundary**: email bodies, PDF text, web pages and generated
  study content are DATA never instructions — triage containment, syllabus/tutor
  AST-scanned zero PC-action surfaces, LLM output strict-JSON validated with loud
  garbage collapse.
- **Build/deploy hygiene**: `.dockerignore` keeps `.env`, OAuth client JSON, session
  files and local state out of the build context; the vendored secret scanner runs
  inside `make gate` (known API key formats, credential-assignment heuristic with
  placeholder allowlist, committed-.env detection); container runs non-root; durable
  state confined to the vault by an enforced audit test.

### Deferred-to-v1.1
- Live bidirectional Telegram voice calls (PyTgCalls WebRTC engine) — v1.0 ships
  ZERO live-call code, locked by test.
- tech-hardware-scout and career-project-incubator proactive skills.
- Mem0/Firestore persistent memory layer (evaluation deferred).
