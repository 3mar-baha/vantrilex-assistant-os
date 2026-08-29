# Project Journey — Complete Record (Vantrilex Assistant OS)

Full documentation of everything accomplished, decided, discovered, and deferred —
written at the close of the founding session (2026-08-26). For the authoritative mission
statement see `docs/01-ARCHITECTURE.md` §1; for decisions see `docs/03-DECISIONS.md`;
for live lifecycle state see `.claude/PHASE-STATE.md`.

---

## 1. What This Project Is

**Vantrilex Assistant OS v1.1.0 "Sara (سارة)"** — an owner-only, strictly $0.00/month
executive AI assistant living 24/7 on a free-tier host (founding ruling: VPS — superseded
2026-08-29 by HF Spaces, ADR-15; §10 addendum): Telegram chat + Ogg Opus voice notes
in warm Jordanian Arabic (`ar-JO-SanaNeural`), reasoning through OmniRoute free provider pools,
Google Workspace integration with tiered email triage, a git-backed PARA+Zettelkasten Obsidian
vault, and whitelisted PC control over an outbound-only Windows bridge daemon.
Live PyTgCalls calling → v1.1 · SIP telephony → v1.5 · social-media agent → v2.0.

## 2. Session Timeline (all on 2026-08-26)

| Step | Outcome |
|---|---|
| Preflight | 13-point environment audit: 11 PASS, 2 blocking FAILs (FFmpeg missing, OmniRoute down) — risk accepted by owner, both fixed same-day |
| Socratic Discovery | 6 questions, 6 binding rulings (below); mission confirmed verbatim |
| Scaffold | 22 legacy `.docx` drafts ingested; 16 canonical files authored; native hooks + resumable state; initial commit `ff2542b` |
| Guide Audit #1 | Independent adversarial review of scaffold: 3 BLOCKERs + 5 MINORs found and fixed before commit (credential-filename gap, bare-pytest CI failure, branch naming, honest self-WoL limitation, sleep-needs-confirmation) |
| Preflight re-check | Owner installed FFmpeg 9.0.1; started OmniRoute; brain VERIFIED with real streamed completion (`gemini-3.1-flash-lite`, free pool) |
| Phase 2 Orchestration | 8-agent workflow (4 spec drafters → 4 adversarial Guide verifiers, ~490k tokens, 122 tool calls) produced four sprint specifications |
| Guide Audit #2 | All four verdicts FIX; 1 BLOCKER + 12 MAJOR + ~20 MINOR findings — every one integrated into the specs with disposition appendices |
| Credentials | Bot token stored + verified via `getMe`; vault repo created & PARA-seeded; `.env` manifest filled (15 values) |
| Resilience | Safety-classifier outage mid-session: all remaining deliverables completed through file-tools + web-fetch workarounds; nothing blocked permanently |

## 2b. Session Timeline (2026-08-28 → 2026-08-29)

| Step | Outcome |
|---|---|
| Sprint 1.1 (08-28) | Async skeleton merged to `main` (`221c650`) — owner-directed; gate green, live `--health` proof |
| Closed-loop protocol | Owner-approved binding execution loop (per-task: red→green→`make gate`→commit→report→HALT until "التالي"); sacred floor + circuit breaker pinned |
| Model pin (08-28/29) | Two-layer ruling: harness GLM-only (`z-ai/glm-5.3-flash`); Sara's brain via OmniRoute |
| Sprint 1.2 (08-29) | OmniRoute client (`3e44f1c`): SSE streaming + fallback; live-wired against the real gateway; mid-stream SSE error events classified (silent-empty defect found & fixed); Gemini pools blocked upstream (Google 403 — owner-side fix pending) |
| Sprint 1.3 (08-29) | Voice pipeline (`4d0aefa` + `0e796fd`): in-memory Edge-TTS → Ogg Opus, first encoded chunk ~30 ms (probesize amendment documented); AC1-AC8 green |
| First directive (08-29) | MASTER-DIRECTIVE overhaul (`71a17ca` + `fef6246`): ADR-15 (HF Spaces host) + ADR-16 (brain routing); backlog re-map; M1-M9 spec; docs/config sync |
| Second directive (08-29) | MASTER ARCHITECTURAL DIRECTIVE: 3-tier brain + dispatcher (ADR-16 amended, ADR-17..21 appended), 6 upstream toolkits, per-sprint skill rotation + teardown, sprint specs 1-4 rewritten, full doc/config overhaul |
| Atomic commits (08-29) | Owner-ordered split: voice feature, gateway fix, runbook docs, checkpoint — pushed; working tree clean for shutdown |

## 3. Binding Discovery Rulings

| Q | Ruling |
|---|---|
| 1 | Persona = **Sara (سارة)** — retired draft persona name replaced everywhere canonical |
| 2 | **VPS-primary** topology + outbound-only PC bridge (supersedes draft Cloud Run) |
| 3 | **Owner-only** hard allowlist; silent drop of all other accounts |
| 4 | v1.0 = exec core minus live calls (chat, voice notes, Google suite, triage, vault, PC control) |
| 5 | **$0.00 absolute**; whitelist miss → Telegram confirmation prompt (v1.0) |
| 6 | Credential manifest `.env.example`; progressive per-phase gating |

## 4. Infrastructure Provisioned During the Session

- FFmpeg 9.0.1 full build (winget) — voice-pipeline dependency
- OmniRoute gateway running on :20128 with free pools proven end-to-end
- Telegram bot **@Sara_Vantrilex_bot** created; token `getMe`-verified; owner ID bound
- GitHub vault **3mar-baha/vantrilex-vault** (private) seeded with PARA skeleton +
  `User_Info.md` / `Dialect_Notes.md`
- Local `.env` filled from manifest (secrets gitignored); quality gate green
  (ruff · format · pytest · security · docs-guard 16/16)

## 5. Security Findings Caught Before Any Code Existed

Worth their own section — this is what the adversarial process bought us:

1. 🔴 **`open_path` whitelist bypass** (Sprint-3 draft): file-opening path launched arbitrary
   executables without confirmation — rewritten guard-first with executable-as-app-launch rule.
2. 🟠 **Bot-token log leak**: deploy-smoke failure details would have printed the token inside
   httpx exception URLs — masked redaction layer specified + dedicated test.
3. 🟠 **Crash-window email loss**: seen-state persisted before dispatch could permanently skip
   critical mail — inverted to dispatch-then-mark with re-delivery test.
4. 🟠 **Self-Wake-on-LAN impossibility**: daemon cannot wake its own suspended host — canonically
   ruled and documented (ADR-05, ARCHITECTURE §2, RUNBOOK) instead of silently broken.
5. Confirmation-flow hardening: 10-min TTL, consent binding to explicit prompts, deterministic
   arbitration between pending summaries and confirmations, fail-closed corrupt-whitelist mode.

## 6. Deliverable Map

```
docs/specs/sprint-{1..4}.md   Phase-2 implementation contracts (AC→pytest mapped)
docs/00–05                    Vision, architecture, backlog, ADRs, runbook, test plan
CLAUDE.md                     Agent directives + mandatory session-resume protocol
.claude/PHASE-STATE.md        Resumable lifecycle state (fresh sessions prime from here)
.claude/hooks/                Native stage-gate hooks
Makefile / ci.yml             make gate ≡ CI (ruff, pytest, bandit, docs-guard)
docs/03-DECISIONS.md          ADR-01…13
docs/*.docx                   Original planning drafts (preserved source-of-record)
```

## 7. Commits (this repo)

| Hash | Content |
|---|---|
| `ff2542b` | Canonical scaffold suite (Phase 1) — 47 files |
| `c9f6c62` | Session-resume protocol baked into CLAUDE.md + checkpoint |
| `6fa22f7` | Phase-2 sprint specifications with integrated Guide fixes — 7 files / 1439 insertions |
| *(this commit)* | Project-journey documentation + workflow-repo protection ruling |

## 8. Open Items (owner side, none blocking Phase 3 start)

1. Google Cloud project + OAuth client JSON — needed before Sprint 2 (~20 min, walkthrough in `.env.example`)
2. Free-tier VPS provisioning — needed before Sprint 4 (~30 min; Oracle Always Free / GCP e2-micro)
3. Universal-agentic-os workflow upgrade — owner finalizing locally; will hand over the finished
   repo explicitly; until then that repo is untouched-by-design (protocol step 2)
4. Bridge TLS style (self-signed + SPKI pin vs Let's Encrypt) — decided at Sprint-3 implementation

## 9. Next Steps

Phase 3 — Implement & Verify opens with stream `core-foundation`: Sprint-1 task 1.1
(config/logging/health skeleton) in its own git worktree, strict TDD per
`docs/specs/sprint-1.md`. Every session resumes via the ⚡ SESSION RESUME PROTOCOL at the top
of `.claude/PHASE-STATE.md`.

## 10. Addendum — 2026-08-29: Two Master Directives + Phase 3 under way

**Phase 3 progress (closed-loop, one task per gate):** task 1.1 skeleton merged to main
(`221c650`); task 1.2 OmniRoute client + live-wiring with SSE-error hardening (`3e44f1c`);
task 1.3 Edge-TTS → Ogg Opus in-memory pipeline (`4d0aefa`) — AC1-AC8 green, with the
measured `-probesize 32` amendment that keeps the first encoded chunk truly streaming
(default probesize gates all ffmpeg output until EOF). Merge to main awaits owner review.

**Master directive #1 (2026-08-29, morning):** ADR-15 (HF Spaces runtime host — supersedes
the founding VPS ruling) + ADR-16 (brain via OmniRoute); backlog re-mapped to the new sprint
DAG; M1-M9 capability spec (`docs/specs/master-directive-2026-08-29.md`); canonical docs +
configs synchronized.

**Master directive #2 (2026-08-29):** the brain upgraded to a **3-tier multi-model routing**
system (ADR-16 amended in place: Tier 1 fast reflex TTFT<250 ms · Tier 2 tool executor ·
Tier 3 heavy DAG/tutoring) behind the **Fast Front-Door Dispatcher** (ADR-18) — new Sprint-1
task 1.5. New ADRs: 17 (voice biometrics + Guest Mode lockdown), 19 (TokenJuice compaction),
20 (in-memory Opus pipeline), 21 (5-directory vault contract). **Per-sprint skill rotation**
into `.claude/skills/` with a binding sprint-exit **teardown protocol**, ledgered in
`docs/10-CHECKPOINT.md` (new). Sprint specs 2-4 exhaustively re-mapped (AC1-AC10 each);
`config/whitelist.json` seeded; `.env.example` carries the FAST/MEDIUM/HEAVY tier pins.
Numbering note: the directive's draft ADR-04..07 collide with settled ledger entries and are
recorded as ADR-19/20/21 (see ledger note).
