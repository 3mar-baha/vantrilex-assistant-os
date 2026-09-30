---
tags: [architecture]
---

# 16 — Operational Workflows (Sovereign 4-Tier Lifecycle Playbook)

> Binding procedure for every implementation session. Companion maps:
> [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md) ·
> [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md) ·
> [Checkpoint](./10-CHECKPOINT.md) · [Testing](./11-TESTING.md).

## 0. Activation Manifest & Provisioning Matrix

Sourced by deep scan 2026-09-18 of `O:\Claude Code\vantrilex\vantrilex-registry\`
(1,486 skills / 283 agents / 903 MCPs / 13 plugins / 19 hooks;
`VANTRILEX_CATALOG.md` 2,743 lines, 18 ✅ defaults — all defaults retained).
Selection rule: load-bearing for the Windows/Telegram/Obsidian/OmniRoute
runtime only. Rejected fluff is logged with cause — no silent omission.

| Component | Type | Registry source | Target role in Sara |
|---|---|---|---|
| `tdd` | Skill | `skills/tdd.md` | Tier 2 Red→Green loop discipline |
| `tdd-workflow` | Skill | `skills/tdd-workflow.md` | Tier 2 coverage workflow (80%+ floor) |
| `tdd-guide` | Agent | `agents/tdd-guide.md` | Proactive write-tests-first enforcement |
| `pytest` (direct) | Runner | project-local `pytest-skill` (NOT in registry — local only) | Suite execution; registry has no pytest entry |
| `ponytail` | Skill | `skills/ponytail.md` | YAGNI/stdlib-first ladder, shortest diff |
| `diagnosing-bugs` / `systematic-debugging` | Skills | `skills/diagnosing-bugs.md`, `skills/systematic-debugging.md` | Incident forensics (14:54–57 storm precedent) |
| `pyright-lsp` | Plugin | `plugins/pyright-lsp.md` | Type intelligence; executable gate stays `ruff` |
| `skill-creator` + `skill-authoring-workflow` + `writing-skills` | Skills | `skills/skill-creator.md`, `skills/skill-authoring-workflow.md`, `skills/writing-skills.md` | Self-expansion authoring path |
| `skill-evolution` + `skill-optimizer` + `skills-janitor` | Skills | `skills/skill-evolution.md`, `skills/skill-optimizer.md`, `skills/skills-janitor.md` | Propose → optimize → prune lifecycle |
| `skills-library` | Skill | `skills/skills-library.md` | Owner-taught skill discovery interview |
| `tool-design` | Skill | `skills/tool-design.md` | `ToolRegistry` (`src/tools.py:90`) addition discipline |
| `mcp-builder` + `MCP Builder` agent | Skill + Agent | `skills/mcp-builder.md`, `agents/MCP Builder.md` | MCP authoring when owner supplies one |
| `auditing-mcp-servers-for-tool-poisoning` | Skill | `skills/auditing-mcp-servers-for-tool-poisoning.md` | Admission gate: every owner-supplied MCP scanned before wiring |
| `memory-systems` + `session-memory` | Skills | `skills/memory-systems.md`, `skills/session-memory.md` | Memory-OS architecture (upsert triples) |
| `obsidian-knowledge-brain` + `Knowledge Graph Engineer` agent | Skill + Agent | `skills/obsidian-knowledge-brain.md`, `agents/Knowledge Graph Engineer.md` | Vault rule evolution, Tier 4 graph sync |
| `RAG Pipeline Engineer` agent | Agent | `agents/RAG Pipeline Engineer.md` | Hybrid retrieval quality (aliases → TF-IDF → residual embeddings) |
| `context-fundamentals` + `context-optimization` | Skills | `skills/context-fundamentals.md`, `skills/context-optimization.md` | 60/40 memory budget + compaction discipline |
| `reflexion` | Skill | `skills/reflexion.md` | Nightly-worker reflection ONLY — banned from hot path (4 s guillotine) |
| `verification-before-completion` | Skill | `skills/verification-before-completion.md` | Pre-commit proof gate |
| `eval-harness` | Skill | `skills/eval-harness.md` | Nightly prompt-regression evals (23:40 window) |
| `clean-code-guard` + `test-guard` + `upstream-docs-guard` | Skills | `skills/clean-code-guard.md`, `skills/test-guard.md`, `skills/docs-guard.md` | Tier 3 guard passes (note: registry file is `docs-guard.md`) |
| `securing-agentic-ai-tool-invocation` + `Application Security Engineer` agent | Skill + Agent | `skills/securing-agentic-ai-tool-invocation.md`, `agents/Application Security Engineer.md` | Tool-boundary threat model (AML.T0053) |
| `git-guardrails` (registry file `git-guardrails-claude-code.md`) + `commit-commands` + `code-review` | Skill + Plugins | `skills/git-guardrails-claude-code.md`, `plugins/commit-commands.md`, `plugins/code-review.md` | Tier 4 safe ship |
| `poka-yoke` + `varlock-claude-skill` | Skills | `skills/poka-yoke.md`, `skills/varlock-claude-skill.md` | Mistake-proofing + secrets hygiene (`.env`/`vault/` never staged) |
| `architect` + `planner` + `Workflow Architect` agent | Agents | `agents/architect.md`, `agents/planner.md`, `agents/Workflow Architect.md` | Tier 1 discovery |
| `multi-agent-patterns` + `Multi-Agent Systems Architect` agent | Skill + Agent | `skills/multi-agent-patterns.md`, `agents/Multi-Agent Systems Architect.md` | **P3-DEFERRED**: fleet design only, no production fan-out (TTFT/429 math) |
| `dispatching-parallel-agents` + `subagent-driven-development` | Skills | (registry) | Harness coordination only — never production orchestration |
| MCPs `filesystem`, `memory`, `openrouter`, `sequential-thinking`, `obsidian-tc` (The-40-Thieves), `calllint`, `sqlite` (dormant) | MCP | `mcp/*.md` | Scoped IO, reasoning, vault path, lint surface |
| Hooks `session-start`, `pre-compact`, `save-state-before-context-compaction`, `session-end`, `block-creation-of-random-md-files-…`, `block-dev-servers-outside-tmux-…`, `reminder-before-git-push-…`, `evaluate-session-for-extractable-patterns`, `suggest-compact` | Hooks | `hooks/*.md` + project-local `dangerous-command-guard.json` | Session integrity, doc-home hygiene, skill-evolution feed |

REJECTED with cause: `rag-blueprint` (NVIDIA GPU-deploy doctrine vs API-first
$0.00 — pattern carried by RAG Pipeline Engineer instead); cloud-vision MCPs
(full-screen exfil vs bbox-ROI doctrine); `fetch`/`time` (dead upstream, per
prior audit); local-weight / vector-DB MCPs (disposable-filesystem violation).

Standing rules: `.claude/skills/` is gitignored (sprint rotation + teardown);
`opencode.json` / `.mcp.json` / `vault/` / `.env` are never committed;
`src/persona.py` is reformat-locked (4,782-byte invariant).

### 0.1 The Mandatory Skill Lock (The Iron Rule)

BINDING: no file is written, edited, or tested unless that phase's designated
skill is physically loaded via the skill-loader with the invocation visible in
the transcript. Doctrine-by-memory is procedurally incomplete. Zero bare-metal
execution — a phase worked without a visible skill invocation is void and
re-run. Minimums: Tier 1 `architect`+`sequential-thinking`; Tier 2
`tdd`+`tdd-workflow`; Tier 3 `clean-code-guard`+`test-guard`+
`securing-agentic-ai-tool-invocation`; Tier 4 `upstream-docs-guard`.

## 1. Tier 1 — /plan (Architectural Discovery & Consensus)

Active stack: `architect` + `sequential-thinking` + `Workflow Architect`.
Protocol: read `docs/10-CHECKPOINT.md` + relevant `docs/01–15`; formulate
phased plan (files, acceptance criteria, gates); HALT for owner sign-off
(`"التالي"`/`"next"`). Default-to-/plan: any task without an explicit tier
lands here, read-only.

## 2. Tier 2 — /code (TDD & Autonomous Engineering)

Active stack: `tdd` + `tdd-workflow` + `ponytail` + direct `pytest` +
`pyright-lsp`→`ruff`. Red → Green → Refactor; smallest abstraction.
Suite command and floor:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --no-cov
# floor ratified 2026-09-18: 1,819 passed; tiered gate 22 core ≥98%, total ≥90%
```

Codified execution paths (all ratified consensus, all tested):

- **In-turn scratchpad healing & tool-lane isolation.** Tool exceptions die
  at `dispatcher.py:951` (`_tool_lane` try/except → plain-tier2 narration;
  tested `test_registry_failure_degrades_to_plain_tier2`). Deterministic
  parameter repair bounded at 2 attempts, zero LLM calls, FAST ack untouched.
- **`memory_upsert` conflict resolution.** Memories normalize to
  (entity, slot, value) via `_normalize`; collisions mark the old row
  `superseded:` (auditable, hidden from RAG). Storage stays append-only.
- **Dynamic MCP self-installation & Ephemeral Composition Cache.** Owner
  MCP → `auditing-mcp-servers-for-tool-poisoning` scan →
  `mcp-builder`/`MCP Builder` wiring → handshake validation →
  `ToolRegistry` promotion. Read-only chains cache ephemerally (session
  scope); PC-effecting skills distill at 23:40 (`ast.parse` allowlist:
  stdlib + `src.*`), OverlayVault-tested, owner-promoted.
- **Gmail quota diet + pool sanitization.** `PEEK_DEFAULT_MAX=10`
  (`src/gmail.py`), `FETCH_BURST_CAP=25` with cursor hold-back (overflow
  redelivers, never lost). MEDIUM/HEAVY primaries are `openrouter/nex-agi/*`
  slugs: the BARE `nex-agi/...` form has no route and 404s `No active
  credentials`, so a 404 on this lane usually means a slug lost its provider
  prefix, not that the pool or the credential died — check the prefix before
  blaming the code.

## 3. Tier 3 — /audit (Security, Invariants & Real-World Validation)

Active stack: `clean-code-guard` + `test-guard` +
`securing-agentic-ai-tool-invocation`. Gates:

| Invariant | Check |
|---|---|
| ar-JO immersion | `SARA_PERSONA_AR` names سارة, Jordanian register |
| Masculine address | masculine verb forms, never feminine-only |
| Zero Edge-TTS | Fish-only voice; no Edge fallback when Fish configured |
| Zero unconfirmed cmd | `launch` without `confirmation_id` → `error`; breaker denies |
| $0.00 cost | free-tier chains only; `PaidModelBlockedError` armed |

```powershell
.venv/Scripts/python.exe scripts/security_gate.py
.venv/Scripts/python.exe scripts/live_interactive_benchmark.py
# target: 6/6 scenarios + 5/5 invariants, DEGRADED or LIVE
```

10-prompt Telegram validation vs `@Sara_Vantrilex_bot` observed through
`.\sara.bat -Trace` (shadow console: `vault/State/SARA_SHADOW_COGNITION_LOG.jsonl`).
Live-pool failures (429/404/quarantine) are carried explicitly per checkpoint,
never fixed by weakening tests.

## 4. Tier 4 — /sync (Knowledge Graph MOC, Checkpoint & Release)

Active stack: `upstream-docs-guard` + `commit-commands` +
`obsidian-knowledge-brain` (+ `Knowledge Graph Engineer` for graph moves).
Protocol: `[[…]]` only inside `vault/`; portable relative links in `docs/`;
every touched behavior updates `docs/10-CHECKPOINT.md` in the same commit;
commit directly to `main`, push immediately (branch directive 2026-08-31);
never stage `.env`, `vault/`, `opencode.json`, dumps, harness UI state.
`scripts/docs_guard.py` 16/16 before every commit. Post ≤5-line proof report →
HALT until `"التالي"`/`"next"`.

## See also (graph links)

- [04 — System Architecture](./04-ARCHITECTURE.md)
- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [11 — Testing](./11-TESTING.md)
- [Master Roadmap & Remaining Work](./MASTER_ROADMAP_AND_REMAINING_WORK.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
