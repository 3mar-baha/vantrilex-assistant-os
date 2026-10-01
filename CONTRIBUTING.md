# Contributing to Vantrilex Assistant OS

## Operating model

Work runs on a tripartite hierarchy: **Leader** (decomposition, sequencing) ->
**Guide** (specification, quality gates, phase sign-off) -> **Implementer**
(TDD cycles). Contributions enter through the same discipline.

## The engineering line

1. **Specification before code** — open with acceptance criteria, get them agreed, then implement.
2. **Tests are the contract** — red -> green -> refactor. No production code without a failing test first.
3. **One item, one commit** — commits land directly on `main` and are pushed
   immediately (`CLAUDE.md` §5, owner directive 2026-08-31, binding). The
   per-stream worktree/branch merge pattern is retired; `core-foundation` is a
   reference checkout only.
4. **Docs ship with behavior** — documentation changes land in the same commit as the code it describes.
5. **Minimalism** — smallest abstraction that satisfies the specification. No speculative features or configuration.
6. **Zero-cost rule** — every dependency added must be free/open-source and run on free tiers.

## Commit conventions

Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:` …). The CHANGELOG
is updated in the same commit for anything user-visible.

## Quality gate (every PR)

```bash
make lint    # ruff check + ruff format --check
make test    # pytest (>=85% branch coverage enforced via addopts)
make gate    # lint + test + security (bandit + secret scan) + docs guard + tiered coverage
```

No **unexplained** failure before merge. A committed RED barrier is legitimate and
must not be "fixed" — that pins the barrier's own bug as correct behaviour. Findings
are fixed or waived explicitly in `docs/09-DECISIONS.md`.

## Environment

See `docs/14-RUNBOOK.md` for reproducible setup (Python 3.12, FFmpeg, OmniRoute, preflight checks)
and `.env.example` for the credential manifest.
