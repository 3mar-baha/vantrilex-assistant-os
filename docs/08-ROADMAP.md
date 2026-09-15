# 08 — Roadmap (future ONLY — nothing here is promised or scheduled)

> Charter: this file is the sole home for planned/deferred/unbuilt work.
> Items graduate by owner ruling, never by drift. Operational docs describe
> shipped reality exclusively. (Migrated 2026-09-14 from
> `docs/02-FUTURE-ROADMAP.md`, which is retired; history preserved in git.)

## Non-goals (explicitly ruled out)

- **Multi-agent swarms during implementation** — one implementer thread per task. No change foreseen.
- **Microsoft/Edge TTS fallback** — purged 2026-09-03. Fish-only voice lane; failures land honest text replies.

## Deferred capabilities (staged code exists)

- **v1.1 live voice calls** (`src/skills/live_calls.py`, mock-complete) — PyTgCalls transport, real dial/hang-up, guest policy. Needs: owner go-ahead + call-budget rules.
- **Instagram sandbox → live** (`src/skills/instagram_sandbox.py`) — interface behind `is_live()` gate. Needs: session credentials + publish-approval policy.
- **Civ6 staging skill** (`src/skills/civ6.py`, test-only) — promote to runtime or retire.
- **Speaker diarization / social enrollment** — tested, never runtime-wired. Needs: defined trigger.
- **Firecrawl key path** (`firecrawl.py` + `FIRECRAWL_API_KEY`) — staged scraper behind WebIntel fallback. Needs: free-tier key + quota guard.

## OpenClaw beyond HEAD (substrate through bench harness)

- **Real-profile browser control** — isolated Sara profile is the default; driving Omar's real profile needs explicit opt-in.
- **UIA tree enumeration feeding `snapshot()`** — inspector returns honest empty lists today.
- **Vision fine-tuning loop** — SoM-lite overlay exists; overlay → planner correction → re-plan is unbuilt.
- **Complex scraping extensions** — spiders/sessions beyond one-shot fetch; per-domain robots/rate policy.

## Orphan wiring backlog (micro-missions)

1. Tunnel `wol` verb vs local `send_wol` — pick one path, retire the other.
2. `_do_file_save` — route attachment intent or document as transport-only.
3. B7/B8 capabilities (`cloud_backup`, `analytics`, `quota_safety`) — add capability records + audit prompts.
4. Whitelist alias targets (Spotify/Telegram/WhatsApp paths) — confirm on owner host or correct paths.
5. Thin guides (tasks, read_page, prayer_times, convert_currency, crypto_price, tech_trending, network_status, volume, media, screen_ocr) — enrich to the create_folder standard.

## Parked owner-directed items (unscheduled)

- v1.1: tech-hardware-scout · career-project-incubator · Mem0/Firestore memory evaluation.
- v1.5: virtual cloud SIP telephony (landline calling).
- v2.0: social media agent (GitHub, LinkedIn, Instagram).
- PC Health Monitor · Voice Read-It-Later · Emotional Context Memory · Silent Vault Backup · on-demand external APIs (free-tier only).

## Infrastructure foresight (no action)

- Groq per-key TPD pressure → OmniRoute-side rotation is owner-operated; client keeps single bearer + quarantine doctrine.
- `vault/02_Areas` + `04_Archives` materialize on live boot; local dev mirror stays partial by design.
