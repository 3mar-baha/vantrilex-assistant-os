# NIGHT RUN REPORT — live canary re-run (2026-09-12 → 2026-09-13)

Goal: clear the 2 red indicators from the evening canary (Fish 401 + bridge down),
ingest the owner's new `OPENROUTER_API_KEY`, verify Fish `s2.1-pro-free:free`
returns HTTP 200, and re-run the live canary to 5/5 GREEN.

## Verdict: NOT GREEN — 4/6 alive, both upstream AI lanes down with 401 "User not found"

| # | Indicator | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Core `:8443` | GREEN | `GET /health` → `{"status":"ok"}` |
| 2 | Bridge `ws://localhost:8443` + LAN `:8000` | GREEN | daemon log `bridge session established`; ws handshake 2046.7 ms; `GET http://127.0.0.1:8000/health` → `200 {"status":"ok"}` |
| 3 | Telegram | GREEN | `getMe` → `Sara_Vantrilex_bot`, ok=true |
| 4 | Vault | GREEN | scaffold already present (`scaffolded_now: []` = correct no-op); canary note landed and cleaned |
| 5 | Brain (FAST `google/gemma-4-31b-it:free` via OmniRoute) | RED | `GatewayError: fatal SSE error [401] on google/gemma-4-31b-it:free: [401]: User not found.` — reproduced twice (00:33 full canary, 05:49 focused retry). Same prompt class worked at 19:35 (TTFT 6068.1 ms, 60 chars). Not transient. |
| 6 | Fish voice (direct OpenRouter `/audio/speech`, NEW key) | RED | `FishVoiceError: fish speech HTTP 401: '{"error":{"message":"User not found.","code":401}}'` — the newly pasted key is rejected with the SAME error as the old key. Account/key-side, not code-side. |

## Timeline (timestamps verbatim as observed on-device)

- 19:35 — canary #1 (old key): bridge connection-fail (TimeoutError/ConnectionRefusedError),
  Telegram ok, brain ok (TTFT 6068.1 ms), Fish 401 `User not found`, vault scaffold created (8 dirs) + round-trip ok.
- Evening — owner pastes new `OPENROUTER_API_KEY` + orders Fish model
  `fish-audio/s2.1-pro-free:free`, bridge up (`ws://localhost:8443` + port 8000), canary re-run to 5/5.
- `.env` updated with the new key (single targeted edit, backup kept). Verified in-file:
  `FISH_AUDIO_MODEL=fish-audio/s2.1-pro-free:free`,
  `FISH_AUDIO_VOICE_REF=56c2f0c23924449781863ff20aceb5fa`. Gateway `:20128` reachable True.
  No `src.main`/`bridge.daemon` processes at that moment.
- `sara.bat`/`sara.ps1` inspected: bat delegates to ps1; ps1 kills doubled cores
  (`-match 'src.main|bridge' -and -not -match 'powershell|pwsh'`), sets `$env:PORT='8443'`,
  `Wait-Port` on 8443, gateway guard. NOT executed (owner runs their own instances; agent used direct launches).
- Core+bridge launch via `powershell.exe Start-Process -WindowStyle Hidden` → `EPERM:
  operation not permitted, uv_spawn powershell.EXE`. Retried with `pythonw.exe` directly → worked.
  (Two attempts aborted by tooling mid-flight; the surviving launches are covered below.)
- Owner: "STARA", "START". Health check: `:8443` False, but TWO `src.main` PIDs (6264, 20992,
  created 8:26 PM). `core.err.log` showed 20:27–21:27 proactive-loop failures:
  `gateway fatal | model=nex-agi/nex-n2.5-pro:free HTTP 404 ::
  {"error":{"message":"No active credentials for provider: nex-agi",... "code":"model_not_found"}}`
  → the re-pinned MEDIUM/HEAVY (`nex-agi/*`) models have NO live credentials either (re-pin risk materialized).
- Misdiagnosed the PID pair as a doubled core and killed both (remaining=0).
  Relaunched ONE core with `PORT=8443` in env → `/health` ok.
- Bridge launched via `pythonw.exe -m bridge.daemon` → `bridge session established`.
  Owner confirmed "bridge is already running".
- 00:33 — canary #2: bridge ws reachable (2046.7 ms); LAN `:8000` over ws:// → `InvalidMessage`
  (diagnosed: the LAN surface is plain HTTP, ws:// was the wrong scheme — HTTP confirmed 200 after);
  Telegram ok; brain 401 (gemma); audio skipped (brain-gated); vault ok.
- Process audit (`Win32_Process`, full command lines + ParentProcessId) revealed the earlier
  "doubled" pairs were PARENT+CHILD of single instances (venv `pythonw.exe` stub → real
  system `pythonw.exe -m …` child), NOT duplicates. The kills above therefore stopped HEALTHY
  singletons (owner's 8:26 PM core; owner's 9:47 PM core + 10:19 PM bridge). My mistake — recorded honestly.
- Killed all 4 PIDs, relaunched exactly ONE core + ONE bridge. Verified ONE logical pair:
  core parent 10916 → child 17780; bridge parent 7668 → child 21156. `/health` ok,
  `bridge session established` 00:34:43, LAN `:8000` HTTP 200.
- 05:49 — focused retry (`retry_probe.py`, Temp, not committed): brain FAST 401 again,
  Fish direct with NEW key 401 `User not found`. Definitive.

## Key findings (no secret values recorded)

1. The newly pasted OpenRouter key is rejected (`401 User not found`) exactly like the old one.
   Next step is account-side: verify the key in the OpenRouter dashboard (correct account,
   not revoked/rotated, has free-pool access). No code change can fix a rejected key.
2. OmniRoute chat for `google/gemma-4-31b-it:free` flipped 200 → 401 between 19:35 and 00:33
   while `/models` and the local proxy stayed up. Account/credential-side on the gateway or upstream.
3. `nex-agi/*` (new MEDIUM/HEAVY pins) return HTTP 404 `No active credentials for provider: nex-agi`
   → the proactive loop parks 30 min and retries. Re-pin or provision before relying on TIER 2/3.
4. `venv\Scripts\pythonw.exe -m …` ALWAYS shows as 2 PIDs (stub parent + real child).
   Future doubled-core checks MUST compare ParentProcessId before killing.
5. Clock anomaly: log timestamps jump 00:34 → 05:49 across back-to-back commands within one session.
   Timestamps above are verbatim; do not trust them for elapsed-time math.

## State at shutdown

- Running: ONE core (10916→17780, `:8443` healthy) + ONE bridge (7668→21156, session established).
- Uncommitted helpers live only in `%TEMP%\opencode` (`canary_smoke.py`, `retry_probe.py`, daemon logs) — intentionally NOT in git.
- This file is the only repo change in this commit.
- Shutdown executed as ordered: `shutdown /s /t 60` (abort with `shutdown /a` within 60 s).

## Recommended next actions (post-reboot)

1. Confirm the OpenRouter key in the provider dashboard; replace in `.env` if mismatched.
2. Check OmniRoute account/credits for the chat + `nex-agi` lanes (`/models` 200 but chat 401/404).
3. Re-run `canary_smoke.py`; expect 5/5 only after (1)+(2) resolve.
4. Consider a `ParentProcessId`-aware guard in `sara.ps1` so stub+child pairs never read as doubled cores.

## Third key rotation + canary #3 (05:56 — NO secret values recorded below)

- Owner supplied a THIRD `OPENROUTER_API_KEY`. Applied to `.env` (gitignored — never staged)
  and to `.mcp.json` `openrouter` server (`https://mcp.openrouter.ai/mcp` + `Authorization: Bearer …`
  header; `.mcp.json` is git-TRACKED, so it is deliberately EXCLUDED from all commits here).
  Model matrix confirmed as ordered: FAST `google/gemma-4-31b-it:free`,
  MEDIUM `nex-agi/nex-n2.5-mini:free`, HEAVY `nex-agi/nex-n2.5-pro:free`,
  ESCALATION `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`,
  FISH `fish-audio/s2.1-pro-free:free`. Daemons untouched — same single core (10916→17780)
  + single bridge (7668→21156) from the previous round, `:8443` True.
- Correction to my own earlier claim: OpenRouter `GET /v1/models` is a PUBLIC endpoint —
  its HTTP 200 validated NOTHING about the key. Proper check is `GET /api/v1/auth/key`:
  → `200`, label matches the new key, `usage: 0`, `limit: None`. The key itself is VALID.
- Yet Fish `/audio/speech` with that same valid key → `401 {"message":"User not found."}`.
  Conclusion: the ACCOUNT behind the key cannot reach the speech lane (not a key-string problem,
  not our code — `fish_audio_key` maps straight to `OPENROUTER_API_KEY`, fresh process per probe).
- Brain lane also shifted: OmniRoute now answers gemma chat with
  `HTTP 404 {"message":"No active credentials for provider: openrouter", "code":"model_not_found"}`
  (was 401 `User not found` an hour earlier). OmniRoute server-side has no upstream credential
  for the `openrouter` provider — independent of `.env`.
- Canary #3: bridge ws reachable (2067.4 ms), Telegram ok (`Sara_Vantrilex_bot`),
  vault ok (scaffold no-op + round-trip), LAN `:8000` ws `InvalidMessage` (probe artifact —
  HTTP `200 {"status":"ok"}` proven separately), brain RED, Fish RED (direct probe, not brain-gated).
  Verdict: 3/5 functional + 1 probe artifact; the 2 reds are BOTH upstream-account-side.
- MCP note: credential verified via authenticated `/auth/key` (200). Any remaining
  `openrouter Needs auth` badge in the harness UI is client-side session state — re-establish
  the MCP session to pick up the new `.mcp.json` header.
- This file is the ONLY staged change in the commit below (`.mcp.json`/`.env` excluded on purpose).
- Shutdown executed as ordered: `shutdown /s /t 60` (abort with `shutdown /a` within 60 s).

## Remaining owner-side actions (nothing code-side left to try tonight)

1. OpenRouter dashboard: why does a valid key get `User not found` ONLY on `/audio/speech`
   (auth/key 200, usage 0)? Account verification / payment-method / provider-routing requirement likely.
2. OmniRoute server: provision upstream credentials for providers `openrouter` (FAST + escalation)
   and `nex-agi` (MEDIUM/HEAVY) — both currently `No active credentials`.
3. Then re-run `canary_smoke.py`; 5/5 is purely gated on (1)+(2).
