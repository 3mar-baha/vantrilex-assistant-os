---
tags: [architecture]
---

# 16 — Operational Workflows (4-tier lifecycle playbook)

> Binding procedure for every implementation session. Companion maps:
> [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md) ·
> [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md) ·
> [Checkpoint](./10-CHECKPOINT.md) · [Testing](./11-TESTING.md).

## 0. Activation manifest (sanitized 2026-09-17 — verified against disk)

> Audit 2026-09-17 found ZERO of the alleged bloat skills
> (`nextjs-turbopack`, `bun-runtime`, `video-editing`, `x-api`, `crosspost`,
> `article-writing`, `investor-*`, `market-research`, `frontend-*`,
> `api-design`, `e2e-testing`, `fal-ai-media`, `dmux-workflows`, `agent-sort`)
> on disk — that premise was false; no such purge was needed. Nine unlisted
> residual dirs were quarantined to `C:\Users\omarb\.vantrilex\
> quarantine-20260917\` (restorable): `code-review`, `dev-agent-skills`,
> `mattpocock-typescript`, `security-review`, `starter`, `verification-loop`,
> `wayfinder`, `writing-for-agents`, `writing-plans`.

Baseline — verified present locally:

| # | Component | On-disk path | Status |
|---|---|---|---|
| 1–5 | Skills `ask-matt`, `find-skills`, `ponytail` (+`ponytail-core`), `skill-creator` | `.claude/skills/<name>/` | **Active** (full bodies) |
| 6–9 | MCPs `filesystem`, `memory`, `openrouter`, `sequential-thinking` | `opencode.json` → `mcp` | **Active** (untracked; live key — never commit; sequential-thinking launch-proven via stdio handshake) |
| 10 | MCP `fetch` | — (removed 2026-09-17) | **Dead** (`@modelcontextprotocol/server-fetch` 404s on npm; no trustworthy successor) |
| 11 | MCP `time` | — (removed 2026-09-17) | **Dead** (no resolvable package found) |
| 12–15 | Plugins `code-review`, `commit-commands`, `typescript-lsp`, `pyright-lsp` | `.claude/plugins/manifest.json` | **Active** (`claude-plugins-official/*`, committed) |
| 16–18 | Hooks `session-start`, `pre-compact`, `block-dev-servers-outside-tmux-…` (+ 9 more local templates) | `.claude/hooks/` + `settings.json` | **Active** |
| 19 | Agent `architect` (+ backend/planner/lead present) | `.claude/agents/architect.md` | **Active** |

Elite additions — sourced per-component (untracked, rotation rule):

| Component | Source → on-disk path | Status |
|---|---|---|
| `clean-code-guard`, `test-guard`, `upstream-docs-guard`, `diagnosing-bugs` | toolkit cache `guard-skills` + local → `.claude/skills/` | **Active** (full bodies) |
| `securing-agentic-ai-tool-invocation` | toolkit cache `cybersecurity` → `.claude/skills/` | **Active** (full body) |
| `git-guardrails` | toolkit cache `mattpocock-skills` → `.claude/skills/` | **Active** (source dir `git-guardrails-claude-code`) |
| `tdd`, `tdd-workflow`, `pytest-skill`, `poka-yoke` | cache + registry cards → `.claude/skills/` | **Active** (`tdd` full body; others indexed with Raw URLs) |
| `obsidian-knowledge-brain`, `varlock-claude-skill` | registry cards → `.claude/skills/<name>/SKILL.md` | **Active (indexed)** |
| `block-creation-of-random-md-files-…`, `session-end` | upstream hooks + cached `memory-persistence` → `.claude/hooks/` | **Active** (adapted: doc-homes stay writable for `/sync`) |
| `Knowledge Graph Engineer`, `Workflow Architect`, `Application Security Engineer` | toolkit cache `agency-agents` → `.claude/agents/` | **Active** (full bodies) |
| MCPs `obsidian-tc` (vault path), `calllint` | registry cards → `opencode.json` → `mcp` | **Active** (packages resolve: 1.30.1 / 0.2.0) |
| MCP `sqlite` | fixed package → `opencode.json` → `mcp` | **Active (dormant)** — `mcp-server-sqlite`, `enabled: false` |
| MCP `06ketan-slideshot` | `opencode.json` → `mcp` | **Active** (resolves 4.4.0; out of Sara scope, retained) |

### Mandatory Invocation Rule (binding from P2 on)

The Implementer MUST physically invoke required skills via the skill-loader
tool with the invocation visible in the turn transcript — doctrine-by-memory
no longer suffices. Minimums: P-phase entry invokes the phase's skill
(`tdd`/`tdd-workflow` for `/code`, `clean-code-guard` + `test-guard` for
`/audit` gates, phase-appropriate guards for `/sync`). A phase worked without
a visible skill invocation is procedurally incomplete.

Standing rules: `.claude/skills/` is gitignored (sprint rotation + teardown);
`opencode.json` / `.mcp.json` / `vault/` / `.env` are never committed;
`src/persona.py` is reformat-locked (4,782-byte invariant).

## Tier 1 — `/plan` (Architectural Discovery)

Tooling: `architect` + `sequential-thinking` + `ask-matt`.
Protocol:

1. Read `docs/10-CHECKPOINT.md` + the relevant `docs/01–15` notes.
2. Formulate a phased plan (files, acceptance criteria, verification gates).
3. **HALT — await owner sign-off** (`"التالي"`/`"next"`) before any code.

## Tier 2 — `/code` (TDD Implementation)

Tooling: `ponytail` + `tdd-workflow` + `pytest-skill`→`pytest` + `pyright-lsp`→`ruff`.
Protocol: Red → Green → Refactor; smallest abstraction that satisfies the spec;
no speculative layers. Verify:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --no-cov
# target: 1,457+ passed, 0 failed
```

## Tier 3 — `/audit` (Security & Invariant Gate)

Tooling: `clean-code-guard` + `test-guard` + `securing-agentic-ai-tool-invocation`.
Protocol — all five invariants plus the gates:

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

## Tier 4 — `/sync` (Obsidian Graph & Checkpoint Sync)

Tooling: vault MOC + `docs-guard` + `commit-commands` (+ pending `session-end`).
Protocol:

1. Wikilinks/tags: `[[…]]` only inside `vault/`; portable relative links in `docs/`.
2. Every touched behavior updates `docs/10-CHECKPOINT.md` in the same commit.
3. Commit directly to `main`, push immediately (branch directive 2026-08-31).
4. Never stage: `.env`, `vault/`, `opencode.json`, dumps, harness UI state.

## See also (graph links)

- [04 — System Architecture](./04-ARCHITECTURE.md)
- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [11 — Testing](./11-TESTING.md)
- [Master Roadmap & Remaining Work](./MASTER_ROADMAP_AND_REMAINING_WORK.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
