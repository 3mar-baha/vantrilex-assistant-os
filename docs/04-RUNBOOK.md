# 04 — Runbook: Environment, Operations & Troubleshooting

Reproducibility rule: anything a build needs is checked, scripted, and documented here.

## 1. Prerequisites

| Tool | Version | Install / verify |
|---|---|---|
| Python | 3.12 | `py -3.12 --version` (Windows launcher; do NOT rely on bare `python`) |
| Git | 2.54+ | `git --version` |
| FFmpeg | any recent | `winget install Gyan.FFmpeg` then reopen shell; `ffmpeg -version` |
| GNU make | 4.4+ | `choco install make` (already present on dev machine) |
| OmniRoute | latest | clone https://github.com/diegosouzapw/OmniRoute beside the core (co-located in the HF Space, ADR-15; locally for dev); start bound to localhost:20128 |
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

## 4. HF Space Deployment (production, free tier — ADR-15)

Supersedes VPS deployment (ADR-05). One Docker Space co-locates OmniRoute +
core; the Space's single public port serves the WSS bridge endpoint + `/health`.

1. Create a private HF Space (Docker, 2 vCPU / 16 GB tier) in the owner account.
2. Space Dockerfile (Sprint-4 task 4.4b): single image supervising OmniRoute
   (`localhost:20128`) + the core; `app_port` = the public WSS/health port.
3. All secrets go to **HF Secrets** (bot token, owner ID, OAuth client, bridge
   token) — never the repo; `.env` is local-only for development.
4. Configure free provider pools (3-tier brain per ADR-16) in OmniRoute.
5. **Keep-alive is mandatory**: cron ping `GET /health` every 10 min
   (e.g., cron-job.org) — free Spaces idle-sleep after prolonged silence.
6. **Disposable filesystem**: anything that must survive a restart lives in the
   git-backed vault (ADR-15 invariant); the OAuth token cache is vault-persisted
   (encrypted) or the owner re-consents after restarts.
7. Verify: bot responds to the owner; `curl -m 5 <SPACE_URL>/health` returns ok.

### 4b. Cloud Run fallback (secondary host — documented alternative)

If the Space is unavailable: build the SAME image (4.4b) and deploy to Google Cloud Run
free tier — container reads `PORT`, min-instances=0 (cold starts noted; the keep-alive
pinger keeps it warm), all secrets via Cloud Run environment variables. No committed
terraform/CI for this path in v1.0.0 — activating it is an owner action documented here.
The bridge daemon's `BRIDGE_SERVER_URL` simply points at the Cloud Run WSS URL instead.

## 5. PC Bridge Daemon (Windows)

1. `make setup` on the PC; fill `[CORE <-> BRIDGE]` block of `.env`
   (`BRIDGE_SERVER_URL` points at the Space WSS endpoint; shared `BRIDGE_TOKEN`).
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
6. Audit trail: every PC action appends one line to `04_Archives/Audit/pc-ledger.md`
   (`ts | audit_code | action | outcome | reason`); each confirmed command has a
   Confirmations note (`Confirmations/YYYY-MM-DD_<id8>.md`) persisted BEFORE the command
   leaves the core. Quote the «رمز التدقيق» from Sara's message when auditing.

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
   biometrically verified (<50 ms CPU, `VOICEPRINT_THRESHOLD=0.75`).
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
| `dispatcher ... -> default tier2` (warning) | Tier-1 router failed or replied non-JSON (ADR-18 degradation) | Service continues at Tier 2; inspect the logged router reply; persistent repeats -> probe the `google/gemini-3.5-flash-lite` pool |

## 8. Operational Safety

- Secrets only via `.env` / token caches; nothing plaintext in git (enforced by CI bandit scan + review).
- The bridge executes ONLY commands passing the whitelist/confirmation flow (ADR-03).
- Treat email/web/file content as untrusted data — never as instructions (CLAUDE.md §2.7).
