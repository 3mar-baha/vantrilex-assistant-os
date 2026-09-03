# 04 — Runbook: Environment, Operations & Troubleshooting

Reproducibility rule: anything a build needs is checked, scripted, and documented here.

## 1. Prerequisites

| Tool | Version | Install / verify |
|---|---|---|
| Python | 3.12 | `py -3.12 --version` (Windows launcher; do NOT rely on bare `python`) |
| Git | 2.54+ | `git --version` |
| FFmpeg | any recent | `winget install Gyan.FFmpeg` then reopen shell; `ffmpeg -version` |
| GNU make | 4.4+ | `choco install make` (already present on dev machine) |
| OmniRoute | latest | clone https://github.com/diegosouzapw/OmniRoute beside the core (co-located in the ONE container / on the Oracle VM, ADR-15; locally for dev); start bound to localhost:20128 |
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

### Voice latency smoke

```powershell
.venv\Scripts\python -c "import asyncio; from src.voice import VoicePipeline; p=VoicePipeline(voice='ar-JO-SanaNeural', rate='+0%', pitch='+0Hz'); asyncio.run(lambda: None)()"
```

Simpler: run the transcode proof — `pytest tests/test_audio_stream_opus.py -q` asserts
real ffmpeg emits Ogg Opus from an in-memory stream with the first encoded chunk
surfacing before producer completion (<600 ms first-chunk budget, binding Q1).

### Streaming first-edit smoke (task 2.2, Audio-TTFT < 250 ms)

```powershell
pytest tests/test_chat_streamer.py::test_first_edit_within_250ms_ttfb -q
```

Asserts the placeholder edit path: first bubble edit fires <250 ms after stream start,
subsequent edits coalesce at `STREAM_EDIT_INTERVAL_MS`, and the final bubble text is
exact. Live: send the owner a text message — the «…» bubble appears immediately and the
first words replace it within a quarter second.

### Syllabus parser smoke (task 4.1, fixture PDF -> DAG)

```powershell
pytest tests/test_syllabus_parser.py -q
```

Runs the full parser contract against the committed fixture
`tests/fixtures/syllabus_sample.pdf`: threaded pypdf extraction, TIER3 strict-JSON
parse (brain doubled), DAG validation (cycles/orphans named), weighted capped review
schedule, Calendar/Tasks materialization with `[sara:syllabus:...]` idempotency tags,
Studies filing, and the untrusted-PDF boundary (injection text travels as DATA only).
Live (AC10, manual): a real PDF -> real Calendar sandbox — the review schedule appears
in Calendar/Tasks with the tags.

### Adding a capability (owner, task 4.2 — no redeploy)

Sara accepts new scheduled background tasks at runtime (M4). The owner flow:

1. Put the new service's key in `.env` under a NEW name (e.g. `WEATHER_API_KEY=...`)
   and restart the core once so the env var is loaded — the KEY never goes into chat.
2. In Telegram, tell Sara the task name, what to fetch, the env NAME, and the
   schedule in natural language: «سجّلي مهمة weather-fetch تجيب الطقس من
   WEATHER_API_KEY كل صباح 7». Arabic/English phrasing both parse («كل ساعة»,
   «كل اثنين 9», "every morning at 7").
3. She probes the credential (>= 16 chars, no whitespace), registers the asyncio job,
   and persists it to `State/capabilities.json` — it re-derives after any restart.
   Reserved names (`pc`, `bridge`, `triage`, ...) are refused; max 8 tasks.
4. If a run fails or exceeds its time budget, the task is DISABLED loudly: she logs
   ERROR with the task name and sends you one notification. Re-enable is explicit.
5. Verify without waiting: read `{VAULT}/State/capabilities.json` — each entry carries
   `schedule_text`, `credential_env` (the NAME, never the value), `enabled`,
   `last_error`.

## 4. Production Deployment — Oracle Cloud Always Free (ADR-15 as amended 2026-08-31)

Production deploys pin a release tag — checkout `v1.0.1` (or later) before building;
never deploy an untagged `main` tip.

**Owner hand-holding guide (Arabic, step by step): `docs/09-ORACLE-DEPLOY.md`** — this
section is the engineering summary. Why Oracle: HF made Docker Spaces paid ($9/mo,
breaks the $0.00 invariant) and Render/Koyeb free tiers (512 MB) cannot carry the full
stack. The always-free Ampere A1 VM is truly always-on (no keep-alive pinger, no sleep).
The container itself is host-agnostic: it reads `$PORT`, runs `scripts/supervise.py`
(OmniRoute gateway child + core child as ONE process tree — first exit tears the tree
down so the host restarts it) and serves `GET /health` + the authenticated bridge WSS
on the single public port. Since v1.0.1 the image carries Node 24 (NodeSource) and
installs the vendored OmniRoute clone globally — `ENV OMNIROUTE_CMD="omniroute run"`
works with zero variables.

1. Provision the always-free VM (Ubuntu 24.04, `VM.Standard.A1.Flex` 2 OCPU / 12 GB,
   expandable to 4/24) and open TCP 22/80/443 in the VNIC security list — §1-2 of the
   guide, incl. the HOME-REGION-IS-PERMANENT warning and the card-verification note.
2. Install Docker (`curl -fsSL https://get.docker.com | sudo sh`) — guide §4.
3. Fetch the tag and clone the gateway BEFORE the build (the clone pins the version):
   `git checkout v1.0.1` then
   `git clone https://github.com/diegosouzapw/OmniRoute scripts/omniroute`
   (`.dockerignore` re-includes `scripts/omniroute/` + `scripts/supervise.py`; everything
   else — tests, docs, `.env`, sessions — never enters the build context). `docker build -t sara-os .`
4. Environment on the VM (`~/sara-secrets/sara.env`, never committed): the 21 variables
   listed in `docs/08-OWNER-NEXT-STEPS.md` + `PORT=8080`. The OAuth client JSON may live
   on the VM (`config/google_oauth_client.json`) — a persistent VM resolves the Space-era
   Google gap; the file itself still NEVER enters git or the image.
5. Serve TLS: Caddy 2 in the same compose project (auto-HTTPS via a free DuckDNS
   subdomain) reverse-proxying to the container — compose + Caddyfile in guide §7.
   `restart: unless-stopped` replaces the keep-alive contract on a no-sleep VM.
6. **Durable state (ADR-15 principle kept)**: anything that must survive a rebuild lives
   in the git-backed vault; the audit test stays authoritative:
   `tests/test_packaging.py::test_durable_state_only_in_vault`.
7. Verify: `curl -m 5 https://<domain>/health` → 200; owner messages the bot on
   Telegram; bridge daemon dials `wss://<domain>/bridge`; on the VM, a smoke against the
   live stack (run `python scripts/deploy_smoke.py` locally against the public URL for
   the space_health-class check, or container logs for the rest).

### 4b. Keep-alive (legacy — obsolete on the no-sleep VM, kept for sleeping hosts)

`.github/workflows/keepalive.yml` pings `GET <SPACE_URL>/health` every 10 minutes
(`*/10 * * * *` cron) and fails the step loudly on any non-200 (`::error::` + exit 1).
On Oracle (ADR-15 amendment) the VM never sleeps — the workflow is OPTIONAL and only
worth arming (repo secret `SPACE_URL` = the public URL) as a free external liveness
alarm that also alerts if the VM is down.

### 4c. Other hosts (documented alternatives, none active)

- **HF Space**: was ADR-15's original choice — Docker Spaces now REQUIRE the paid PRO
  plan ($9/mo): rejected by the $0.00 invariant. Historical packaging (README metadata
  `sdk: docker` / `app_port: 7860`) remains valid if the owner ever buys PRO.
- **Google Cloud Run**: build the SAME image; the container reads `PORT` and serves the
  same public port. Free grant caps an always-on service at 512 MB memory — same
  starvation that disqualified Render/Koyeb; only viable for a reduced text-only trial.
- **Render / Koyeb free**: 512 MB / 0.1 vCPU + scale-to-zero — text-only Sara at best,
  plus an external pinger dependency. Documented, not recommended.

### 4-validation. Dated deploy validation (2026-08-31, sprint-4 task 4.4b AC10; re-anchored to Oracle with the ADR-15 amendment)

Executed order on a fresh VM deploy (guide: `docs/09-ORACLE-DEPLOY.md`); every box
verified before ticking:

- [ ] `docker build` of the repo root succeeds on the VM (or `test_docker_build_succeeds`
      run on a docker-equipped machine) — image carries src/, common/, OmniRoute clone.
- [ ] Container boots: `docker compose up -d` then `docker compose logs -f sara` shows
      the supervisor starting both children
      (`supervisor started omniroute…` / `supervisor started core…`).
- [ ] `GET https://<domain>/health` returns 200 `{"status":"ok"}` (Caddy TLS green).
- [ ] `restart: unless-stopped` active — `sudo reboot` on the VM brings Sara back
      without manual action (the no-sleep host replaces the keep-alive contract).
- [ ] Owner messages the bot on Telegram; Sara answers in Jordanian Arabic.
- [ ] Bridge daemon on the PC dials the VM WSS (`bridge session online` in core logs).
- [ ] Full smoke against the live VM — container health + Telegram round-trip; the
      checklist ends when every probe is green.

## 5. PC Bridge Daemon (Windows)

### 5a. One-command local cycle (owner utility, 2026-09-01)

`sara.bat` (repo root, double-clickable) runs the FULL stop/stop-start cycle: kills
stale `src.main` / `bridge.daemon` python processes (the TelegramConflictError fix),
checks the OmniRoute gateway :20128 with a warning when it is down, then opens two
PowerShell windows — core (`$env:PORT='8443'; make run-core`) and bridge
(`make run-bridge`). Options: `-StopOnly` (shutdown only), `-Port 9000` (other port).
Equivalent PowerShell: `.\sara.ps1`.

1. `make setup` on the PC; fill `[CORE <-> BRIDGE]` block of `.env`

1. `make setup` on the PC; fill `[CORE <-> BRIDGE]` block of `.env`
   (`BRIDGE_SERVER_URL` points at the Oracle VM's WSS endpoint, e.g.
   `wss://sara-os.duckdns.org/bridge`; shared `BRIDGE_TOKEN`).
2. Register as an auto-start task:
   `schtasks /Create /SC ONLOGON /TN VantrilexBridge /TR "pwsh -NoProfile -Command 'cd <repo>; make run-bridge'"`
3. Listener check (directive: LAN port 8000): the daemon's ONLY listener is the
   LAN-authenticated port 8000 (telemetry `GET /telemetry/live-state` + executor surface);
   zero public-facing ports. Verify: `netstat -ab | findstr :8000` shows it bound to the
   LAN address, and no other LISTENING entry for the daemon.
   Telemetry smoke — with the daemon up, ask Sara «شو وضع الجهاز؟» on Telegram: she
   answers one Jordanian line with real cpu/ram/disk/uptime numbers (psutil, BSD dep);
   with the bridge down she says «الجسر مو متصل هسا» instead of inventing numbers.
   Direct LAN check: `curl -H "Authorization: Bearer $BRIDGE_TOKEN"
   http://localhost:8000/telemetry/live-state` returns the LiveState JSON (401 without
   the Bearer header).
4. Enable Wake-on-LAN in the NIC's advanced properties + BIOS ("Wake on Magic Packet"),
   on Ethernet.
5. Whitelist editing (owner, `config/whitelist.json`): the guard RE-READS the file on
   every check — edits apply live, no daemon restart. A corrupt/unreadable file fails
   CLOSED (everything requires confirmation) and logs CRITICAL.
   **Auto-populate (v1.0.2)**: `.venv/Scripts/python.exe -m src.app_indexer` scans the
   two Start Menu shortcut roots (`C:\ProgramData\...` + `%APPDATA%\...`), resolves each
   `.lnk` target (PowerShell WScript.Shell COM, batched EncodedCommand — no shell),
   categorizes (Coding / Gaming / Study / Productivity) and merges into
   `config/whitelist.json` idempotently — existing entries and `restricted_actions`
   untouched, anything resolving under `C:\Windows` (System32 included) DROPPED.
   Preview first: add `--dry-run`.
6. Audit trail: every PC action appends one line to `04_Archives/Audit/pc-ledger.md`
   (`ts | audit_code | action | outcome | reason`); each confirmed command has a
   Confirmations note (`Confirmations/YYYY-MM-DD_<id8>.md`) persisted BEFORE the command
   leaves the core. Quote the «رمز التدقيق» from Sara's message when auditing.

### 5b. Headless remote boot: Auto-Logon + daemon at startup (v1.0.2)

Goal: Sara wakes the PC via Wake-on-LAN (UDP:9) → Windows boots **straight into the
owner's desktop session** (no lock screen) → the bridge daemon is already up → Sara's
PC commands work with nobody at the keyboard.

**Step 1 — Windows Auto-Logon** (choose ONE):

- *Preferred — Sysinternals Autologon* (stores the credential as an LSA secret, NOT
  registry plaintext): download from
  `https://learn.microsoft.com/sysinternals/downloads/autologon`, run `Autologon64.exe`
  **as administrator**, enter domain\username + password → **Enable** → reboot verifies.
  Disable any time with the same tool (**Disable**).
- *Alternative — netplwiz*: `Win+R` → `netplwiz` → select the owner account → uncheck
  «Users must enter a user name and password» → OK (stores the password in registry
  LSA-protected). Windows 11 22H2+ first: Settings → Accounts → Sign-in options → turn
  OFF «For improved security, only allow Windows Hello sign-in for Microsoft accounts»,
  otherwise the checkbox is hidden.

> Security note (honest): auto-logon means anyone physically at the PC lands on the
> desktop. Accepted for the owner's private machine — the bridge's LAN surface is still
> Bearer-token gated, PC actions stay whitelist/confirmation-guarded from Telegram, and
> the audit ledger keeps working. Pair it with a BIOS power-on password if physical
> access is a concern (that does not block WoL).

**Step 2 — bridge daemon at startup** (choose ONE; the daemon module is
`bridge.daemon` — `make run-bridge` = `python -m bridge.daemon` — with its LAN
listener on port 8000):

- *Preferred — at logon* (fires right after auto-logon, runs inside the user session,
  no stored password in the scheduler):
  `schtasks /Create /SC ONLOGON /TN VantrilexBridge /TR "pwsh -NoProfile -Command 'cd <repo>; make run-bridge'"`
- *Alternative — at system startup* (runs pre-logon as the given account; requires the
  account password):
  `schtasks /Create /SC ONSTART /RU <DOMAIN\user> /RP <password> /TN VantrilexBridge /TR "pwsh -NoProfile -Command 'cd <repo>; make run-bridge'"`
  Verify either with: `schtasks /Query /TN VantrilexBridge /V` and
  `netstat -ab | findstr :8000` after the trigger fires.

**Step 3 — end-to-end headless proof**: shut the PC down → send the magic packet from
the LAN sender → Windows boots + auto-logs-on + the daemon dials the core
(`bridge session established` in core logs) → Sara executes a whitelisted launch
remotely, audit line lands in `pc-ledger.md`.

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

### Email triage tuning (owner, `.env`)

Triage (§2.3) reads five optional variables; edit, then restart the core to apply
(settings are cached at boot):

- `GOOGLE_VIP_SENDERS` — comma-separated sender addresses that always reach Sara as
  **Critical** (voice note + repeat ping) without any model call. Empty = none.
- `TRIAGE_KEYWORDS_AR` / `TRIAGE_KEYWORDS_EN` — urgency keywords (subject hits weigh
  double body hits). Empty = built-in defaults (عاجل، مستعجل، ضروري، فوراً، حالا /
  urgent, asap, critical, immediately, deadline).
- `CRITICAL_PING_INTERVAL_MIN` — repeat-ping spacing for Critical mail (default 5).
- `CRITICAL_PING_MAX` — pings per Critical message before Sara stops (default 6;
  `0` = unlimited until you press «تم الاطلاع» or send any activity).
- `TOKENJUICE_MAX_CHARS` — classification budget for the compacted body (default 4000):
  before scoring and the model call, quoted reply chains, signature blocks, legal
  footers and tracking boilerplate are stripped and the remainder capped. Raise it
  only if long legit bodies lose needed context.

### Whisper warmup (one-time, owner shell)

Voice memos transcribe with LOCAL faster-whisper (ADR-22 — never cloud STT). The first
run downloads the model into the local HF cache; warm it up once before going live so
the first real memo never pays that cost:

```
.venv/Scripts/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
```

Tuning (`.env`): `WHISPER_MODEL_SIZE` (tiny/base/small/medium — `small` balances Arabic
accuracy vs CPU time), `WHISPER_COMPUTE_TYPE` (default `int8`), `VOICE_MEMOS_DIR`
(default `Voice_Memos`). Transcription runs only for biometric-verified owner voice
notes; each memo files to `{VAULT_LOCAL_PATH}/Voice_Memos/YYYY-MM-DD-HHMM.md` and the
transcript flows through the normal reply pipeline. If transcription fails, Sara still
acknowledges the voice note (text ack) and the failure is logged loud.

### Daily brief schedule (owner, `.env`)

`BRIEF_ENABLED=true` + `BRIEF_LOCAL_TIME=07:30` (24h, local `TZ`): once per day Sara
sends one Jordanian-Arabic digest — today's events (24h window), uncompleted tasks due
today, and the mail picture (unread count + up to 3 heuristic IMPORTANT+ highlights).
Deterministic template, no model call. Verify without waiting: check
`{VAULT_LOCAL_PATH}/State/gmail_state.json` — `last_brief_date` holds the ISO date of
the last successful send (failed sends retry the same day; a healthy daily brief
updates it every morning).

### Evening journaler schedule (owner, `.env`)

`JOURNALER_ENABLED=true` + `JOURNALER_WINDOW_START=18:00` / `JOURNALER_WINDOW_END=19:30`
(24h, local `TZ`): once per day, at a randomized moment inside that window, Sara sends
ONE short evening check-in (tasks done, critical mail, voice memos + an open question)
and files the day's ledger `{VAULT_LOCAL_PATH}/Daily_Logs/YYYY-MM-DD.md` (YAML
frontmatter `date` + `checkin_sent`). If your calendar is booked through the window she
skips the message but still writes the ledger. Verify without waiting: check
`{VAULT_LOCAL_PATH}/State/journaler.json` — `last_checkin_sent` / `last_ledger_date`
hold the ISO date of the last successful send/ledger (a failed send retries; a healthy
journaler updates both every evening). `JOURNALER_ENABLED=false` silences the message
and stops ledger writes.

### Voice enrollment + social registry (owner, Telegram)

1. Send `/enroll-voice` to Sara, then ONE short voice note — she seals your
   ECAPA-TDNN voiceprint to `{VAULT_LOCAL_PATH}/State/owner_voiceprint.enc`
   (Fernet-encrypted with `VAULT_ENC_KEY`). Every later voice note is then
   biometrically verified (<50 ms CPU, `VOICEPRINT_THRESHOLD=0.60` — live-calibrated
   2026-09-03: owner intra-speaker cosine ~0.76, TTS impostor 0.11).
2. Non-owner voices: a recognized contact (enrolled in `State/voiceprints/`)
   gets the warm message-taking reply only; anyone unknown lands in Guest
   Mode — one staging note under `Voice_Memos/Pending_Speakers/` (encrypted
   embedding + placeholder transcript) and zero privileged effects.
3. Brief management: each `Pending_Speakers/YYYY-MM-DDTHHMM.json` note is a
   pending brief (`claimed_name` + transcript hint). Route it by verdict:
   `confirm:{Category}` -> `Contacts/{Category}/{Name}.md` + stored voiceprint;
   `ignore` -> `Contacts/Ignored/` (never matches again); `unknown` ->
   `Contacts/Unknown/` with a security flag (re-matchable embedding).
4. Re-enroll after voice changes: run `/enroll-voice` again — the new note
   atomically replaces the sealed owner voiceprint.

### First-boot vault bootstrap (automatic, credentials-gated)

On the core's first run with `VAULT_GITHUB_REPO` + `VAULT_GITHUB_TOKEN` set
(fine-grained PAT, repo scope — required from sprint-3), `ensure_mandatory_dirs()`
bootstraps the vault: an `_index.md` note per mandatory directory (`Contacts/`,
`Call_Transcripts/`, `Studies/`, `Voice_Memos/`, `Daily_Logs/`) and contacts
subdir (`Family/Friends/Colleagues/Ignored/Unknown`), plus
`02_Areas/Profile/User_Info.md` and `Dialect_Notes.md` — each a real note
(frontmatter + purpose line), one commit per note (`sara: bootstrap <path>`).
Legacy `02_Areas/Studies/` notes migrate to top-level `Studies/` as ONE structural
commit (`sara: migrate Studies to top-level`). Re-runs are no-ops (zero writes).
Verify: `git log` on the vault repo shows the bootstrap + migration commits.

### Reviewing vault structure via git log (sprint-3 3.2)

Sara grows the vault taxonomy herself as domains emerge — no manual Obsidian re-org, no
redeploy. Every structural change is ONE commit on the vault repo (`sara: expand vault —
<domain>`, Git Data API), so structure is reviewed entirely through git history:

```
git -C <vault-clone> log --oneline --follow -- "01_Projects/<domain>/"
git -C <vault-clone> show <sha>            # exactly what one expansion created
```

Each domain root carries `_tags.yaml` (its tag ontology: `domain`, `created` ISO-UTC,
`tags`) and an `_index.md` per directory (wikilinked to the domain root). The PARA
backbone is expansion-only — Sara cannot delete, rename, or move anything under
`01_Projects/ 02_Areas/ 03_Resources/ 04_Archives/ Contacts/ Call_Transcripts/ Studies/
Voice_Memos/ Daily_Logs/` (refused pre-flight, `BackboneImmutableError`), and re-runs
of an expansion are no-ops. If a domain tree looks wrong: git history is the audit
trail — revert the commit on the vault repo and Sara's next read derives the corrected
state (no local cache to invalidate).

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Preflight: gateway HTTP 000 / exit 7 | OmniRoute not running | Start it on the host that runs the core; re-probe `/v1/models` |
| `python` opens Microsoft Store | Store alias shadowing | Use `py -3.12`; optionally disable App execution aliases |
| ffmpeg not found in fresh shell | PATH not refreshed after winget | Reopen terminal; verify `ffmpeg -version` |
| Bot silent for everyone except owner | By design (ADR-06) | None — owner-only allowlist |
| Non-whitelisted app request stalls | Confirmation pending | Approve/deny on Telegram; or add app to `config/whitelist.json` |
| Voice note fails to send | ffmpeg missing/mispath | Re-run preflight; check `ffmpeg -version` inside the venv shell |
| `GatewayError: all models exhausted (<tier chain>)` | A whole tier's chain down/quota — pools drained or OmniRoute offline | Check OmniRoute dashboard pools + `curl -m 5 http://localhost:20128/v1/models`; the log line names the last cause per model in the chain |
| `GatewayError: fatal HTTP 401/403 on <model>` | Bad/missing gateway key | Verify `OMNIROUTE_API_KEY` in `.env`; never appears in logs (only status + body snippet) |
| `dispatcher ... -> default tier2` (warning) | Tier-1 router failed or replied non-JSON (ADR-18 degradation) | Service continues at Tier 2; inspect the logged router reply; persistent repeats -> probe the `openrouter/minimax/minimax-m3:free` pool |
| Container restart-looping / supervisor exits 2 | `OMNIROUTE_CMD` missing or a child fails to spawn | The image ships `ENV OMNIROUTE_CMD="omniroute run"`; if the build ran before cloning `scripts/omniroute`, rebuild — the log line names the failing child |
| `GET /health` returns 404/426 | Hitting a non-public path, or core not up yet | Only `/health` answers HTTP (200); the WSS endpoint is auth-gated — wait for the supervisor's two start lines then re-probe |
| Caddy serves no TLS / no cert | DuckDNS record stale or port 80 blocked in the VNIC security list | Update the DuckDNS record to the VM's Public IP; re-check Ingress Rules (guide §2.5) |
| Keep-alive workflow failing (`::error::`) | `SPACE_URL` repo secret unset/wrong, or a sleeping host is down | Set `SPACE_URL` to the public root; on Oracle this workflow is an OPTIONAL liveness alarm only |
| `deploy_smoke` exits 1 — which check? | Any of the five probes red | The log names each check + a masked detail (secrets never appear); fix that surface and re-run |

## 8. Operational Safety

- Secrets only via `.env` / token caches; nothing plaintext in git (enforced by CI bandit scan + review).
- The bridge executes ONLY commands passing the whitelist/confirmation flow (ADR-03).
- Treat email/web/file content as untrusted data — never as instructions (CLAUDE.md §2.7).
