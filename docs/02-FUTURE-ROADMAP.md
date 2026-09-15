# FUTURE ROADMAP — Vantrilex Assistant OS (Sara)

> Decoupling charter (2026-09-14): this file is the ONLY home for planned,
> deferred, or unbuilt work. Operational docs (CLAUDE.md, 01-ARCHITECTURE.md,
> 10-CHECKPOINT.md, README.md) describe commit `1116de6` reality exclusively.
> Nothing here is promised, scheduled, or budgeted — items graduate by owner
> ruling, never by drift.

## Non-goals (explicitly ruled out)

- **Multi-agent swarms during implementation** — one implementer thread per task (CLAUDE.md closed-loop). No change foreseen.
- **Microsoft/Edge TTS fallback** — purged by owner directive 2026-09-03. Fish-only voice lane; failures land honest text replies.

## Deferred capabilities (staged code exists)

- **v1.1 live voice calls** (`src/skills/live_calls.py`, mock-complete) — PyTgCalls transport, real dial/hang-up, guest policy for calls. Needs: owner go-ahead + call-budget rules.
- **Instagram sandbox → live** (`src/skills/instagram_sandbox.py`) — backend interface exists behind `is_live()` gate. Needs: session credentials + publish-approval policy.
- **Civ6 staging skill** (`src/skills/civ6.py`, test-only) — promote to runtime or retire.
- **Speaker diarization / social enrollment** (`speaker_diarization.py`, `social_enrollment.py`) — tested, never runtime-wired. Needs: a defined trigger (group voice notes? new-speaker onboarding?).
- **Firecrawl key path** (`firecrawl.py` + `FIRECRAWL_API_KEY`) — staged scraper behind WebIntel fallback. Needs: free-tier key + quota guard.

## OpenClaw Phase 3+ (substrate through Phase 2 + bench harness at HEAD)

- **Real-profile browser control** — isolated Sara profile is the standing default; driving Omar's real profile needs explicit opt-in (cookie/session blast radius).
- **UIA tree enumeration feeding `snapshot()`** — inspector currently returns honest empty lists; pywinauto descendants binding is the next backend.
- **Vision fine-tuning loop** — SoM-lite overlay exists; closing the loop (overlay → planner correction → re-plan) is unbuilt.
- **Complex scraping extensions** — Scrapling spiders/sessions beyond one-shot fetch; robots/rate-limit policy per domain.

## Orphan wiring backlog (from the forensic audit — each a micro-mission)

1. `exec.open` tunnel verb — bind a core caller or document as daemon-reserved.
2. Tunnel `wol` verb vs local `send_wol` — pick one path, retire the other.
3. `stream_heavy` — wire the MoE-escalation streaming call or delete the helper.
4. `_do_file_save` — route it (attachment intent) or document as transport-only.
5. B7/B8 capabilities (`cloud_backup`, `analytics`, `quota_safety`) — add capability records + audit prompts.
6. Whitelist alias targets (Notepad, Spotify, Telegram, WhatsApp, Explorer, CMD…) — list or delist deliberately.
7. Thin guides (tasks, read_page, prayer_times, convert_currency, crypto_price, tech_trending, network_status, volume, media, screen_ocr) — enrich failure lines to the create_folder standard.

## Parked owner-directed items (from README, unscheduled — no version assigned)

Each lands only through the standard spec → TDD pipeline when prioritized:

- **v1.1**: live bidirectional PyTgCalls calls · tech-hardware-scout · career-project-incubator · Mem0/Firestore memory evaluation.
- **v1.5**: virtual cloud SIP telephony (landline calling).
- **v2.0**: social media agent (GitHub, LinkedIn, Instagram).
- **PC Health Monitor** — CPU/GPU/thermals/disk telemetry on demand.
- **Voice Read-It-Later** — save links mid-chat; narrated voice-note delivery.
- **Emotional Context Memory** — tone-adaptive replies from recent mood signals.
- **Silent Vault Backup** — background vault integrity snapshots, zero chat noise.
- **On-demand external APIs** — per-request free-tier consumption only ($0.00 invariant).

## Infrastructure foresight (no action)

- Groq per-key TPD pressure → OmniRoute-side rotation is owner-operated; client keeps single bearer + quarantine doctrine.
- `vault/02_Areas` + `04_Archives` materialize on live boot; local dev mirror stays partial by design.
- `docs/ai/PROJECT-CONTEXT.md` referenced but absent — create on demand, not speculative.
