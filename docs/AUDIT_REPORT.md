# 🔍 DEEP ARCHITECTURAL AUDIT REPORT — Vantrilex Assistant OS

> **Audit date**: 2026-09-02, 16:12 → 22:30 (owner-commissioned, read-only forensic)
> **Scope**: full repository — `src/`, `bridge/`, `common/`, `tests/`, `docs/`, `config/`, scripts, CI, deployment surface
> **Method**: 6-axis parallel forensic investigation (max reasoning effort) → deduplication → adversarial verification of the top 12 findings (3 independent refuters each, majority vote) → completeness critic. **43 agents, 0 errors, 2.57M tokens, 538 tool calls.** The coordinator (this session) additionally re-verified every critical claim by reading the cited code directly before it entered this report.
> **Facts baseline at audit time**: working tree = 8 uncommitted modified files (the Path A voice upgrade, gate-green 355 passed / 1 skipped / 85.71% branch, **FROZEN by owner order**). HEAD = `3fe13ea`. Live runtime = the owner's local Windows machine via `sara.ps1` (NOT the Oracle container).
> **Verdict vocabulary**: **CONFIRMED** = survived 2-of-3 adversarial refuters. **Refuted** = majority refuted (documented honestly below). **Passthrough** = evidence-cited finding not adversarially re-tested (severity-ranked).

---

## 1. Executive Summary

### 1.1 Overall health score: **56 / 100**

| Component | Score | One-line verdict |
|---|---|---|
| PC bridge / WSS transport & guard core | **75** | Tunnel is genuinely well-built: outbound-only, Hello-first auth, atomic session, bounded backoff — the security skeleton holds |
| Test suite | **70** | Sacred floors are real behavioral pins; but the shell layer asserts its own fakes, the composition root is 0%-covered, and three live defects are pinned as *intended* |
| Tool lane (ToolRegistry honesty design) | **60** | The registry itself is honest-by-design (real backend → real result → narration), but everything *around* it lets a model answer instead of execute |
| Memory & vault | **55** | Write-mostly memory: new facts land where the brain never reads them; two unreconciled "vaults"; 409 races lose ledger lines |
| Tool routing (dispatcher) | **50** | Router-miss → free chat lane with zero tool context is the single hallucination engine; ack architecture leaks on every surface |
| Persona & acoustics | **50** | The one user-visible model text (the ack) is generated with no persona and a third-person gateway identity; dual-modality delivery by design |
| Bloat / YAGNI | **40** | ~30% of production code is unreachable from the live bot (1,530 src lines + 1,420 test lines kept alive) |
| Deploy & infra | **45** | Fresh clone cannot build the Docker image; keepalive CI pings a decommissioned endpoint; health probe blind to the two services that actually fail |

### 1.2 Top-3 architectural bottlenecks

1. **The ack-first front-door (ADR-18) leaks on every surface it touches.** The Tier-1 router ack is unverified model free text (length-guard only) yielded as the first stream delta — glued permanently into the final reply text, the 50-message rolling memory, the Daily_Logs ledger, and re-read aloud by the voice note. It is generated with **no persona and a third-person gateway identity** («أنت بوابة سارة الأمامية») — so «أنا بوابة سارة» is not drift of Sara's persona; it is the router's *assigned* identity leaking through. For launch intents the ack **is the final answer**, meaning an unverified ≤30-char claim («تم فتح الآلة الحاسبة») can be the entire delivered outcome.

2. **There is no deterministic boundary between intent and execution.** Whether a message becomes a real tool call rests solely on one free-tier LLM reading colloquial Arabic at temperature 0. Every miss (misclassification, invalid tool string — silently coerced to `"none"` with no log, unparsable JSON, GatewayError) degrades to a chat lane that receives the bare user text with **zero tool context** — and nothing anywhere forbids the model from narrating a fabricated outcome. Even when the verdict lands, the launch argument is Arabic free text matched by exact casefold against English whitelist keys — a confirmed launch then spawns the raw Arabic string and dies with FileNotFoundError. **The honest ToolRegistry exists, is wired, and is reachable only through this fragile text path.**

3. **Memory is structurally write-mostly — the brain rarely reads back what it writes.** Facts are appended to the tail of `User_Info.md` while the envelope slices the head; only today's ledger note is loaded so yesterday's summary is write-only; the rolling buffer is process-local so every restart is amnesia; the dialect-learning loop («تعلمي:») is dead end-to-end (notes never reach TTS or prompt); and two parallel "vaults" (GitHub API vs local disposable `./vault/`) hold same-named Daily_Logs paths that are never reconciled.

### 1.3 Root cause of the live behavioral failures (the one-paragraph version)

The system was assembled sprint-by-sprint, each module tested in isolation against fakes that assert the module's own assumptions — **and the two things that only exist at the composition level were never exercised by any test: the production wiring `run_bot()` (0% covered) and real-model behavior (router drift, minimax→gpt-oss fallback prose, ack leakage)**. The suite consequently *pins* three of the owner's live complaints as intended behavior (the ack-glued bubble, the dual text+voice delivery, the router prompt's gateway identity). The product ships green while diverging from lived reality — a green gate certifies plumbing, not behavior.

### 1.4 Live-symptom → mechanism index (all five explained, mechanically)

| # | Owner-reported symptom | Confirmed mechanism(s) | Anchor |
|---|---|---|---|
| 1 | Robotic register, «أنا بوابة سارة», gender/pronoun confusion | Router ack built with third-person gateway identity + length-only guard; 3-sentence persona prompt forbids nothing; **residual**: tier2/fallback routing streams user prose through gpt-oss-120b (English-centric), violating the settled "gpt-oss never user prose" ruling | `dispatcher.py:28,69-70,108`; `bot.py:47-51`; §13 |
| 2 | Voice note dispatched alongside duplicate/growing text | Voice-origin turns deliver the full streamed text **and** a voice note of the same string; ack glued into the growing bubble; /start sends near-duplicate text+voice greeting; unenrolled voice adds a stray static ack with no `return`; cancelled prior streams still fire late `voice.synthesize` of the partial | `bot.py:113-116,132-133,180-182,284-289`; `dispatcher.py:108` |
| 3 | «تم فتح الآلة الحاسبة» hallucination; Gmail "refused" while `src/gmail.py` exists | Router-miss → context-free chat lane (the only path that can fabricate outcomes); historical 20:25→20:51 window (09-01) when tools were built but unwired; voice «نعم» never consumed by the coordinator; Arabic app names can never match whitelist keys even after confirmation; Google stack silently degrades at boot (and on the live local machine the OAuth token cache **has never been bootstrapped** — `./vault/State/` is empty) | `dispatcher.py:87,109-116`; `bot.py:169,341-362`; `guard.py:53-56`; §14 |
| 4 | Colloquial misreads («كفيك»), short/long-term memory gaps | Whisper runs untuned (no `language="ar"`, no dialect bias, greedy beam); dialect loop dead end-to-end; User_Info head-slice vs tail-append; today-only envelope; restart-wiped buffer; failed/error turns never remembered | `transcriber.py:100`; `voice.py:79`; `memory.py:93,105`; `bot.py:268-281` |
| 5 | Suspected over-engineering / dead code | ~30% of production unreachable (7 whole modules); 3 owner-commissioned background loops built but never started; dead config knobs; duplicated micro-helpers; the heaviest dependency (torch/ECAPA biometrics) is inert in production because enrollment never happened | §6.4, §9, §14 |

---

## 2. Methodology & evidence standards

1. **Six axis investigators** (read-only, `max` effort): tool-lane integrity, persona/acoustic, memory/vault, bloat/YAGNI, bridge security, test validity. Each produced a narrative summary + structured findings, every finding citing a file and line actually read.
2. **Deduplication** by `file:line` → **80 unique findings** (10 + 18 + 15 + 18 + 10 + 12 raw).
3. **Adversarial verification**: top-12 by severity, each attacked by 3 independent refuters with distinct lenses (counterexample / mitigation-elsewhere / severity-and-intent), default-refute, majority decides. Result: **10 CONFIRMED, 2 REFUTED**. The remaining 68 are passthrough — evidence-cited, severity-ranked, flagged as unverified in every table below.
4. **Completeness critic** (separate agent) hunted gaps across all six narratives → 7 additional probe areas + 2 unexplained symptom residuals, all folded into this report (§13, §14).
5. **Coordinator re-verification**: the critical claims were independently re-read in the live code by the coordinating session before inclusion here (spot-checks of `bot.py` wiring, consent grammar, the background-loop inventory, and a full async/race analysis of the voice engine, §7).

The two REFUTED findings are documented in §5 with the refuters' reasoning — an audit that hides its dead findings is an audit that cannot be trusted.

## 3. Discrepancy Matrix (The Reality Gap)

| Feature | Expected goal (docs/CLAUDE.md/ADRs promise) | Current implementation reality | Failure mechanism |
|---|---|---|---|
| Tool execution («افحصي الجيميل») | Router verdict → **real backend** → honest narration (ADR-18, tools.py docstring: «never a hallucinated success») | Real registry exists and is wired, but reachable only if the free-tier router classifies colloquial Arabic correctly; every miss silently degrades to a context-free chat lane | Misclassification/coercion/unparsable verdict → `tool="none"` → `_plain_messages(system, history, user_text)` with zero tool context — the model invents the outcome (CONFIRMED critical, `dispatcher.py:87,109-116`) |
| App launch («افتحي الآلة الحاسبة») | Whitelisted launch with confirmation + audit code (rule 4) | Confirmed-critical exists, but the router's Arabic arg can never match English whitelist keys — exact casefold only, no alias layer; after «نعم» the raw Arabic string is spawned → FileNotFoundError «البرنامج مش موجود عالجهاز» | No normalization between model free text and whitelist keys (`guard.py:53-56`, `executor.py:57`) — CONFIRMED major; even a successful launch reports "executed" on spawn alone, never checking the child survived (passthrough major, `executor.py:65`) |
| Voice-note confirmation of PC actions | «text/voice-note confirmation in v1.0» (rule 4, no exceptions) | Only `on_text` consumes pending confirmations; a spoken «نعم» streams to the brain instead, pending expires after 10 min, next affirmative text gets hijacked by the stale pending | Missing 3-line guard in `on_voice` (CONFIRMED critical, `bot.py:169` vs `173-176`) — breaks the sacred whitelist floor |
| Gmail/Calendar/Tasks live | Modules exist, OAuth flow documented | Live runtime (local Windows) has **never run the OAuth bootstrap** — `./vault/State/` empty, no `google_token.json.enc`; RUNBOOK points the client JSON at the retired core-foundation worktree; Google stack construction swallows any failure into `inbox=None` with one warning line | Never-bootstrapped credentials + silent blanket degrade + generic `TOOL_FAIL_AR` masking the real cause (`bot.py:341-362`; CONFIRMED for the container path — compose mounts no `config/` — and reconciled for the local path in §14) |
| Evening check-in (18:00-19:30) | CLAUDE.md rule 6: randomized evening check-in, calendar-conflict-guarded | `EveningJournaler` fully built and tested (258 lines) — **never constructed at runtime**; `JOURNALER_ENABLED=true` configures a feature that cannot fire | run_bot starts exactly one loop (the summarizer); the journaler has no wiring (`bot.py:388`) — CONFIRMED-context major (passthrough tier) |
| Morning brief 07:30 | Proactive daily digest (BRIEF_ENABLED=true, BRIEF_LOCAL_TIME=07:30) | Only `collect()` is reachable (on-demand "brief" tool); the schedule machinery (`render/fire_if_due/fire_once/run_forever`) is dead | Not started in run_bot (`daily_brief.py:177`) — passthrough major |
| Proactive Gmail triage/push | Voice-rendered important mail, critical ping loops (ADR chain) | `run_gmail_poll`, fetch/seen-state, `TriageDispatcher` — all unreachable; live gmail tool only calls `peek_unread` | Not started in run_bot (`gmail.py:288`) — passthrough major |
| Adaptive dialect learning («تعلمي:») | Continuous adaptive loop feeding TTS + prompt (rule 6, M1) | Teach-lines have **zero production callers**; `shape_for_tts` called without notes; `load_long_term` reads the note body while `append_notes` writes the frontmatter | The loop is dead end-to-end — corrections are persisted then ignored (`voice.py:79`, `memory.py:103` vs `dialect.py:141-145`) — passthrough major |
| Memory (short-term) | 50-message rolling buffer, every exchange | Remembered only after a non-empty streamed reply; failed/error/empty turns and coordinator-consumed «نعم» vanish; restart wipes everything (process-local, no restore) | Early returns precede `remember()` (`bot.py:268-281`) — passthrough minor/major |
| Memory (long-term) | Facts learned → shown to the model again | Facts append to the tail of User_Info.md; envelope slices the FIRST 1600 chars → once the head fills, every new fact is persisted yet never read; only today's ledger loads — yesterday's summary is write-only | Head-slice vs tail-append (`memory.py:105` vs `168-173`); today-only path list (`memory.py:93`) — passthrough major ×2 |
| Voice replies to voice notes | «بجاوبك صوت» (HELP_AR) | Every voice-origin turn delivers the full text AND a voice note of the identical string (incl. the ack); ack read aloud again | By-design dual delivery (`bot.py:284-289`) — CONFIRMED critical; the pinning test enshrines it (`test_bot_shell.py:394-424`) |
| Voice quality (owner: «رديء وغير بشري») | Local free Edge-TTS, warm Jordanian | 24k voip-mode Opus + emoji→TTS + forced MSA tanween (the exact findings behind the Path A upgrade, now green-but-FROZEN on disk); remaining ceiling: Egyptian Salma reading Jordanian text, untuned Whisper upstream, 10-word seed lexicon, sequential synthesis after full text | Encoding/shaper fixed in the frozen tree (§6.6); persona/prosody/lexicon residual in §8 |
| $0.00 invariant | All free tiers | Held everywhere — no paid dependency found; the one "heavy" stack (torch/speechbrain, ~600MB resident once enrolled) is the price of the sacred biometrics rule and imports lazily | Invariant intact (verified by axes 4/5) |
| Durable state | «ALL durable state lives in the git-backed vault» (ADR-15) | Two parallel vaults: GitHub API (chat ledgers, User_Info, audit) vs local disposable `./vault/` (Voice_Memos, journaler ledger, voiceprints, contact dossiers) — same-named Daily_Logs paths in different stores, never reconciled | Split-brain ledger; redeploy loses memos/voiceprints (`bot.py:95`, `evening_journaler.py:201-210`) — passthrough major |
| Deployability | Clone → build → Oracle deploy (docs/09) | `scripts/omniroute/` is untracked and absent from git — **a fresh clone cannot build the Docker image**; the manual clone step in the guide is the only thing that saves it; CI never builds the image so the breakage is invisible | Missing tracked asset (`Dockerfile:18-21` + `git ls-files`) — critic probe, §13 |
| Health/ops visibility | `/health` go/no-go | Probes gateway + telegram token + ffmpeg only — blind to the vault token and the Google stack, so it reads `ok` in the exact state where every vault write and Gmail call fails | Probe scope (`health.py:14-29`) — critic probe, §13 |

## 4. CONFIRMED critical & major findings (survived 3-refuter adversarial verification)

> 10 findings confirmed by majority vote (≥2 of 3 refuters voting KEEP after independently re-reading the code). Quoted evidence is verbatim from the sources.

### C-1 ⚠️ CRITICAL — Router-miss → context-free chat lane (the hallucination engine)
`src/dispatcher.py:87,109-116`
Every path on which the Tier-1 verdict misses — colloquial misclassification, invalid tool string (silently coerced to `"none"` **with no log**, lines 67-68), unparsable JSON, GatewayError — lands the bare user text in `_plain_messages(system, history, user_text)` with zero tool context while the real registry sits behind the line-109 gate. The model is free to reply «تم فتح الآلة الحاسبة» or fabricate a digest. **This is the only mechanism that can produce the owner's hallucination symptom** (the ToolRegistry itself always returns honest strings or None).
*Fix*: deterministic Arabic/English keyword net before/behind the router call (if the text matches gmail/calendar/tasks/telemetry/launch/brief intent patterns, force the tool verdict — never fall to the chat lane on a bare tool request); log every `_VALID_TOOLS` coercion.
*Refuter consensus notes*: the tier2 degrade itself is documented intent (ADR-18 never-hang), and GatewayError/unparsable paths do log loudly — "silently" is imprecise for 3 of 4 entry paths — but the fabrication consequence stands unmitigated, the system prompt forbids nothing, and free-pool quota exhaustion makes the miss path realistic (gateway fallback walk, `gateway.py:152-207`).

### C-2 ⚠️ CRITICAL — Voice confirmations never consumed (sacred-floor breach)
`src/bot.py:169` (vs the guard at `173-176`)
`on_voice` ends `_spawn_stream(message, bot, text, voice_origin=True)` with no `coordinator.pending_active()` check, while `on_text` consumes pending launch/power confirmations. A spoken «نعم» streams to the brain instead; the pending stays armed for its 10-min TTL (`pc_actions.py:20,51`) and then **hijacks the owner's next affirmative text into a stale launch**. Directly violates CLAUDE.md rule 4 («text/voice-note confirmation in v1.0 … No exceptions») and bot.py's own docstring (lines 8-9).
*Fix*: mirror the 3-line on_text guard in on_voice after transcription succeeds.

### C-3 ⚠️ CRITICAL — Every voice-origin reply delivered twice
`src/bot.py:284-289` (plus `_voice_fail_reply` at 224-229)
The full reply is streamed as a growing text bubble (placeholder → edits → verbatim final), then `voice.synthesize(reply)` sends the identical string (ack included) as a voice note. No config toggle exists; production always wires VoicePipeline. The pinning test (`test_bot_shell.py:394-424`) enshrines the dual delivery as intended — the owner's live report overrides the pin.
*Fix*: voice-origin turns get the voice note ONLY, with a genuine text fallback on synthesis failure (the current except branch only logs — it must resend text); same single-modality choice in `_voice_fail_reply`; update the pinning test.

### C-4 ⚠️ CRITICAL — The ack is glued into every reply, memory, and ledger
`src/dispatcher.py:108` → `telegram_chat_streamer.py:41` → `bot.py:280-283`
`yield ack` makes the router ack the first stream delta; the streamer accumulates it into `pending` (final verbatim edit AND the returned reply = ack+answer, no separator — the test literally asserts «تمام، ببدأسجّلت الموعد بكره» with mid-word fusion); `memory.remember(chat_id, "assistant", reply)` stores the mash in the 50-message buffer, `_persist_exchange` writes it to Daily_Logs, and the voice note reads it aloud again. Every later prompt carries ack-glued pseudo-Arabic as Sara's prior speech — poisoning register and memory quality simultaneously.
*Fix*: treat the first delta as a transient ack (strip from `pending` when the second delta arrives, track separately), or emit the ack as its own short-lived message; assert memory/ledger entries contain only the answer. Must update the enshrining tests (`test_bot_shell.py:90,372-374`).

### C-5 ⚠️ CRITICAL — The router ack is unverified free text with a third-person gateway identity, yielded before execution
`src/dispatcher.py:28,63,69-70,108` (and for launch, `145-146` makes it the final answer)
The router prompt opens «أنت بوابة سارة الأمامية» — the owner's reported «أنا بوابة سارة» line is **verbatim this assigned identity**, not a coincidence. The only guard is `len(ack) > 30`; a 14-char identity line or a 21-char false completion claim («تم فتح الآلة الحاسبة») passes untouched — and for launch intents the ack is the *only* streamed outcome, so the owner can receive a pure hallucinated success the code never verified. «بوابة» appears nowhere else in the codebase — there is exactly one source for this symptom.
*Fix*: code-enforce the ack (fixed list of Jordanian acknowledgment phrases, or reject acks matching claim patterns تم/فتحت/راح/بعت or identity markers بوابة); for `tool=launch` suppress the streamed ack entirely and let the coordinator's audited notification be the sole report; drop the persona sentence from the router prompt (start at «صنّف طلب المالك»).

### C-6 ⚠️ CRITICAL — Google stack cannot load credentials in the documented container deployment; construction-time validation is a lie
`src/bot.py:341-362` + `google_auth.py:217-226` + `Dockerfile:18-21` + `docs/09-ORACLE-DEPLOY.md:107-129`
`GoogleSession.__init__` validates nothing — missing client secret yields an empty `GoogleTokens` object, so the boot-time try/except never fires despite its «missing Google creds degrade to honest offline lines» comment; the first tool call then dies inside `_do_refresh → load_client_secret` and surfaces as the generic TOOL_FAIL_AR apology. The Dockerfile copies no `config/`, and the Oracle compose mounts no volumes while the guide scp's the client secret to the host — `/app/config/google_oauth_client.json` can never exist in-container. The token cache lives under disposable `./vault/State/` (lost on every `--force-recreate` upgrade).
*Fix*: compose volumes for `/app/config` and `/app/vault/State`; one startup probe (e.g. `suite.list_events` 1-day window) so a missing secret lands in the honest `GOOGLE_OFFLINE_AR` branch instead of request-time apologies.
*§14 reconciliation*: on the owner's **local** runtime (where the live symptoms were produced) the container half of this finding does not apply — the local cause is the never-run OAuth bootstrap + possibly the owner-side Google 403; both are documented in §14.

### C-7 MAJOR — Arabic app names can never match whitelist keys; confirmed launches dead-end
`bridge/guard.py:53-56` + `dispatcher.py:38` + `pc_actions.py:123-125` + `executor.py:57,118-120`
Whitelist entries are English .lnk stems ({"name": "calculator", "executable": "calc.exe"}); the router prompt gives no instruction to emit whitelist keys, so «افتحي الآلة الحاسبة» yields arg «الآلة الحاسبة» → not whitelisted → confirmation → after «نعم» the same Arabic name is re-sent → `argv = [Arabic name]` → FileNotFoundError. A wasted confirmation round-trip ending in «البرنامج مش موجود عالجهاز» **even for auto_approve apps**. The round-trip protocol is test-pinned (AC4 stubs `_spawn` with a spy) while the outcome is broken.
*Fix*: alias map (Arabic colloquial → whitelist keys, seedable from the indexer's .lnk display names) applied in `request_launch` before `_send`; reject no-hit names with the honest unknown-app line instead of a doomed confirmation.

### C-8 MAJOR — Rejected/failed confirmations leak a bare «نعم»/«لا» into the chat lane
`src/bot.py:173-177` + `pc_actions.py:84-93,137-138`
`handle_owner_reply` returns None after a rejection and on bridge failure — the bare reply falls through to `_spawn_stream`, and the coordinator's prompts/outcomes (`_BotNotifier.notify`, bot.py:316-317) never enter `memory.remember`. The brain sees [«افتح X» → ack, «نعم»] with zero confirmation context and can hallucinate success — a direct symptom-3 mechanism. Contradicts bot.py's own docstring («answered by the coordinator before the brain ever sees it»).
*Fix*: return a sentinel for consumed pending replies *restricted to bare consent/refusal tokens* (a blanket sentinel would swallow unrelated chat during the 10-min window); record coordinator prompts/outcomes into memory so any fall-through sees the confirmation conversation.

### C-9 MAJOR — Vault 409 retry re-PUTs stale content: concurrent appends silently lose ledger lines
`src/vault.py:212-213,229-235`
`append_section` is a read-modify-write over two GitHub API calls with no lock anywhere in the vault write path; the 409 retry re-PUTs the **same stale-merged content** instead of re-reading. Two rapid messages spawn concurrent `_persist_exchange` tasks (bot.py:304, no queue) → lost exchanges. The 23:50 summarizer widens the window (read → MEDIUM call up to 120s → write) and re-reads the ledger ~20× per evening because `due()` stays true 23:50-24:00.
*Fix*: one `asyncio.Lock` in VaultClient serializing appends; on 409 re-run the whole append (re-read + re-merge + re-PUT).

### C-10 MAJOR — 3 sequential GitHub GETs before every router call: the <250ms ack target is unreachable
`src/bot.py:256-265` + `memory.py:93-95`
`load_long_term` (User_Info, Dialect_Notes, today's ledger) runs three awaited HTTPS round trips **before** `front.handle(...)` — while the router call itself needs none of it. Every reply gains ~0.3-1.5s pre-ack latency; a vault hiccup degrades the whole turn's context.
*Fix*: TTL cache (~60s) on the long-term block — vault content only changes when this process's own writers land; a 3-line memo.

## 5. REFUTED findings (documented honestly)

### R-1 (refuted 2:1) — «Launch outcomes never enter memory or the ledger»
`bot.py:279` — The premise "no record of what actually happened" is false: every launch outcome is durably persisted with audit code and timestamp to the vault's append-only audit ledger (`pc_actions.py:143-152` → `Audit/pc-ledger.md`) and delivered to the owner directly. The ack-only stream is an explicit owner directive pinned by tests («launch notifies the owner direct (audit code, no narration)»). The proposed fix would double-send the notification — reproducing the owner's own dual-message complaint — and reverse an owner-ruled design. *Residual truth (1 refuter kept it)*: `memory.py:93` doesn't load pc-ledger.md, so the *conversation* context lacks launch outcomes — a minor envelope nicety, not a critical defect. Folded into the §8 remediation as an optional context line.

### R-2 (refuted 3:0) — «Registry-absent / registry-exception degrade paths stream context-free answers live»
`dispatcher.py:129-144` — The code shape is real, but neither branch is production-reachable: `run_bot` unconditionally constructs ToolRegistry (its `__init__` cannot raise) and passes it; degraded Google/bridge boots flow through the registry's honest offline lines narrated with results. Only tests pass `tools=None`. Historical interest only: the 09-01 20:25→20:51 window (tools built in `3cd26c1`, wired in `f22283d`) genuinely ran this path — explaining that evening's hallucinations — but the current tree cannot reproduce it. Fixing it would change zero live behavior.

## 6. Hidden Vulnerabilities & Failure Points

### 6.1 Race conditions & async-leak audit (owner-mandated deep dive)

| # | Defect | Mechanism | Anchor | Severity |
|---|---|---|---|---|
| V-1 | **Voice engine: no-timeout hang chain** | No timeout anywhere in the synthesis chain. If Edge-TTS (free service) stalls: `produce()` hangs inside `com.stream()` → stdin never closes → ffmpeg waits for input → `proc.stdout.read()` awaits forever → the caller's `synthesize()` (`b"".join(async for ...)`) hangs permanently → **orphaned asyncio task + orphaned ffmpeg process + leaked pipes, repeated per voice message** (the bot survives; the handler leaks). | `voice.py:89-151` (coordinator's own analysis) | major |
| V-2 | **Voice engine: stderr pipe deadlock** | `stderr=PIPE` but stderr is read only in the failure path AFTER `proc.wait()`. If ffmpeg writes >64KB to stderr before exiting (chatty failure on corrupt input), it blocks on the pipe write → `wait()` never returns → the consumer hangs in `stdout.read()` — classic subprocess deadlock, no exit. `-loglevel error` keeps it rare in practice. | `voice.py:96,133,150` (coordinator's own analysis) | major |
| V-3 | **Cancel sets an Event, never cancels the task** | The owner's interjection raises `cancel.set()` only — the old stream task keeps running: old + new streamers interleave edits on one chat (the "randomly growing" text), and the abandoned turn still fires its late `voice.synthesize(partial)` after the next turn began — a delayed voice note from a previous context. | `bot.py:180-182` (axis 3/4 finding) | major |
| V-4 | **Concurrent persist tasks, unlocked read-modify-write** | One fire-and-forget `_persist_exchange` task per exchange, no queue/lock → C-9's lost lines; `run_bot`'s finally never gathers `_PERSIST_TASKS` → in-flight exchanges dropped when `vault.aclose()` closes the session under them; failures logged without the error object. | `bot.py:292-306,391-394` | major |
| V-5 | **Summarizer window races the writer** | read → MEDIUM (120s timeout) → write against the same note `log_exchange` appends to; idempotence is a substring check on the whole body — any owner message containing «ملخص محادثة اليوم» permanently suppresses that day's summary. | `memory.py:211-252,229` | minor |
| V-6 | **Failed/error turns never remembered** | Both except blocks and the empty-reply branch return before `remember()` — after an apology turn, Sara has no idea what was asked. | `bot.py:268-281` | minor |
| V-7 | **Bridge single-session check** | Verified race-FREE: no await between the `self._session is not None` check and the assignment — atomic in the event loop. (Documented as clean, not a defect.) | `bridge_server.py:91-100` | — |
| V-8 | **telemetry.state blocks the daemon loop** | `live_state()` runs synchronously on the event loop (`time.sleep(0.15)` + two psutil sweeps) — violates the 100%-async rule; stalls the tunnel ~0.5-2s per request. Fix: `asyncio.to_thread` (the pattern `send_wol` already uses). | `daemon.py:134-136` | minor |
| V-9 | **Unbounded in-memory security_log** | `security_log: list[str] = []` with appends and no cap on a public endpoint; token comparisons are plain equality (not constant-time); no auth rate-limiting. Low practical risk (32-byte token) — hardening. | `bridge_server.py:26,37,83-96` | minor |
| V-10 | **Orphaned detached process transports** | Successful launches never close the subprocess transport (fire-and-forget spawn) — handle accumulation on the Windows proactor loop, one per launch; «شغّلت X» is reported on spawn alone with no liveness check (a crashed exe is ledgered as 'executed'). | `executor.py:59,118-127` | major |
| V-11 | **Daemon redials forever on persistent auth rejection** | No give-up cap, no owner-visible alert — a misconfigured token spins reconnection indefinitely (bounded 30s backoff, so no tight spin, but silent). | `daemon.py:56-65` | minor |

### 6.2 Security-relevant gaps

| # | Gap | Anchor | Note |
|---|---|---|---|
| S-1 | `open_path` blocked-suffix list omits ShellExecute-executable types (.lnk, .url, .jar, .hta, .html); absolute paths accepted on ANY drive (the only check is `not is_absolute() and ".." in parts`); relative paths resolve against the daemon CWD | `executor.py:39,103,129-130` | Major; currently unreachable from production (core never sends `exec.open`) — the hole is one wiring change from live. The module's own docstring says opening a .lnk IS launching it. |
| S-2 | Daemon accepts ANY non-empty `confirmation_id` — never verified against the vault-persisted confirmation note; the sacred floor tests only the None/empty case | `executor.py:55` | The stated rule-4 model («recorded confirmation ID persisted to the vault») is enforced core-side only; a compromised core can mint arbitrary ids. |
| S-3 | Public WSS accepts upgrades at ANY path (no /bridge enforcement); daemon dials whatever scheme `BRIDGE_SERVER_URL` holds — plaintext `ws://` crosses the token unencrypted with no warning | `main.py:25-28`, `daemon.py:68` | TLS is Caddy's job per docs/09 §7 — this is the code-level guard missing behind it. |
| S-4 | Consent grammar: any sentence whose FIRST token is affirmative confirms («نعم بس استنى» executes) | `common/consent.py:29` | Weakens the confirmation floor (coordinator-level). Fix: standalone-affirmative requirement (≤3 tokens, no negation words). |
| S-5 | `is_system_path` filters only `C:\Windows` — UNC/other-drive .lnk targets pass with `auto_approve: True`; line-count mismatch in the indexer warns then still zips (names can bind to wrong targets) | `app_indexer.py:124,175-181` | Requires prior Start-Menu write access (PC already compromised) — minor, contained. |
| S-6 | Indiscriminate whitelist: 156 Start-Menu entries ALL `auto_approve: true` hollows the whitelist's practical strength; the `category` field on every entry is read by nothing | `app_indexer.py:147`, `guard.py:43-72` | Owner-side pruning recommendation in §8. |

### 6.3 Error-swallowing points (honesty gaps)

- `bot.py:341-362` — the Google blanket degrade (C-6): one warning line for a whole subsystem going dark.
- `tools.py:55-59` — `ToolRegistry.call` swallows every handler exception into the generic apology, masking OAuth/permission causes (the owner cannot distinguish config failure from outage).
- `bot.py:297-302` — persist failures logged without the exception object; `voice_out` failure logged as «text reply already delivered» even on voice-origin turns where it hadn't been.
- `gateway.py:243-245` — SSE tail-truncation silently drops the final partial delta (untested shape).
- `vault.py:193` — no 403/429/Retry-After handling: a rate-limited evening permanently drops exchanges with zero distinct diagnostics.
- `bot.py:132-133` — the unenrolled static ack's comment says «static ack only» but there is no `return`: flow continues to full processing (comment-code lie).

### 6.4 The dead-weight inventory (what the live bot cannot reach)

**Ground truth**: `run_bot` starts exactly ONE background loop (the summarizer). Everything else below is unreachable from the production assembly.

| Module / feature | Lines | Kept alive by | Verdict |
|---|---|---|---|
| `src/expansion.py` (M4 CapabilityScheduler, parse_nl_cron, 20-name reserved table) | 407 + 265 test | tests only | Delete or wire — no awaiting directive |
| `src/skills/evening_journaler.py` | 258 + tests | tests only | **Wire it** (owner-commissioned, rule 6) — one `create_task` |
| `src/daily_brief.py` schedule half (render/fire_if_due/fire_once/run_forever) | ~90 | tests only | **Wire it** (BRIEF_ENABLED promises it) — one `create_task` |
| `src/gmail.py` polling half (run_gmail_poll, fetch/seen-state, users.watch) + `email_triage.py` TriageDispatcher | ~160 | tests only | Wire (triage pushes) or strip to peek-only — owner decision |
| `src/summary.py` + `src/skills/social_graph.py` + `src/vault_expand.py` (sprint-3 orphan trio) | ~500 + ~1,420 test lines combined | tests only | Delete (zettel_link/commit_files lose their last consumers with them) |
| `src/syllabus.py` + `src/tutor.py` + **pypdf** (a production dependency serving only dead code — ships in the Docker image) | 360 + tests | tests only | Delete + drop the dependency |
| `src/pc_actions.py` request_power/handle_idle_choice + POWER_ARGV + guard.check_power + executor.power + daemon 'power' branch + wol branch + `bridge/idle.py` IdleMonitor + LanServer token/provider wiring + `target_pc_*` config | ~80 + ~180 | tests only | The whole idle/power/WoL cluster: wire or delete — currently RUNBOOK §5's idle-offer cannot fire and docs/06's Bearer telemetry table describes a route that 404s (provider=None) |
| `src/skills/social_enrollment.py` VoiceprintRegistry — 6 of 9 methods (the multi-speaker contact lifecycle) | ~140 | tests only | Keep match_vector; decide on the pending-speaker verdict UX |
| `config/agents_config.json` | 1.5KB | NOTHING (zero code consumers) — and stale: pins retired Gemini models + SanaNeural, contradicting live `.env.example` | Delete outright (misleading audit surface) |
| `src/config.py` dead knobs: telegram_api_id/hash/session_string, obsidian_rest_*, target_pc_*, idle_shutdown_minutes; `.env.example` GOOGLE_CLOUD_PROJECT (not even a Settings field) | — | declarations only | Prune or move to a 'planned' comment block |
| `GoogleSuite` 4 of 6 methods (drive/contacts/create_event/add_task) + the 2 OAuth scopes requested solely for them | ~60 | dead callers (syllabus only) | Drop the scopes (least privilege) even if methods stay for v1.1 |
| `memory.build_messages` (tested envelope builder) vs dispatcher's inline `_plain_messages` re-implementation | — | tests only | One envelope builder — drift between the tested and the running copy is a latent bug surface |
| Duplicated micro-helpers: 2× `_json_array`, 2× identical `\{.*\}` LLM-JSON regexes, 3× `_fernet`, 2× enums named `Tier` (brain vs mail — forces alias imports), 3× tick-loop pattern | — | — | One shared `parse_llm_json`, one crypto helper, rename MailTier |

### 6.5 Config & dependency bloat

- `config/whitelist.json`: 30KB / 156 entries / all auto_approve (146 executables exist on this machine; 125 default-bucketed "Productivity") — a real allowlist is 5-10× smaller; `category` metadata read by nothing.
- Dependencies verdict: torch/speechbrain heavy-but-justified (sacred rule) **and correctly lazy** (import inside `_embed_sync`/`_load_model`; nothing module-level) — but **inert in production because the owner never enrolled** (no `State/owner_voiceprint.enc`; every voice note takes the unenrolled trust path — §14); faster-whisper lazy + justified; **pypdf serves only dead code**; everything else right-sized.

### 6.6 The frozen Path A voice upgrade (context for the acoustic plan — it is ON DISK, gate-green, uncommitted)

The working tree contains the fix set for the owner's live «صوت رديء» complaint, delivered through the closed loop before the audit froze it: Opus 24k/voip → **64k/audio-mode** (`voice.py` FFMPEG_ARGS), `shape_for_tts()` dialect shaper (emoji strip + 10-word seed pronunciation lexicon + تسكين الأواخر, shadda preserved; never-blocking), voice pin `ar-JO-SanaNeural` → `ar-EG-SalmaNeural` (switchable via `VOICE_NAME`), injectable clock in ToolRegistry (the date-rollover test bomb). Gate: 355 passed / 1 skipped / 85.71%. Commits staged in three conventional slices (`feat(voice)`, `fix(tools)`, docs sync) but **NOT committed — owner order**. Note: `.env.example`'s committed pin now says Salma while CLAUDE.md rule 1 still says Sana — doc lag resolved in the same docs commit when Path A lands.

## 7. Test-suite validity vs mock illusions (owner-mandated deep dive: «are the 347-355 tests real behavior or fake-asserting-fake?»)

### 7.1 What the suite genuinely pins (credit where due)

- **Sacred floors are real behavioral pins, not trivia**: `test_owner_middleware.py:17-32` proves a stranger update produces literally zero outbound methods through the real middleware+dispatcher; `test_whitelist_guardrail.py:136-238` runs the real Guard+Executor with spied OS edges (fail-closed on corrupt JSON, RefusedOrigin for llm_output/email origins, power-always-confirm even when the whitelist flag lies); `test_guest_lockdown.py:38-77` proves a guest voice yields one SendMessage, zero gateway calls (breach-asserting spy), zero subprocess, exactly one sealed staging note.
- **HTTP is treated as a system edge, honestly**: `httpx.MockTransport` drives the *real* OmniRouteClient SSE parser (`test_omniroute_gateway.py:80-239`), the *real* GoogleSession refresh logic (`test_google_clients.py:106-199`), and the real VaultClient Git-Data flow (`helpers_vault.py:19`).
- **The WSS bridge pair runs over real websockets on loopback** (`test_bridge_protocol.py:44-103`) — the outbound-only structure is asserted (`:84-88`).
- **ffmpeg encode/decode is real where marked** `needs_ffmpeg` (audio stream opus tests, the new 64k/audio-mode regression guard).

**Verdict on the mock-illusion question**: the 355 green tests are a *mix* — roughly: the unit seams under HTTP/WSS/ffmpeg boundaries are genuine behavioral contracts; the shell layer (bot-level) contains the illusions catalogued below; and the composition root is dark. The number "355 passed" certifies plumbing and module contracts, **not** end-to-end behavior against real models or the real Telegram wire.

### 7.2 The mock illusions (ranked by damage)

| # | Illusion | Damage |
|---|---|---|
| M-1 | **The suite enshrines the live defects as intended behavior.** `test_bot_shell.py:90` asserts the ack-glued final text «تمام، ببدأسجّلت الموعد بكره» (mid-word fusion!) as CORRECT; `:372-374` asserts the glued string entering rolling memory as Sara's turn; `:394-424` pins the dual text+voice delivery. The tests that "verify" the owner's complaints were built to *require* them. | Any fix for symptoms 1/2/3 must first change the pinned contract — the suite actively defends the defects. |
| M-2 | **Shell tests assert the values their own fakes injected.** `router_replies` script the classification: «تمام، ببدأ» in edits[0] proves plumbing, never routing reliability. Every router-drift live symptom (jargon acks, identity bleed, tool misclassification) is structurally invisible to the suite. | The exact class of live failure the owner reports cannot be caught by any current test. |
| M-3 | **`RecordingSession` breaks the real download chain** (returns `True` for non-send methods, `stream_content` raises NotImplementedError), so all five voice-path tests monkeypatch `bot.download` — the production `_download_voice` wire path (expired file_id, 429, partial chunks) has zero coverage. | A regression in the most-used production path (every owner voice note) surfaces only live. |
| M-4 | **The composition root is 0%-covered**: coverage arcs stop at `bot.py:320` — `run_bot` (320-395, the most integration-dense function in the codebase, including the C-6 blanket degrade) is never invoked by any test; `main.run`'s non-health path likewise. | The 85% branch threshold aggregates unit seams while the place where all failures actually happen is dark. This is why the gate reads green in the exact state that produced the live symptoms. |
| M-5 | **The 64k/audio-mode regression guard (the direct fix for the live voice complaint) is skipif-guarded** and CI never installs ffmpeg — on an ffmpeg-less runner the newest live-fix verification silently vanishes. Inconsistently, two biometric/transcriber tests invoke ffmpeg WITHOUT the mark (hard-fail instead of skip). | A regression to 24k/voip could pass the whole gate as "skipped". |
| M-6 | Trivia tail: `test_scaffold.py:10` asserts a constant against itself (16 == 16); `test_vault_dirs.py:81` pins pyproject strings; the floors test only 2 of 6 update-event shapes. | Inflates the green count without pinning invariants (small, but real). |

### 7.3 Untested critical edges (the holes a real model/network will find)

1. **Router tool-verdict trust** — no test feeds an invalid tool name (the silent `"none"` coercion); no test of `route="direct"` + `tool="launch"` (the tool lane runs *before* any route check); nothing but a prompt stops a drifted real model from emitting `{"tool":"launch"}` for casual chat, auto-executing any whitelisted app with origin hardcoded `"owner_chat"`. This is the unguarded back of symptom 3.
2. **Google refresh timeout/5xx mid-conversation** — `_do_refresh` has no failure branch of its own; only clean 401→refresh→retry paths are tested.
3. **Arabic presentation forms (U+FB50-FEFF)** bypass both the shaper's `_ARABIC_CLASS` and the harakat regex — no NFC/NFKC normalization anywhere in `shape_for_tts`; zero test cases. Mobile-keyboard/paste input silently skips the entire dialect shaper.
4. **Gateway SSE EOF mid-JSON-line** — the tail delta is silently dropped (skip path untested for the truncation shape).
5. **Zero/None-duration voice notes** — fixtures always carry `duration=2`; the defended `or 0` branches are dead-untested.
6. **PowerShell escaping under hostile/Arabic .lnk names** — the only real-shortcut test is ASCII «Tiny Target App»; the line-count-mismatch branch (wrong name→target binding) is uncovered.

## 8. Acoustic & Persona Remediation Plan (owner-mandated: authentic female Jordanian persona, human feel)

### 8.1 The persona contract (code-enforced, not prompt-hoped)

1. **Ack personality** (fixes C-5 at its root): replace the generated ack with a fixed pool of Sara-voice Jordanian acknowledgments («من عيوني»، «تمام هسا»، «على Wool») or code-filter: reject any ack containing identity markers (بوابة، مساعد، روبوت، بوت، خدمة) or claim verbs (تم، فتحت، ربحت، بعت، رح) → substitute `DEFAULT_ACK_AR`. Drop the «أنت بوابة سارة الأمامية» sentence from the router prompt entirely (it should never speak of itself).
2. **Extend `SYSTEM_PROMPT_AR`** (currently 3 sentences that forbid nothing): speak ALWAYS as سارة, first person feminine (جاهزة، بقدر، رح أعمل); never identify as a gateway/program/bot/assistant; never customer-service register (كيف يمكنني مساعدتك، يسرني خدمتك، أعدك بأن); **never claim an action succeeded unless a tool result in THIS turn confirms it**; tease procrastination, empathize under stress, firm when urgent (the rule-5 friendship register).
3. **Fix the hardcoded lines** (they are Sara's voice too): «لسأ أعالجها» → «لسا»؛ «سمسعتك» → «سمعتك»؛ «انسمعت» → «سمعت بصمتك»؛ «وهسا القريب من الميك» → rewrite; EMPTY_REPLY_AR support-desk phrasing → Sara's register. These strings also feed TTS — garbled text reads as garbled speech.

### 8.2 Single-modality delivery (fixes the dual-modality collision family)

4. Voice-origin turns → **voice note only** (text fallback on synthesis failure — the except branch must actually resend text). `_voice_fail_reply` likewise. `/start` → one modality (voice greeting + one-line caption, drop the duplicated identity clause). Delete the stray unenrolled VOICE_ACK_AR (the front-door ack replaced it — and fix the comment-code lie by adding the missing `return` or removing the send).
5. Interjection cancel → actually `task.cancel()` the previous stream (fixes V-3: interleaved edits + late voice notes of stale partials).
6. Ack as transient (fixes C-4): strip from `pending` when the answer starts; memory/ledger store the answer only.

### 8.3 The acoustic ladder (what remains after the frozen 64k/audio + shaper + Salma tree)

7. **Whisper tuning** (upstream of everything — fixes «كفيك» at its source): `language="ar"`, `beam_size=5`, `initial_prompt` built from the dialect lexicon + owner name; injectable via the same Dialect_Notes load.
8. **Wire the dialect loop** (one-line-ish, high value): pass parsed Dialect_Notes into `shape_for_tts(notes=...)` at synthesis time; wire `dialect.learn` into the persist path so «تعلمي:» corrections actually land; fix the frontmatter/body mismatch (`load_long_term` reads the body; `append_notes` writes the frontmatter) — currently the loop is dead end-to-end.
9. **Extend the seed lexicon**: + the ~20 highest-frequency Jordanian particles (مش، مو، وين، راح، خلص، زلمة، شوفي، كفيك…) + an Arabic-reading map for Latin app names (Chrome, Calculator) that narrations will contain.
10. **NFC normalization** at the top of `shape_for_tts` (presentation-form input currently bypasses the whole shaper) + presentation-form test cases.
11. **Prosody tuning by ear**: rate/pitch are pinned +0%/+0Hz; typical warmth tweaks for Salma-class voices are rate ≈ −4%, pitch ≈ −2Hz — generate an A/B set through the real pipeline, pick, and pin in `.env`. Document that ar-JO offers only Sana (the rejected voice) — Salma is the accepted ceiling inside the free stack.
12. **Voice TTFT**: synthesize from the delta stream (or at the first completed sentence) instead of after the full reply lands — currently the voice note waits out the entire model latency.
13. **Long narrations**: `MAX_TTS_CHARS=4000` raises and the caller swallows — truncate with a spoken closing («والباقي بالنص») or chunk into sequential notes; a voice-origin owner must never silently lose the voice modality.
14. **The model-lane honesty rule** (critic's residual, §13): tier2 verdicts, the unparsable default, and minimax quota fallback all stream user-facing Arabic prose through gpt-oss-120b — violating the settled «gpt-oss never user prose» brain-role ruling and plausibly the systematic source of register/gender drift. Options: force tier2 direct-chat back through the FAST model (only depth passes to MEDIUM's *internal* work), or accept and document. **Owner ruling needed.**

### 8.4 What would make Sara feel human (beyond correctness)

15. **Emotional continuity**: carry a lightweight mood/state line in the envelope (last mood, open threads) so empathy persists across turns instead of resetting.
16. **Proactive life**: wire the evening check-in (rule 6) and morning brief — a Sara that initiates contact once a day reads as a person; one that only reacts reads as a tool. (One `create_task` each — §9.)
17. **Voice-note-back with the owner's chosen personality** — after enrollment completes, a natural voice reply chain (single modality, Salma, tuned prosody, dialect-shaped) is the single biggest perceived-humanity jump available inside the $0 stack.
18. **Memory that shows itself**: tail-slice User_Info (recent facts visible), load yesterday's summary into the envelope — the "she remembered" moments are what the owner experiences as a person, not a bot.

## 9. Prioritized Surgical Action Plan (zero speculative fluff)

### Phase 1 — Breaches & Persona (each: red test → green → gate → commit → push, closed loop)

| # | Action | Fixes | Effort |
|---|---|---|---|
| 1.1 | Voice-confirmation guard in `on_voice` (mirror on_text's 3 lines after transcription) | C-2, rule 4 | XS |
| 1.2 | Ack content guard + router prompt identity drop (+ suppress streamed ack on launch) | C-5, symptom 1 | S |
| 1.3 | Ack-as-transient in ChatStreamer (strip from final/memory/ledger) + update the enshrining tests | C-4, symptoms 1/2/4 | S |
| 1.4 | Voice-origin single-modality + real text fallback + /start single-modality + delete stray VOICE_ACK_AR | C-3, symptom 2 | S |
| 1.5 | Interjection cancel = real task.cancel() | V-3, symptom 2 | XS |
| 1.6 | Persona prompt rewrite (8.1.2) + hardcoded-line corrections | symptom 1 | S |
| 1.7 | Consent grammar: standalone-affirmative only | S-4 | XS |
| 1.8 | **Commit the frozen Path A tree** (feat(voice) + fix(tools) + docs sync) — the acoustic base everything above stands on | §6.6 | XS (work done) |

### Phase 2 — Tool Execution Wiring

| # | Action | Fixes | Effort |
|---|---|---|---|
| 2.1 | Deterministic keyword net (force tool verdict on intent patterns; never fall to chat on a bare tool request; log coercions) | C-1, symptom 3 | S |
| 2.2 | Anti-fabrication clause in the system prompt (never claim an action succeeded without a tool result this turn) | C-1 defense-in-depth | XS |
| 2.3 | App alias map (Arabic colloquial → whitelist keys; no-hit → honest unknown-app line) + `shutil.which` pre-check | C-7, symptom 4 | S |
| 2.4 | Launch liveness check + transport close (bounded grace-window check; downgrade to honest failure) | V-10 | S |
| 2.5 | Confirmation sentinel (bare consent/refusal tokens only) + coordinator prompts/outcomes into memory | C-8 | S |
| 2.6 | Google stack: startup probe + per-dependency degrade + boot message naming what's offline; **owner-side first: run the OAuth bootstrap once** (§14 — the live machine has no token cache at all) | C-6, symptom 3 | S |
| 2.7 | Container deploy fix: compose volumes for config/ + vault/State | C-6 | S |
| 2.8 | `asyncio.to_thread` for daemon telemetry; VaultClient lock + 409 re-merge-retry; persist-task gather on shutdown | V-8, C-9, V-4 | S |
| 2.9 | Voice engine: overall `asyncio.timeout` (~30s) around synthesis + stderr drain task | V-1, V-2 | S |
| 2.10 | Vault rate-limit handling (403/429 + Retry-After, one retry) | §6.3 | XS |

### Phase 3 — Pruning & Optimization (owner decisions embedded — several "orphans" are owner-commissioned features awaiting one line, not YAGNI)

| # | Action | Type | Effort |
|---|---|---|---|
| 3.1 | **Wire, don't delete**: `asyncio.create_task` for EveningJournaler + BriefComposer.run_forever (+ decide on run_gmail_poll) — three owner-promised features, one line each | activate | XS×3 |
| 3.2 | **Delete**: `config/agents_config.json` (zero consumers, actively misleading); `src/expansion.py` + test; sprint-3 trio (`summary.py`, `social_graph.py`, `vault_expand.py`) + tests; `syllabus.py` + `tutor.py` + tests + **pypdf from requirements** | prune | S |
| 3.3 | Decide per cluster: idle/power/WoL (wire with a 'power' tool verdict + LanServer token/provider, or delete the ~260 lines + 3 config keys + docs/06 table) — either beats shipping both code and docs for an unwired feature | decision | M |
| 3.4 | Config hygiene: prune dead Settings knobs + matching .env.example/conftest keys; drop drive/contacts OAuth scopes | prune | S |
| 3.5 | Long-term TTL cache for `load_long_term` (~60s) — kills 3 GitHub GETs per turn | C-10 | XS |
| 3.6 | Memory visibility: tail-slice User_Info; load yesterday's summary; remember user turns before early returns | symptom 4 | S |
| 3.7 | Consolidate duplicates: one `parse_llm_json`, one `_fernet`, `MailTier` rename, one envelope builder (delete `build_messages` or route through it) | refactor | S |
| 3.8 | Reconcile the two vaults: journaler ledger + contact dossiers through VaultClient (ADR-15 invariant); ./vault strictly for seals/cache | architecture | M |
| 3.9 | Test suite honesty: un-pin the defect-asserting tests (M-1); RecordingSession serves GetFile + stream_content (then delete the 5 bot.download monkeypatches); a boot-level run_bot test (healthy + raising Google stack); CI installs ffmpeg; NFC presentation-form shaper tests; invalid-tool-name + direct+launch verdict tests | M-1..M-4, §7.3 | M |
| 3.10 | Track `scripts/omniroute/` (or vendor it) — fresh clones currently cannot build the image; add an image build to CI; kill or repoint the keepalive workflow; extend `/health` with vault-token + Google probes | §13 probes | S |
| 3.11 | Security hardening batch: constant-time token compares, bounded security_log, auth rate-limit, /bridge path enforcement, ws:// scheme warning, executor confirmation-id → vault-note verification, open_path suffix/roots fix | S-1..S-3, S-6 | S |

**Sequencing rule**: Phase 1 lands before any live retest (it changes what the owner sees and hears); Phase 2.6's owner-side OAuth bootstrap can start today in parallel; Phase 3.1 (three create_tasks) rides with Phase 1's commit train. Everything follows the closed loop — red test first, `make gate`, docs in the same commit, push to main.

## 10. Improvement proposals — usability & maturity (owner-requested)

**Usability**
- `/status` command: which lane is live (bridge, Google, vault, brain pools) in one Arabic line — surfaces C-6-class silent degrades to the owner instantly instead of request-time apologies.
- `/cancel` command + real stream cancellation (V-3) — the owner's only current recourse is a new message.
- Single-command everything: `sara.bat` exists; document the one command + one-time OAuth bootstrap as THE setup path in RUNBOOK (currently the client-JSON step points at the retired worktree — fix the runbook line).
- Confirmation UX: include the app name + what will happen in the prompt; report honest unknown-app names instead of doomed confirmations (C-7).

**Maturity**
- The envelope budget: cap total envelope chars (today only counts are capped — 3×1600 + 50 messages can reach 30-40k tokens on tutoring days); dedupe today's ledger head vs the newest history turns (currently duplicated).
- Restart-safe short-term memory: seed the rolling buffer from today's ledger on boot (the data already exists).
- `due()` gate fixes: once-per-evening summarizer trigger; heading-line idempotence match (the substring poison bug).
- Health/keepalive truthfulness (3.10) so ops read what the owner actually experiences.

## 11. The audit round in numbers

80 raw findings → 80 unique (dedup by file:line) → top-12 adversarially verified → **10 CONFIRMED, 2 REFUTED** + 68 evidence-cited passthrough (severity-ranked, flagged) + 7 critic probe areas + 2 symptom residuals → this report. Axis verdicts: tool-lane 10 findings; persona-acoustic 18; memory-vault 15; bloat-yagni 18; bridge-security 10; test-validity 12. Zero agent errors; every effort level pinned max/high explicitly (the GLM provider rejects xhigh — operational note for future runs).

## 12. Full passthrough findings index (severity-ordered quick reference)

**Major (unverified)**: open_path bypass classes (`executor.py:109`) · launch liveness/handle leak (`executor.py:65`) · idle/power/WoL cluster dead (`bridge/__main__.py:21`) · dead background loops ×3 (journaler/brief/gmail-poll) · dialect loop dead end-to-end (`voice.py:79`) · expansion/syllabus/tutor/orphan-trio/pypdf dead modules ×4 · User_Info head-slice (`memory.py:105`) · today-only envelope (`memory.py:93`) · split-brain vaults (`bot.py:95`) · run_bot 0% coverage (`bot.py:320`) · shell enshrines glued text (`test_bot_shell.py:90`) · RecordingSession download break (`conftest.py:205`) · router-verdict trust untested (`dispatcher.py:109`) · VoiceBiometricRegistry dead lifecycle (`social_enrollment.py:70`).

**Minor (unverified)**: ChatStreamer dangling «…» placeholder on empty streams · summary substring poison (`memory.py:229`) · persist-failure logging + shutdown gather (`bot.py:297-391`) · failed-turn amnesia (`bot.py:276`) · vault 403/429 no-retry (`vault.py:193`) · telemetry sync block (`daemon.py:136`) · constant-time/bounded-log/rate-limit (`bridge_server.py:86`) · any-path upgrade + ws:// dial (`main.py:27`) · is_system_path UNC + mismatch-zip (`app_indexer.py:124`) · ffmpeg skipif CI hole (`helpers_voice.py:14`) · SSE truncation shape (`gateway.py:244`) · NFC shaper bypass (`dialect.py:77`) · refresh-timeout untested (`google_auth.py:283`) · PS escaping untested (`app_indexer.py:153`) · executor id-trust (`executor.py:55`) · duration=0 fixtures (`conftest.py:245`) · tautology tests · dead config knobs · agents_config.json · whitelist category metadata · consent first-token (S-4) · power unreachable · GoogleSuite dead methods/scopes · build_messages dead · micro-helper duplicates · gmail 2-day window vs «كل شي مقروء» honesty (`tools.py:21`) · MAX_TTS_CHARS swallow (`voice.py:82`) · sequential voice TTFT (`bot.py:286`) · +0%/+0Hz prosody pins (`config.py:73`) · seed lexicon 10 words (`dialect.py:80`).

## 13. Completeness critic — the gaps no axis claimed (next-round lead list)

1. **The tier2/fallback model-lane honesty residual (symptom 1's unexplained half)**: tier2 verdicts, the unparsable-router safe default, and minimax quota fallback all hand user-facing Jordanian prose to `groq/openai/gpt-oss-120b` (`dispatcher.py:43-47,87,113-116`; `.env` FAST_MODEL_FALLBACKS; OpenRouter free pool 50 req/day makes the fallback path routine). This violates the settled ruling «FAST talks / MEDIUM works / HEAVY deep; gpt-120b never user prose» (memory pins `22d3396`). An English-centric model writing Sara's first-person feminine Jordanian prose is the most plausible mechanical source of the systematic register/gender drift no finding claimed. **Needs an owner ruling** (§8.3.14).
2. **Live-runtime attribution (symptom 3's local half)**: the confirmed C-6 describes the Oracle container — but the live symptoms came from the LOCAL runtime where config/ exists and `./vault/State/` is **empty**: the OAuth bootstrap has never been run (`10-CHECKPOINT.md:54` lists it as carry-over with a pending owner-side Google 403 fix), and RUNBOOK §6's bootstrap step points at the retired worktree. Before any Gmail retest: run the bootstrap once, fix the runbook path.
3. **The flagship security layer is inert in production**: no `owner_voiceprint.enc` — the owner never enrolled, so ECAPA/torch contributes zero live protection and Guest-Mode biometric lockdown can never trigger. Enrollment is a 2-minute owner action that activates the heaviest installed dependency (§14 owner checklist).
4. ChatStreamer dangling placeholder: zero-delta streams leave the «…» bubble stuck while EMPTY_REPLY_AR arrives as a second message.
5. Deploy/infra: keepalive workflow pings a decommissioned HF Space (or fails red every 10 min); the Docker build is broken-by-clone; CI never builds the image.
6. `/health` blindness (vault token + Google stack unprobed).
7. The audited runtime ≠ CI-certified runtime: the working tree (live) is 8 files ahead of HEAD (green CI certifies yesterday's code).

## 14. Owner checklist (what only you can do — 10 minutes total)

1. `/enroll-voice` in Telegram + one voice note — activates biometrics (currently every voice note runs on middleware-only trust; also removes the stray pre-enrollment ack surface).
2. Run the Google OAuth bootstrap once (the token cache has never existed on this machine) — then Gmail/Calendar/Tasks live. If it 403s, that's the known owner-side Google project block (from sprint 1), fixable in the Google console.
3. Say «التالي» to unfreeze Path A (commits + docs sync are staged and ready) — the acoustic base of everything in §8.
4. Ruling needed (§8.3.14): should tier2/degraded prose route back through the FAST model (keeping gpt-120b out of user prose), or accept the fallback writing Sara's words?
5. Ruling needed (Phase 3.3): wire or delete the idle/power/WoL cluster.
6. After Phase 1 lands: re-run `sara.bat` and retest — voice note (single modality now), text turn (no glued ack), a launch by its Arabic name, a Gmail check.

---

## Appendix A — Session context this report preserves (everything discussed, per owner order)

- **The voice saga (2026-09-02)**: live complaint «رديء جداً وغير بشري وغير عربي» → root causes found by code+file forensics: 24kbps voip-mode Opus, emoji passed to TTS (👋 in the greeting), Microsoft G2P forcing MSA tanween on unvocalized dialect, Sana's Jordanian training-data ceiling → 6-voice A/B set generated to `D:/Downloads/sara-voice-samples/` (Sana 64k/24k, Layla, Salma, Zariyah, AvaMultilingual) → owner: «Ava أفضل لكنها لا تنطق بشكل صحيح أبداً» → Path A (free Microsoft stack) approved over ElevenLabs (breaks $0: free 10k chars/mo ≈ 10 min audio) → implemented through the closed loop (red `3fe13ea` → green tree, 355 gate) → **frozen uncommitted by the audit order**.
- **The 2026-09-01 live-debug arc**: no memory on direct chat (envelope never reached any model on the most common path — fixed `ab40440`); minimax wrote a wrong answer INTO the ack (fixed `ca1b065`, MAX_ACK_CHARS=30); silent 6s voice note left the owner with static acks (fixed `ca1b065`, EMPTY_VOICE_AR + `_voice_fail_reply`); rolling buffer 15→50; duplicated/stale processes cleared via the fixed `sara.ps1` launch (base64 precompute fix `19aff81`).
- **Model history**: Gemini 403-retired (Google blocks the project at API level) → 7-candidate bake-off → owner-set roles: minimax = Sara's exclusive voice, gpt-oss = worker (never prose), nemotron = tool master. **DeepSeek V4 Pro offer assessed, nothing stuck**; two candidates await owner rulings (conversation-lane quality, Jordanian pronunciation lexicon drafting). Harness stays GLM-only.
- **Deferred**: Oracle deploy (bank card blocked), dormant skills activation, v1.1 acoustic intelligence roadmap (committed `ea011ce`: diarization, affective context, paralinguistics, PyTgCalls).
- **Operational lessons for future orchestration** (this audit run): GLM free rejects `xhigh` effort (pin max/high explicitly); 8 req/min — 6-wide bursts need retry headroom or the 429 storm kills agents; two agents stalled 1h48m on a background permission prompt (the "always allow" ruling fixed it); workflow resume-from-cache saved 45+ minutes twice.

*Report generated by the 2026-09-02 forensic audit (43 agents + coordinator synthesis). Read-only audit: no source file was modified — the only file created is this report. Repairs start only on the owner's explicit go.*
