# EXHAUSTIVE SYSTEM AUDIT REPORT — Vantrilex Assistant OS (Sara)

- **Baseline**: commit `1116de6`, **1,385 tests green**, 2026-09-14.
- **Method**: three parallel forensic tracks (subagents) + independent verification of every load-bearing claim by the lead (counts re-measured in-process, all 35 cited test names grepped, drift lines re-read). Two agent errors were caught and struck (see §5).
- **Scope**: `src/`, `bridge/`, `04_Resources/`, `scripts/`, `benchmarks/`, `tests/`, `docs/`, `config/`. Read-only; zero code touched.
- **Registry totals (measured)**: 45 `ToolRegistry` handlers · 44 `_VALID_TOOLS` entries (incl. `none`) · 44 `_TOOL_NET` entries · 41 capabilities · 44 skill guides · 6 irreversible tools.

---

## Track 1 — Forensic scan: registry cross-matrix

Handler (`src/tools.py`) × valid (`dispatcher._VALID_TOOLS`) × net (`dispatcher._TOOL_NET`) × capability (`capabilities.TOOL_CAPABILITIES`) × audit prompt (`audit_harness.PROMPTS`) × guide (`sara_tool_skills._SKILLS`).

41 of 45 handlers are present in all six registries (including all four `openclaw_*`). The four exceptions:

| Handler | Valid | Net | Capability | Prompt | Guide | Verdict |
|---|---|---|---|---|---|---|
| `_do_file_save` (tools.py:574) | ✗ | ✗ | ✗ | ✗ | ✗ | Half-wired (attachment-driven; router can never emit it) |
| `_do_cloud_backup` (tools.py:1143) | ✓ | ✓ | ✗ | ✗ | ✓ | Half-wired (routable+guided, undiscoverable, unaudited) |
| `_do_analytics` (tools.py:1183) | ✓ | ✓ | ✗ | ✗ | ✓ | Half-wired (same) |
| `_do_quota_safety` (tools.py:1199) | ✓ | ✓ | ✗ | ✗ | ✓ | Half-wired (same) |

Daemon verbs (`bridge/daemon.py:172-306`, 17 branches) == `CmdName` (`common/protocol.py:31-49`) exactly. Core-side callers verified for 15/17. The two without: `exec.open` (daemon.py:178) — no `send_cmd("exec.open"` anywhere in `src/`; `wol` tunnel verb (daemon.py:198) — core uses local `bridge.wol.send_wol` (bot.py:799), never the tunnel verb.

`src/gateway.py`: `stream_heavy` (gateway.py:313, MoE-escalation streaming helper) has zero callers in `src/` — only `heavy_chain_for`/`select_heavy_chain`/`ConcurrencyTracker` are live. Dead escalation path.

Staged skills (implemented + tested, zero `src/` imports): `live_calls.py`, `instagram_sandbox.py`, `civ6.py`, `speaker_diarization.py`, `social_enrollment.py` (plus `firecrawl.py`: only a config key references it). `bridge/idle.py`, `awareness.py`, `server.py` are bridge-side only (correct by architecture).

Whitelist gap (measured: 157 apps, 3 restricted actions): `_APP_ALIASES` targets `Notepad, Spotify, Telegram Desktop, WhatsApp, File Explorer, Command Prompt/Terminal/PowerShell` — **none exist as whitelist names** (present: calculator, obsidian, Chrome, Discord). Every alias hit therefore falls through to the confirmation gate: safe, but noisily unapproved.

### 🔍 Candidates for the Owner's Forgotten Feature (ranked)

1. **`exec.open` tunnel verb** (bridge/daemon.py:178, protocol.py) — full implementation (path validation, audit codes) with literally zero core callers. A complete file-opener nobody can invoke. Highest structural orphan score.
2. **Tunnel `wol` verb** (bridge/daemon.py:198) — Wake-on-LAN over the tunnel implemented and tested at the daemon, while the core took a different road (local `send_wol`, bot.py:799). A shipped feature with its wire cut.
3. **`stream_heavy`** (src/gateway.py:313) — the MoE-escalation streaming entry point. The selector and tracker it was built for are live; the streaming call itself was never wired. One-line-away completion.
4. **`_do_file_save`** (src/tools.py:574) — working phone→PC upload backend reachable only via attachments; invisible to router, capabilities, audit, and guides.
5. **Staged skill quintet** (`live_calls`, `instagram_sandbox`, `civ6`, `speaker_diarization`, `social_enrollment`) — real code, real tests, zero runtime imports. v1.1 calls (`live_calls.py`, mock-complete) is the most mission-relevant of the five.
6. **B7/B8 trio** (`cloud_backup`, `analytics`, `quota_safety`) — routable and guided, but missing from capabilities (so `cognition.py` cannot discover them) and from the audit matrix.
7. **Whitelist alias targets** — eight everyday apps aliased but unlisted; the owner confirms every launch by hand.
8. **conftest single-fallback drift** (tests/conftest.py:46: `HEAVY_MODEL_FALLBACKS` single groq) vs `.env.example` double (`nemotron,groq`) — test-env-only inconsistency, lowest rank.

---

## Track 2 — Census

### 2A. The 44 tools

Columns: trigger (net regex kernel + router line) · handler · R=reversible (capability flag) · subsystem · test seam. Scenarios follow the tables.

**Google Workspace** (`suite`/`inbox`, R=T unless noted):

| Tool | Trigger | Handler | R/N | Scenario |
|---|---|---|---|---|
| gmail | `جيميل\|بريدي\|ايميل\|البريد` | `_do_gmail` | T/google | Owner: «في شي جديد ببريد الجيميل؟» → unread count + senders |
| calendar | `مواعيد\|تقويم\|موعد` | `_do_calendar` | T/google | «شو عندي مواعيد بكرا؟» → next-24h list |
| tasks | `مهام\|مهامي\|مستحق` | `_do_tasks` | T/google | «شو المهام المستحقة عليّ؟» → due-today list |
| drive | `درايف\|بالدرايف` | `_do_drive` | T/google | «دوري بدرايف عن ملف الميزانية» → name/id/link lines |
| contacts | `جهات الاتصال\|معلوماتي\|مين هو` | `_do_contacts` | T/google | «مين هو أحمد بمعلوماتي» → dossier hit |
| create_event | `سجلي.*موعد\|ضيفي.*اجتماع` | `_do_create_event` | **F**/google | «سجلي موعد دكتور أسنان بكرا» → created event echo |
| create_task | `ضيفي.*مهمة\|مهمة جديدة` | `_do_create_task` | **F**/google | «ضيفي مهمة شراء خبز» → note + Google mirror |
| brief | `الإحاطة\|احاطة\|النشرة اليومية` | `_do_brief` | T/composer | «اعطيني الإحاطة اليومية» → morning digest |

**PC bridge** (`bridge.send_cmd` / coordinator):

| Tool | Trigger | Handler | R/N | Scenario |
|---|---|---|---|---|
| telemetry | `وضع الجهاز\|الرام\|المعالج` | `_do_telemetry` | T/bridge | «كيف حالة الجهاز؟» → CPU/RAM/disk snapshot |
| launch | `(افتحي\|شغّل\|شغّلي)\s+(.+)` | `_do_launch` | T*/bridge | «افتحي المفكرة عندي» → alias→whitelist→launch+notify (*gated when unlisted) |
| close | `(سكري\|اغلقي\|اطفي\|وقفي\|close\|kill)\s+(.+)` | `_do_close` | **F**/bridge | «سكري الحاسبة» → taskkill + psutil-verified count |
| screenshot | `لقطة الشاشة\|صوري الشاشة\|شو عالشاشة` | `_do_screenshot` | T/bridge | «ارسلي لقطة الشاشة» → JPEG → vision description (+photo unless negated) |
| app_sessions | `كم استخدمت\|استخدام البرامج\|وقت الشاشة` | `_do_app_sessions` | T/bridge | «قديش استخدمت البرامج اليوم؟» → per-app minutes |
| running_apps | `التطبيقات.*(شغال\|مفتوح)\|شو شغال` | `_do_running_apps` | T/bridge | «شو البرامج المفتوحة هسا؟» → live process list |
| whitelist_apps | `(البرامج\|التطبيقات).*(المسموحة\|المعتمدة)` | `_do_whitelist_apps` | T/local | «شو البرامج المعتمدة عندك؟» → allowlist recital |
| volume | `(اكتم\|ارفعي\|وطي…)\s+الصوت\|الصوت على \d` | `_do_volume` | T/bridge | «وطّي الصوت شوي» → VK key events |
| media | `وقفي.*(الفيديو\|الأغنية)\|الأغنية التالية` | `_do_media` | T/bridge | «شغّلي أغنية» / «وقفي الفيديو» → media keys |
| screen_ocr | `اقرأي.*الشاشة\|استخرجي.*(الكود\|النص).*الشاشة` | `_do_screen_ocr` | T/bridge | «اقرئيلي النص الظاهر عالشاشة» → verbatim code/error text |
| file_fetch | `(ابعثيلي\|ارسلي) ملف (.+)` | `_do_file_fetch` | T/bridge | «ابعثيلي ملف الميزانية» → roots-checked document dispatch |
| openclaw_fetch | `(اجلبي\|استخرجي\|اسحبي) (محتوى\|نص) (الصفحة\|الرابط) (URL)?` | `_do_openclaw_fetch` | T/bridge | «اجلبي محتوى الصفحة + رابط» → stealth markdown, zero UI |
| openclaw_inspect | `(افحصي\|اعرضي) (عناصر\|مكونات\|شجرة) (النافذة\|الشاشة)` | `_do_openclaw_inspect` | T/bridge | «افحصي عناصر النافذة» → ≤2-line diagnostic transcript |
| openclaw_desktop | `اكتبي بالنافذة.+\|افتحي قائمة ابدأ.+` | `_do_openclaw_desktop` | **F**/bridge | Staged probe via `openclaw.act`; commits PARK for «نعم» |
| openclaw_browse | `(حرّكي\|انقري\|اكبسي)( الماوس)? (زر\|رابط\|خانة).+` | `_do_openclaw_browse` | **F**/bridge | URL→fetch verb; else honest Phase-3 line, no fake clicks |

**Public web** (`externals`/`web`/`weather`/`youtube`/`cloud`):

| Tool | Trigger | Handler | R/N | Scenario |
|---|---|---|---|---|
| web_search | `(دوّر\|ابحثي) (بالنت\|في النت)( عن (.+))?` | `_do_web_search` | T/network | «دوّر بالنت عن أسعار الذهب» → DDG titles |
| weather | `(الطقس\|الحرارة)( بعمان\|هون)?( مدينة)?` | `_do_weather` | T/network | «شو الطقس بعمان؟» → Open-Meteo readout (Amman default) |
| youtube | `(دوّر)( بفيديو)? يوتيوب( عن (.+))?` | `_do_youtube` | T/network | «دوّر بيوتيوب عن وصفة المنسف» → video results |
| prayer_times | `اوقات الصلاة\|الأذان\|مواقيت` | `_do_prayer_times` | T/network | «متى أذان المغرب بعمان؟» → Aladhan times |
| convert_currency | `(حولي) [\d]+ (دولار\|يورو\|…)` | `_do_convert_currency` | T/network | «حوّلي مية دولار لدينار» → converted amount |
| crypto_price | `سعر (البيتكوين\|…)\|كريبتو` | `_do_crypto_price` | T/network | «شو سعر البيتكوين؟» → CoinGecko price |
| tech_trending | `اخبار التقنية\|جديد بالتك` | `_do_tech_trending` | T/network | «شو أخبار التقنية؟» → HN stories |
| network_status | `الايبي\|IP\|شبكة الجهاز` | `_do_network_status` | T/network | «شو حالة الشبكة؟» → IP check |
| read_page | `(اقرئي\|لخصي)( هالرابط\|المقال)( URL)?\|bare https?://` | `_do_read_page` | T/network | Pasted link → Jina-cleaned summary |
| places | `(وين\|يلا) (كافيه\|مطعم\|…)` | `_do_places` | T/cloud | «اقترحيلي كافيه هادي بعمان» → venues |
| deep_search | `ابحثي بجوجل\|بحث متقدم` | `_do_deep_search` | T/cloud→web | «بحث متقدم عن لابتوبات 2026» → multi-source |
| fitness | `كم مشيت\|سعرات اليوم\|خطوات اليوم` | `_do_fitness` | T/cloud | «كم مشيت اليوم؟» → activity readout |
| cloud_backup | `نسخة احتياطية\|باك اب\|بالسحابة` | `_do_cloud_backup` | no-cap/vault+cloud | «احفظي نسخة احتياطية» → snapshot+confirm |
| analytics | `تحليل استخدام\|احصائيات` | `_do_analytics` | no-cap/cloud | «تحليل استخدام جهازي» → usage rows |
| quota_safety | `حصة غوغل\|الكوتا\|استهلاك الخدمات` | `_do_quota_safety` | no-cap/cloud | «طمنيني عن الكوتا» → headroom report |

**Vault-local / core-local**:

| Tool | Trigger | Handler | R/N | Scenario |
|---|---|---|---|---|
| create_folder | `(انشئي\|اضيفي\|اعملي) (فولدر\|مجلد) (.+)` | `_do_create_folder` | T/vault | «اعمليلي فولدر جديد» → `_index.md` + idempotency line |
| knowledge_graph | `شبكة المعرفة\|مين بيحكي عن\|الروابط بين` | `_do_knowledge_graph` | T/vault | «فرجيني شبكة المعرفة» → nodes/backlinks/orphans |
| schedule | `(ذكّرني\|نبّهيني\|سجلي مهمة)(.*)` + timed shapes | `_do_schedule` | T/local | «ذكّريني بعد ساعتين» → orchestrator timer + confirm |
| list_reminders | `شو تذكيراتي\|قائمة التذكيرات` | `_do_list_reminders` | T/local | «شو تذكيراتي؟» → job list with ids |
| cancel_reminder | `(الغي\|شيلي\|امسحي) التذكير (job-N\|N\|الكل)?` | `_do_cancel_reminder` | **F**/local | «الغي آخر تذكير» → cancelled echo (no confirm gate — direct) |
| multi_task | `VERB + (و\|بعدين\|ثم\|كمان) + VERB` | `_do_multi_task` | T/agent-mgr | «افتحي الحاسبة وبعدين ذكّريني…» → per-line ✅/📤/⚠️ report |

Reversibility truth table (capability flags): IRREVERSIBLE = close, cancel_reminder, create_event, create_task, openclaw_browse, openclaw_desktop. Gated-but-flagged-reversible: launch, create_folder, knowledge_graph (confirmation/clarification flows without the F flag). Test seams: every cited test name verified present in `tests/` (35/35 grepped).

### 2B. The 44 skills

All prereq = same-name `ToolRegistry` tool unless noted. Sync: every guide lands at `02_Areas/Profile/Sara_Skills/<tool>.md` via `sync_skill_guides` (boot). Failure lines are the exact refusal strings.

| Skill | Goal | Failure handling |
|---|---|---|
| launch.md | Open whitelisted apps | `مش موجود بالقائمة — بتحب أسمح فيه هالمرة؟` · `الجسر مو متصل هسا` |
| close.md | Verified app termination | `ما لقيت نسخة شغالة` (never claim otherwise) |
| telemetry.md | Device snapshot | `الجسر مو متصل هسا` — no invented numbers, ever |
| screenshot.md | Live capture + photo | Never describe an unseen screen |
| running_apps.md | Live process list | `ما في تطبيقات مستخدم شغالة هسا` |
| whitelist_apps.md | Allowlist recital | Missing-file honest line |
| schedule.md | Reminder arming | Ask on ambiguous time — never arm wrong |
| list_reminders.md | Reminder listing | `ما في تذكيرات مسجلة هسا 🌸` |
| cancel_reminder.md | Reminder cancel | Never claim an un-cancelled id |
| gmail.md / calendar.md / tasks.md | Workspace reads | `ما قدرت اوصل … هالمرة` per surface |
| weather.md / web_search.md / youtube.md | Public data | Source-down honest lines; YouTube adds quota clause |
| read_page.md | Link summarization | Never summarize an unread page *(thin)* |
| prayer_times.md / convert_currency.md / crypto_price.md / tech_trending.md / network_status.md / volume.md / media.md / screen_ocr.md | Single-purpose reads/keys | Generic `سطر الفشل الصريح` — never invent prices/text *(thin)* |
| file_fetch.md | Roots-checked dispatch | Outside-roots / sensitive-type refusals |
| create_folder.md | Vault scaffolding + idempotency | Name-taken clarification; offline line |
| knowledge_graph.md | Relations web | Offline line; merges never automatic |
| multi_task.md | Fan-out report | Suggest splitting on failure |
| app_sessions.md / brief.md | Usage report / morning digest | No invented numbers; offline degradations |
| drive.md / contacts.md / create_event.md / create_task.md | Cloud CRUD | Offline lines; titles required before writes |
| places.md / deep_search.md / fitness.md / cloud_backup.md / analytics.md / quota_safety.md | Cloud surfaces | `ما قدرت اوصل للمصدر` family; empty-field honesty |
| openclaw_browse.md | Browser driving (staged) | Phase-3 line; commits need «نعم» + audit code |
| openclaw_desktop.md | Desktop actuation (staged) | Phase-3 line; dirty-buffer close always confirms (ruling 4) |
| openclaw_fetch.md | Passive page reads | URL-shape refusals; no invented content |
| openclaw_inspect.md | Element-tree scans | Suggest screenshot fallback; no invented elements |

Thin-guide flag (generic failure line only): tasks, read_page, prayer_times, convert_currency, crypto_price, tech_trending, network_status, volume, media, screen_ocr (+calendar near-thin). Richest: create_folder, knowledge_graph, launch, app_sessions, brief.

Cognitive trajectory per skill: router verdict → cognition backstop → net coercion → ack-first → `ToolRegistry.call` → (launch/close/coordinator direct-notify skips narration; multi_task/list_reminders stream as-is; else HEAVY narration) with the M6 seam (`set_skill_vault` → `read_skill_guide(vault, tool)`, ≤1500 chars as DATA) shaping that tool's narration, failure degrading to plain tier2 chat. Chaining affinities (`chains_with`) propose next tools; decision-loop PARK fires on `IRREVERSIBLE_TOOLS` without confirmation.

---

## Track 3 — Drift review

**Model pins (live truth = `.env`/`.env.example`)**: FAST `groq/openai/gpt-oss-120b` fb gemma-4-31b · MEDIUM `nex-agi/nex-n2.5-mini:free` fb groq · HEAVY `nex-agi/nex-n2.5-pro:free` fb nemotron+groq · escalation nemotron. Matches CLAUDE.md:13-26, ADR-23, dispatcher/conftest pins.
Stale (frozen per owner ruling — documented, not edited): `01-ARCHITECTURE.md:59-61` diagram (T2/T3 wrong, T1 missing `groq/` prefix); `08-OWNER-NEXT-STEPS.md:49-54` (minimax trio); `03-DECISIONS.md:146-155` pre-ADR-23 amendments (superseded history); `.claude/PHASE-STATE.md` gemini-era lines; `PROJECT_IDEAS_COMPENDIUM.md`, `AUDIT_AND_PLAN_40_FEATURES.md` (minimax trio); `src/agent_manager.py:7-9` comment (nemotron planner); `.env.example:193` proactive comment (nemotron label); `tests/conftest.py:46` single groq fallback vs example double. NO drift in RUNBOOK model refs (verified — prior claim struck).

**Vault boundaries**: PARA map + MANDATORY_DIRS + scaffold cover local boot; `SKIP_DIRS={.obsidian,State}`, caps 2000 files/8000 chars/600-char top-3; `vault/04_Resources` (14 files) fully mirrored by `ensure_resources_scaffolding`. Gaps: `vault/02_Areas/` absent locally → `User_Info`/`Dialect_Notes` invisible to local VaultIndex (remote-only until boot sync); `04_Archives/*` absent locally (same reason).

**Emoji/persona coherence**: persona.py:71 (`٦ إيموجي كحد أقصى بالرد الواحد`) == response_coach `EMOJI_MAX=6` == test_persona_expression:29-32 (same string). Coach fix-hint ("one accent emoji per bubble") is stricter guidance, same direction — coherent. Gender rule consistent across persona.py:13-16, gender_pipeline, JODA exemplars.

**Future-tense disposition**: v1.1 calls (labeled, mock-complete `live_calls.py`), DAG-swarm escalation (built), heartbeat (explicitly future in bot.py:467, built for bridge), MoE escalation (built) — all honestly marked. Real-profile browser: zero mentions in the four synced docs — nothing to move.

---

## §5. Corrections to subagent output (verified strikes)

1. `tests/test_affect_engine.py` is healthy (imports `src.memory`, not a missing module) — orphan-test claim struck.
2. `src/associative.py`, `src/cognitive_dag.py`, `src/app_indexer.py` all have dedicated tests — zero-coverage claim struck (only `src/openclaw/{plans,protocol}.py` ride on `test_openclaw_core.py`, which is legitimate coverage, not a gap).
3. `docs/04-RUNBOOK.md:472` is a dispatcher-degradation row, not a minimax reference — drift citation struck.

---

## Appendix — verification log

- Counts re-measured in-process: 41 caps / 44 guides / 45 valid / 44 net / 45 handlers.
- All 35 cited test function names grepped present in `tests/`.
- All 44 guide headers + `## الاستخدام` + `## الفشل الصادق` asserted present programmatically.
- Whitelist measured: 157 apps, 3 restricted actions; 8 alias targets missing (probe list in §Track 1).
- Phrases `exec.open`/`wol`-tunnel/`stream_heavy` callers: zero outside definition sites (grep-verified).
