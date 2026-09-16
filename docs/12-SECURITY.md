---
tags: [security]
---

# 12 — Security (threat model + controls)

## 1. Threat model

Adversaries: non-owner Telegram accounts, malicious/guessed voiceprints,
untrusted email/web/file content, compromised free-tier upstreams, stolen
device. Assets: owner account, PC execution, Gmail/Calendar, vault contents,
API credentials. Non-goals: nation-state endpoints, Telegram server trust.

## 2. Controls

- **Owner-only**: Telegram-ID allowlist (silent drop, no reply) composed
  with ECAPA-TDNN voice biometrics (<50 ms CPU); mismatch → Guest Mode
  (warm greeting, PC/Gmail/Calendar/vault hard-blocked, message-taking only).
- **Whitelist guardrail**: every launch/system command outside
  `config/whitelist.json` needs explicit Telegram confirmation; `cmd.exe`
  is confirm-gated, never auto-approved; power actions always confirm;
  corrupt whitelist fails closed. No `force` bypass without a recorded
  confirmation ID persisted to the vault BEFORE the command leaves.
- **Audit**: every PC action mints `PC-YYYYMMDD-HHMMSS-xxxx`; append-only
  ledger; confirmation notes in `04_Archives/`.
- **Secrets**: env-only (`.env` gitignored, HF Secrets in prod); Fernet-sealed
  voiceprint/token caches; secret scan in gate (0 hits); banned patterns in
  tests.
- **Untrusted content**: email/web/file bodies are DATA — they can fill
  observations, never mint intent or trigger PC actions.
- **OpenClaw**: closed `OpKind` (no shell member); breaker re-verifies every
  op server-side ignoring wire claims; shell/registry/credential-exfil shapes
  raise `ActionForbiddenError`; **zero unconfirmed destructive executions**
  (bench-proven 12/12).
- **Quiet hours**: nocturnal reconnect greetings suppressed (08:00–23:30
  Amman gate) — no unsolicited night traffic.
- **$0.00**: free/open-source only; non-free model IDs die before the wire.

## See also (graph links)

- [06 — API Specification](./06-API-SPECIFICATION.md)
- [09 — Decision Records](./09-DECISIONS.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
