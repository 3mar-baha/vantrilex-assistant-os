---
tags: [architecture]
---

# 01 — Product Requirements (PRD)

> Living document. Active scope = shipped at HEAD. Anything v1.1+ lives in
> `docs/08-ROADMAP.md` — never here.

## 1. Vision

**Vantrilex Assistant OS** is an autonomous, 24/7 personal executive operating
system: one assistant — **Sara (سارة)** — consolidating workspace management,
knowledge structuring, remote hardware automation, and proactive tech tracking,
reachable over Telegram in warm, authentic Jordanian Arabic. (Source:
`docs/VISION.md`, frozen.)

## 2. User personas

- **Omar (owner, sole principal)** — Amman-based builder; Arabic-first,
  technical precision in English. The ONLY account Sara serves; every other
  Telegram account is dropped silently at middleware level, no reply.
- **Sara (the product voice)** — executive chief of staff, polymath tutor,
  witty and warm; feminine self, masculine address to Omar; platonic only,
  strictly no romantic roleplay. Affectionate banter welcome; empathy under
  stress; firmness when urgent.

## 3. Functional scope (shipped, v1.0)

1. Telegram text chat + Ogg Opus voice notes (Fish Audio, dialect-shaped).
2. 3-tier OmniRoute brain (Groq FAST / nex-mini MEDIUM / nex-pro HEAVY) behind
   the Fast Front-Door Dispatcher (instant ack, tiered execution/narration).
3. Google Workspace: Gmail triage matrix, Calendar, Drive, Contacts, Tasks.
4. Obsidian vault (PARA+Zettelkasten): episodic capture, RAG inject, daily
   ledger, evening check-in, 23:50 summarizer.
5. Whitelisted PC control over an outbound-only bridge (launch/close/volume/
   media/screenshot/OCR/file-drop/telemetry/WoL) with explicit-confirmation
   gates and per-action audit codes.
6. OpenClaw substrate Phases 1–4 + bench harness (inspect/fetch live;
   browse/desktop breaker-gated and staged).
7. Tiered living memory (digest + deep dives + write-back) with intent-gated
   injection; /start WoL + reconnect greeting under quiet hours.

## 4. Non-functional requirements (hard)

| Requirement | Target | Enforced by |
|---|---|---|
| Monthly cost | Exactly $0.00 | free-only deps; `PaidModelBlockedError` guillotine |
| Owner-only access | 0 non-owner accounts processed | Telegram-ID allowlist + voice biometrics |
| Unauthorized PC execution | 0% | whitelist guardrail + confirmation IDs + audit ledger |
| FAST first-token latency | < 1.2 s bar (measured ~0.6–1.2 s) | 4 s guillotine + 15 min quarantine + cascade |
| RAG retrieval p95 | ≤ 5 ms (measured ~3.1 ms) | lazy mtime-cached `VaultIndex`, 8000-char cap |
| Voice | Fish-only; zero Edge-TTS traces | purge + zero-edge gate row |
| Test health | 1,457 passed, 0 failures; coverage ≥ 85% | `make gate` (ruff + pytest + security + docs guard) |
| Async discipline | 100% async Python; blocking calls in executors | ruff + review |

## 5. KPIs

TTFT < 1.2 s · RAG p95 ≤ 5 ms · voice-note first chunk < 600 ms target ·
0 unconfirmed destructive executions · 0 guest-mode private-tool leaks ·
1,457/0 suite · $0.00/mo.

## 6. Out of scope (see `docs/08-ROADMAP.md`)

v1.1 live calls, social agents, SIP telephony, multi-agent swarms (ruled
out), Edge-TTS fallback (ruled out), real-profile browser control.

## See also (graph links)

- [02 — Product Specification](./02-PRODUCT-SPECIFICATION.md)
- [04 — System Architecture](./04-ARCHITECTURE.md)
- [08 — Roadmap](./08-ROADMAP.md)
- [09 — Decision Records](./09-DECISIONS.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
