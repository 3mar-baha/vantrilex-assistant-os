# Spec — Harden & Release (stream: release-hardening)

Phase 2 implementation specification, Sprint 4 of `docs/02-BACKLOG.md`. Stream worktree:
`release-hardening`. Repo state at spec time: documentation scaffold only — `src/` arrives with
Sprint 1–3 streams; every task below opens from a tree where Sprints 1–3 are merged to `main`.

## Dependency-order task list

1. **4.1 Full quality gate green (>=85% branch coverage activation)** — depends on Sprints 1–3 merged.
2. **4.2 Packaging** — depends on 4.1; contracts from 1.1 (Settings), 2.1 (token-cache path), 3.4 (TLS/WSS endpoint).
3. **4.3 Release v1.0.0** — depends on 4.2 (tag marks a deploy-validated commit).

No parallelism inside this stream — it is the DAG tail by definition.

---

### 4.1 Full quality gate green incl. >=85% branch coverage activation

**Intent** — Turn the scaffold gate into the enforcing gate of `docs/05-TEST-PLAN.md`: branch
coverage switches on at >=85% over measured trees, four guards run identically locally and in CI,
and the pragma escape hatch is budgeted so "green" means something at release time.

**Interface**

- `pyproject.toml` (tools-only; extend if 1.1 created it):
  ```toml
  [tool.ruff]
  line-length = 100
  target-version = "py312"

  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  testpaths = ["tests"]
  addopts = "--cov=src --cov=bridge --cov=common --cov-branch --cov-report=term-missing --cov-fail-under=85"

  [tool.coverage.run]
  branch = true
  source = ["src", "bridge", "common"]

  [tool.coverage.report]
  fail_under = 85
  show_missing = true
  exclude_lines = ["pragma: no cover", "if __name__ == .__main__.:"]
  ```
  Threshold lives once in addopts so make/bare-pytest/CI all inherit. Coverage scope covers the
  safety-critical guard/executor code per Sprint-3 review.
- `.github/workflows/ci.yml`: bandit step body becomes `python scripts/security_gate.py` (one gate implementation everywhere).

Pragma policy (documented in TEST-PLAN): every exclusion written `# pragma: no cover -- <reason>`;
allowed reasons exhaustively: `__main__` guards, OS-gated branches (`sys.platform` blocks
unreachable on Linux CI, e.g. WoL raw-socket send). **ffmpeg-binary-presence fallbacks REMOVED
from the allowlist (Guide amendment) — binary-absence branches are trivially mock-testable.**

**Acceptance criteria**

1. AC1 — coverage config parsed & asserted (`fail_under=85`, branch=true, three sources). → `tests/test_quality_gate.py::test_coverage_threshold_configured`
2. AC2 — every runner inherits threshold via addopts. → `test_coverage_enforced_for_every_runner`
3. AC3 — every pragma carries `-- <reason>`; bare pragma fails; sibling scan extends to `# nosec` lines. → `test_pragmas_are_justified`
4. AC4 — Makefile gate order lint->test->security->docs-guard asserted. → `test_makefile_gate_order`
5. AC5 — CI invokes ruff, pytest, security_gate.py, docs_guard.py. → `test_ci_runs_all_four_guards`
6. AC6 — **gate fails closed, pinned mechanism (Guide amendment)**: spawn `sys.executable -m pytest` in tmp_path containing mini src/ package + pyproject with fail_under=100; assert returncode 1 + "Coverage failure" message. → `test_threshold_fails_closed`
7. AC7 — full `make gate` exits 0 on merged tree at >=85% real branch coverage (evidence pasted into PR — manual).

**Error modes** — below-threshold -> exit 1 with term-missing report; never auto-lowered (lowering requires spec amendment); bandit high/critical -> exit 1, suppression only via documented `# nosec <id> -- <reason>` under same rigor scan; ruff -> fix code, never widen ignores; missing doc -> docs-guard lists filename.

**Zero-cost check** — no new deps; dev tools already pinned, dev-only (never shipped in image). $0.00.

**Docs impact** — TEST-PLAN §1 flips to active threshold **plus explicit deviation note (Guide amendment): "threshold enforced from 4.1; Sprints 1–3 ran measurement-only"** + pragma/nosec policy; CHANGELOG Unreleased entry; CONTRIBUTING one-liner (gate green before merge).

---

### 4.2 Packaging: Dockerfile core, systemd notes, VPS deploy runbook validated

**Intent** — Ship the ONE container the architecture needs (core on VPS) plus smallest honest kit:
compose file matching runbook, `.dockerignore` keeping secrets out of build context, copy-pasteable
systemd unit notes, async deploy-smoke script turning "is Sara alive on the box?" into an exit
code, and an executed validation pass on the real free-tier VPS. Bridge daemon deliberately NOT
containerized (runs on Windows via schtasks).

**Interface**

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY common/ common/
RUN useradd --system --home /app sara && chown -R sara /app
USER sara
ENV TZ=Asia/Amman
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import os,httpx; r=httpx.get(os.environ['OMNIROUTE_BASE_URL']+'/models', timeout=5); r.raise_for_status()" || exit 1
CMD ["python", "-m", "src.main"]
```

(`common/` copied for the shared protocol package per Sprint-3 layout.)

`docker-compose.yml`: service `core`, `env_file: .env`, `restart: unless-stopped`,
ports `"${BRIDGE_BIND_PORT:-8443}:8443"`, volumes `./data:/app/data` (OAuth cache, path per 2.1)
and `./certs:/app/certs:ro` (TLS per 3.4).

`.dockerignore`: `.git .venv .env .env.* tests/ docs/ scripts/ .github/ .claude/ .ingest/ *.docx
config/google_oauth_client.json *.session __pycache__/ .pytest_cache/ .ruff_cache/ .coverage htmlcov/`.

`scripts/deploy_smoke.py` — stdlib asyncio+httpx CLI:

```python
@dataclass(frozen=True)
class CheckResult: name: str; ok: bool; detail: str   # gateway|telegram|vault|google_token_cache
async def check_gateway(settings) -> CheckResult      # GET OMNIROUTE_BASE_URL/models expect 200 JSON
async def check_telegram(settings) -> CheckResult     # getMe expect ok:true
async def check_vault(settings) -> CheckResult        # GET api.github.com/repos/<repo> w/ PAT expect 200
async def check_google_token_cache(settings) -> CheckResult  # non-empty refresh-token file at 2.1 path
async def run_all(settings, timeout_s=10.0) -> list[CheckResult]
def main() -> int                                     # loguru INFO per check, CRITICAL summary, exit 0 iff all ok
```

All checks run even after one fails. **Secret redaction (Guide amendment — MAJOR): exception text
NEVER lands raw in detail/log lines — httpx errors embed full request URLs including the bot
token; every check wraps failures through a Settings-aware masker (TELEGRAM_BOT_TOKEN,
VAULT_GITHUB_TOKEN, BRIDGE_TOKEN stripped), logging host + path-class only; pytest asserts a
failing telegram check's detail contains no token substring.** Per-check `asyncio.timeout`.

systemd notes appended to RUNBOOK §4b (documentation block, deliberately not a checked-in unit file).

**Acceptance criteria**

1. AC1 — Dockerfile contract (base pin, ffmpeg, non-root USER, CMD). → `tests/test_packaging.py::test_dockerfile_contract`
2. AC2 — dockerignore keeps secrets/tests/docs out of context. → `test_dockerignore_keeps_secrets_out_of_context`
3. AC3 — compose contract (env_file, restart, single published port, both mounts). → `test_compose_core_service_contract`
4. AC4 — image builds + compose config validates on dev machine (skipped when docker absent). → `test_docker_build_succeeds`
5. AC5–AC7 — smoke: all-green exit 0; single failure exits 1 while remaining checks ran and named; timeout bounded per check as failed CheckResult. → `tests/test_deploy_smoke.py::test_all_green_exits_zero` etc.
6. AC8 — failing-check redaction: no secret substring in any logged detail. → `test_deploy_smoke.py::test_failure_details_redacted`
7. AC9 — **no-live-call artifact grep lives HERE (Guide amendment)**: `grep -rE "pytgcalls|telethon|pyrogram" Dockerfile docker-compose.yml requirements.txt` empty — authored and green in 4.2. → `tests/test_packaging.py::test_no_live_call_stack_in_artifacts`
8. AC10 — runbook §4 dated validation checklist ending in deploy_smoke exit 0 on target VPS (manual, reviewer-verifiable via diff).

**Error modes** — invalid env at boot -> CRITICAL + non-zero exit + restart loop until fixed (runbook row); OmniRoute down -> brain path degrades per 1.2, HEALTHCHECK unhealthy after 3 misses; cert issues -> WSS rejections logged WARNING per handshake; port occupied -> loud bind failure; smoke network errors -> ok=False details, always reaches verdict.

**Zero-cost check** — zero new Python packages; Docker/compose FOSS; python:3.12-slim PSF; ffmpeg Debian FOSS; Oracle Always Free/GCP e2-micro free tier. $0.00/month intact.

**Docs impact** — RUNBOOK §4 rewritten to actual files + §4b systemd + troubleshooting rows + dated checklist; README quickstart compressed; CHANGELOG entry.

---

### 4.3 Release v1.0.0

**Intent** — Cut the first product tag: finalize CHANGELOG, single version source with consistency
guard, release script refusing ungross/inconsistent states, annotated tag pushed, GitHub Release
published from the CHANGELOG section. Scope enforcement is part of the release contract: v1.0.0
ships ZERO live-call code (ADR-07) and a test locks that fact plus the other v1.0 exclusions.

**Interface**

- `src/__init__.py`: `__version__ = "1.0.0"` (single source of truth).
- `CHANGELOG.md`: `[Unreleased]` drained into `## [1.0.0] — <date>` with complete Added/Changed/
  Security/Deferred-to-v1.1 sections across Sprints 1–4; `[Unreleased]` retained empty.
- `scripts/make_release.py` (stdlib + loguru):

```python
def current_version() -> str                                   # reads src.__version__
def changelog_release(version) -> tuple[str,str] | None        # (date, section text) or None
def verify_consistency() -> str    # version == newest CHANGELOG heading else SystemExit(1)+ERROR naming both
def verify_clean_tree() -> None    # git status --porcelain must be empty
def verify_gate() -> None          # subprocess make gate, propagate non-zero
def main(argv) -> int              # default dry-run: all verifications, prints exact gh command
                                   # --tag: additionally git tag -a v<version> (refuses if exists)
```

Script stops at the annotated tag; publishing stays owner-run (`gh release create v1.0.0 ...`).

**Release sequence (Guide amendment — reordered)**: finalize CHANGELOG + bump version in ONE commit
-> commit if pending -> push main -> dry-run verifications -> `--tag` creates annotated tag on the
validated HEAD -> push tag -> owner publishes Release -> runbook gains "production deploys pin
`git checkout v1.0.0`" line -> BACKLOG ticks. Post-tag: container rebuilt from tag, smoke re-run
once (closes tagged-vs-running loop).

**Acceptance criteria**

1. AC1 — version matches newest CHANGELOG heading carrying ISO date. → `tests/test_release_metadata.py::test_version_matches_changelog`
2. AC2 — **scope lock, complete exclusion set (Guide amendment)**: regex alternation
   `pytgcalls|telethon|pyrogram` absent from artifacts AND src/ imports; PLUS `mem0` and `firestore`
   absent from requirements/src imports — locking the whole settled v1.0 exclusion set. → `test_no_live_call_stack_in_artifacts` (extends 4.2's artifact scan to source)
3. AC3 — CHANGELOG [1.0.0] documents deferrals incl. PyTgCalls. → `test_v100_documents_scope_deferrals`
4. AC4 — script refuses version mismatch (exit 1, ERROR names both values). → `test_release_script_refuses_version_mismatch`
5. AC5 — refuses dirty tree. → `test_release_script_refuses_dirty_tree`
6. AC6 — refuses red gate (subprocess mocked returncode 1). → `test_release_script_refuses_red_gate`
7. AC7 — no git writes without --tag; with it exactly one annotated tag command; existing tag error surfaces unswallowed. → `test_tag_only_with_explicit_flag`
8. AC8 — manual: tag resolves to validated commit; Release page exists with CHANGELOG notes; redeployed-from-tag container passes deploy_smoke exit 0.

**Error modes** — mismatches refuse loudly; dirty tree echoes porcelain; red gate names failing guard; NO --force flag (absence IS the safety feature); existing tag means bumping to 1.0.1 (docstring-documented); gh missing at final manual step -> runbook prerequisite note.

**Zero-cost check** — stdlib + loguru only; Releases/artifacts free for this use. $0.00.

**Docs impact** — CHANGELOG finalized; BACKLOG 4.1–4.3 ticked; RUNBOOK pin-tag line; README version + link; ARCHITECTURE §8 verified accurate for shipped build; PHASE-STATE Phase-4 completion marker.

---

## Stream-level definition of done

`make gate` green at >=85% branch coverage across `src/ bridge/ common/` · container deployed +
smoke-validated on free-tier VPS · `v1.0.0` annotated tag pushed · GitHub Release published ·
BACKLOG Sprint-4 boxes ticked · every doc edit landed same-commit-as-behavior.

---

## Guide Review — Verdict: FIX (dispositions below)

Reviewer: independent Guide agent, adversarial pass, 2026-08-26. *(Verifier ran during classifier
rate-limit degradation — Leader personally re-read draft and every finding before acceptance;
findings verified genuine and resolutions sound.)*

- 🟠 **MAJOR — bot-token leak via smoke-script failure details**: RESOLVED — Settings-aware masker on ALL check details/logs; dedicated redaction AC8.
- 🟠 **MAJOR — AC8's proof vehicle didn't exist at 4.2 close**: RESOLVED — grep test moved INTO test_packaging.py (authored+green in 4.2, AC9); 4.3's test EXTENDS to src imports instead of duplicating.
- **MINOR — fail-closed AC had two mechanisms, one invalid**: RESOLVED — pinned subprocess-in-tmp-tree mechanism only (AC6).
- **MINOR — ffmpeg-presence pragma immunity contradicted own rule**: RESOLVED — removed from allowlist; mocked test required like any error branch.
- **MINOR — silent coverage-threshold delay**: RESOLVED — explicit deviation note added to TEST-PLAN edit (decided change, not drift).
- **MINOR — release sequencing self-contradiction**: RESOLVED — commit-before-dry-run order fixed.
- **MINOR — 'quamob' undefined pattern + partial scope lock**: RESOLVED — exact alternations enumerated; mem0/firestore exclusions locked too.

### Open questions carried into implementation

1. TLS provisioning contract resolved toward self-signed + SPKI pinning now (Sprint-3 ruling); Let's Encrypt swap documented for packaging if hostname exists — confirm at 4.2 start.
2. OAuth token-cache path pinned to `/app/data/google_token.json` (compose volume matches).
3. If Sprint-1 chose a config home other than pyproject.toml, 4.1 consolidates into pyproject.toml.
4. Validation VPS choice (Oracle ARM vs GCP e2-micro) recorded on the dated checklist whichever box runs.
5. Repo public-vs-private at release time = OWNER DECISION required before 4.3 publishes.
