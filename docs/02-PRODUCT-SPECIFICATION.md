---
tags: [architecture]
---

# 02 — Product Specification (feature logic, workflows, edge cases)

> Shipped behavior at HEAD. Future work: `docs/08-ROADMAP.md`.

## 1. Conversation turn lifecycle

1. Owner message → allowlist middleware (silent drop otherwise) → voice
   biometrics gate (Guest Mode lockdown on mismatch).
2. `_stream_answer` builds the system prompt: persona core + long-term
   memory + affect guide + acoustic block + RAG inject (intent-gated:
   routine device turns inject `""`, zero tokens; advisory turns prepend
   Tier-1 digest + top-3).
3. Dispatcher: FAST router verdict `{route, tool, arg, ack, voice_reply}` →
   instant ack → cognition backstop → deterministic keyword net → tool lane
   (`ToolRegistry.call`) → HEAVY narration (2 lines, Sara-voiced), or
   direct/plain chat tiers.
4. Turn end (background, never blocking): ledger write + fact learn +
   write-back check (weight ≥ 4 or explicit "remember this").

Edge cases: router unparsable → safe tier2 default; tool exception →
honest apology line, never silence; newer owner message cancels in-flight
stream (zombie edits prohibited); empty reply → `EMPTY_REPLY_AR`.

## 2. Voice pipeline

Telegram voice → faster-whisper STT (local, int8) → dialect normalize →
brain → Fish Audio `s2.1-pro-free:free` (سمسم ref) via OpenRouter speech →
`shape_for_tts` (emoji strip + lexicon + تسكين الأواخر) → ffmpeg → Ogg
Opus 64k voice note. Fish failure → honest text reply (no fallback
engine, ever). Reply channel: explicit owner request wins; else router
`voice_reply`; voice-origin defaults voice.

## 3. Email triage matrix

Spam → drop. Semi-important → Markdown text. Important → voice note.
Critical/VIP → priority voice note + repeat ping. Bodies compacted
(TokenJuice-style) before classification; bodies are DATA, never
instructions (untrusted-content boundary).

## 4. Whitelist + confirmation flow (`config/whitelist.json`, 157 apps)

Launch/close/power/file ops check the guard (re-read per check; corrupt →
fail closed). Non-listed app or power action → explicit Telegram
confirmation → `confirmation_id` (uuid12) persisted to vault BEFORE the
tunnel command leaves → daemon executes → audit ledger line
(`PC-YYYYMMDD-HHMMSS-xxxx`). `cmd.exe` is confirm-gated, never
auto-approved. No `force` bypass without a recorded confirmation ID.

## 5. Memory: dual-tier + write-back

50-message rolling buffer + Obsidian envelope (User_Info, Dialect_Notes,
capabilities manifest, daily ledger). Associative RAG: lazy
mtime-invalidated `VaultIndex` (2000 files / 8000 chars / top-3 / 600-char
block). Tier-1 digest (`Omar_Master_Digest.md`, ≤800 words, disjoint
aliases) + Tier-2 deep dives; nested ledger `Daily_Logs/YYYY/MM/*.md`
with flat-legacy read fallback; 90-day hot index helper. Write-back fires
only on weight ≥ 4 or explicit intent, async in `_PERSIST_TASKS`.

## 6. OpenClaw arms (breaker-gated)

| Arm | Verb | State |
|---|---|---|
| inspect | `openclaw.perceive` (+`full`) | LIVE (screenshot+foreground; OCR fail-soft) |
| fetch | `openclaw.fetch` | LIVE (Scrapling-first, httpx fallback, ≤10 s) |
| browse | `openclaw.browse` | LIVE navigate (isolated profile); non-URL → staged line |
| desktop | `openclaw.act` | Probe executes; real DAGs via `plans.py` (PARK + breaker sole enforcers) |

Reversibility table: READ/NAVIGATE + safe hotkeys + non-commit typing →
auto. Enter-submit, save/overwrite, delete, dirty-buffer close, power →
compulsory human confirm. Shell/registry/credential-exfil shapes →
`ActionForbiddenError`, never executable (`OpKind` has no shell member).

## 7. Bridge reconnect + /start WoL

`/start` with bridge down + `PC_MAC_ADDRESS` set → WoL packet + the single
static offline string; bridge live → normal welcome. Reconnect monitor
greets once per reconnect (30-min debounce) only 08:00–23:30 Amman; nocturnal
reconnects stay silent unless an owner turn landed within 15 min.

## See also (graph links)

- [01 — Product Requirements](./01-PRODUCT-REQUIREMENTS.md)
- [03 — Technical Specification](./03-TECHNICAL-SPECIFICATION.md)
- [04 — System Architecture](./04-ARCHITECTURE.md)
- [06 — API Specification](./06-API-SPECIFICATION.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
