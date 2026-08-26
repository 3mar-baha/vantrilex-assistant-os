# 03 — Architecture Decision Records

Status legend: Accepted · Superseded · Deferred.

## ADR-01: OmniRoute as the Central AI Gateway — **Accepted**
- **Context**: High-quality LLM reasoning without recurring monthly bills.
- **Decision**: Route all LLM calls through OmniRoute (`http://localhost:20128/v1`)
  aggregating 90+ free provider pools with quota-aware auto-fallback.
- **Consequences**: $0 inference cost; resilience to provider outages; dependency on
  gateway uptime (mitigated: co-located on VPS, health-checked).

## ADR-02: Telegram as Primary Transport (voice notes now, live calls v1.1) — **Accepted**
- **Context**: PSTN/SIP trunks carry per-minute fees; Telegram voice is free.
- **Decision**: Aiogram 3.x chat + Ogg Opus voice notes in v1.0; PyTgCalls WebRTC
  live calls in v1.1; cloud SIP telephony deferred to v1.5.
- **Consequences**: 100% free voice; live-call fragility isolated out of first release.

## ADR-03: Whitelist Verification Loop for PC Control — **Accepted**
- **Context**: Unrestricted remote OS execution is unsafe.
- **Decision**: `config/whitelist.json` gates all actions; non-whitelisted requests
  require explicit owner confirmation before execution (Telegram prompt in v1.0;
  live verbal call from v1.1); approvals recorded with confirmation IDs.
- **Consequences**: Convenience cost on first use of any app; hard safety floor.

## ADR-04: Persona Named Sara (سارة) — **Accepted** (2026-08-26)
- **Context**: Mission brief said Sara; prepared docx drafts said Mona (منى).
- **Decision**: Sara is canonical; all draft material renamed during scaffold.
- **Consequences**: Drafts remain source-of-record with the old name until superseded.

## ADR-05: VPS-Primary Topology with Outbound-Only PC Bridge — **Accepted**
Supersedes draft preference for Google Cloud Run deployment.
- **Context**: The brain (OmniRoute) ran on localhost; Cloud Run could not reach it
  without tunnels; true 24/7 must survive PC sleep.
- **Decision**: Free-tier VPS hosts core + OmniRoute + Edge-TTS pipeline; Windows PC
  runs a bridge daemon that dials OUT over TLS WebSocket (zero inbound ports,
  token-authenticated). WoL magic packets are sent LAN-locally by the daemon.
- **Consequences**: Core survives PC sleep/shutdown; waking the PC requires an external
  LAN-side sender — the on-PC daemon cannot self-wake its host (see runbook §5).

## ADR-06: Owner-Only Access Model — **Accepted**
- **Decision**: Hard Telegram user-ID allowlist (`AUTHORIZED_USER_ID`); all other
  accounts silently dropped at middleware before any processing.
- **Consequences**: Smallest attack surface; no multi-user capability until demand exists.

## ADR-07: v1.0 Scope = Executive Core minus Live Calls — **Accepted**
- **Decision**: v1.0 ships text chat, Ogg Opus voice notes, Google Workspace suite,
  tiered email triage, Obsidian vault, PC control. Deferred to v1.1: PyTgCalls live
  calling, scout skills (tech-hardware-scout, career-project-incubator),
  Mem0/Firestore memory layer. Critical-triage falls back to priority voice note +
  repeat ping until live calls land.
- **Consequences**: Most fragile dependency (WebRTC/MTProto session) excluded from
  first green release.

## ADR-08: Zero-Cost Invariant Absolute — **Accepted**
- **Decision**: Strictly $0.00/month, no exceptions. Whitelist misses confirm via
  Telegram prompt until live calls exist.
- **Consequences**: Provider choice constrained to free tiers/pools forever.

## ADR-09: Credential Manifest with Progressive Gating — **Accepted**
- **Decision**: `.env.example` documents every secret and where to obtain it; each
  phase gate verifies exactly the credentials that phase needs.
- **Consequences**: No upfront credential blockade; explicit readiness checks per phase.

## ADR-10: Python 3.12 Pin — **Accepted**
- **Context**: Machine default is 3.14 (wheel gaps in aiogram/pytgcalls ecosystem);
  3.12 also installed.
- **Decision**: All environments target Python 3.12 via `py -3.12`.
- **Consequences**: Predictable wheels; revisit when ecosystem supports 3.14.

## ADR-11: Docx Drafts Retained as Source-of-Record — **Accepted**
- **Decision**: The 22 `.docx` planning drafts stay committed untouched until their
  content is superseded by markdown specifications (Phase 2); extraction cache
  `.ingest/` is gitignored.
- **Consequences**: Provenance preserved; temporary duplication.

## ADR-12: Single Formatter (Ruff) — **Accepted**
- **Decision**: Ruff handles lint + format checking; no Black/isort duplication.
  Supersedes the draft gate's "ruff + black" pairing.
- **Consequences**: One tool, one config, same guarantees.

## ADR-13: uos CLI Anchoring & Native Pattern Adoption — **Accepted** (2026-08-26)
- **Context**: `uos.sh` hardwires `REPO_ROOT` to the universal-agentic-os repo itself
  (script_dir/..); its project commands (`status/ingest/plan/dispatch/merge/graph/ship`)
  operate on that repo, not on consumer projects.
- **Decision**: Use `uos doctor` globally for environment diagnostics; apply the OS's
  workflow patterns natively inside this repository — plain git worktrees per stream +
  our `make gate` (functional equivalent of `uos ship`). Revisit a cwd-anchored fork of
  the CLI only if multi-stream dispatch overhead ever justifies it.
- **Consequences**: No dependency on OS-repo internals for daily flow; upstream pulls
  still deliver diagnostics/tooling improvements via `uos doctor` + toolkit sync.
