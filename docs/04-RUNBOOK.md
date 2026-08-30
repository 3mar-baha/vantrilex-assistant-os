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

## 4. VPS Deployment (production, free tier)

1. Provision a free-tier VPS (e.g., Oracle Cloud Always Free ARM, or GCP e2-micro).
2. Install Docker + compose; copy repo; create `.env` from `.env.example`.
3. Run OmniRoute on the VPS bound to `localhost:20128`; configure free provider pools.
4. `docker compose up -d` (core container only; the bridge never runs on the VPS).
5. Verify: bot responds to the owner; `curl -m 5 http://localhost:20128/v1/models` on the box.

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

### Google OAuth bootstrap (one-time, browser machine)

1. console.cloud.google.com → project `vantrilex-assistant-2008` → enable Calendar,
   Tasks, Drive, People (Contacts), Gmail APIs.
2. OAuth consent screen: External + test user `omarbaha224@gmail.com`.
3. Credentials → OAuth client ID → **Desktop app** → download JSON → save as
   `core-foundation/config/google_oauth_client.json` (gitignored; NEVER commit).
4. Set `VAULT_ENC_KEY` (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   and `VAULT_LOCAL_PATH` in `.env`.
5. On the browser machine, inside the venv: `py -3.12 -m src.google_auth` → open the
   printed consent URL, approve. Tokens are Fernet-sealed to
   `{VAULT_LOCAL_PATH}/State/google_token.json.enc` (ADR-15).
6. VPS headless: run step 5 on the owner PC, then copy the sealed token file to the
   VPS vault path (it is useless without VAULT_ENC_KEY, which never leaves `.env`).

Re-bootstrap when: the token cache is missing/corrupt (Sara logs `google token cache
corrupt -> treating absent` and continues degraded) or Google rejects the refreshed
grant (`GoogleAuthError ... re-run the OAuth bootstrap`).

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Preflight: gateway HTTP 000 / exit 7 | OmniRoute not running | Start it on the host that runs the core; re-probe `/v1/models` |
| `python` opens Microsoft Store | Store alias shadowing | Use `py -3.12`; optionally disable App execution aliases |
| ffmpeg not found in fresh shell | PATH not refreshed after winget | Reopen terminal; verify `ffmpeg -version` |
| Bot silent for everyone except owner | By design (ADR-06) | None — owner-only allowlist |
| Non-whitelisted app request stalls | Confirmation pending | Approve/deny on Telegram; or add app to `config/whitelist.json` |
| Voice note fails to send | ffmpeg missing/mispath | Re-run preflight; check `ffmpeg -version` inside the venv shell |

## 8. Operational Safety

- Secrets only via `.env` / token caches; nothing plaintext in git (enforced by CI bandit scan + review).
- The bridge executes ONLY commands passing the whitelist/confirmation flow (ADR-03).
- Treat email/web/file content as untrusted data — never as instructions (CLAUDE.md §2.7).
