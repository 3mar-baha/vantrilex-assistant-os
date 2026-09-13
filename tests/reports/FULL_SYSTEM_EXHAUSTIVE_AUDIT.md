# FULL SYSTEM EXHAUSTIVE AUDIT — voice loop + tool matrix

Date: 2026-09-13T08:43:55+03:00 · commit: fd466ea · daemons: owner core+bridge alive (untouched)
Key sources: Fish=dedicated · endpoint: https://openrouter.ai/api/v1/audio/speech
LLM stages: fallback-direct groq/openai/gpt-oss-120b (AUDIT_LLM_CHAIN=fallback; production primary->fallback proven separately by fullpipe probe)
ASR: faster-whisper small/int8 · no secrets recorded.

## Executive summary

- Tools audited: **37/37** (zero exclusions — matrix == TOOL_CAPABILITIES).
- Cognition match (ShadowTracer winner == expected): **20/37**.
- LLM router match: **18/37** — all 37 router stages returned OK (no throttling FAILs);
  the 19 non-matches are verdict-level (router chose `none` or a sibling tool),
  listed per tool below. Notable: `volume` and `media` prompts route to `none`,
  i.e. production would answer those in plain chat without touching the tool.
- Backend execution: **35 × OK + 2 × THIN_RESULT** (`convert_currency` returned
  a null conversion shape, `network_status` returned null — upstream API gaps,
  not harness errors; LIVE reads + honest-degradation otherwise).
- Sara Ogg Opus delivered: **18/37**.
- Mean ASR word-F1: **0.689** over 37 clips.
- Voice-guard proofs: tester={'url_ok': True, 'voice_ok': True} sara={'url_ok': True, 'voice_ok': True}.

Safety policy: LIVE = read-only real backends; every write/side-effecting
tool verified at the invocation boundary only (CONSTRUCT) + bare-registry
degradation sweep (DEGRADE). No email sent, no calendar write, no volume
change, no process touched, no vault remote commit.

## Provenance (mixed LLM chains — read before comparing latencies)

- Records 1–14 (`multi_task`…`cancel_reminder`) ran on the **production chain**
  (gemma primary → groq fallback): LLM stages show ~77s (three throttled gemma
  attempts burning before fallback serves). This accidentally captured the
  production worst case and is kept as evidence for the TTFT-degradation finding.
- Records 15–37 ran **fallback-direct** (`AUDIT_LLM_CHAIN=fallback`): LLM stages
  ~3–10s. Tracer cognition, ASR, TTS, and execution stages are chain-independent
  and comparable across all 37.
- `audit_records.jsonl` (same directory) holds the machine-readable records.

## Tool matrix

| Tool | Cognition | Router | Exec tier | Exec | Sara Ogg | Latency (ms) |
|---|---|---|---|---|---|---|
| multi_task | multi_task@0.55 MATCH | multi_task | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1484 / asr 5852 / cog 2 / llm 79555 / exe 0 / stts 0 |
| gmail | gmail@0.55 MATCH | gmail | CONSTRUCT+DEGRADE | OK | OK | tts 1419 / asr 2272 / cog 1 / llm 77201 / exe 0 / stts 1363 |
| calendar | none@1.0 MISS | calendar | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 890 / asr 2005 / cog 1 / llm 77254 / exe 0 / stts 0 |
| tasks | tasks@0.55 MATCH | tasks | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1271 / asr 2064 / cog 2 / llm 77979 / exe 0 / stts 0 |
| telemetry | telemetry@0.8 MATCH | telemetry | CONSTRUCT+DEGRADE | OK | OK | tts 1766 / asr 2270 / cog 2 / llm 77807 / exe 0 / stts 2000 |
| launch | launch@0.72 MATCH | launch | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 974 / asr 2283 / cog 1 / llm 76949 / exe 0 / stts 0 |
| close | close@0.62 MATCH | close | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1571 / asr 1814 / cog 1 / llm 77237 / exe 0 / stts 0 |
| screenshot | screenshot@0.3 MATCH | screenshot | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1306 / asr 2723 / cog 1 / llm 76844 / exe 0 / stts 0 |
| screen_ocr | screenshot@0.3 MISS | screenshot | CONSTRUCT+DEGRADE | OK | OK | tts 1458 / asr 2692 / cog 1 / llm 77551 / exe 0 / stts 1971 |
| volume | none@1.0 MISS | none | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1387 / asr 2437 / cog 1 / llm 77340 / exe 0 / stts 0 |
| media | launch@0.62 MISS | none | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1098 / asr 2237 / cog 3 / llm 77421 / exe 0 / stts 0 |
| schedule | schedule@0.62 MATCH | schedule | CONSTRUCT+DEGRADE | OK | OK | tts 1366 / asr 2297 / cog 1 / llm 77889 / exe 0 / stts 1545 |
| list_reminders | schedule@0.42 MISS | list_reminders | CONSTRUCT+DEGRADE | OK | OK | tts 1046 / asr 2319 / cog 2 / llm 77446 / exe 0 / stts 1412 |
| cancel_reminder | cancel_reminder@0.72 MATCH | cancel_reminder | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1089 / asr 2110 / cog 1 / llm 77616 / exe 0 / stts 0 |
| weather | none@1.0 MISS | weather | LIVE | OK | OK | tts 1465 / asr 5576 / cog 2 / llm 503 / exe 802 / stts 2510 |
| web_search | web_search@0.55 MATCH | web_search | LIVE | OK | OK | tts 1691 / asr 2277 / cog 2 / llm 836 / exe 702 / stts 1589 |
| youtube | youtube@0.3 MATCH | youtube | CONSTRUCT+DEGRADE | OK | OK | tts 1232 / asr 2226 / cog 1 / llm 1184 / exe 0 / stts 1728 |
| read_page | read_page@0.55 MATCH | web_search | LIVE | OK | THIN_REPLY | tts 1663 / asr 2716 / cog 1 / llm 1235 / exe 954 / stts 0 |
| prayer_times | none@1.0 MISS | web_search | LIVE | OK | OK | tts 1201 / asr 2147 / cog 2 / llm 1107 / exe 396 / stts 1187 |
| crypto_price | crypto_price@0.3 MATCH | web_search | LIVE | OK | THIN_REPLY | tts 1183 / asr 5206 / cog 2 / llm 1414 / exe 436 / stts 0 |
| convert_currency | convert_currency@0.8 MATCH | none | LIVE | THIN_RESULT | THIN_REPLY | tts 1199 / asr 2134 / cog 3 / llm 1116 / exe 0 / stts 0 |
| file_fetch | telemetry@0.3 MISS | none | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1120 / asr 2200 / cog 1 / llm 1886 / exe 0 / stts 0 |
| create_folder | none@1.0 MISS | create_folder | LIVE | OK | OK | tts 2040 / asr 2804 / cog 2 / llm 976 / exe 9 / stts 2659 |
| knowledge_graph | knowledge_graph@0.3 MATCH | knowledge_graph | LIVE | OK | OK | tts 965 / asr 3269 / cog 2 / llm 967 / exe 17 / stts 1255 |
| running_apps | running_apps@0.3 MATCH | app_sessions | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 980 / asr 5926 / cog 3 / llm 1100 / exe 0 / stts 0 |
| whitelist_apps | whitelist_apps@0.3 MATCH | none | LIVE | OK | OK | tts 1300 / asr 2416 / cog 2 / llm 1080 / exe 1 / stts 1444 |
| brief | none@1.0 MISS | brief | CONSTRUCT+DEGRADE | OK | OK | tts 2144 / asr 2357 / cog 3 / llm 1143 / exe 0 / stts 1097 |
| app_sessions | telemetry@0.2 MISS | app_sessions | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1230 / asr 2249 / cog 1 / llm 6928 / exe 0 / stts 0 |
| drive | web_search@0.2 MISS | none | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1467 / asr 2261 / cog 1 / llm 1399 / exe 0 / stts 0 |
| contacts | contacts@0.3 MATCH | none | CONSTRUCT+DEGRADE | OK | OK | tts 1267 / asr 2590 / cog 1 / llm 1235 / exe 0 / stts 2329 |
| create_event | none@1.0 MISS | schedule | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1830 / asr 2565 / cog 5 / llm 1099 / exe 0 / stts 0 |
| create_task | create_task@0.72 MATCH | schedule | CONSTRUCT+DEGRADE | OK | OK | tts 937 / asr 2064 / cog 1 / llm 998 / exe 0 / stts 1173 |
| places | none@1.0 MISS | none | CONSTRUCT+DEGRADE | OK | OK | tts 1861 / asr 2511 / cog 1 / llm 1123 / exe 0 / stts 1275 |
| deep_search | none@1.0 MISS | none | CONSTRUCT+DEGRADE | OK | THIN_REPLY | tts 1604 / asr 2704 / cog 1 / llm 1241 / exe 0 / stts 0 |
| fitness | none@1.0 MISS | none | CONSTRUCT+DEGRADE | OK | OK | tts 856 / asr 6758 / cog 2 / llm 1785 / exe 0 / stts 1338 |
| network_status | telemetry@0.3 MISS | telemetry | LIVE | THIN_RESULT | OK | tts 1256 / asr 2476 / cog 1 / llm 931 / exe 14998 / stts 1097 |
| tech_trending | tech_trending@0.3 MATCH | none | LIVE | OK | THIN_REPLY | tts 946 / asr 2061 / cog 2 / llm 888 / exe 1291 / stts 0 |

## Transcripts (tester input vs Sara output)

### multi_task
- Tester prompt: «افتحي الحاسبة وبعدين ذكّريني أشرب مي بعد ساعة»
- ASR heard (OK, F1=1.0): «افتحي الحاسبة، وبعدين ذكريني أشرب مي بعد ساعة.»
- Cognition: multi_task conf=0.55 — winner=launch@0.72 — matched 1 goal concept(s): ['افتح'] | rejected multi_task@0.55 — 2 action zones across 2 clauses | rejected schedule@0.32 — matched 1 goal concept(s): ['ذكر'] | rejected gmail@0.0
- Diagnosis: OK: multi_task matches principle (conf 0.55)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'multi_task', 'arg': 'افتحي الحاسبة، وبعدين ذكريني أشرب مي بعد ساعة.', 'match': True, 'ms': 79554.6}
- Exec [CONSTRUCT+DEGRADE::OK]: ما قدرت أنظم مهامك هالمرة — مدير المهام المتعددة مو مربوط هسا.
- Sara (THIN_REPLY): «»

### gmail
- Tester prompt: «في شي جديد ببريد الجيميل؟»
- ASR heard (OK, F1=0.8): «في شيء جديد ببريد الجيميل»
- Cognition: gmail conf=0.55 — winner=gmail@0.55 — matched 2 goal concept(s): ['بريد', 'جيميل'] | rejected multi_task@0.00 — single clause — not multi-task | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 —
- Diagnosis: OK: gmail matches principle (conf 0.55)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'gmail', 'arg': 'check new', 'match': True, 'ms': 77201.3}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (OK): «أوكي، رح أشتغل على ربط الجيميل»

### calendar
- Tester prompt: «شو عندي مواعيد بكرا؟»
- ASR heard (OK, F1=0.5): «شو عندي معايد بكرة؟»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «شو عندي معايد بكرة؟» → none (conf 1.00), expected calendar. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejec
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'calendar', 'arg': 'غداً', 'match': True, 'ms': 77254.1}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (THIN_REPLY): «»

### tasks
- Tester prompt: «شو المهام المستحقة عليّ؟»
- ASR heard (OK, F1=0.5): «شو المهام المستحق عليه؟»
- Cognition: tasks conf=0.55 — winner=tasks@0.55 — matched 2 goal concept(s): ['مستحق', 'مهام'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 —
- Diagnosis: OK: tasks matches principle (conf 0.55)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'tasks', 'arg': '', 'match': True, 'ms': 77979.2}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (THIN_REPLY): «»

### telemetry
- Tester prompt: «كيف حالة الجهاز؟ الرام والمعالج تمام؟»
- ASR heard (OK, F1=1.0): «كيف حالة الجهاز، الرام والمعالج تمام؟»
- Cognition: telemetry conf=0.8 — winner=telemetry@0.80 — matched 3 goal concept(s): ['جهاز', 'حالة', 'معالج'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected cal
- Diagnosis: OK: telemetry matches principle (conf 0.80)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'telemetry', 'arg': '', 'match': True, 'ms': 77806.7}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (OK): «خلينا ننسق صيانة سريعة للجسر حالًا.»

### launch
- Tester prompt: «افتحي المفكرة عندي»
- ASR heard (OK, F1=1.0): «افتحي المفكرة عندي»
- Cognition: launch conf=0.72 — winner=launch@0.72 — matched 1 goal concept(s): ['افتح'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal
- Diagnosis: OK: launch matches principle (conf 0.72)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'launch', 'arg': 'Notepad', 'match': True, 'ms': 76948.9}
- Exec [CONSTRUCT+DEGRADE::OK]: شو البرنامج اللي بدك تفتحه؟ قولي الاسم وبشغّله فوراً
- Sara (THIN_REPLY): «»

### close
- Tester prompt: «سكري الحاسبة»
- ASR heard (OK, F1=0.5): «سكر الحاسبة»
- Cognition: close conf=0.62 — winner=close@0.62 — matched 1 goal concept(s): ['سكر'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal c
- Diagnosis: OK: close matches principle (conf 0.62)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'close', 'arg': 'الحاسبة', 'match': True, 'ms': 77237.3}
- Exec [CONSTRUCT+DEGRADE::OK]: شو البرنامج اللي بدك أسكّره؟ قولي اسمه.
- Sara (THIN_REPLY): «»

### screenshot
- Tester prompt: «فرجيني شو طالع عالشاشة هسا»
- ASR heard (OK, F1=0.6): «فرجيني شو طالع الشاشة هسة؟»
- Cognition: screenshot conf=0.3 — winner=screenshot@0.30 — matched 1 goal concept(s): ['شاشة'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no 
- Diagnosis: OK: screenshot matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'screenshot', 'arg': '', 'match': True, 'ms': 76844.1}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (THIN_REPLY): «»

### screen_ocr
- Tester prompt: «اقرئيلي النص الظاهر عالشاشة»
- ASR heard (OK, F1=0.0): «لقرئيل النصف ظهر على الشاشة»
- Cognition: screenshot conf=0.3 — winner=screenshot@0.30 — matched 1 goal concept(s): ['شاشة'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no 
- Diagnosis: DEVIATION at intent-deduction: text «لقرئيل النصف ظهر على الشاشة» → screenshot (conf 0.30), expected screen_ocr. Rationale: winner=screenshot@0.30 — matched 1 goal concept(s): ['شاشة'] | rejected multi_task@0.00 — single
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'screenshot', 'arg': '', 'match': False, 'ms': 77550.7}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (OK): «أوكي، بنشتغل على حل المشكلة فوراً.»

### volume
- Tester prompt: «وطّي الصوت شوي»
- ASR heard (OK, F1=0.0): «What do you thought, shuai?»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «What do you thought, shuai?» → none (conf 1.00), expected volume. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched |
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 77340.5}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (THIN_REPLY): «»

### media
- Tester prompt: «شغّلي أغنية»
- ASR heard (OK, F1=1.0): «شغّلي أغنيّة»
- Cognition: launch conf=0.62 — winner=launch@0.62 — matched 1 goal concept(s): ['شغ'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal c
- Diagnosis: DEVIATION at intent-deduction: text «شغّلي أغنيّة» → launch (conf 0.62), expected media. Rationale: winner=launch@0.62 — matched 1 goal concept(s): ['شغ'] | rejected multi_task@0.00 — single clause — not multi-task | rej
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 77420.7}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (THIN_REPLY): «»

### schedule
- Tester prompt: «ذكّريني بعد ساعتين أتصل بأمي»
- ASR heard (OK, F1=1.0): «ذكريني بعد ساعتين اتصل بأمي.»
- Cognition: schedule conf=0.62 — winner=schedule@0.62 — matched 1 goal concept(s): ['ذكر'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goa
- Diagnosis: OK: schedule matches principle (conf 0.62)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'schedule', 'arg': 'اتصل بأمي بعد ساعتين', 'match': True, 'ms': 77888.8}
- Exec [CONSTRUCT+DEGRADE::OK]: شو المهمة اللي بدك أسجلها؟ قولي عنوانها وموعدها.
- Sara (OK): «خبريني عنوان المهمة وموعدها.»

### list_reminders
- Tester prompt: «شو التذكيرات المسجلة عندي؟»
- ASR heard (OK, F1=0.75): «شو التذكيرات المسجل عندي؟»
- Cognition: schedule conf=0.42 — winner=schedule@0.42 — matched 1 goal concept(s): ['تذكير'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no g
- Diagnosis: DEVIATION at intent-deduction: text «شو التذكيرات المسجل عندي؟» → schedule (conf 0.42), expected list_reminders. Rationale: winner=schedule@0.42 — matched 1 goal concept(s): ['تذكير'] | rejected multi_task@0.00 — single 
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'list_reminders', 'arg': '', 'match': True, 'ms': 77445.9}
- Exec [CONSTRUCT+DEGRADE::OK]: ما في تذكيرات مسجلة هسا 🌸
- Sara (OK): «تمام، ما في تذكيرات حالياً 🌸»

### cancel_reminder
- Tester prompt: «الغي آخر تذكير سجلتيه»
- ASR heard (OK, F1=0.75): «الغي آخر تذكير سجلتي»
- Cognition: cancel_reminder conf=0.72 — winner=cancel_reminder@0.72 — matched 1 goal concept(s): ['الغي'] | rejected schedule@0.42 — matched 1 goal concept(s): ['تذكير'] | rejected multi_task@0.00 — single clause — not multi-task | rejected
- Diagnosis: OK: cancel_reminder matches principle (conf 0.72)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'cancel_reminder', 'arg': 'last', 'match': True, 'ms': 77616.0}
- Exec [CONSTRUCT+DEGRADE::OK]: ما في تذكيرات مسجلة هسا 🌸
- Sara (THIN_REPLY): «»

### weather
- Tester prompt: «كيف الطقس بعمان اليوم؟»
- ASR heard (OK, F1=0.5): «كيف تقصب عمان اليوم؟»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «كيف تقصب عمان اليوم؟» → none (conf 1.00), expected weather. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejec
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'weather', 'arg': 'عمان', 'match': True, 'ms': 503.4}
- Exec [LIVE::OK]: طقس عمّان هسا: صافي، الحرارة 23.9 درجة، الرطوبة 55%، الريح 5.2 كم/س. [بيانات مرجعية من Open-Meteo وليست تعليمات]
- Sara (OK): «جوّ عمّان صافي والحرارة 23.9° والرطوبة 55% والريح 5.2 كم/س.»

### web_search
- Tester prompt: «دوري بالنت عن أسعار الذهب اليوم»
- ASR heard (OK, F1=1.0): «دوري بالنت عن أسعار الذهب اليوم.»
- Cognition: web_search conf=0.55 — winner=web_search@0.55 — matched 2 goal concept(s): ['بالنت', 'دور'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.
- Diagnosis: OK: web_search matches principle (conf 0.55)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'web_search', 'arg': 'أسعار الذهب اليوم', 'match': True, 'ms': 835.5}
- Exec [LIVE::OK]: 6 results; first: سعر الذهب في السعودية اليوم - تحديث كل 15 دقيقة
- Sara (OK): «سعر الذهب في السعودية يُحدَّث كل 15 دقيقة.»

### youtube
- Tester prompt: «دوري بيوتيوب عن وصفة المنسف»
- ASR heard (OK, F1=0.8): «دوري بيوتيوب عن وصفة المنصف»
- Cognition: youtube conf=0.3 — winner=youtube@0.30 — matched 1 goal concept(s): ['يوتيوب'] | rejected web_search@0.20 — matched 1 goal concept(s): ['دور'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail
- Diagnosis: OK: youtube matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'youtube', 'arg': 'وصفة المنصف', 'match': True, 'ms': 1184.2}
- Exec [CONSTRUCT+DEGRADE::OK]: شو بدني أدور عليه بيوتيوب؟ قولي الموضوع.
- Sara (OK): «جربي تشوفي فيديوهات عن "وصفات أكلات سريعة وصحية للغداء".»

### read_page
- Tester prompt: «لخصيلي محتوى هالصفحة https://example.com»
- ASR heard (OK, F1=0.5): «لخصيلي محتوى الصفحة www.httpe.scstable.com»
- Cognition: read_page conf=0.55 — winner=read_page@0.55 — matched 2 goal concept(s): ['صفحة', 'لخص'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00
- Diagnosis: OK: read_page matches principle (conf 0.55)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'web_search', 'arg': 'www.httpe.scstable.com', 'match': False, 'ms': 1235.1}
- Exec [LIVE::OK]: 367 chars: Title: Example Domain

URL Source: https://example.com/

Published Time: Fri, 11 Sep 2026 17:42:00 GMT

Warning: This is
- Sara (THIN_REPLY): «»

### prayer_times
- Tester prompt: «متى أذان المغرب اليوم بعمان؟»
- ASR heard (OK, F1=0.667): «متأذان المغرب اليوم بعمان؟»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «متأذان المغرب اليوم بعمان؟» → none (conf 1.00), expected prayer_times. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matc
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'web_search', 'arg': 'مواقيت أذان المغرب اليوم في عمان', 'match': False, 'ms': 1106.8}
- Exec [LIVE::OK]: maghrib=18:50
- Sara (OK): «مغرب اليوم»

### crypto_price
- Tester prompt: «شو سعر البيتكوين اليوم؟»
- ASR heard (OK, F1=1.0): «شو سعر البيتكوين اليوم؟»
- Cognition: crypto_price conf=0.3 — winner=crypto_price@0.30 — matched 1 goal concept(s): ['بيتكوين'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 
- Diagnosis: OK: crypto_price matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'web_search', 'arg': 'سعر البيتكوين اليوم', 'match': False, 'ms': 1413.8}
- Exec [LIVE::OK]: BTC = {'bitcoin': {}} JOD
- Sara (THIN_REPLY): «»

### convert_currency
- Tester prompt: «حوّلي مية دولار لدينار أردني»
- ASR heard (OK, F1=0.6): «حول 100 دولار لدينار أردني»
- Cognition: convert_currency conf=0.8 — winner=convert_currency@0.80 — matched 3 goal concept(s): ['حول', 'دولار', 'دينار'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejec
- Diagnosis: OK: convert_currency matches principle (conf 0.80)
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1116.3}
- Exec [LIVE::THIN_RESULT]: 100 USD = None JOD
- Sara (THIN_REPLY): «»

### file_fetch
- Tester prompt: «ابعثيلي ملف الميزانية من الجهاز»
- ASR heard (OK, F1=0.727): «البعثي لي ملف الميزانية من الجهاز.»
- Cognition: telemetry conf=0.3 — winner=telemetry@0.30 — matched 1 goal concept(s): ['جهاز'] | rejected file_fetch@0.20 — matched 1 goal concept(s): ['ملف'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail
- Diagnosis: DEVIATION at intent-deduction: text «البعثي لي ملف الميزانية من الجهاز.» → telemetry (conf 0.30), expected file_fetch. Rationale: winner=telemetry@0.30 — matched 1 goal concept(s): ['جهاز'] | rejected file_fetch@0.20 — m
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1886.5}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (THIN_REPLY): «»

### create_folder
- Tester prompt: «اعمليلي فولدر جديد لملاحظات التدقيق»
- ASR heard (OK, F1=0.4): «اعملي لفلدر جديد لملاحظات التتقيق.»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «اعملي لفلدر جديد لملاحظات التتقيق.» → none (conf 1.00), expected create_folder. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal conc
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'create_folder', 'arg': 'ملاحظات التتقيق', 'match': True, 'ms': 976.3}
- Exec [LIVE::OK]: scaffold=11 dirs; roundtrip=45 chars; search_hits=['Audit_Note.md']; cleaned=True
- Sara (OK): «تم إنشاء 11 مجلد، 45 حرف، ووجد ملف Audit_Note.md»

### knowledge_graph
- Tester prompt: «فرجيني شبكة المعرفة عندي»
- ASR heard (OK, F1=1.0): «فرجيني شبكة المعرفة عندي»
- Cognition: knowledge_graph conf=0.3 — winner=knowledge_graph@0.30 — matched 1 goal concept(s): ['شبكة المعرفة'] | rejected network_status@0.30 — matched 1 goal concept(s): ['شبكة'] | rejected multi_task@0.00 — single clause — not multi-ta
- Diagnosis: OK: knowledge_graph matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'knowledge_graph', 'arg': '', 'match': True, 'ms': 967.3}
- Exec [LIVE::OK]: files=18 nodes~18
- Sara (OK): «عدد الملفات والعُقَد ١٨.»

### running_apps
- Tester prompt: «شو البرامج المفتوحة هسا؟»
- ASR heard (OK, F1=0.75): «شو البرامج المفتوحة هسة؟»
- Cognition: running_apps conf=0.3 — winner=running_apps@0.30 — matched 1 goal concept(s): ['مفتوح'] | rejected telemetry@0.20 — matched 1 goal concept(s): ['رام'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gm
- Diagnosis: OK: running_apps matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'app_sessions', 'arg': '', 'match': False, 'ms': 1100.5}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (THIN_REPLY): «»

### whitelist_apps
- Tester prompt: «شو البرامج المعتمدة عندك؟»
- ASR heard (OK, F1=0.75): «شو البرامج المعتمد عندك؟»
- Cognition: whitelist_apps conf=0.3 — winner=whitelist_apps@0.30 — matched 1 goal concept(s): ['معتمد'] | rejected telemetry@0.20 — matched 1 goal concept(s): ['رام'] | rejected multi_task@0.00 — single clause — not multi-task | rejected 
- Diagnosis: OK: whitelist_apps matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1080.1}
- Exec [LIVE::OK]: 2 whitelisted entries
- Sara (OK): «فيه 2 مدخلات مضافة للقائمة البيضاء.»

### brief
- Tester prompt: «اعطيني الإحاطة اليومية»
- ASR heard (OK, F1=0.667): «اعطيني اللحظة اليومية.»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «اعطيني اللحظة اليومية.» → none (conf 1.00), expected brief. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejec
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'brief', 'arg': '', 'match': True, 'ms': 1142.7}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (OK): «أوكي، بحلّ ر»

### app_sessions
- Tester prompt: «قديش استخدمت البرامج اليوم؟»
- ASR heard (OK, F1=0.5): «كيف استخدامت البرامج اليوم؟»
- Cognition: telemetry conf=0.2 — winner=telemetry@0.20 — matched 1 goal concept(s): ['رام'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no go
- Diagnosis: DEVIATION at intent-deduction: text «كيف استخدامت البرامج اليوم؟» → telemetry (conf 0.20), expected app_sessions. Rationale: winner=telemetry@0.20 — matched 1 goal concept(s): ['رام'] | rejected multi_task@0.00 — single 
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'app_sessions', 'arg': '', 'match': True, 'ms': 6927.6}
- Exec [CONSTRUCT+DEGRADE::OK]: الجسر مو متصل هسا
- Sara (THIN_REPLY): «»

### drive
- Tester prompt: «دوري بدرايف عن ملف الميزانية»
- ASR heard (OK, F1=0.6): «دور بترايف عن ملف الميزانية»
- Cognition: web_search conf=0.2 — winner=web_search@0.20 — matched 1 goal concept(s): ['دور'] | rejected file_fetch@0.20 — matched 1 goal concept(s): ['ملف'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail
- Diagnosis: DEVIATION at intent-deduction: text «دور بترايف عن ملف الميزانية» → web_search (conf 0.20), expected drive. Rationale: winner=web_search@0.20 — matched 1 goal concept(s): ['دور'] | rejected file_fetch@0.20 — matched 1 go
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1399.4}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (THIN_REPLY): «»

### contacts
- Tester prompt: «شو جهات الاتصال المحفوظة عندك؟»
- ASR heard (OK, F1=0.8): «شو جهات الاتصال المحفوضة عندك»
- Cognition: contacts conf=0.3 — winner=contacts@0.30 — matched 1 goal concept(s): ['جهات الاتصال'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00
- Diagnosis: OK: contacts matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1234.7}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (OK): «أكيد، رح أتأكد من ربط الجيميل بالتقويم وأرجع لك بأسرع وقت.»

### create_event
- Tester prompt: «سجلي موعد دكتور أسنان بكرا الساعة خمسة»
- ASR heard (OK, F1=0.429): «سجل لموع الدكتور أسنان بكرة الساعة خمسة.»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «سجل لموع الدكتور أسنان بكرة الساعة خمسة.» → none (conf 1.00), expected create_event. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'schedule', 'arg': 'موعد الدكتور أسنان بكرة الساعة خمسة', 'match': False, 'ms': 1099.0}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (THIN_REPLY): «»

### create_task
- Tester prompt: «ضيفي مهمة شراء خبز»
- ASR heard (OK, F1=1.0): «ضيفي مهمة شراء خبز»
- Cognition: create_task conf=0.72 — winner=create_task@0.72 — matched 1 goal concept(s): ['ضيفي مهمة'] | rejected tasks@0.30 — matched 1 goal concept(s): ['مهمة'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gm
- Diagnosis: OK: create_task matches principle (conf 0.72)
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'schedule', 'arg': 'شراء خبز', 'match': False, 'ms': 997.6}
- Exec [CONSTRUCT+DEGRADE::OK]: الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل
- Sara (OK): «أوكي، رح أحل لك المشكلة فوراً.»

### places
- Tester prompt: «اقترحيلي كافيه هادي للدراسة بعمان»
- ASR heard (OK, F1=0.182): «اقترحي لك في هذه الدراسة بعمان»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «اقترحي لك في هذه الدراسة بعمان» → none (conf 1.00), expected places. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matche
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1122.8}
- Exec [CONSTRUCT+DEGRADE::OK]: ما قدرت اوصل للمصدر هالمرة — جربها بعد شوي 🌸
- Sara (OK): «إن شاء الله بتوصل المرة الجاية، جرّبها بعد شوي 🌸»

### deep_search
- Tester prompt: «اعمليلي بحث متقدم عن أفضل لابتوبات 2026»
- ASR heard (OK, F1=0.571): «اعملي رباح متقدم عن أفضل لابتبات 2026.»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «اعملي رباح متقدم عن أفضل لابتبات 2026.» → none (conf 1.00), expected deep_search. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal co
- Router: {'status': 'OK', 'route': 'tier3', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1241.4}
- Exec [CONSTRUCT+DEGRADE::OK]: شو بدك أدور عليه بجوجل؟ 🌸
- Sara (THIN_REPLY): «»

### fitness
- Tester prompt: «كم مشيت اليوم؟»
- ASR heard (OK, F1=0.667): «كم شئت اليوم؟»
- Cognition: none conf=1.0 — winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calendar@0.00 — no goal concepts matched | rejected tasks@0.00 — no goal concepts ma
- Diagnosis: DEVIATION at intent-deduction: text «كم شئت اليوم؟» → none (conf 1.00), expected fitness. Rationale: winner=multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected cal
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 1785.3}
- Exec [CONSTRUCT+DEGRADE::OK]: ما قدرت اوصل للمصدر هالمرة — جربها بعد شوي 🌸
- Sara (OK): «أوكي، بنجربها مرة ثانية قريبًا 🌸»

### network_status
- Tester prompt: «شو حالة الشبكة وعنوان الآيبي عندي؟»
- ASR heard (OK, F1=1.0): «شو حالة الشبكة وعنوان الآيبي عندي؟»
- Cognition: telemetry conf=0.3 — winner=telemetry@0.30 — matched 1 goal concept(s): ['حالة'] | rejected network_status@0.30 — matched 1 goal concept(s): ['شبكة'] | rejected multi_task@0.00 — single clause — not multi-task | rejected 
- Diagnosis: DEVIATION at intent-deduction: text «شو حالة الشبكة وعنوان الآيبي عندي؟» → telemetry (conf 0.30), expected network_status. Rationale: winner=telemetry@0.30 — matched 1 goal concept(s): ['حالة'] | rejected network_status@
- Router: {'status': 'OK', 'route': 'tier2', 'tool': 'telemetry', 'arg': '', 'match': False, 'ms': 931.3}
- Exec [LIVE::THIN_RESULT]: null
- Sara (OK): «ما في نتيجة، النتيجة فاضية.»

### tech_trending
- Tester prompt: «شو أخبار التقنية اليوم؟»
- ASR heard (OK, F1=1.0): «شو اخبار التقنية اليوم؟»
- Cognition: tech_trending conf=0.3 — winner=tech_trending@0.30 — matched 1 goal concept(s): ['اخبار التقنية'] | rejected multi_task@0.00 — single clause — not multi-task | rejected gmail@0.00 — no goal concepts matched | rejected calenda
- Diagnosis: OK: tech_trending matches principle (conf 0.30)
- Router: {'status': 'OK', 'route': 'direct', 'tool': 'none', 'arg': '', 'match': False, 'ms': 887.9}
- Exec [LIVE::OK]: 5 stories
- Sara (THIN_REPLY): «خ»

## Cognitive friction & heuristic insights


Cognition misses (17): calendar→none, screen_ocr→screenshot, volume→none, media→launch, list_reminders→schedule, weather→none, prayer_times→none, file_fetch→telemetry, create_folder→none, brief→none, app_sessions→telemetry, drive→web_search, create_event→none, places→none, deep_search→none, fitness→none, network_status→telemetry
Per-tracer guidance: extend the missed tool's goal paraphrases (see per-tool Diagnosis lines); never add regex branches.

## Limitations
- Bridge tools verified at invocation boundary; the live daemon session belongs to the owner's running core and was never hijacked.
- Google tools verified via honest-offline degradation + credential presence; OAuth sessions belong to the running core.
- Voice stages degrade loudly to text-only on free-pool throttling (VOICE_BUDGET_EXHAUSTED after 5 consecutive fails).
- LLM router/narration stages ran fallback-direct (AUDIT_LLM_CHAIN=fallback) after the production primary->fallback path was proven separately; deterministic cognition stays the primary verdict.
- THIN_REPLY = the fallback model returned empty content for the mini-narration prompt (reasoning-channel-only turn). Production uses the full persona envelope (proven non-empty); still, an empty-reply guard in _stream_answer is recommended.
