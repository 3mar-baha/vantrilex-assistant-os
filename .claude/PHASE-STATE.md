# Phase State — resumable execution record

## ⚡ SESSION RESUME PROTOCOL (every fresh session executes this BEFORE acting)

1. **Prime context** — read, in order: `CLAUDE.md` → this file → `docs/01-ARCHITECTURE.md` §1
   (binding mission record) → `docs/03-DECISIONS.md` → `docs/02-BACKLOG.md`. Then `uos status`.
2. **Sync the OS framework — PRESERVE LOCAL WORK**: the clone at
   `C:\Projects\Git-hub\Workflow\universal-agentic-os` often carries owner improvements that are
   uncommitted/unpushed; LOCAL STATE IS THE LATEST VERSION. First inspect:
   `git -C <repo> status --short` and `git -C <repo> log --oneline "@{upstream}..HEAD"`.
   NEVER run reset/checkout/clean/stash against that repo. `pull --ff-only` only when actually
   behind. Then `uos doctor` must be green; confirm subcommands (`status`,`graph`,`decide`,
   `dispatch`,`merge`,`ship`). Toolkit integrity failure -> that repo's `scripts/setup-toolkit.sh`
   then `scripts/sync-toolkit.sh`.
   **HANDOVER COMPLETE (2026-08-26, owner-explicit)**: final workflow pushed & pulled —
   launcher feature series (vantrilex.ps1 multi-agent, 46/46 SelfTest PASS, e2e lifecycle
   suite, `uos doctor` healthy, symlink re-installed via `uos.sh install` after an e2e test
   left it dangling on a temp path). **CHERRY-PICK VENDORING DONE (2026-08-28, commit `24f8790`)**:
   `.githooks/{commit-msg,pre-commit}` ADOPTED + `core.hooksPath=.githooks` active (from then on
   NO Co-Authored-By trailers — enforced by hook) · `scripts/*.sh` vendored · skills: none upstream.
   PENDING owner action: `.mcp.json` (fetch/sequential-thinking/filesystem/git, WITHOUT
   brave-search) was blocked by permission classifier — content in session transcript; owner to
   approve/create. Unchanged REFUSALS: our `.claude/settings.json`, `.github/workflows/ci.yml`,
   `.claude/hooks/session-primer.ps1`.
3. **Preflight gate (blocking)** — FFmpeg present (`ffmpeg -version`) · OmniRoute
   `http://localhost:20128/v1/models` HTTP 200 AND pools non-empty (log line
   "matched no connected models" ⇒ halt and ask the owner to connect free provider
   credentials) · git identity set · `make gate` green on py -3.12.
4. **Resume** at the phase marked ← **current** in the lifecycle below. The six discovery
   rulings recorded here are SETTLED — never re-litigate them.
5. **Discipline** — report like a leader after every phase (completed / remaining / risks /
   next action); update this file at every phase exit; end every session resumable from disk.

## ⚙️ CLOSED-LOOP EXECUTION PROTOCOL (binding for ALL implementation — owner-approved 2026-08-26)

1. **One worktree per stream** (`git worktree add ../<stream>`, created once); merge to main
   only at stream end, after the owner reviews the stream summary. No other worktrees.
2. **Per-task loop, then mandatory STOP**: write the pre-specified failing test(s) (the
   AC→pytest mapping in `docs/specs/` IS the test design — never invent new test structure)
   -> minimal code to green -> `make gate` -> commit -> post a ≤5-line report WITH proof of
   working behavior -> **HALT. Do not start the next task until the owner replies
   "التالي"/"next".**
3. **Sacred floor** (immune to any future methodology amendment):
   `tests/test_owner_middleware.py` and `tests/test_whitelist_guardrail.py` always exist,
   always run, and block every merge.
4. **Circuit breaker** (Invariant 4): 3 failed fix attempts on one defect = full halt + DIR.
   Loop-burn is structurally impossible.
5. **Cost discipline**: ONE implementer thread per task (no agent swarms during
   implementation — the spec fleet era is over); fast model welcome; Guide review once per
   sprint exit, not per task; zero speculative layers (ponytail).
   **Model pin (owner directives 2026-08-28/29 + MASTER DIRECTIVE 2026-08-29)**: two layers —
   (a) HARNESS (Claude Code's own calls): GLM-only `z-ai/glm-5.3-flash`; Anthropic/Claude
   FORBIDDEN; non-GLM spend cap $0.01. (b) SARA'S BRAIN (Gemini via OmniRoute, per master
   directive): `PRIMARY_MODEL=gemini/gemini-3.7-flash` (extended thinking; deep agentic/
   tutoring), `FAST_MODEL=gemini/gemini-3.5-flash-lite` (<600ms TTS text, classification);
   pool-level failover covers the gemini-3.1-pro class.
   **Brain pins SUPERSEDED (ADR-16 amended 2026-08-30 + owner bake-off 2026-08-31)**:
   Gemini RETIRED; current pins live in `.env.example` — FAST/MEDIUM
   `groq/openai/gpt-oss-20b` (fb minimax-m2.7:free, gpt-oss-120b), HEAVY
   `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (fb gpt-oss-120b). Harness stays GLM-only.
   **Branch directive (owner, 2026-08-31, binding — supersedes loop item 1's merge rule)**:
   ALL commits land directly on `main` and push immediately (owner: «اريد ان يتم توجيه
   جميع الكوميتات الى main»). The per-stream worktree/branch pattern is retired — `main`
   is the implementation branch; work in the docs checkout. The `core-foundation` worktree
   is a reference checkout only: keep its branch ff-synced to `main`, never commit new
   work on it.

Updated at every phase exit and every significant turn end.

## Mission (confirmed 2026-08-26; host updated 2026-08-31)

Vantrilex Assistant OS — **Sara (سارة)** — product v1.0.2. Owner-only, strictly
$0.00/month, **Oracle Cloud Always-Free VM** host (ADR-15 amendment; supersedes VPS-primary
and the HF-Space interim) + OmniRoute brain (`http://localhost:20128/v1`), Telegram
chat/Ogg Opus voice notes in Jordanian Arabic (`ar-JO-SanaNeural`), Google suite +
tiered email triage, git-backed Obsidian PARA vault, whitelisted PC control over an
outbound-only Windows bridge daemon. Live calls -> v1.1; scouts -> v1.1; SIP -> v1.5;
social agent -> v2.0. ("v1.1.0" in framework branding = the Universal Agentic OS, not the
product.)

## Discovery rulings (binding)

| Q | Ruling |
|---|---|
| 1 | Persona = Sara (retired draft persona name replaced everywhere) |
| 2 | VPS-primary + outbound-only PC bridge (supersedes Cloud Run drafts) |
| 3 | Owner-only hard allowlist, silent drop |
| 4 | v1.0 = exec core minus live calls (verbatim scope excludes scout skills) |
| 5 | Zero-cost absolute; whitelist miss -> Telegram confirmation (v1.0) |
| 6 | Credential manifest `.env.example`, progressive gating |

## Lifecycle position

- [x] Preflight — ALL GREEN (2026-08-26): FFmpeg 9.0.1 installed; OmniRoute :20128 healthy.
      Watch item: several OmniRoute auto pools reported "no connected models" at startup —
      connect free provider credentials before Phase 3 brain smoke tests.
- [x] Phase 1a — Socratic discovery, mission confirmed
- [x] Phase 1b — scaffold complete; Guide audit findings (3 blockers, 5 minors) all fixed;
      quality gate green; initial commit
- [x] Preflight re-check mid-session — OmniRoute brain VERIFIED live (real completion streamed
      from gemini-3.1-flash-lite free pool); bot token verified via getMe (@Sara_Vantrilex_bot);
      vault repo created+seeded (3mar-baha/vantrilex-vault); .env filled except owner-side
      account secrets (Google OAuth, VPS, bridge TLS)
- [x] Phase 2 — Architect & Guide COMPLETE: 4 per-sprint implementation specs written to
      docs/specs/sprint-{1..4}.md by parallel draft agents, adversarially verified by Guide
      agents (all verdicts FIX), every finding integrated inline + disposition appendix per file.
      Highlights caught pre-code: open_path whitelist bypass (BLOCKER), bot-token log-leak,
      crash-window email loss, self-WoL impossibility ruling.
- [x] Phase 2 — Architect & Guide COMPLETE + COMMITTED (`6fa22f7`, 7 files / 1439 insertions):
      docs/specs/sprint-{1..4}.md with every Guide finding integrated; ADR-13 recorded.
      **Guide sign-off: GRANTED** (conditional-on-commit condition satisfied).
- [x] Phase 3 — Implement & Verify COMPLETE (2026-08-31): Sprints 1-4 all delivered
      (records: `docs/10-CHECKPOINT.md` + `docs/PROJECT-JOURNEY.md` §11-13; full sprint-4
      closure in the Phase-4 line below).
      DONE 1.2: client + SSE-error hardening (`3e44f1c`); live-wired 2026-08-29 — Gemini
      pools blocked upstream by Google (403 "project denied access" — OWNER fixes in
      Google: enable Generative Language API / unflag the key's project). DONE 1.3
      (2026-08-29): `src/voice.py` AC1-AC8 green, gate green — commits `4d0aefa` (voice)
      + `0e796fd` (docs) on branch `core-foundation`, PUSHED; awaiting owner merge decision
      + HALT per protocol.
      **MASTER-DIRECTIVE OVERHAUL (2026-08-29)**: committed on branch `core-foundation`
      (pushed for review: `71a17ca` + `fef6246` on top of task-1.2 commits) — ADR-15 (HF
      Spaces host) + ADR-16 (Gemini dual-brain) in 03-DECISIONS; BACKLOG re-mapped to the new
      sprint DAG (bot shell → Sprint 2.1; biometrics 2.6, evening ledger 2.7, dialect engine
      1.4, vault dirs 3.1, expansion 4.1, coverage 85% 4.2, Space deploy 4.3); M1-M9 spec at
      docs/specs/master-directive-2026-08-29.md; CLAUDE.md / 01-ARCHITECTURE / 00-VISION /
      RUNBOOK / .env.example / agents_config.json / AI-INSTRUCTIONS.md synchronized.
      MERGE to main pending owner review. Task 1.2 AC10 live smoke still awaits valid
      Gemini pool credential (upstream 400 "API key not valid" — owner-side fix in OmniRoute).
      **SECOND MASTER DIRECTIVE (2026-08-29)**: brain upgraded to 3-TIER multi-model
      routing (ADR-16 amended in place: FAST `google/gemini-3.5-flash-lite` TTFT<250ms /
      MEDIUM `google/gemini-3.7-flash` / HEAVY `nvidia/nemotron-3-ultra-550b` + fallbacks)
      behind the **Fast Front-Door Dispatcher** (ADR-18) — new Sprint-1 task 1.5 (3-tier
      gateway chain + dispatcher + `.env` `google/`-prefix migration); ADR-17 (voice
      biometrics + Guest Mode), ADR-19 (TokenJuice), ADR-20 (in-memory Opus), ADR-21
      (5-dir vault) appended; **per-sprint skill rotation** into `.claude/skills/` with
      binding sprint-exit teardown, ledgered in new `docs/10-CHECKPOINT.md`;
      `config/whitelist.json` seeded; sprint specs 2-4 exhaustively re-mapped (AC1-AC10
      each); TEST-PLAN (85% branch gate), RUNBOOK (Cloud Run fallback + LAN :8000),
      PROJECT-JOURNEY (§10 addendum), VISION/ARCHITECTURE/CLAUDE.md/AI-INSTRUCTIONS/
      .env.example/agents_config.json all synchronized. Committed on branch
      `core-foundation`, pushed for review; merge to main pending.
      **THIRD DIRECTIVE (2026-08-29, social-graph addendum)**: `skill-social-graph-and-voice-
      enrollment` specced in — `Contacts/{Family,Friends,Colleagues,Ignored,Unknown}` taxonomy
      (ARCH §6b + sprint-3 3.1b), daily story entity extractor (TEST-PLAN
      `test_story_extractor.py`), multi-speaker voiceprint lifecycle A/B/C (sprint-2 2.3b,
      guest staging re-homed to `Voice_Memos/Pending_Speakers/` per ADR-15). Final branch
      state: `79b9563` (3-tier doc/config sync) + `5519a6c` (sprint 2-4 spec re-maps) +
      `53d8d71` (social-graph) — ALL pushed to origin/core-foundation; `make gate` green
      (32 tests). Merge to main pending owner review. Task 1.2 AC10 still blocked on
      Google 403 (owner-side).
      **TASK 1.4 DONE (2026-08-29)**: Sprint-1 skills ingested into `core-foundation/.claude/skills/`
      (tdd · ponytail/* · clean-code-guard; git-ignored `ff79bad` — provenance in
      `docs/10-CHECKPOINT.md`); TDD red->green: `tests/test_dialect.py` (3/3 M1 ACs) +
      `src/dialect.py` (normalize longest-first, never-blocking `learn()`, prompt snapshot) —
      commit `aa64644` + docs `59c2a7e` + ignore `ff79bad` on branch, PUSHED; `make gate`
      green (35 tests).
      **TASK 1.5 DONE — SPRINT 1 COMPLETE (2026-08-29)**: 3-tier chains in `src/gateway.py`
      (Tier FAST/MEDIUM/HEAVY walked per request) + `src/dispatcher.py` (ADR-18 front door:
      Tier-1 router verdict -> instant ack «من عيوني هسا ببدأ...» as first delta <250ms TTFT,
      direct stays Tier 1, tier2/tier3 stream after the ack, safe-default tier2 + loud log on
      router failure). Settings: medium/heavy required + comma-separated fallback lists
      (fast/medium/heavy_chain); `.env.example` + runtime `.env` migrated to `google/` pins;
      2-slot chain retired. TDD red->green: `tests/test_dispatcher.py` AC1-AC9 (9/9), suite
      45 green, gate green. Commits `fe4e5ca` (code) + `5ead135` (docs) + `643093f`
      (teardown of tracked skills + RUNBOOK tier-chain signatures) — PUSHED; branch head
      `643093f`. **Sprint-exit teardown executed**: `.claude/skills/*` wiped, 45 green after
      teardown, recorded in `docs/10-CHECKPOINT.md`. AC10 live smoke blocked on Google 403
      (owner-side). HALTED — next: Sprint 2 (2.2 bot shell -> 2.1 Google foundation ->
      2.3/2.3b biometrics+social -> 2.4 triage -> 2.5 transcriber -> 2.6 journaler).
      SESSION-CLOSE VERIFICATION (2026-08-29): final `make gate` green (45 passed, security
      + docs guards OK); both repos clean and pushed (core-foundation `643093f`, docs main
      `5373255`). NOTE for next session: live `--health` probe at close showed OmniRoute
      NOT RUNNING (`http://localhost:20128/v1` unreachable) — owner starts OmniRoute before
      Sprint-2 preflight (protocol step 3) and for the Google-403 live-smoke retest.
      **TASK 2.2 DONE (2026-08-30, sprint-2 open)**: skill-telegram-chat-streamer + bot
      shell (old-1.4 body carried) — `src/skills/telegram_chat_streamer.py` (placeholder «…»
      -> first edit <250 ms TTFT -> coalesced edits @STREAM_EDIT_INTERVAL_MS=750 -> final
      verbatim; cancel keeps partial; rate-limit doubles interval; placeholder failure ->
      aggregate fallback), `src/bot.py` + `src/middleware.py` (owner-ID silent drop on
      update.outer_middleware — SACRED FLOOR test_owner_middleware.py born AC1-AC5;
      /start welcome+Ogg greeting, /help, voice ack zero gateway, global dp.errors),
      `FrontDoorDispatcher.handle` gains keyword `system=` carrying the persona prompt into
      the tier stream (1.5 tests untouched). Skills ingested: tdd, diagnosing-bugs,
      clean-code-guard, test-guard (git-ignored). TDD red->green: 21 new tests
      (test_owner_middleware 5, test_bot_shell 8, test_chat_streamer 8), suite 66 green,
      gate green. Commits `0a5ae11` (code) + `4ba0183` (docs) on branch core-foundation,
      PUSHED. aiogram 3.31 surfaces probed empirically (FakeSession returning real Message
      models; ErrorEvent injection by name; BufferedInputFile.data). NOTE: old-1.4 AC9
      empty-buffer fallback absorbed by the dispatcher's safe-default ack (ADR-18 — bubble
      is never empty); one-line guard kept in shell. HALTED — next per owner: 2.1 Google
      foundation. OmniRoute still offline locally (owner starts before live smoke).

      **BRAIN RE-PIN (2026-08-30, owner-directed, before 2.1)**: Gemini formally retired —
      Google denies the project at API level (403 "project denied access" even with
      Generative Language API enabled; free tier gated behind a billing card the owner's
      bank rejects). Read-only OmniRoute SQLite probes (keys redacted): key lives under
      provider `gemini` (only `gemini/...` slugs route); Groq live catalog = ONLY
      gpt-oss-120b/20b (llama-3.3/scout/qwen3 404-retired; OmniRoute BUILT-IN groq list is
      stale — Import-from-/models + Test-all used); OpenRouter `:free` pool imported
      (400/400). 7-candidate talker bake-off (same Sara persona prompt): gpt-oss-20b 0.5s
      TTFT clean Jordanian; minimax-m2.7 warmest dialect 2.2s + one typo; nemotron-super +
      ling role-inverted (called owner «يا سارة»); glm-5.2/gemma-26b/inkling empty
      (reasoning ate budget); gemma-4 owner-rejected («لغته ركيكة كعربية»).
      OWNER-SET ROLES: FAST = Sara's voice/talker (only user-facing model); MEDIUM =
      worker (Obsidian librarian + task executor; gpt-oss-120b pins at 2.3; never user
      prose); HEAVY = deep tasks. New pins (ADR-16 amendment, recorded in 03-DECISIONS):
      FAST/MEDIUM `groq/openai/gpt-oss-20b` (fb minimax-m2.7:free [+gpt-oss-120b]),
      HEAVY `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (fb gpt-oss-120b).
      OpenRouter :free = 50 req/day/account; owner adding 6 rotating keys (native
      OmniRoute rotation). Gate green (66), commit `22d3396` on core-foundation.
      Task 2.1 red artifacts UNTRACKED in worktree (test_google_clients.py,
      test_gmail_watch.py, src/google_auth.py torn — needs clean rewrite); 2.1 resumes
      from red, gate open per owner.

      **TASK 2.1 DONE (2026-08-30, sprint-2 §2.1)**: `src/google_auth.py` rewritten clean
      from the corrupted draft — OAUTH_AUTH_URL/TOKEN_URL, AUTH_SCOPES (5, readonly where
      the OS never writes + gmail.modify), GoogleAuthError/GoogleAPIError(status,
      body_excerpt), GoogleTokens, token_cache_path ({vault}/State/google_token.json.enc,
      ADR-15), load_client_secret (unwraps installed; missing -> actionable error naming
      path+runbook), build_consent_url (one raw scope param per scope, encoded loopback
      redirect, offline+consent+state), verify_state (compare_digest), save/load_tokens
      (atomic Fernet tmp+replace, chmod600 best-effort; corrupt -> warn+None),
      exchange_code/refresh_tokens, authorize_interactive (ephemeral loopback listener,
      state CSRF check, sealed save) + `python -m src.google_auth`; GoogleSession:
      proactive single-flight refresh (lock + stale re-check; expires_at==0 = unknown
      expiry, 401 handles it), 401 -> single-flight refresh -> replay once -> still 401
      -> GoogleAuthError re-bootstrap; other non-2xx -> GoogleAPIError(excerpt<=300).
      `src/google_suite.py`: CalendarEvent/TaskItem/DriveFile/Contact (UTC-normalized,
      wire aliases mimeType/modifiedTime/status) + GoogleSuite list_events/create_event/
      list_tasks/add_task/list_drive_files/search_contacts. Red-test bug fixes (spec is
      contract): 3 sync session.request -> async/await; _settings gains
      GOOGLE_OAUTH_CLIENT_JSON override; added spec-mapped test_proactive_refresh_single_
      flight + tests/test_google_suite.py (AC4 x4 fixtures). Gate green (79 passed,
      Security Gate OK, Docs Guard OK). Commit `11c733f` on core-foundation. RUNBOOK §6
      gained the Google OAuth bootstrap walkthrough. 2.2 gmail red tests parked at
      tests/test_gmail_watch.py.red. HALTED — next per owner: 2.2 Gmail watch+fetch.

      **TASK 2.2 DONE (2026-08-30, sprint-2 §2.2)**: `src/gmail.py` — EmailMessage
      (list_unsubscribe real field, body capped at triage_body_max_chars with
      «…[مقتطع]» marker), GmailState (seen_ids capped 2000 newest on save),
      StateStore (plaintext {vault}/State/gmail_state.json — no secrets per ADR-15;
      corrupt -> *.corrupt os.replace + fresh), GmailInbox.watch (topic gated:
      unset -> False + no wire call; set -> users.watch POST, response historyId
      seeds cursor; API failure -> warning + False, polling unaffected),
      fetch_new (Lock-serialized; no cursor -> sweep is:unread newer_than:{N}d
      seeding cursor from list historyId; cursor -> history.list messagesAdded
      minus SENT; 404/expiry -> sweep fallback; dedupe on message id),
      mark_seen = the ONLY persistence point (dispatch-then-mark — crash
      re-delivers), unread_digest, parse_message PURE (From split via parseaddr,
      Date header -> internalDate -> epoch defaults, «بدون عنوان», recursive
      parts walk preferring text/plain, HTML strip via HTMLParser with
      script/style skip, base64 failure skips part, has_attachments),
      run_gmail_poll (fetch -> dispatch per message -> mark full batch; API
      errors logged, loop continues). RED-TEST CORRECTIONS (spec is contract):
      first-boot route was history-only — spec mandates no-cursor -> sweep
      (real history.list requires startHistoryId) -> Routes gained LIST_URL in
      tests 1-3, message_payload gained labels param; added missing spec-mapped
      AC1/AC5/AC6/AC7 tests (plain fixture, watch gating, corrupt state,
      lock serialization with yielding session wrapper). Gate green (87 passed,
      Security Gate OK, Docs Guard OK). Commit `ae48aea` on core-foundation.
      Docs: TEST-PLAN rows (google_suite + gmail_watch), ARCHITECTURE §4
      delivery footnote. HALTED — next per owner: 2.3 triage classifier +
      dispatcher.

      **TASK 2.3 DONE (2026-08-30, sprint-2 §2.3)**: `src/email_triage.py` —
      Tier (drop/semi/important/critical) + _VISIBILITY, TriageDecision,
      escape_mdv2, render_semi (fixed template, escaped slots, excerpt ≤400),
      render_voice_script (ar-JO), TriageClassifier.heuristic PURE (VIP
      sender ∈ google_vip_senders -> +0.6 AND floor CRITICAL, subject
      keyword +0.25 each distinct + floor SEMI, body +0.15 each distinct
      capped +0.30, list_unsubscribe −0.40; bands ≥0.9/[0.6,0.9)/[0.3,0.6)/
      <0.3), classify (VIP-floor and obvious-newsletter skip the brain;
      else ONE FAST_MODEL call temperature 0 max_tokens 120, 15 s timeout,
      body wrapped <<<EMAIL_DATA>>>/<<<END_EMAIL_DATA>>> + containment
      clause; merge = higher visibility — rescue upward never downgrade;
      invalid JSON/bad tier/timeout/exception -> heuristic alone), Dispatcher
      (register callback «تم الاطلاع» triage:ack:{id}; dispatch matrix DROP
      log-only / SEMI MarkdownV2 text with plain-text retry / IMPORTANT voice
      note with text fallback / CRITICAL priority voice + ping task every
      critical_ping_interval_min (clamped ≥1 min) until ack / note_owner_
      activity / critical_ping_max (0 = unlimited)); settings keys
      google_vip_senders, triage_keywords_ar/en (empty -> module defaults),
      critical_ping_interval_min=5, critical_ping_max=6. Tests AC1-AC10 per
      spec mapping incl. injection-twin trace equality + AST import-surface
      scan (no bridge/whitelist/subprocess/socket/system identifiers).
      Gate green (102 passed, Security Gate OK, Docs Guard OK). Commit
      `438bfb3` on core-foundation. Docs: ARCHITECTURE §4 refinement lane +
      ping cap, RUNBOOK §6 triage tuning, TEST-PLAN row. HALTED — next per
      owner: 2.4 daily brief composer.

      **TASK 2.4 DONE (2026-08-30, sprint-2 §2.4 — sprint-2 CLOSED)**:
      `src/daily_brief.py` — BriefData (None section = degraded),
      BriefComposer(suite, inbox, classifier, bot, chat_id, settings):
      render PURE MarkdownV2 Arabic template (Amman zoneinfo, Arabic weekday
      + Levantine month names, escaped dynamics), collect (suite.list_events
      now..now+24h, uncompleted tasks due Amman-today, unread_digest +
      peek_unread -> heuristic IMPORTANT+ capped 3, NO LLM), fire_if_due
      (enabled + past BRIEF_LOCAL_TIME + last_brief_date != today, Amman
      local), fire_once (send -> persist date ONLY on success -> same-day
      retry), run_forever (30s tick, exception-surviving). gmail.py gained
      last_brief_date on GmailState + save_state + read-only peek_unread
      (never touches cursor/seen — cannot suppress dispatcher delivery).
      config: brief_enabled=true, brief_local_time="07:30" with loud HH:MM
      validator; tzdata dependency added (zoneinfo on Windows). Tests
      AC1-AC5 per spec mapping (+ send-failure persistence error mode).
      NEW OWNER RULING: every task ships ~10 granular pushed commits — 2.4
      delivered 11 (9 core + 2 docs). Gate green (108 passed, Security Gate
      OK, Docs Guard OK). Core commits 98a9617..56325bd. Docs: TEST-PLAN
      row, RUNBOOK daily-brief schedule, BACKLOG 2.1-2.4 ticked. SPRINT-2
      EXIT CHECKLIST: gate green ✓, backlog ACs mapped ✓, .env.example/
      RUNBOOK/TEST-PLAN/BACKLOG/CHANGELOG updated ✓, google_oauth_client +
      data/ gitignored ✓; live smoke pending owner credentials. HALTED —
      next per owner: Sprint 3 (vault client 3.1 first).
      **SPRINT-2 RE-OPENED + REORDERED (2026-08-30, owner ruling on the authoritative
      re-mapped spec)**: daily brief KEPT as built; order = 2.3 biometrics -> 2.3b social ->
      TokenJuice (2.4 remainder) -> 2.5 transcriber -> 2.6 journaler; **sprint-level HALT**
      (no per-task stops), ~10 granular commits per part; GitHub default branch switched
      back to `main` and core-foundation fully MERGED into main (`e7e0f2f`, unified
      code+docs single tree — both worktrees synced).
      **TASK 2.3 DONE (2026-08-30, sprint-2 §2.3 voice biometrics)**: speechbrain pinned
      (py3.12 wheel-verified 1.1.1 + torch 2.13.0 CPU); `src/skills/voice_biometric_auth.py`
      (lazy ECAPA load in executor, in-memory ffmpeg Ogg->16k mono PCM decode, cosine vs
      Fernet-sealed `{vault}/State/owner_voiceprint.enc`, fail-closed -> Guest Mode);
      `stage_guest_note` (ONE `Voice_Memos/Pending_Speakers/` note, encrypted embedding,
      collision-suffixed); `/enroll-voice` wiring in `src/bot.py`. Sacred floor gained
      `tests/test_guest_lockdown.py` (spy-proven zero privileged effects). Commits
      `01678b4`+`76f7066`+`ed21bb6`+`08470db`+`52ff96a`+`5e2c063`+`fc24e43` (missing
      implementation slice recovered — tests had landed before src) + `112eba5` (real-ffmpeg
      decode contract fix + test). Gate green (126).
      **TASK 2.3b DONE (2026-08-30, sprint-2 §2.3b social enrollment)**:
      `src/skills/social_enrollment.py` — `VoiceprintRegistry` (owner-first match_vector
      <50 ms, `enroll`/`update_stability` running centroid + `record_transcript`, Fernet
      vectors under `State/voiceprints/` + dossier `voiceprint_ref` frontmatter,
      `stage_pending`/`pending_briefs`/`resolve_pending` three-way verdicts -> Contacts/
      {Category} | Ignored (never re-matches) | Unknown+security_flag re-matchable);
      bot contact-mode routing via `verify_or_lockdown(registry=...)` -> CONTACT_MODE_AR
      message-taking only. Tests `tests/test_social_enrollment.py` AC11/AC12 + carried
      internals (encrypted-at-rest, unknown-flag, restart-survival, zero-privileged
      contact mode). Commits `112eba5`+`583e3c9`+`ff5d92e`+`a799e0e` + docs. Gate green
      (126 passed, Security Gate OK, Docs Guard OK).
      **TASK 2.4-COMPACTION DONE (2026-08-30, sprint-2 §2.4 TokenJuice remainder, ADR-19)**:
      pure `tokenjuice_compact(body_text, *, max_chars)` in `src/email_triage.py` — quoted
      reply chains (`> `), signature blocks (standard `--` delimiter), legal footers/tracking
      boilerplate (fixed case-insensitive phrase list) stripped, whitespace collapsed, capped
      with `[…]` marker inside budget. Wired to feed BOTH the heuristic body-keyword scan and
      the FAST `_refine_messages` payload. Settings `TOKENJUICE_MAX_CHARS=4000` (config +
      .env.example + conftest mirror). Tests: `tests/test_triage_compaction.py` (M7 trio
      signature_and_quotes_stripped / body_capped_at_budget /
      classification_unchanged_on_compacted_input + footer/whitespace/keyword-survival) +
      `test_email_triage.py::test_tokenjuice_strips_before_llm` + `test_vip_skips_llm_refinement`
      (AC8). Commits `67c9d7a` (red) + `b8f2c5c` (green) + docs. Gate green (134 passed,
      Security Gate OK, Docs Guard OK).
      **TASK 2.5 DONE (2026-08-30, sprint-2 §2.5 voice-to-vault transcriber, ADR-22)**:
      `src/skills/voice_to_vault_transcriber.py` — `VoiceToVault` (in-memory ffmpeg
      16 kHz mono s16le decode -> LOCAL faster-whisper 1.2.1 CPU int8, lazy model load
      naming the RUNBOOK warmup on failure; atomic `Voice_Memos/YYYY-MM-DD-HHMM.md`
      YAML notes, same-minute suffixes, `(empty)` fallback, write retried once never
      blocking) + bot wiring: enrolled owner voice -> transcribe -> file -> transcript
      enters the standard streamed text pipeline; guest voice never reaches it.
      faster-whisper installed (1.2.1 / ctranslate2 4.8, wheel-verified py3.12 win).
      Tests `tests/test_voice_to_vault_transcriber.py` (AC9 + zero-cloud AST scan + 5
      error modes) + bot-shell wiring test. Commits `5df9f80` (red) + `ed03b03`
      (module) + `8d1e385` (red wiring) + `afc8975` (wiring) + docs. Gate green (142
      passed, Security Gate OK, Docs Guard OK).
      **TASK 2.6 DONE (2026-08-31, sprint-2 §2.6 evening proactive journaler)**:
      `src/skills/evening_journaler.py` — `LedgerData` + `EveningJournaler`:
      `pick_slot` (uniform `random.uniform` inside [JOURNALER_WINDOW_START,
      JOURNALER_WINDOW_END) Amman), `collect` (per-section isolation: events /
      completed tasks / CRITICAL mail via heuristic classifier / today's Voice_Memos
      glob), PURE Arabic `render_ledger` (YAML `date`+`checkin_sent` frontmatter,
      Calendar/Mail/Voice memos/Notes sections degrading to «غير متوفر حالياً»),
      calendar-guarded `fire_once` (busy -> no message, ledger still lands; send
      failure never persists `last_checkin_sent` -> 30 s retry tick; ledger once per
      local day, state-loss re-run appends ONE corrigenda line), `run_forever`
      exception-proof tick loop. Settings `JOURNALER_ENABLED/JOURNALER_WINDOW_START/
      JOURNALER_WINDOW_END/DAILY_LOGS_DIR` (config + .env.example + conftest) with
      loud HH:MM validators; state `{vault}/State/journaler.json`.
      Tests `tests/test_evening_journaler.py` (AC10 both contracts + 6 error modes).
      Commits `c619e12` (red) + `0959333` (green) + `30381d9` (docs). Gate green (150
      passed, Security Gate OK, Docs Guard OK).
      **SPRINT 2 CLOSED (2026-08-31)**: §2.1-§2.6 all delivered; teardown executed
      (`.claude/skills/*` wiped — untracked session aids; post-teardown suite 150
      passed; sacred floor `test_owner_middleware.py` + `test_guest_lockdown.py` 7
      passed); sprint-exit Guide verification in `docs/10-CHECKPOINT.md` (full gate +
      AC coverage + docs sync); core-foundation re-merged to `main` + pushed per owner
      directive. NEXT: sprint-level HALT — owner decides Sprint 3 start (vault + PC
      bridge + whitelist).
      **SESSION PAUSED (2026-08-31 evening, owner: resumes tomorrow)**: everything
      committed & pushed; `main` = implementation branch @ `90c4132` (reference
      worktree ff-synced). Next session: run the ⚡ SESSION RESUME PROTOCOL, then open
      Sprint 3 on the owner's «التالي» — ingest sprint-3 skills (mattpocock TDD +
      git-guardrails · guard-skills test-guard · everything-claude-code
      systems-architect) into `.claude/skills/`, pass the preflight gate, then task 3.1
      (`skill-obsidian-vault-architect`) red tests. Full sprint-2 record:
      `docs/PROJECT-JOURNEY.md` §11.
      **SPRINT 3 CLOSED (2026-08-31)**: tasks 3.1-3.5 ALL delivered directly on `main`
      (binding branch directive — worktree/merge pattern retired, `core-foundation` is a
      reference checkout only): 3.1 vault client + social graph + first-boot bootstrap ·
      3.2 VaultExpander (one-commit domain growth, PARA backbone immutable) · 3.3 verbal
      action-summary protocol + shared consent grammar · 3.4 PC control plane (v1 wire
      protocol, fail-closed whitelist guard, executor/WoL/idle, owner-side coordinator
      with confirmations-before-command + audit ledger, WSS tunnel + outbound-only daemon,
      LAN :8000 surface) · 3.5 desktop telemetry (psutil LiveState, Bearer LAN route +
      tunnel cmd, Tier-1 FAST Arabic narration with real numbers, honest offline line).
      Teardown executed (`.claude/skills/*` wiped; post-teardown suite 228 passed; sacred
      floor green incl. `test_whitelist_guardrail.py`). Full gate green. Sprint record:
      `docs/10-CHECKPOINT.md` (Sprint 3). **NEXT: sprint-level HALT — owner decides
      Sprint 4 start (syllabus parser 4.1, dynamic capability expansion 4.2, polymath
      tutor 4.3, hardening + v1.0.0 release 4.4).**
- [x] Phase 4 — Harden & Release COMPLETE (2026-08-31) — **v1.0.0 TAGGED + PUSHED**
      **SPRINT 4 CLOSED (2026-08-31)** — tasks 4.1-4.4 all delivered directly on `main`
      (closed loop, red-tests-first per task): 4.1 syllabus->DAG parser (`src/syllabus.py`)
      · 4.2 dynamic capability expansion (`src/expansion.py`, M4) · 4.3 polymath tutor
      (`src/tutor.py`, M9) · 4.4a quality-gate hardening (85% branch LIVE, secret scan in
      gate, pragma-reason policy) · 4.4b HF Spaces packaging (Dockerfile + single-tree
      supervisor, $PORT health+WSS, keep-alive cron, deploy smoke w/ secret masker,
      durable-state audit) · 4.4c release (`src.__version__` single source, CHANGELOG
      drained to `## [1.0.0] — 2026-08-31` w/ Security + Deferred-to-v1.1, scope-lock
      test, `scripts/make_release.py` verifications + --tag-only, NO --force).
      Teardown executed (`.claude/skills/*` wiped; post-teardown sacred floor 16 passed).
      Full gate green: 285 passed / 1 skipped / 85.62% branch. Release sequence executed:
      dry-run green -> annotated tag `v1.0.0` on validated HEAD -> tag pushed to origin.
      **OWNER STEPS REMAIN**: publish the GitHub Release with the printed
      `gh release create v1.0.0 --verify-tag ...` command; post-tag container-from-tag
      rebuild + deploy_smoke re-run (AC8, manual); then v1.1 decisions. Sprint record:
      `docs/10-CHECKPOINT.md` (Sprint 4) + `docs/PROJECT-JOURNEY.md` §13.

      ### POST-RELEASE ARC — v1.0.1 + Oracle migration (2026-08-31, owner `التالي`)
      Owner pivoted at deploy time: HF Docker Spaces now PAID ($9/mo PRO — owner
      screenshots), Render/Koyeb free can't carry the stack → **owner ruled Oracle
      Always Free; $0.00 invariant kept**. Executed directly on `main` (closed loop):
      83a61f7 red (container must carry Node >=22 for the npm gateway — OmniRoute
      engines node >=22.22) → 9545753 green (Dockerfile: NodeSource 24 layer +
      `npm install -g /app/scripts/omniroute` + `ENV OMNIROUTE_CMD="omniroute run"`;
      gate 285/85.67%) → 5f07db9 docs (ADR-15 amendment, `docs/09-ORACLE-DEPLOY.md`
      Arabic guide, RUNBOOK §4/4b/4c/validation/troubleshooting re-anchored, HANDOFF
      + OWNER-NEXT-STEPS synced) → 7e49f85 release (version 1.0.1 + CHANGELOG
      [1.0.1]; scope-deferral test pinned to v1.0.0 — patch releases carry no
      deferral block). Release sequence: dry-run green → tag `v1.0.1` pushed →
      GitHub Release published. **OWNER NEXT (physical)**: Oracle account + VM +
      DuckDNS + `sara.env` per `docs/09-ORACLE-DEPLOY.md`; then /enroll-voice +
      Google consent (works on the VM) + PC bridge `BRIDGE_SERVER_URL=wss://<domain>/bridge`.

      ### POST-RELEASE ARC — v1.0.2 + local test phase (2026-09-01, owner directive)
      Owner directive: integrate the Start Menu app indexer + headless auto-logon
      runbook into the release (owner label said v1.0.0; v1.0.0/v1.0.1 were already
      published tags → executed as **v1.0.2**, stated to owner). Closed loop on
      `main`: `3cfdc43` red (9 tests: name extraction, .lnk-only discovery, dedupe,
      system-filter, safe merge, idempotency, Guard end-to-end, dry-run) →
      `1203cde` green (`src/app_indexer.py` — PowerShell WScript.Shell COM via
      batched `-EncodedCommand`; `C:\Windows` targets dropped; idempotent casefold
      merge preserving `restricted_actions`; audit allowlist justified) →
      `ee70660` docs+live (RUNBOOK §5b Auto-Logon + Task Scheduler; §5
      auto-populate note; LIVE whitelist merge on the owner machine: 223
      discovered / 154 added / 63 system-skipped / 156 total) → `82afb03` release
      (version 1.0.2 + CHANGELOG [1.0.2] + HANDOFF component row + README badge).
      Release sequence: gate green (294 passed / 85.73%) → dry-run green → tag
      `v1.0.2` pushed → GitHub Release published. Owner pivoted to LOCAL testing
      first (health probe green: ffmpeg/gateway/telegram all ok; OmniRoute :20128
      live; local `.env` `BRIDGE_SERVER_URL=ws://localhost:8443/bridge`).
      ### POST-RELEASE ARC — two-strong-model refactor + live-testing fixes (2026-09-01, owner directive)
      Live Telegram testing exposed: no vault memory, no rolling buffer, tool refusals +
      hallucinated «تم فتح الآلة الحاسبة», «كفيك» misheard, voice acked but never answered.
      Owner revised the architecture mid-task: TWO strong models only — (1) conversation &
      memory lane `openrouter/minimax/minimax-m2.7:free` (fb `groq/openai/gpt-oss-120b`) is
      Sara's EXCLUSIVE speaker (remembers 15 messages, reads/updates User_Info.md, spontaneous
      Jordanian); (2) tool master `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` executes
      ALL tool calls exclusively. Closed loop on `main`: `10a1924` model pins (env + defaults +
      conftest mirror, suite 294/85.78%) → `b7309e2`+`dcc7f5e` dual-tier memory `src/memory.py`
      (ConversationMemory 15-msg deque; envelope persona+vault excerpt+history+current;
      VaultMemoryWriter Daily_Logs ledger + FAST-tier fact learner → User_Info; 13 tests,
      suite 307/85.96%) → `439aa35`+`3cd26c1` dispatcher tool lane (router verdict gains
      `tool`+`arg`; ToolRegistry executes real backend; narration streams Tier.HEAVY
      exclusively; launch -> ack-only coordinator notify; registry crash / no-registry ->
      plain tier2; tier asserted via scripted model slugs; suite 312/86.10%) →
      `7755454` ToolRegistry `src/tools.py` (gmail digest/calendar 24h/tasks due-today/
      telemetry honest offline/launch origin owner_chat/brief plain-text; 18 tests,
      suite 330/86.40%) → `44a38a3`+`f22283d` bot.py wiring (envelope every turn, memory
      remember both turns, background _persist_exchange writer, on_text pending-launch
      intercept, voice_origin -> SendVoice reply, run_bot(bridge) full production wiring +
      main.py passes bridge; HELP_AR refreshed; suite 334/85.82%) → docs sync (CLAUDE §1,
      01-ARCHITECTURE mermaid, 03-DECISIONS ADR-16 amendment, 07-HANDOFF pins,
      08-OWNER-NEXT-STEPS env, 04-RUNBOOK probe line, 05-TEST-PLAN rows, CHANGELOG
      [Unreleased]).
      Owner follow-up (same day): daily conversation summary — `e812ee1` red (11
      tests: day_chat_lines extract/ignore-prose/cap-150, summarize_day append section
      with turns+context in prompt / cap enforced in the TURNS block / skips no-note,
      prose-only, already-summarized / survives brain failure / due() at 23:50 /
      multi-paragraph verbatim) → `535aa72` green (`DailySummarizer` in src/memory.py:
      reads the day's ledger, extracts **المالك:**/**سارة:** lines capped to last 150,
      one MEDIUM call with Obsidian context, appends separate `## ملخص محادثة اليوم
      YYYY-MM-DD` section, idempotent via heading; run_forever tick loop launched in
      run_bot + cancelled on shutdown; suite 345/85.64%).
      Owner utility: `sara.ps1` + `sara.bat` one-command local cycle (kill stale
      src.main/bridge.daemon -> gateway :20128 preflight -> two launch windows,
      -StopOnly/-Port; RUNBOOK 5a + CHANGELOG). LIVE: two stale src.main PIDs found
      running (29300/23220) — the owner's next cycle run clears them.
      LIVE-DEBUG 2026-09-01 evening: owner's first cycle run — stop phase worked,
      launch windows failed (inline `[Convert]::ToBase64String` in -ArgumentList bound
      as string + leaked Byte[] positional) → `19aff81` precompute `$coreEnc`/`$bridgeEnc`
      + real marker-file launch test. Owner re-ran, Sara answered on Telegram — but
      DENIED her memory on simple chat. Root cause (code-read): the ADR-18 `direct`
      route answered from the history-less router ack alone — envelope never reached
      ANY model on the most common path. `4edad0a` red → `ab40440` green: direct
      route now acks Tier 1 then streams the FAST lane via `_plain_messages` with the
      full envelope (router classifies only); rolling buffer 15 → 50 messages (owner
      directive; tests + CLAUDE/DECISIONS/TEST-PLAN/CHANGELOG synced, suite 345/85.71%).
      Vault clarified to owner: GitHub repo `3mar-baha/vantrilex-vault` via API — no
      local Obsidian install needed (token verified present in .env).
      Second live-debug wave (same evening): (a) router mini-answer acks — minimax
      wrote a wrong conversational answer INTO the ack, so the owner saw a bad reply
      then the real one in one bubble → `a4ccf1b` red → `ca1b065` green: MAX_ACK_CHARS=30
      guard discards drifted acks for the default placeholder + router prompt forbids
      answering inside the ack; (b) silent 6s voice note (22:03, "(empty)") left the
      owner with two static acks and no voice → `EMPTY_VOICE_AR` + `_voice_fail_reply`:
      empty transcript or transcription failure answers with honest text + ar-JO voice
      note, memo still filed. Suite 347/85.71%, docs synced.
      ← **current: both live fixes shipped — owner side = run `/enroll-voice` then send
      a voice note (kills the static pre-ack; no State/owner_voiceprint.enc yet), check
      the mic (22:03 note was silence), re-run `sara.bat`; dormant skills + Oracle deploy
      (docs/09) deferred until owner says**

## Open items / blockers

- **ACTIVE BLOCKER (2026-08-31, owner pausing for today)**: Oracle signup declined the
  owner's bank card ("Your credit card has been declined…"). Owner contacts the bank
  TOMORROW (2026-09-01) to enable online/international transactions, then retries signup.
  Recovery checklist already given to the owner + documented in `docs/09-ORACLE-DEPLOY.md`
  §1 (bank-side toggles, OTP check, exact name/address match, no VPN, 24h retry, alternative
  real card — $1 hold only, never charged). NOTHING on the dev side is blocked — the
  machine-side work (v1.0.1, docs, guides) is COMPLETE; only the owner-side Oracle deploy
  waits on the card.
  UPDATE (2026-09-01): owner pivoted to LOCAL testing while the card clears — v1.0.2
  shipped (app indexer + headless-boot docs, whitelist live-merged 156 apps), health
  probe green, two-terminal run instructions given (terminal 1: `$env:PORT="8443";
  make run-core` — silence after «core starting» = LIVE; terminal 2: `make run-bridge`).
- **Google 403 (upstream, from sprint 1)**: project `vantrilex-assistant-2008` blocked by
  Google ("project denied access") — owner must unblock in Google Cloud console before
  Gmail/Calendar anywhere (Gemini itself retired from the brain; OAuth client shares the project).
- **Key rotation (recommended, optional)**: real secrets were pasted in at least two chat
  sessions — GitHub PAT, Telegram API_HASH, Groq/OpenRouter keys should rotate when
  convenient (owner informed; plan in `docs/08-OWNER-NEXT-STEPS.md`).
- DONE (2026-08-26): FFmpeg 9.0.1 · OmniRoute verified live · bot token (getMe) · vault repo
  seeded · Google OAuth client delivered at `config/google_oauth_client.json` (gitignored).
- Delivered (2026-08-26): TELEGRAM_API_ID/API_HASH stored (v1.1 calling ready — session
  string itself generated at v1.1 login flow) · Google Cloud project `vantrilex-assistant-2008`
  recorded + OAuth client JSON in place. Sprint-2 first boot will run the one-time consent flow ·
  PC hardware bound: TARGET_PC_MAC_ADDRESS=08-BF-B8-28-B2-F9, TARGET_PC_IP=192.168.100.73 ·
  Owner's OPENROUTER_API_KEY routes to the OmniRoute gateway dashboard (upstream provider),
  NOT into the app .env — brain owns providers, app owns none (architecture boundary).

## Key file map

Mission record: `docs/01-ARCHITECTURE.md` · Backlog+ACs: `docs/02-BACKLOG.md` ·
ADRs: `docs/03-DECISIONS.md` · Setup/troubleshooting: `docs/04-RUNBOOK.md` ·
Oracle deploy guide (owner, Arabic): `docs/09-ORACLE-DEPLOY.md` ·
Gates: `docs/05-TEST-PLAN.md` · Handoff briefing: `docs/07-HANDOFF.md` ·
Owner steps: `docs/08-OWNER-NEXT-STEPS.md`.
