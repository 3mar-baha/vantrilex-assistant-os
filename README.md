---
# Space-compatible metadata (kept for host portability; production host = Oracle VM,
# ADR-15 amended 2026-08-31 — see docs/15-ORACLE-DEPLOY.md)
title: Vantrilex Assistant OS — Sara
emoji: 🌟
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Vantrilex Assistant OS (نظام فانتريلكس المساعد)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-green.svg)](https://python.org)
[![Telegram: Aiogram 3.x](https://img.shields.io/badge/Telegram-Aiogram%203.x-blue.svg)](https://docs.aiogram.dev)
[![Voice: Fish Audio](https://img.shields.io/badge/Voice-Fish%20Audio%20s2.1-purple.svg)](docs/09-DECISIONS.md)
[![Brain: OmniRoute](https://img.shields.io/badge/Brain-OmniRoute%20free%20pools-orange.svg)](https://github.com/diegosouzapw/OmniRoute)
[![Version: v1.0.2](https://img.shields.io/badge/Version-v1.0.2-8A2BE2.svg)](CHANGELOG.md#102---2026-09-01)
[![Cost: $0.00/month](https://img.shields.io/badge/Cost-%240.00%2Fmonth-brightgreen.svg)](docs/09-DECISIONS.md)

> **نظام تشغيل وكلاء ذكي موحد** يجسّد مساعدة تنفيذية ومعلمة موسوعية شاملة (**سارة**) تعمل
> سحابياً على مدار الساعة (24/7)، وتتحدث باللهجة واللكنة الأردنية الدافئة والعفوية —
> بتكلفة شهرية صفرية تماماً ($0.00).

Vantrilex Assistant OS is an owner-only personal executive assistant named **Sara (سارة)** —
Chief of Staff, polymath tutor, tech scout, and PC automation companion — running 24/7 on an
Oracle Cloud Always-Free VM (ADR-15, amended 2026-08-31), speaking warm Jordanian Arabic over
Telegram, reasoning through a 3-tier multi-model brain behind a fast front-door dispatcher
(ADR-16/18), at exactly **$0.00/month**.

## What Sara does (v1.0)

1. **Executive partner** — Google Calendar, Gmail, Drive, Contacts, Tasks with a tiered email
   triage matrix: spam dropped · semi-important as Markdown text · important as a voice note ·
   critical as priority voice note + repeat ping (live call from v1.1).
2. **Jordanian voice & chat** — Telegram text chat plus native Ogg Opus voice notes synthesized
   with Fish Audio (`fish-audio/s2.1-pro-free:free`, سمسم voice) via OpenRouter speech, dialect-shaped
   before synthesis — zero cloud fees beyond the free tier. Fish is the only voice: no Edge fallback;
   a Fish failure lands an honest text reply.
3. **Knowledge vault** — every conversation, preference, and voice memo filed automatically into a
   git-backed Obsidian vault (PARA + Zettelkasten), including her own adaptive dialect notebook.
4. **Safe PC control** — Wake-on-LAN, whitelisted app launching, drive access, and a 20-minute
   idle monitor via an outbound-only Windows bridge daemon. Anything not whitelisted requires
   your explicit confirmation before it executes.

## Architecture (one glance)

```
Owner ⇄ Telegram ⇄ [Oracle VM 24/7 (ADR-15)]       [Windows PC]
                     ├─ Aiogram 3.x core             └─ Bridge daemon (outbound-only WSS)
                     ├─ Dispatcher → OmniRoute :20128    ├─ Windows-MCP executor
                     │   ├─ Tier1 fast (converse/ack)    ├─ Wake-on-LAN sender
                     │   ├─ Tier2 medium (tools)         └─ Idle monitor (20 min)
                     │   └─ Tier3 heavy (DAG/tutoring)
                     ├─ Fish Audio s2.1 → ffmpeg → Opus
                     ├─ Google Suite clients
                     └─ Obsidian vault (GitHub-backed)
```

Details: [`docs/04-ARCHITECTURE.md`](docs/04-ARCHITECTURE.md) · decisions:
[`docs/09-DECISIONS.md`](docs/09-DECISIONS.md).

### Measured first-token latency, not vendor marketing

There is no sub-second reflex tier. The `Tier1 fast` label describes **role**, not
speed: it is the conversation and acknowledgment lane. Under real free-tier provider
load, measured across 14 probe samples on 2026-09-30
([`benchmarks/CANDIDATE_MODELS_PROBE_REPORT.md`](benchmarks/CANDIDATE_MODELS_PROBE_REPORT.md)):

| Model | Samples | Best | Worst |
|---|---|---|---|
| `google/gemma-4-31b-it:free` (Tier 1 fallback) | 6 | 1.6 s | **102.1 s** |
| `openrouter/*` (Tier 2/3 primaries + fallbacks) | 8 | 3.6 s | 47.3 s |

The spread is the point: **1.6 s and 102 s are the same model on the same free pool.**
A slow first token is a provider queue, not a Sara bug, and the gateway answers it with a
first-token guillotine plus quarantine-and-cascade rather than a three-minute stall. If you
need a latency SLA, the free tier cannot give you one.

## Dual terminal

Two independent processes, either or both running:

```cmd
sara.bat -Chat          REM clean interactive console  -> src/bot_shell.py
sara.bat -Trace         REM live shadow tracer HUD     -> scripts/live_shadow_tracer.py
sara.bat --tracer       REM alias of -Trace
```

Terminal 1 answers in authentic Amman dialect with a fixed masculine address anchor for
Omar, and routes every turn through the same front-door dispatcher Telegram uses — it is a
second *window*, not a second code path, so there is no route by which an invariant can
bypass the dispatcher.

Terminal 2 streams the mechanics live: model tier, TTFT, per-tool latency, `$0.00` cost
checks, Fish audio spans, and invariant results. It reads the same log sink the runtime
writes, so it observes the real system rather than replaying a report.

## Self-evolution engine — what is actually built

Three stages are **shipped and tested**; the fourth is **not**.

| Stage | State |
|---|---|
| **P3-A** gap detection | LIVE — `EvolutionTask`, append-only JSONL backlog, marker-vs-tool gap classification |
| **P3-B** AST security gate | LIVE — 5 rules; rejects non-allow-listed imports, dynamic execution, `importlib`, and ambient-authority references (`confirmation_id`, `.env`, `getattr`, …) |
| **P3-C** registration overlay | LIVE — a merge layer that makes tool registration editable, **shipping empty** |
| **P3-D** live registration | **NOT BUILT** — barrier tests committed; no implementation |

**Sara does not synthesize or register tools autonomously today.** The overlay exists and
is empty by design: registering a tool requires four coordinated edits, and three
unguarded ones fail *silently* — the tool simply never becomes reachable, with no
exception raised. P3-C exists to remove that trap before P3-D allows anything through it.
A pass from the AST gate means *structurally admissible*, never *correct* — the gate does
not execute the code it inspects.

## Quickstart

Prerequisites: Python 3.12 (`py -3.12`), FFmpeg, GNU make, a running OmniRoute gateway,
and a Telegram bot token. Full walkthrough: [`docs/14-RUNBOOK.md`](docs/14-RUNBOOK.md).

```bash
git clone <repo-url> && cd vantrilex-assistant-os
make setup                      # .venv + dependencies
cp .env.example .env            # fill credentials (comments name each source)
make gate                       # lint + tests + security + docs guard
make run-core                   # start Sara's core
```

On the Windows PC (bridge): same repo, fill the `[CORE <-> BRIDGE]` block of `.env`, then
`make run-bridge`.

### Production (Oracle Cloud Always Free — ADR-15, amended 2026-08-31)

ONE Docker container on an always-free Ampere A1 VM co-locates OmniRoute + the core behind
the supervised entrypoint (`scripts/supervise.py`); Caddy 2 terminates TLS for a free DuckDNS
name and the single public port serves `/health` + the bridge WSS; `restart: unless-stopped`
replaces keep-alive (the VM never sleeps). Every credential lives in the VM's environment
file (`~/sara-secrets/sara.env`) — never the repo. The Arabic hand-held deploy guide:
[`docs/15-ORACLE-DEPLOY.md`](docs/15-ORACLE-DEPLOY.md); engineering summary:
[`docs/14-RUNBOOK.md` §4](docs/14-RUNBOOK.md). The container is host-agnostic (reads `$PORT`).
Verify a deployment with `python scripts/deploy_smoke.py` (exit 0 = Sara is alive).

Ops health probe (no Telegram traffic): `python -m src.main --health` prints a JSON report
(`gateway` / `telegram_token` / `ffmpeg` / `overall`) and exits 0 when ok, 1 when degraded.

## Roadmap

Shipped at HEAD: chat + voice notes (Fish), 3-tier OmniRoute brain + dispatcher (Groq FAST),
voice biometrics + Guest Mode, Google suite + triage, Obsidian vault + RAG, whitelisted PC
control, OpenClaw substrate (Phases 1–4, bench-harnessed). Planned, deferred, and unbuilt
work lives exclusively in [`docs/08-ROADMAP.md`](docs/08-ROADMAP.md) — nothing
here is promised or scheduled.

## Security

Owner-only access, whitelist-gated PC execution, outbound-only bridge, secrets never committed.
Full policy: [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Madaar Team / Vantrilex Assistant OS Contributors
