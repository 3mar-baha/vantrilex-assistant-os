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

Updated at every phase exit and every significant turn end.

## Mission (confirmed 2026-08-26)

Vantrilex Assistant OS v1.1.0 — **Sara (سارة)**. Owner-only, strictly $0.00/month,
free-tier VPS-primary core + OmniRoute brain (`http://localhost:20128/v1`), Telegram
chat/Ogg Opus voice notes in Jordanian Arabic (`ar-JO-SanaNeural`), Google suite +
tiered email triage, git-backed Obsidian PARA vault, whitelisted PC control over an
outbound-only Windows bridge daemon. Live calls -> v1.1; scouts -> v1.1; SIP -> v1.5;
social agent -> v2.0.

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
- [ ] Phase 3 — Implement & Verify  ← **current** — GOVERNED BY the ⚙️ CLOSED-LOOP EXECUTION
      PROTOCOL below (binding, owner-approved). Entry gate: OmniRoute VERIFIED · bot token
      getMe-verified · ffmpeg installed. Worktree `core-foundation` EXISTS (created once,
      keep using it). DONE: task 1.1 skeleton — commit `221c650` MERGED to main (owner-directed
      2026-08-28); gate green (13 tests, AC1-AC6), live `--health` proof ok vs OmniRoute.
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
- [ ] Phase 4 — Harden & Release: guards, full gate, tag v1.0.0, release report

## Open items / blockers

- DONE (2026-08-26): FFmpeg 9.0.1 · OmniRoute verified live · bot token (getMe) · vault repo
  seeded · Google OAuth client delivered at `config/google_oauth_client.json` (gitignored).
- Remaining owner-side: free-tier VPS provisioning (before Sprint 4); workflow-repo upgrade
  handover (owner finalizing).
- Delivered (2026-08-26): TELEGRAM_API_ID/API_HASH stored (v1.1 calling ready — session
  string itself generated at v1.1 login flow) · Google Cloud project `vantrilex-assistant-2008`
  recorded + OAuth client JSON in place. Sprint-2 first boot will run the one-time consent flow ·
  PC hardware bound: TARGET_PC_MAC_ADDRESS=08-BF-B8-28-B2-F9, TARGET_PC_IP=192.168.100.73 ·
  Owner's OPENROUTER_API_KEY routes to the OmniRoute gateway dashboard (upstream provider),
  NOT into the app .env — brain owns providers, app owns none (architecture boundary).

## Key file map

Mission record: `docs/01-ARCHITECTURE.md` · Backlog+ACs: `docs/02-BACKLOG.md` ·
ADRs: `docs/03-DECISIONS.md` · Setup/troubleshooting: `docs/04-RUNBOOK.md` ·
Gates: `docs/05-TEST-PLAN.md` · Drafts source-of-record: `docs/*.docx` (extraction cache `.ingest/`, gitignored).
