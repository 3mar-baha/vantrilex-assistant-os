# 13 — Deployment (topology, env, boot, containers)

## 1. Topology (ADR-15 as amended 2026-08-31)

ONE Docker container on an Oracle Cloud Always-Free Ampere A1 VM co-locates
OmniRoute + core behind Caddy 2 TLS (free DuckDNS name); single public port
serves WSS bridge endpoint + `/health`. `restart: unless-stopped` (VM never
sleeps; keep-alive cron optional). Windows PC bridge daemon dials
outbound-only (zero inbound ports). Container is host-agnostic (`$PORT`).

## 2. Environment variables (names only — values live in `.env`/HF Secrets)

`OMNIROUTE_BASE_URL/KEY`, `FAST/MEDIUM/HEAVY_MODEL(+_FALLBACKS)`,
`HEAVY_ESCALATION_*`, `TELEGRAM_BOT_TOKEN`, `AUTHORIZED_USER_ID`,
`VAULT_ENC_KEY`, `VAULT_GITHUB_REPO/TOKEN`, `BRIDGE_TOKEN/URL`,
`PC_MAC_ADDRESS` (WoL target; unset → honest no-MAC answer),
`FISH_AUDIO_*`, `OPENROUTER_API_KEY`, `TZ=Asia/Amman`. Full template with
per-var sources: `.env.example`.

## 3. Boot scaffolding sequence (`run_bot`)

`ensure_vault_scaffolding` (mandatory dirs) → `ensure_resources_scaffolding`
(04_Resources mirror, strict copy-if-missing) → `ensure_master_digest`
(Tier-1 plant, copy-if-missing) → VaultClient → dialect lexicon seed →
capabilities manifest sync → skill-guide sync → loops → reconnect watcher →
polling. Any single failure degrades loudly; boot never dies on scaffolding.

## 4. Container requirements

Python 3.12-slim, ffmpeg, Node ≥22 (OmniRoute engines), non-root `sara`
user, `ENV TZ=Asia/Amman`, supervised entry (`scripts/supervise.py`).
Bridge wheels (`requirements-bridge.txt`: Playwright/pywinauto/Scrapling)
install on the PC only — never in the Oracle image.
Verify: `python scripts/deploy_smoke.py` (exit 0 = alive);
`python -m src.main --health` (JSON report). Run: `make run-core` (VM),
`make run-bridge` (PC).
