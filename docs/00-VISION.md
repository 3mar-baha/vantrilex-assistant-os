# 00 — Product Vision & Core Pillars

## 1. Executive Summary

**Vantrilex Assistant OS** is an autonomous, 24/7 personal executive operating
system and polymath companion. It consolidates workspace management, knowledge
structuring, remote hardware automation, proactive tech tracking, and career
project ideation into a single unified assistant — **Sara (سارة)** — accessible
via Telegram in warm, authentic Jordanian Arabic.

## 2. Confirmed Mission (v1.0)

An owner-only, strictly $0.00/month executive assistant living 24/7 in a free
Hugging Face Space (ADR-15 — one Docker container co-locating the OmniRoute
gateway; all durable state in the git-backed vault) — conversing in Jordanian
Arabic over Telegram text and Ogg Opus voice notes, reasoning through the
Gemini dual-brain via OmniRoute's free pools (ADR-16), triaging Gmail into
text/voice-note escalations, driving Calendar/Drive/Contacts/Tasks, verifying
the owner's voiceprint with a warm Guest-Mode fallback (M2), keeping a daily
ledger with a randomized evening check-in (M3), and filing everything into a
git-backed PARA+Zettelkasten Obsidian vault — while a thin outbound-only daemon
on the owner's Windows PC executes whitelisted automation via Windows-MCP and
Wake-on-LAN.

## 3. Core Pillars & Value Proposition

- **Chief of Staff**: Autonomous coordination of Google Workspace (Calendar,
  Gmail, Drive, Contacts, Tasks) with tiered email triage.
- **Cultural & Linguistic Authenticity**: Real-time Jordanian Arabic voice
  synthesis (`ar-JO-SanaNeural`) with an adaptive dialect-learning loop persisted
  to `Obsidian/02_Areas/Profile/Dialect_Notes.md`.
- **Obsidian Vault Mastery**: Structured logging of conversations, voice memos,
  contacts, and (from v1.1) call transcripts via PARA + Zettelkasten.
- **Hardware Security Guard**: Safe PC automation via Wake-on-LAN, 20-minute idle
  monitor, and mandatory confirmation for anything outside `config/whitelist.json`.
- **Zero-Cost Hard Constraint**: Guaranteed $0.00 USD/month runtime architecture.

## 4. Success Criteria (KPIs)

| KPI | Target |
|---|---|
| Voice-note response latency | < 600 ms to first audible chunk |
| Monthly infrastructure cost | Exactly $0.00 |
| Unauthorized execution of non-whitelisted desktop actions | 0% |
| Non-owner Telegram accounts processed | 0 (silent drop) |
| Guest-Mode private-tool leakage | 0 (voiceprint lockdown) |
| Test coverage | >= 85% (gate-enforced from Sprint 4) |

## 5. Persona Vibe

Witty teasing and gentle scolding for procrastination; empathetic support during
busy or stressed days; direct firmness on urgent priorities. Affectionate, warm
banter that pushes friendship boundaries is welcome — strictly no romantic
roleplay — professional, warm — "أهلاً يا هلا", "ولا يهمك", "من عيوني".
