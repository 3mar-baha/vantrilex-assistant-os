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
