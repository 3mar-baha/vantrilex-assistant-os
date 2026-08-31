# 06 — API Specification: PC Bridge & Vault Write Surfaces

Machine-facing contracts realized in sprint 3 (§3.1–§3.4): the core↔bridge wire
protocol, the PC command catalog, the confirmation/audit lifecycle, the vault-record
schemas, and the owner-intent tool surface. Implemented by `common/protocol.py`,
`bridge/*`, `src/pc_actions.py`, `src/vault.py`; the tests in `tests/` are the
executable form of this document.

## 1. Wire protocol (core ↔ bridge tunnel)

Transport: ONE JSON document per WebSocket text frame. The core LISTENS on its single
public port (ADR-15, path `/bridge`); the daemon dials OUT — the PC holds zero inbound
ports. Token auth only (the tunnel rides the HF Space's own TLS termination).

Constants (`common/protocol.py`):

| Constant | Value | Meaning |
|---|---|---|
| `PROTOCOL_VERSION` | 1 | every frame carries `v`; mismatch → ProtocolError |
| `HEARTBEAT_INTERVAL_S` | 15 | daemon app-level heartbeat cadence |
| `DEAD_PEER_MULTIPLIER` | 3 | peer silent > 45 s is dropped |
| `AUTH_TIMEOUT_S` | 10 | Hello must arrive within 10 s of connect |
| `MAX_FRAME_BYTES` | 1_048_576 | 1 MiB frame cap |
| `BACKOFF_CAP_S` | 30.0 | reconnect backoff ceiling (exponential, ±20% jitter, reset on a full session) |

Handshake:

1. Daemon → core: `Hello {v:1, token, hostname}` — the token travels ONLY here and is
   never logged (`security_log` records the peer IP and the verdict, not the secret).
2. Core → daemon: `HelloAck {v:1, ok, reason?}`.
3. Bad token → close **4401**. Second session while one is active → `ok:false
   "another_session_active"` + close **4400**. Slow/invalid Hello → close **4400**.

Envelopes (both directions after auth):
`Envelope {v, id, type: heartbeat|cmd|result|event, ts, cmd?, args?, status: ok|error?, payload?}`

- `type:"cmd"` — core → daemon; `cmd` ∈ catalog (§2); results correlate by `id`.
- `type:"result"` — daemon → core; `status` mirrors the ExecResult; `payload` IS the
  ExecResult model dump.
- `type:"heartbeat"` — counted by the core; drives the silence watchdog.
- Results for unknown ids are dropped with a WARN — never crash the session.

## 2. Command catalog

| cmd | args | Guard rule | Result |
|---|---|---|---|
| `exec.launch` | `name`, `confirmation_id?`, `audit_code?` | whitelist `auto_approve` OR live `confirmation_id` | ExecResult |
| `exec.open` | `path`, `confirmation_id?`, `audit_code?` | blocked suffix → refuse; UNC / relative traversal → `outside_allowed_roots` | ExecResult |
| `power` | `action`, `confirmation_id` (MANDATORY), `audit_code?` | action in whitelist AND id present — ALWAYS, regardless of any whitelist flag | ExecResult |
| `wol` | `mac`, `ip?=255.255.255.255`, `port?=9` | stateless UDP, one sendto, SO_BROADCAST | ExecResult |
| `telemetry.state` | — | (sprint-3 §3.5) | LiveState |

**Force semantics: DROPPED** — no force flag exists on any surface. Anything outside
`config/whitelist.json` — and EVERY power action — needs an owner confirmation on
Telegram (CLAUDE.md rule 4; no exceptions, no bypass). Missing executable → detail
«البرنامج مش موجود عالجهاز». Spawns are detached, `shell=False`,
`CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS`.

## 3. Confirmation ID + audit code lifecycle

- `confirmation_id = uuid4().hex[:12]` — minted core-side at approval time.
- `audit_code = "PC-" + YYYYMMDD + "-" + HHMMSS + "-" + 4hex`
  (`bridge.executor.mint_audit_code`).
- ONE audit code chains the whole event: Confirmations note → command args →
  ExecResult → owner-facing Telegram message (quotable: «رمز التدقيق PC-…»).
- **Note-before-command**: the Confirmations note is persisted to the vault BEFORE the
  command leaves the core — approval without audit is void.
- The daemon refuses unconfirmed non-whitelisted commands even from a compromised core
  (defense in depth: the guard re-checks on the PC side).

## 4. Data-model schemas (vault records)

Confirmations note — `Confirmations/YYYY-MM-DD_<id8>.md`:

```yaml
---
type: pc-confirmation
confirmation_id: <uuid4 hex, 12 chars>
audit_code: <PC-YYYYMMDD-HHMMSS-4hex>
kind: launch|power
target: <app name | power action>
confirmed_at: <ISO-8601 UTC>
---
```

Audit ledger — `04_Archives/Audit/pc-ledger.md`, one line per event, append-only:

```
<ISO-8601 ts> | <audit_code> | <action> | <outcome: executed|refused|error> | <reason>
```

ExecResult (`bridge/executor.py`): `{status: ok|error, detail: str, audit_code: str}`.

## 5. LAN surface (daemon side)

`LanServer` binds loopback/LAN — NEVER 0.0.0.0. Routes:

- `GET /health` → 200 `{"status":"ok"}`.
- `GET /telemetry/live-state` → Bearer-gated, arrives with sprint-3 §3.5.

## 6. Owner-intent tool surface (what Sara's tool calls map to)

| Tool | Implementation | Safety chain |
|---|---|---|
| `launch_desktop_app(name)` | `PCActionCoordinator.request_launch(origin="owner_chat")` | origin gate → daemon guard → confirmation prompt → ExecResult |
| power action (shutdown/restart/sleep) | `request_power` / `handle_idle_choice` («نوم»/«اطفاء») | ALWAYS a confirmation id + audit code |
| `save_obsidian_note(...)` | `VaultClient.upsert/upsert_note/append_section/commit_files` (3.1) + `VaultExpander.expand` (3.2) | one auditable vault commit per structural change; PARA backbone is expansion-only |
| `open_path(path)` | daemon `exec.open` | suffix/UNC/traversal checks; executables must go through the whitelist |

Origin gate: `RefusedOrigin` for any origin ≠ `owner_chat` — untrusted content (email
bodies, web pages, vault parses) is DATA and never mints PC intent (CLAUDE.md rule 7).
