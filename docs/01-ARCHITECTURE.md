# 01 — System Architecture

## 1. Confirmed Mission Record (Discovery, 2026-08-26)

- **Project**: Vantrilex Assistant OS — Universal Agentic OS v1.1.0, persona **Sara (سارة)**.
- **Rulings**: Sara naming (Q1) · VPS-primary topology (Q2 — **superseded by ADR-15: HF
  Spaces runtime host, 2026-08-29**) · owner-only access (Q3) ·
  v1.0 = exec core minus live calls (Q4) · $0.00 absolute + Telegram confirmation fallback
  for whitelist misses (Q5) · credential manifest filled progressively (Q6).
- **OmniRoute gateway**: `http://localhost:20128/v1`, co-located with the core;
  aggregates 90+ free provider pools with quota-aware auto-fallback. Adapter:
  `src/gateway.py` (`OmniRouteClient`) — the only module speaking LLM wire format;
  SSE streaming, 3-tier model chain (ADR-16), quota/transient/fatal classification
  (mid-stream SSE error events classified, never swallowed); consumers get plain text
  deltas or `GatewayError`. The **Fast Front-Door Dispatcher** (ADR-18) answers with
  Tier 1 (<250 ms TTFT) and routes single/dual-tool work to Tier 2, multi-step DAGs to
  Tier 3.
- **Telegram voice/chat architecture**: Aiogram 3.x long-polling plain-text chat;
  **progressive delivery** (task 2.2): placeholder message instantly, first edit on the
  ack (<250 ms Audio-TTFT), deltas coalesced at `STREAM_EDIT_INTERVAL_MS` (750 ms default),
  final text verbatim; a newer owner message cancels the in-flight stream; long replies
  re-split into 2-3 short chat bubbles (round-3, 2026-09-03). **Voice = Fish Audio**
  (`s2.1-pro-free:free`, the «سمسم» reference voice, via OpenRouter's speech API — owner
  directive 2026-09-03: Fish is Sara's ONLY voice, NO Microsoft fallback; a Fish failure
  retries once then lands the honest text) synthesized in-memory, transcoded by ffmpeg to
  native Ogg Opus voice bubbles (<600 ms first-chunk target); unconfigured deployments
  stay pure Edge-TTS (`ar-EG-SalmaNeural`, switchable `VOICE_NAME`); live bidirectional
  calls via PyTgCalls arrive in v1.1. **Reply channel** (round-2): the router's
  `voice_reply` verdict picks voice-vs-text per turn; the owner's explicit «رد صوتي/رد
  نصي» always wins; voice-origin defaults voice.
- **Validated deployment path (ADR-15 as amended 2026-08-31)**: **Oracle Cloud Always-Free
  VM** hosts ONE Docker container co-locating core + OmniRoute + Edge-TTS (single public
  port behind Caddy TLS = WSS bridge endpoint + `/health`; environment file on the VM;
  `restart: unless-stopped` — the VM never sleeps, the keep-alive cron is an optional
  liveness alarm); the disposable-filesystem rule stays as a design principle — all durable
  state lives in the git-backed vault; **Windows PC Bridge daemon**
  connects outbound-only (TLS WebSocket, zero inbound ports) executing WoL + Windows-MCP tasks.
  PC may sleep; Sara stays up. (Amendment history: HF Space chosen 2026-08-29 — HF made
  Docker Spaces paid $9/mo, discovered at deploy time 2026-08-31; owner ruled Oracle.)

## 2. Component Topology

**Active background loops** (remediation 3.1/3.2, wired through ONE testable
stitch point `start_background_loops` in `src/bot.py`; all cancelled on
shutdown): the 07:30 morning brief (`BriefComposer`), the 18:00–19:30 evening
check-in (`EveningJournaler`), the ~45-min proactive outreach
(`ProactiveOutreach` — HEAVY-judged voice check-ins, 08:00–22:30 window,
max 3/day, cooldown, calendar guard), the real Gmail watch (`run_gmail_poll`
+ triage), and the 23:50 daily conversation summary (`DailySummarizer`).

```mermaid
graph TD
    User([Owner]) <-->|Chat / Voice Notes / v1.1 Calls| TG[Telegram]
    TG <--> Core[Oracle VM: Aiogram 3.x Core + Orchestrator]

    subgraph VM [Oracle Always-Free Docker - 24/7, Caddy TLS, restart unless-stopped]
        Core <--> Disp[Fast Front-Door Dispatcher ADR-18]
        Disp <--> Omni[OmniRoute :20128 - 3-tier ADR-16]
        Omni <--> T1[Tier1 FAST: minimax-m3 - talker]
        Omni <--> T2[Tier2 MEDIUM: gpt-oss-120b - depth]
        Omni <--> T3[Tier3 HEAVY: nemotron-3-ultra-550b - tool lane]
        Core <--> TTS[Fish Audio (سمسم) -> ffmpeg -> Ogg Opus | fb: Edge-TTS]
        Core <--> Bio[Voice biometrics ECAPA-TDNN + Guest Mode]
        Core <--> G[Google Suite clients: Calendar / Gmail / Drive / Contacts / Tasks]
        Core <--> Vault[(Git-backed Obsidian Vault via GitHub API)]
        Core --> WSS[Public port via Caddy: WSS bridge endpoint + /health]
    end

    WSS <-->|outbound-only link| Bridge[Windows PC Bridge Daemon]
    subgraph PC [Windows PC - may sleep]
        Bridge --> MCP[Windows-MCP executor]
        Bridge --> LAN[LanServer :8000 loopback/LAN - /health + /telemetry/live-state Bearer]
        Bridge --> Tele[Telemetry snapshot - psutil LiveState]
        Bridge --> WoL[Wake-on-LAN sender UDP:9]
        Bridge --> Idle[Idle monitor 20 min]
        MCP --> Apps[Whitelisted apps / files C:, D:]
    end
```

## 3. Audio Pipeline (voice notes) — `src/voice.py`

1. Response text is finalized by the orchestrator, then shaped by the dialect TTS
   shaper (`shape_for_tts`, owner directive 2026-09-02): emoji stripped, whole-word
   pronunciation lexicon applied, trailing harakat removed (تسكين الأواخر, shadda
   preserved) — Microsoft G2P otherwise forces MSA tanween on unvocalized dialect.
2. `VoicePipeline.synthesize_stream(text)`: the configured lane synthesizes MP3
   chunks straight into the ffmpeg child's stdin — zero disk writes anywhere.
   Production lane: **Fish Audio** via OpenRouter's `/api/v1/audio/speech`
   (one-shot MP3, then the same 64k opus chain); the unconfigured fallback lane
   streams Edge-TTS `ar-EG-SalmaNeural` (pure local, $0.00).
3. ffmpeg runs via asyncio subprocess (natively non-blocking) transcoding MP3 -> Ogg
   Opus (48 kHz mono, 20 ms frames, 64k VBR `audio` application mode — the former
   24k `voip` mode choked every voice, live 2026-09-02); tiny `-probesize 32` keeps
   output flowing from the first frames (the default probesize gates ALL output
   until EOF — measured 2026-08-29).
4. Latency metric (binding, Q1): **time-to-first-encoded-chunk** — Telegram Bot API
   cannot progressively upload one voice bubble, so the first Ogg Opus chunk is
   handed to the sender as soon as it is encoded (<600 ms target); the remainder
   follows. Caller sends via
   `await message.answer_voice(BufferedInputFile(ogg_bytes, filename="sara.ogg"))`.
5. Dialect notes (`Dialect_Notes.md`) tune pronunciation/colloquialism over time.

## 4. Tiered Email Triage Matrix

| Tier | Detection | v1.0 Action | v1.1 Action |
|---|---|---|---|
| Low / Spam | Classifier score low | Drop & ignore | Drop & ignore |
| Semi-important | Medium score | Structured Telegram Markdown text | Same |
| Important / review needed | High score | Edge-TTS voice note | Voice note |
| Critical / urgent / VIP | VIP sender or urgency keywords | Priority voice note + repeat ping until acknowledged | **Immediate PyTgCalls outbound call** |

Classifier input is untrusted data: parsed email bodies can never trigger PC actions.
Before any LLM classification the body is compacted (M7, TokenJuice pattern): signatures,
disclaimers, tracking boilerplate and quoted chains are stripped and the body is capped to
the classification budget — cutting free-pool token burn without changing tier decisions.

Refinement lane (v1.0): deterministic heuristics first; the ambiguous remainder gets
ONE `FAST_MODEL` call (temperature 0, JSON verdict `{tier, reason}`, 15 s timeout) with
the body wrapped between `<<<EMAIL_DATA>>>` / `<<<END_EMAIL_DATA>>>` markers and a
containment clause in the system prompt. The final tier is the higher-visibility of
heuristic vs model — the model can rescue upward but never downgrade or silence
(model failure/timeout/invalid JSON ⇒ heuristic verdict alone). Critical mail repeats
its ping every `CRITICAL_PING_INTERVAL_MIN` minutes until the ack button, any owner
activity, or `CRITICAL_PING_MAX` pings (`0` = unlimited) — VIP senders skip the model
entirely.

Delivery note (v1.0): Gmail `users.watch` is registered once at startup when
`GMAIL_PUBSUB_TOPIC` is set (push option kept open), but inbox delivery is POLLING —
historyId incremental with query-sweep fallback — preserving the zero-inbound-ports
posture. True Pub/Sub webhook (public HTTPS) is deferred to v1.1.

## 5. Whitelist Guardrail (PC control)

```json
{
  "allowed_apps": [
    {"name": "calculator", "executable": "calc.exe", "auto_approve": true},
    {"name": "obsidian", "executable": "Obsidian.exe", "auto_approve": true}
  ],
  "restricted_actions": [
    {"action": "shutdown", "requires_confirmation": true},
    {"action": "restart", "requires_confirmation": true},
    {"action": "sleep", "requires_confirmation": true}
  ]
}
```

Flow (realized in sprint-3 3.4, `bridge/` + `src/pc_actions.py`): the daemon dials OUT to
the core's WSS endpoint (zero inbound PC ports) and is the only process on the PC that
executes commands — the guard re-checks `config/whitelist.json` on EVERY check (owner
edits apply live; a corrupt file fails CLOSED, confirming everything, with a CRITICAL
log). request -> lookup -> whitelisted (`auto_approve`) => execute and notify ->
NOT whitelisted => confirmation prompt on Telegram (v1.0 text/voice note; v1.1 live call:
"هاد البرنامج مش بالقائمة المعتمدة، هل بتأكدلي صراحة؟") => explicit approval => the core
mints a `confirmation_id` + audit code (`PC-YYYYMMDD-HHMMSS-4hex`), persists the
Confirmations note BEFORE the command leaves (approval without audit is void), then
re-sends WITH the id => execute. One audit code chains note -> command -> ExecResult ->
the owner-quotable «رمز التدقيق». Every event lands one line in
`04_Archives/Audit/pc-ledger.md`. Power actions ALWAYS need a confirmation id regardless
of any whitelist flag. Idle >20 min => Sara offers sleep/shutdown once per idle window
(real activity re-arms); the owner's choice rides the same confirmation flow.

The same bridge channel (LAN port 8000, token-authenticated, loopback/LAN-bound — never
0.0.0.0) serves the **desktop telemetry protocol** (sprint-3 3.5): one psutil snapshot
(`bridge/telemetry.live_state()`) — cpu, ram, C:/D: disks, uptime, top-CPU process —
degrades unmeasurable metrics to None instead of crashing, and reaches Sara two ways:
`GET /telemetry/live-state` (Bearer BRIDGE_TOKEN) for direct LAN diagnostics, and the
tunnel cmd `telemetry.state` for the core-side `TelemetryClient`, which narrates ONE
Jordanian line at Tier 1 FAST («شو وضع الجهاز؟») — numbers verbatim from the state,
deterministic numeric fallback when the brain is unreachable, honest
«الجسر مو متصل هسا» when the bridge is offline. Payload carries no secrets (no token,
no hostname, no paths). Wire contract: `docs/06-API-SPECIFICATION.md`.

## 6. Knowledge Vault Layout (PARA + Zettelkasten)

```
01_Projects/   03_Resources/   04_Archives/
02_Areas/Profile/User_Info.md   02_Areas/Profile/Dialect_Notes.md
Contacts/
  Family/  Friends/  Colleagues/  Ignored/  Unknown/
Call_Transcripts/       Studies/       Voice_Memos/       Daily_Logs/
```

Mandatory directories (master directive 2026-08-29; `02_Areas/Studies/` migrates to top-level
`Studies/`): `Contacts/`, `Call_Transcripts/` (written from v1.1), `Studies/`, `Voice_Memos/`,
`Daily_Logs/YYYY-MM-DD.md` — a first-boot guard test asserts all exist. The vault taxonomy
itself is dynamic (M5): Sara creates new sub-directories/tag ontologies as domains emerge,
every structural change landing as an auditable git commit; the PARA backbone is
expansion-only.

Vault transport (sprint-3 3.1, `src/vault.py`): `VaultClient` speaks the GitHub Contents API
directly (`api.github.com`, `Bearer VAULT_GITHUB_TOKEN` + versioned headers, `?ref=VAULT_BRANCH`)
— chosen over a local clone because the core's container filesystem is disposable by
design (ADR-15 principle, kept on the Oracle VM) and owner-only write volume makes
per-write commits cheap. `upsert` reads the sha
first (404 -> create, 200 -> sha update), retries one 409 via GET->PUT then raises
`VaultConflictError`; auth errors propagate loudly with zero retries. Structural changes (the
Studies migration, 3.2 expansion) land as ONE commit through the Git Data API (`commit_files`:
blobs -> tree -> commit -> ref). Payloads above 1,000,000 bytes are refused pre-flight
(defensive content bound, not an API limit). Note titles pass ONE deterministic sanitizer
(separators -> spaces, forbidden chars stripped, Arabic preserved:
«ملاحظة: اجتماع/الأسبوع؟» -> «ملاحظة اجتماع الأسبوع»). Frontmatter is
`yaml.safe_dump(allow_unicode=True, sort_keys=False)` inside leading `---` fences only;
malformed YAML on read raises ValueError naming the path. Canonical constants consumed by
3.3/3.4: `PROFILE_USER_INFO`, `PROFILE_DIALECT`, `CONVERSATIONS_DIR`,
`CONFIRMATIONS_DIR`, `AUDIT_DIR` (all under `04_Archives/`). The token never reaches a log,
exception, or URL (`redact_secret` screens every such path). First boot:
`ensure_mandatory_dirs()` upserts an index note per missing mandatory dir and contacts
subdir plus both profile files — idempotent, re-run writes nothing.

Vault taxonomy expansion (sprint-3 3.2) was PRUNED 2026-09-03 (remediation 3.3 —
`src/vault_expand.py` deleted: never wired to a production caller). Structural vault
growth now happens through the VaultClient's Git Data API directly when a live
consumer needs it. The PARA backbone stays immutable:

```
01_Projects/  02_Areas/  03_Resources/  04_Archives/
Contacts/  Call_Transcripts/  Studies/  Voice_Memos/  Daily_Logs/
```

any request whose domain touches one of those names raises `BackboneImmutableError` pre-flight
(zero API calls), and the module has no delete/move code path at all. Idempotent: existence is
read from the vault on every call (vault state IS the memory — no local cache), existing
dirs/notes are left untouched, and the result reports only the delta (re-run = empty delta, no
commit). LLM-proposed structure is DATA — the orchestrator validates proposals through this
typed interface only; invalid proposals (empty domain, nothing to create, residual separators)
are refused pre-flight with owner-readable reasons. The owner reviews every structural change
through the vault repo's git history.

Voice memos from mobile are transcribed, tagged with YAML frontmatter, and filed
automatically. Conversations that produce actionable tasks close with Sara asking:
"هل بتحب ألخص لك شو رح أعمل هسا؟" — then recites the summary and files it
(suppressed for casual check-ins). Full transcript persistence applies to calls from v1.1.

Verbal action summary protocol (sprint-3 3.3): the `src/summary.py` extractor was
PRUNED 2026-09-03 (remediation 3.3 — never wired to a production caller; conversation
capture now rides the 2.4 confirmation memory + DailySummarizer instead). Its consent
grammar lives on in `common/consent.py` — shared with the live PC-action coordinator
(`AFFIRMATIVES`, `is_affirmative`: standalone-affirmative rule, remediation 1.8 — a
guarded action launches on a clean short yes alone; «نعم بس استنى» is a reservation
and never executes).

Voice-to-vault leg (sprint-2 2.5, `src/skills/voice_to_vault_transcriber.py`): after the
2.3 biometric gate passes, the owner's voice note decodes in-memory (ffmpeg, 16 kHz mono
s16le) and transcribes via LOCAL faster-whisper (MIT, CPU `int8` — cloud STT settled to
never, ADR-22) on a dedicated executor, then files `Voice_Memos/YYYY-MM-DD-HHMM.md`
atomically (YAML frontmatter: `date` (+03:00), `source`, `duration_s`; same-minute
memos get numeric suffixes). The transcript then enters the standard owner-text
pipeline — tier selection is the ADR-18 dispatcher's decision, never this module's.

Evening journaler (sprint-2 2.6, `src/skills/evening_journaler.py`): once per local day,
at a `random.uniform` slot inside `[JOURNALER_WINDOW_START, JOURNALER_WINDOW_END)`
(Amman), Sara sends ONE short Jordanian check-in (tasks done, critical mail, memos filed
+ one open question) and writes the ledger `Daily_Logs/YYYY-MM-DD.md` — YAML frontmatter
(`date`, `checkin_sent`) with Calendar / Mail / Voice memos / Notes sections, each
degrading independently to «غير متوفر حالياً». Calendar-booked owners get no message but
still get the ledger; send failures retry the next 30 s tick without persisting the
check-in date; a state-loss same-day re-run appends a corrigenda line instead of
duplicating. Zero LLM in the hot path, stdlib `zoneinfo` + `asyncio.sleep` scheduling.

### 6b. Social Graph & Multi-Speaker Enrollment (`skill-social-graph-and-voice-enrollment`)

The vault's `Contacts/` tree is a structured social graph, each person a dossier with
relational tags, interaction log, and (when enrolled) an encrypted voiceprint vector:

| Dossier dir | Meaning |
|---|---|
| `Contacts/Family/` | Family — relational tags + voiceprint vectors |
| `Contacts/Friends/` | Social-circle profiles + interaction logs |
| `Contacts/Colleagues/` | Academic/professional peers and collaborators |
| `Contacts/Ignored/` | Blacklisted/ignored — no interaction tracking |
| `Contacts/Unknown/` | Unidentified speakers — anonymous embeddings + timestamped transcripts, security flag |

**Story entity & action extractor**: the sprint-3 `SocialGraph` story extractor was
PRUNED 2026-09-03 (remediation 3.3 — `src/skills/social_graph.py` deleted, never wired
to a production caller). Dossier structure and the enrollment/verdict lifecycle below
remain live through `src/skills/social_enrollment.py`.

**Voiceprint lifecycle** (extends ADR-17 from owner-only to multi-speaker):
- **A — known speaker**: incoming voice matching an enrolled contact -> transcript appended
  to their dossier, embedding stability updated (running centroid). Contact-mode is
  conversational ONLY — zero privileged calls (no PC, whitelist, Gmail, private vault).
- **B — new speaker, owner present**: Sara asks verbally — «عمر، هاد أخوك أحمد؟ أعتمد
  بصمته وأضيفه للعائلة؟» — and on owner confirmation creates the dossier and stores the
  voiceprint (category per the owner's answer).
- **C — new speaker, owner absent (Guest Mode)**: message + temporary voiceprint embedding
  staged under `Voice_Memos/Pending_Speakers/`; at the owner's next interaction Sara briefs
  verbally — «اتصل شخص حكى إنه أخوك أحمد وتركلك رسالة كذا... أعتمد بصمته وأعمل له ملف؟» —
  then routes the verdict: confirmed -> `Contacts/{Category}/{Name}.md` + stored voiceprint;
  «تجاهليه» -> `Contacts/Ignored/`; «ما بعرفه» -> `Contacts/Unknown/` with a security flag.

LANDED (sprint-2 2.3b, `src/skills/social_enrollment.py`): `VoiceprintRegistry` —
`match_vector` (owner checked first, <50 ms cosine), `enroll`/`update_stability`
(Fernet-sealed vectors under `State/voiceprints/`, dossier frontmatter `voiceprint_ref`),
`stage_pending`/`pending_briefs`/`resolve_pending` (three-way verdict routing above),
`record_transcript` (timestamped dossier section). Bot wiring: `verify_or_lockdown`
routes matched contacts to `CONTACT_MODE_AR` (message-taking only) before Guest Mode.

VAULT-SIDE (sprint-3 3.1b): the `SocialGraph` dossier/extract/file module was
PRUNED 2026-09-03 (remediation 3.3 — `src/skills/social_graph.py` deleted; no
production consumer ever wired it). The dossier tree structure above stays the
schema `social_enrollment.py` writes into.

## 6c. The v1.1 Intelligence Suite (owner overnight mission 2026-09-04)

Five new capabilities, all local, all zero-cost, all contract-tested:

- **Universal multi-speaker diarization** (`src/skills/speaker_diarization.py`):
  a recording splits into per-speaker dialogue turns on CPU — energy windows
  segment, ECAPA embeds each segment (the biometric gate's own model), cosine
  clustering groups turns, attribution crosses the sealed owner print + the
  Contacts registry (unknown stays unknown), local Whisper transcribes each
  turn. Transcripts are DATA — the module has no tool/exec surface at all.
- **Affect & emotional trajectory** (`AffectiveStateTracker` in
  `src/memory.py`): one FAST micro-verdict per turn reads the recent turns +
  the profile baseline and judges banter vs genuine fatigue; the subtle
  Arabic guide rides the envelope. Failures inject nothing.
- **Acoustic paralinguistics** (`src/skills/acoustic_nuance.py`):
  deterministic DSP (RMS windows, zero ML) turns HOW he spoke — pace,
  pauses, energy — into envelope context on every voice turn. ECAPA remains
  the only authorization path; this module never touches auth.
- **Self-evolution** (`src/skills/self_evolution.py`, sixth background loop,
  ~23:40 local): a nightly reflection proposes recurring Jordanian idioms
  she kept missing — filed as owner-review PROPOSALS, never silent learning.
- **Live-call scaffold** (`src/skills/live_calls.py`): the CallSession facade
  is mock-complete today (recorded + tested) and routes to PyTgCalls the
  moment TELEGRAM_USER_SESSION_STRING lands — see
  `docs/OWNER_ACTION_REQUIRED.md` §1 (the 10-minute owner login).

## 7. Component Registry

*(Removed 2026-09-03, remediation 3.3: `config/agents_config.json` was deleted —
zero consumers, and its stale Gemini/Sana pins misdescribed the shipped system.
The live component registry is §12 of this document and HANDOFF §5; agent
identity lives in `SYSTEM_PROMPT_AR` + `docs/01-ARCHITECTURE.md` §1.)*

## 8. Future Roadmap (owner-finalized 2026-09-01 — authoritative, not yet built)

The authoritative expanded roadmap (supersedes the previous staging table; mirrored in
BACKLOG "Deferred Backlog" and HANDOFF §10). Every item enters implementation through the
standard spec pipeline (acceptance criteria first, TDD) and inherits the hard invariants:
$0.00/month, owner-only, untrusted-content boundary, whitelist guardrail.

### Milestone v1.1 — Live Voice Calling & Advanced Acoustic Intelligence

- **Universal Multi-Speaker Diarization & Separation** (`skill-universal-speaker-diarization`):
  universal multi-voice separation across any audio context (Discord, single-microphone room
  speakerphone, multi-party group calls, ambient voice notes). Chain: audio source separation
  via `SpeechBrain SepFormer` / `PyAnnote.audio 3.1` -> speaker identification via `ECAPA-TDNN`
  biometrics against `Contacts/` -> parallel `faster-whisper` transcripts with precise
  timestamps and speaker tags.
- **Universal Context-Aware Affect & Emotion Engine** (`skill-affective-context-engine`):
  universal emotional intelligence analyzing prosody, pitch, energy, semantics and the
  `User_Info.md` baseline across all interactions; distinguishes banter, sarcasm and playful
  mock-frustration from genuine anger, sadness, fatigue, excitement and deep focus.
  **Strict invariant**: 100% preservation of Sara's authentic female Jordanian persona and
  warm tone across all emotional adaptations.
- **Human Conversational Paralinguistics & Self-Repair in Live Calls**
  (`skill-human-paralinguistics-and-self-repair`): natural conversational disfluencies and
  self-corrections during live calls (e.g. «رح أفتح البرنامـ... قصدي اللعبة»,
  «الموعد بكره... لا استنى، بعد بكره»); contextual micro-breaths, sighs of relief after hard
  tasks, light laughs before jokes, Jordanian hesitation fillers («اممم شوف...», «يعني هسا...»).
- **Engaged Life Conversational Partner**: active listening, empathetic curiosity and natural
  follow-up questions when the owner shares daily personal situations, university encounters
  or reflections.
- **PyTgCalls WebRTC Live Calling Engine**: bidirectional live voice streaming over Telegram
  with VAD + barge-in interruption detection (M8) and emergency call escalation for critical
  VIP emails. (v1.0 ships ZERO live-call code — scope-locked by test.)
- Carried v1.1 items (unchanged): `tech-hardware-scout`, `career-project-incubator`,
  Mem0/Firestore context engine (evaluation only — the vault loop must prove out first).

### Milestone 1-Month Post-Stabilization — Automation & Content Engine

- **Personal Weekly Audio Story / Podcast** (`skill-weekly-audio-digest`): every Saturday
  evening, an entertaining motivating 2-3 minute narrative voice note synthesizing the
  week's 7 `Daily_Logs/` in Sara's Jordanian voice.
- **Shared History & Inside Jokes Graph** (`skill-shared-history-graph`): persistent tracking
  of shared milestones, development struggles, inside jokes and personal journey narratives
  in Obsidian.
- **Clipping Bounty Automation & Anti-Shadowban Pipeline** (`sub-agent-clip-farming-and-warmup`):
  autonomous sub-worker pipeline under Sara's supervisory control for revenue generation:
  1. *Ingestion*: auto-fetch approved campaign clips from bounty platforms (Whop / Drive).
  2. *Anti-duplicate mutation*: FFmpeg micro-zoom (1%), 1.01x subtle speed shift, AI dynamic
     hook/caption generation — to defeat duplicate content detection.
  3. *Human-behavior warm-up* (Playwright Stealth): random FYP browsing (5-25s watch times),
     probabilistic interactions (15% likes, 5% follows), niche-specific search warming to
     build account trust.
  4. *Staggered multi-account publishing* (TikTok, Reels, Shorts).
  5. *Bounty submission* + daily earnings tracking reported to Sara's `Daily_Logs/`.
  **Risk note (implementer-recorded, owner-decided)**: steps 2-4 (duplicate-detection
  evasion + simulated-engagement warm-up across multiple accounts) contradict TikTok/
  Reels/Shorts platform ToS — account bans and campaign clawbacks are a real operating
  risk; the pipeline stays owner-gated at every publish step.
- **Private VoIP / Softphone (SIP over Wi-Fi)**: inbound/outbound calling to virtual
  internal extensions via Wi-Fi (Linphone / Zoiper) without cellular SIM (v1.5).

### Milestone v2.0 & Beyond — Gaming, Persona & Multi-Agent Squad

- **Distributed Civilization VI LAN Gaming Module**: multiplayer LAN integration with Discord
  voice, secret in-game alliance coordination via Telegram, and post-match tactical learning
  filed to `Studies/Gaming/Civ6/`.
- **Autonomous Social Media Virtual Persona (AI Influencer)**: autonomous Instagram/TikTok
  persona with consistent LoRA face generation and Jordanian captions.
- **Multi-Agent Squad (post-v2.0)**: six specialized autonomous agents — Sara (Chief of
  Staff), Captain Sakhr (Fitness), Prof. Nour (Academic), Tarek (Dev), Rami (Gaming),
  Karim (Finance) — in a shared Telegram group with private Obsidian memory silos.

### Formally Excluded / Deferred Scope (owner decision 2026-09-01)

- Complex PC-based ambient situational awareness — deferred to avoid inference errors.
- Cognitive load / burnout guard — deferred.

Owner-parked **Future Scope** (no version assigned, each enters via the standard spec pipeline
when prioritized): PC Health Monitor · Voice Read-It-Later · Emotional Context Memory ·
Silent Vault Backup · on-demand YouTube/Weather/Maps API calls (per-request only, free-tier
endpoints — the $0.00 invariant is preserved; no standing subscriptions). Morning Briefing
already ships in v1.0 (Sprint-2 daily brief).

## 9. Master-Directive Capability Map (2026-08-29)

Binding spec: `docs/specs/master-directive-2026-08-29.md` (M1-M9) — adaptive Jordanian
dialect engine (Sprint 1.4) · speaker verification + Guest Mode with zero-trust lockdown
(Sprint 2.6, ADR-17; lockdown test on the sacred floor) · daily activity ledger +
randomized evening check-in (Sprint 2.7) · triage token compaction (Sprint 2.4, ADR-19) ·
mandatory vault directories + dynamic taxonomy expansion (Sprint 3.1/3.4, ADR-21) ·
dynamic capability expansion with natural-language Arabic cron (Sprint 4.2, M4) ·
syllabus PDF-to-DAG parser (Sprint 4.1, TIER3) · polymath tutor (Sprint 4.3, M9;
artifacts filed to `Studies/`) · >=85% coverage gate (Sprint 4.4a) · ONE-container
packaging (Sprint 4.4b, ADR-15; host amended to Oracle 2026-08-31) · per-sprint skill rotation + teardown
(`.claude/skills/` wiped at sprint exit, outcomes in `docs/10-CHECKPOINT.md`) ·
VAD + barge-in on live calls (v1.1, M8). Hosting and brain-routing rulings: ADR-15 / ADR-16 / ADR-17 / ADR-18 /
ADR-19 / ADR-20 / ADR-21 in `docs/03-DECISIONS.md`.
