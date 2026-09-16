---
tags: [architecture]
---

# 16 — Operational Workflows (4-tier lifecycle playbook)

> Binding procedure for every implementation session. Companion maps:
> [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md) ·
> [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md) ·
> [Checkpoint](./10-CHECKPOINT.md) · [Testing](./11-TESTING.md).

## 0. Activation manifest (verified 2026-09-16; no `VANTRILEX_CATALOG.md` exists in-repo)

Baseline (17) — all present locally:

| # | Component | Location | Status |
|---|---|---|---|
| 1–5 | Skills `ask-matt`, `code-review`, `find-skills`, `ponytail`, `skill-creator` | `.claude/skills/` | **Active** |
| 6–10 | MCPs `filesystem`, `fetch`, `memory`, `openrouter`, `sequential-thinking` | `opencode.json` | **Active** (untracked; carries a live key — never commit) |
| 11 | Plugin `commit-commands` | `.claude/plugins/manifest.json` | **Active** |
| 12–13 | Plugins `code-review`, `typescript-lsp` (+ `pyright-lsp`) | — | **Missing** (manifest holds `circuit-breaker-guard`, `context-primer` instead) |
| 14–16 | Hooks `session-start`, `pre-compact`, `block-dev-servers-outside-tmux-…` | `.claude/hooks/` + `settings.json` | **Active** |
| 17 | Agent `architect` | `.claude/agents/architect.md` | **Active** |

Elite additions — ingested from the local toolkit cache (untracked, rotation rule):

| Component | Source | Status |
|---|---|---|
| `clean-code-guard`, `test-guard`, `upstream-docs-guard` | `guard-skills` cache | **Active** (`docs-guard` renamed: repo already owns `scripts/docs_guard.py`) |
| `securing-agentic-ai-tool-invocation` | `cybersecurity` cache | **Active** |
| `git-guardrails` | `mattpocock-skills` cache | **Active** (source dir `git-guardrails-claude-code`) |
| `tdd` | local `tdd-workflow` skill | **Covered** (name differs, contract identical) |
| `varlock-claude-skill`, `obsidian-knowledge-brain`, `obsidian-tc`, `Knowledge Graph Engineer`, `pytest-skill`, `pyright-lsp`, `block-creation-of-random-md-files`, `session-end` | — | **Pending** (no catalog, no cache, no URLs — owner supplies source) |

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
- [Repository Audit & Cleanup Proposal](./reports/REPOSITORY_AUDIT_AND_CLEANUP_PROPOSAL.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
