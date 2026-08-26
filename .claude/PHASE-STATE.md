# Phase State — resumable execution record

## ⚡ SESSION RESUME PROTOCOL (every fresh session executes this BEFORE acting)

1. **Prime context** — read, in order: `CLAUDE.md` → this file → `docs/01-ARCHITECTURE.md` §1
   (binding mission record) → `docs/03-DECISIONS.md` → `docs/02-BACKLOG.md`. Then `uos status`.
2. **Sync the OS framework to latest upstream** and verify its surface:
   `git -C "C:\Projects\Git-hub\Workflow\universal-agentic-os" pull --ff-only`
   `uos doctor` must be green; confirm subcommands exist (`status`, `graph`, `decide`,
   `dispatch`, `merge`, `ship`). If toolkit integrity fails, run that repo's
   `scripts/setup-toolkit.sh` then `scripts/sync-toolkit.sh`.
3. **Preflight gate (blocking)** — FFmpeg present (`ffmpeg -version`) · OmniRoute
   `http://localhost:20128/v1/models` HTTP 200 AND pools non-empty (log line
   "matched no connected models" ⇒ halt and ask the owner to connect free provider
   credentials) · git identity set · `make gate` green on py -3.12.
4. **Resume** at the phase marked ← **current** in the lifecycle below. The six discovery
   rulings recorded here are SETTLED — never re-litigate them.
5. **Discipline** — report like a leader after every phase (completed / remaining / risks /
   next action); update this file at every phase exit; end every session resumable from disk.

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
| 1 | Persona = Sara (drafts' Mona renamed) |
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
- [ ] Phase 2 — Architect & Guide: specs per backlog task, plan, toolkit assembly  ← **current**
- [ ] Phase 3 — Implement & Verify: TDD micro-cycles, worktree per concern (Sprints 1–4 of docs/02-BACKLOG.md)
- [ ] Phase 4 — Harden & Release: guards, full gate, tag v1.0.0, release report

## Open items / blockers

- User side: `winget install Gyan.FFmpeg`; start OmniRoute gateway on :20128 (blocking for Phase 3 entry).
- Credentials: fill `.env` progressively (manifest comments name sources).

## Key file map

Mission record: `docs/01-ARCHITECTURE.md` · Backlog+ACs: `docs/02-BACKLOG.md` ·
ADRs: `docs/03-DECISIONS.md` · Setup/troubleshooting: `docs/04-RUNBOOK.md` ·
Gates: `docs/05-TEST-PLAN.md` · Drafts source-of-record: `docs/*.docx` (extraction cache `.ingest/`, gitignored).
