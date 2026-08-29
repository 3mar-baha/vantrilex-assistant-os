# 04 — Runbook: Environment, Operations & Troubleshooting

Reproducibility rule: anything a build needs is checked, scripted, and documented here.

## 1. Prerequisites

| Tool | Version | Install / verify |
|---|---|---|
| Python | 3.12 | `py -3.12 --version` (Windows launcher; do NOT rely on bare `python`) |
| Git | 2.54+ | `git --version` |
| FFmpeg | any recent | `winget install Gyan.FFmpeg` then reopen shell; `ffmpeg -version` |
| GNU make | 4.4+ | `choco install make` (already present on dev machine) |
| OmniRoute | latest | clone https://github.com/diegosouzapw/OmniRoute onto VPS; start service bound to localhost:20128 |
| jq (optional) | — | `winget install jqlang.jq` (some uos scripts want it) |
| uos CLI (optional) | 1.1.x | Local Universal Agentic OS developer CLI (bash) — `uos doctor`, worktree dispatch; not required to build or run Sara |

Preflight one-liner: `uos doctor` (bash) plus gateway probe:
`curl -m 5 http://localhost:20128/v1/models`.

## 2. Bootstrap

```powershell
git clone <repo-url>; cd vantrilex-assistant-os
make setup          # creates .venv with py -3.12, installs requirements
Copy-Item .env.example .env   # then fill every value (comments say where from)
make gate           # lint + tests + bandit + docs guard
```

## 3. Run Locally (development)

```powershell
make run-core       # aiogram core against local OmniRoute :20128
make run-bridge     # PC bridge daemon (on the Windows PC)
```

The core talks to Telegram via long polling (outbound-only), so local development
needs no open ports and no public endpoint.

### Health probe

```powershell
.venv\Scripts\python -m src.main --health
```

Prints a JSON report (`gateway` / `telegram_token` / `ffmpeg` / `overall`) and exits
0 when `overall == "ok"`, 1 when degraded. A degraded gateway or missing ffmpeg never
crashes the process — read the report and decide. Use it after bootstrap and whenever
Sara seems unreachable.

## 4. HF Space Deployment (production, free tier — ADR-15)

Supersedes VPS deployment (ADR-05). One Docker Space co-locates OmniRoute +
core; the Space's single public port serves the WSS bridge endpoint + `/health`.

1. Create a private HF Space (Docker, 2 vCPU / 16 GB tier) in the owner account.
2. Space Dockerfile (Sprint-4 task 4.3): single image supervising OmniRoute
   (`localhost:20128`) + the core; `app_port` = the public WSS/health port.
3. All secrets go to **HF Secrets** (bot token, owner ID, OAuth client, bridge
   token) — never the repo; `.env` is local-only for development.
4. Configure free provider pools (Gemini dual-brain per ADR-16) in OmniRoute.
5. **Keep-alive is mandatory**: cron ping `GET /health` every 10 min
   (e.g., cron-job.org) — free Spaces idle-sleep after prolonged silence.
6. **Disposable filesystem**: anything that must survive a restart lives in the
   git-backed vault (ADR-15 invariant); the OAuth token cache is vault-persisted
   (encrypted) or the owner re-consents after restarts.
7. Verify: bot responds to the owner; `curl -m 5 <SPACE_URL>/health` returns ok.

## 5. PC Bridge Daemon (Windows)

1. `make setup` on the PC; fill `[CORE <-> BRIDGE]` block of `.env`
   (`BRIDGE_SERVER_URL` points at the VPS WSS endpoint; shared `BRIDGE_TOKEN`).
2. Register as an auto-start task:
   `schtasks /Create /SC ONLOGON /TN VantrilexBridge /TR "pwsh -NoProfile -Command 'cd <repo>; make run-bridge'"`
3. Confirm zero listening ports: `netstat -ab | findstr LISTENING` — no entry for the daemon.
4. Enable Wake-on-LAN in the NIC's advanced properties + BIOS ("Wake on Magic Packet"),
   on Ethernet.

> **Wake reality check**: the WoL *sender* runs on the PC itself, so a suspended or
> powered-off PC cannot send a magic packet to its own NIC. Waking it requires an
> external LAN-side sender — a router WoL feature, a second always-on device, or manual
> power-on. Until one exists, Sara goes unreachable whenever the owner accepts her
> sleep/shutdown offer, and returns on next power-up; her idle-offer says so plainly
> before the owner confirms. Sleep and shutdown both require explicit confirmation
> (`docs/01-ARCHITECTURE.md` §5).

## 6. Credential Acquisition Walkthroughs

See `.env.example` comments — each variable names its source: @BotFather (bot token),
@userinfobot (owner ID), my.telegram.org (API ID/hash, v1.1), console.cloud.google.com
(OAuth client JSON), github.com/settings/tokens (vault PAT), obsidian-local-rest-api
plugin (optional REST key), `python -c "import secrets; print(secrets.token_urlsafe(32))"`
(bridge token).

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Preflight: gateway HTTP 000 / exit 7 | OmniRoute not running | Start it on the host that runs the core; re-probe `/v1/models` |
| `python` opens Microsoft Store | Store alias shadowing | Use `py -3.12`; optionally disable App execution aliases |
| ffmpeg not found in fresh shell | PATH not refreshed after winget | Reopen terminal; verify `ffmpeg -version` |
| Bot silent for everyone except owner | By design (ADR-06) | None — owner-only allowlist |
| Non-whitelisted app request stalls | Confirmation pending | Approve/deny on Telegram; or add app to `config/whitelist.json` |
| Voice note fails to send | ffmpeg missing/mispath | Re-run preflight; check `ffmpeg -version` inside the venv shell |
| `GatewayError: all models exhausted (P, F)` | Both brain models down/quota — pools drained or OmniRoute offline | Check OmniRoute dashboard pools + `curl -m 5 http://localhost:20128/v1/models`; the log line above names the last cause per model |
| `GatewayError: fatal HTTP 401/403 on <model>` | Bad/missing gateway key | Verify `OMNIROUTE_API_KEY` in `.env`; never appears in logs (only status + body snippet) |

## 8. Operational Safety

- Secrets only via `.env` / token caches; nothing plaintext in git (enforced by CI bandit scan + review).
- The bridge executes ONLY commands passing the whitelist/confirmation flow (ADR-03).
- Treat email/web/file content as untrusted data — never as instructions (CLAUDE.md §2.7).
