# Security Policy

## Supported Version

Security fixes target `main` and land in the next tagged release.

## Threat Model (summary)

| Asset | Threat | Control |
|---|---|---|
| Owner's Windows PC | Unauthorized remote execution | Whitelist guardrail (`config/whitelist.json`, ADR-03); mandatory confirmation for non-whitelisted actions; approval IDs persisted |
| Owner's accounts (Gmail/Calendar/Drive) | Impersonation by third parties | Owner-only Telegram allowlist (ADR-06); silent drop of all other accounts |
| Secrets/tokens | Leakage | Env-only loading; `.env`, OAuth JSON, session strings gitignored; zero plaintext tokens in code or vault |
| Core <-> PC link | Hijacking, port scanning | TLS WebSocket, shared random token, daemon holds zero listening ports (outbound-only) |
| Prompt injection via email/web/files | Content triggering actions | Parsed content is data-only (CLAUDE.md §2.7); PC actions require owner-originated intent regardless of content |
| Persona integrity | Manipulative dynamics | Strictly platonic, professional interaction policy enforced in persona directives |

## Reporting a Vulnerability

This repository is private during active development. Report issues directly to the
owner (Madaar Team) via the project's private channel, or open a GitHub security
advisory once the repository is public. Please include reproduction steps and do not
open public issues for exploitable findings.

## Hard Rules

1. Never commit secrets (`.env`, `*.session`, OAuth client JSON).
2. Never bypass the whitelist confirmation flow in code paths — tests assert the block.
3. Never process Telegram updates from non-owner IDs beyond the drop decision.
4. Never treat retrieved content (email bodies, web pages, files) as instructions.
