# Vantrilex Assistant OS (نظام فانتريلكس المساعد)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-green.svg)](https://python.org)
[![Telegram: Aiogram 3.x](https://img.shields.io/badge/Telegram-Aiogram%203.x-blue.svg)](https://docs.aiogram.dev)
[![Voice: ar-JO-SanaNeural](https://img.shields.io/badge/Voice-ar--JO--SanaNeural-purple.svg)](https://github.com/rany2/edge-tts)
[![Brain: OmniRoute](https://img.shields.io/badge/Brain-OmniRoute%20free%20pools-orange.svg)](https://github.com/diegosouzapw/OmniRoute)
[![Cost: $0.00/month](https://img.shields.io/badge/Cost-%240.00%2Fmonth-brightgreen.svg)](docs/03-DECISIONS.md)

> **نظام تشغيل وكلاء ذكي موحد** يجسّد مساعدة تنفيذية ومعلمة موسوعية شاملة (**سارة**) تعمل
> سحابياً على مدار الساعة (24/7)، وتتحدث باللهجة واللكنة الأردنية الدافئة والعفوية —
> بتكلفة شهرية صفرية تماماً ($0.00).

Vantrilex Assistant OS is an owner-only personal executive assistant named **Sara (سارة)** —
Chief of Staff, polymath tutor, tech scout, and PC automation companion — running 24/7 on a
free-tier VPS, speaking warm Jordanian Arabic over Telegram, at exactly **$0.00/month**.

## What Sara does (v1.0)

1. **Executive partner** — Google Calendar, Gmail, Drive, Contacts, Tasks with a tiered email
   triage matrix: spam dropped · semi-important as Markdown text · important as a voice note ·
   critical as priority voice note + repeat ping (live call from v1.1).
2. **Jordanian voice & chat** — Telegram text chat plus native Ogg Opus voice notes synthesized
   locally with Edge-TTS (`ar-JO-SanaNeural`) — <600 ms to first audible chunk, zero cloud fees.
3. **Knowledge vault** — every conversation, preference, and voice memo filed automatically into a
   git-backed Obsidian vault (PARA + Zettelkasten), including her own adaptive dialect notebook.
4. **Safe PC control** — Wake-on-LAN, whitelisted app launching, drive access, and a 20-minute
   idle monitor via an outbound-only Windows bridge daemon. Anything not whitelisted requires
   your explicit confirmation before it executes.

## Architecture (one glance)

```
Owner ⇄ Telegram ⇄ [Free-tier VPS 24/7]           [Windows PC]
                     ├─ Aiogram 3.x core            └─ Bridge daemon (outbound-only WSS)
                     ├─ OmniRoute brain :20128          ├─ Windows-MCP executor
                     ├─ Edge-TTS → ffmpeg → Opus        ├─ Wake-on-LAN sender
                     ├─ Google Suite clients            └─ Idle monitor (20 min)
                     └─ Obsidian vault (GitHub-backed)
```

Details: [`docs/01-ARCHITECTURE.md`](docs/01-ARCHITECTURE.md) · decisions:
[`docs/03-DECISIONS.md`](docs/03-DECISIONS.md).

## Quickstart

Prerequisites: Python 3.12 (`py -3.12`), FFmpeg, GNU make, a running OmniRoute gateway,
and a Telegram bot token. Full walkthrough: [`docs/04-RUNBOOK.md`](docs/04-RUNBOOK.md).

```bash
git clone <repo-url> && cd vantrilex-assistant-os
make setup                      # .venv + dependencies
cp .env.example .env            # fill credentials (comments name each source)
make gate                       # lint + tests + security + docs guard
make run-core                   # start Sara's core
```

On the Windows PC (bridge): same repo, fill the `[CORE <-> BRIDGE]` block of `.env`, then
`make run-bridge`.

## Roadmap

| Release | Scope |
|---|---|
| **v1.0** | Chat + voice notes, OmniRoute reasoning, Google suite + triage, Obsidian vault, whitelisted PC control |
| **v1.1** | Live bidirectional PyTgCalls calls · tech-hardware-scout · career-project-incubator · Mem0/Firestore memory evaluation |
| **v1.5** | Virtual cloud SIP telephony (landline calling) |
| **v2.0** | Social media agent (GitHub, LinkedIn, Instagram) |

### Future Scope (unscheduled — no version assigned)

Owner-directed additions parked without release commitment; each lands only through the
standard spec → TDD pipeline when prioritized:

- **PC Health Monitor** — CPU/GPU/thermals/disk telemetry surfaced to the owner on demand
- **Voice Read-It-Later** — save links mid-chat; Sara delivers them as narrated voice notes
- **Emotional Context Memory** — tone-adaptive replies driven by recent owner mood signals
- **Silent Vault Backup** — background vault integrity snapshots, zero chat noise
- **On-demand external APIs — YouTube / Weather / Maps** — per-request consumption on
  free-tier endpoints only; no standing subscriptions, $0.00 invariant preserved.
  (Morning Briefing is **not** future scope — it ships in v1.0 as the Sprint-2 daily brief.)

## Security

Owner-only access, whitelist-gated PC execution, outbound-only bridge, secrets never committed.
Full policy: [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Madaar Team / Vantrilex Assistant OS Contributors
