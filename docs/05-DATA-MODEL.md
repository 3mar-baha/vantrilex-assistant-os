---
tags: [architecture]
---

# 05 — Data Model (vault records, wire entities, indexes)

## 1. Vault directories (PARA backbone, expansion-only)

| Path | Content | Writer |
|---|---|---|
| `01_Projects/` | venture/project notes, scheduled tasks | Sara + tools |
| `02_Areas/Profile/User_Info.md` | durable owner facts (append-only sections) | fact learner |
| `02_Areas/Profile/Dialect_Notes.md` | dialect lexicon (term → phonetic) | dialect learner + voice |
| `02_Areas/Profile/Omar_Master_Digest.md` | Tier-1 living digest (≤800 words) | write-back (capped) |
| `02_Areas/Profile/Sara_Skills/*.md` | 44 per-tool skill guides | boot sync |
| `02_Areas/Profile/Sara_Capabilities.md` | capabilities manifest | boot sync |
| `Contacts/{Family,Friends,Colleagues,Ignored,Unknown}/` | dossiers | enrollment |
| `Call_Transcripts/` | v1.1 call transcripts | calls lane |
| `Studies/` | tutoring material | studies flows |
| `Voice_Memos/` | guest + owner voice-note notes | transcriber |
| `Daily_Logs/YYYY/MM/YYYY-MM-DD.md` | dated ledgers (flat legacy fallback) | writers + journaler |
| `04_Archives/{Conversations,Confirmations,Audit}/` | transcripts, confirmation IDs, audit ledger | coordinator |
| `04_Resources/` | mirrored knowledge bases (boot copy-if-missing) | boot mirror |
| `State/` | runtime JSON (voiceprint, timers, journaler) — **index-skipped** | loops |

## 2. Note frontmatter schema

`title` (string, required) · `type` (`knowledge-base` | `living-digest` |
`profile` …) · `date: YYYY-MM-DD` · `summary` (one line; the key is
`summary:`, never `description:`) · `tags: [a, b]` · `aliases: [ar.., en..]`
(YAML-parsable; malformed frontmatter raises naming the path).
Alias hits dominate retrieval (+10); disjoint alias sets per file (no
top-k collisions by construction).

## 3. OpenClaw wire entities (`bridge/openclaw/protocol.py`, canonical)

`OpKind` (closed: focus/click/double_click/right_click/type_text/hotkey/
scroll/navigate/extract/screenshot/inspect_tree — no shell member).
`ElementHandle{id,role,name,bbox?,hotkey?,source:uia|dom|vision}`.
`Op{op,target?,value?,reversibility,verify?}`.
`ActionDAG{goal,ops[],weight,plan_id}`.
`ActionTranscript{plan_id,success,observations[],audit_codes[]}`.
Tunnel verbs: `openclaw.perceive` (+`full`), `.act` (op + `confirmation_id?`),
`.fetch` (validated URL), `.browse` (`action` + `params`).

## 4. Indexes

`VaultIndex`: lazy, mtime-invalidated; caps 2000 files / 8000 chars per doc;
skips `.obsidian/`, `State/`; scoring alias+10, title×3, tags×2, body×1;
top-3 ≤600-char injection block. 90-day hot window helper over the local
mirror; deep history stays in cold RAG (same index walks everything).

## See also (graph links)

- [04 — System Architecture](./04-ARCHITECTURE.md)
- [06 — API Specification](./06-API-SPECIFICATION.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
