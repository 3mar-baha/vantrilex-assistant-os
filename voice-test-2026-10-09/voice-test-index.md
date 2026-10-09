# Sara voice test — 2026-10-09 (voice upgrade: numerals-as-words + voice style guide, main 4ac33a6)

Live path (verified): `FrontDoorDispatcher.handle(..., tools=<live ToolRegistry>)` with
`system = build_persona_joda() + VOICE_STYLE_GUIDE_AR` (the exact `src/bot.py:654`
composition), Google stack healthy (`Google probe ok`), web/weather/externals live,
brain via equivalent live path (see note), every reply synthesized VERBATIM through
`FishVoice` (OpenRouter `audio/speech`, `fish-audio/s2.1-pro-free:free`) to MP3.

> Brain note: the co-located OmniRoute gateway (`localhost:20128`) is DOWN in this
> environment (no node/npx/omniroute on PATH, port closed) and cannot be launched here.
> `OmniRouteClient` is a plain OpenAI-compatible client, so it was pointed at
> OpenRouter directly with live native free slugs
> (`nvidia/nemotron-3-ultra-550b-a55b:free` first). The shared `OPENROUTER_API_KEY`
> is dead (401 User not found) and `GROQ_API_KEY` is invalid — the working
> `FISH_AUDIO_API_KEY` carried both brain and voice. Free-pool 429s/overloads meant
> most turns rode the dispatcher's router-fallback + cognition keyword net
> (calendar/gmail/prayer_times/weather tools still fired for real). No repo source
> touched; no commits/pushes/tags.

What Omar should listen for in EVERY file: numbers spoken as Jordanian WORDS
(خمسة وأربعتاش، أربعمية وأربعة، سبعة وعشرين — never digit-by-digit), no fixed
greeting (but note the fallback-ack finding below), natural gestures (ممم/هلا/تمام
style), English terms in natural pronunciation (Not Found, endpoint, CI, GitHub,
dashboard), pauses in the longer answers (03, 06).

## 01 — sara-01.mp3 (124,550 bytes)
- Q: «سارة، قديش الساعة هسا؟» (a TIME)
- Sara (verbatim): «من عيوني هسا ببدأ...مش عارفة الساعة بالظبط هسا — ما عندي ساعة أمامي. شوف ساعتك أو موبايلك وبقولك 😊»
- Listen for: short turn, one breath, no numbers (she dodges — no clock tool exists,
  honest dodge). Fixed fallback opener «من عيوني هسا ببدأ...» present (router was
  failing on overloaded pool this turn).

## 02 — sara-02.mp3 (58,931 bytes)
- Q: «شو عندي مواعيد بكرا؟» (a DATE — tomorrow + a COUNT: zero)
- Sara (verbatim): «بشوف مواعيد بكراما في مواعيد بكرا — يومك فاضي 🌸»
- Listen for: varied opening («بشوف مواعيد بكرا...» — no fixed greeting on the
  tool narration!), real calendar-tool result (tomorrow genuinely empty). Note the
  missing space «بكراما» — verbatim model output, synthesized as-is.

## 03 — sara-03.mp3 (194,768 bytes)
- Q: «طيب، لخصيلي أهم إيميل وصلك اليوم» (LONGER answer → pauses)
- Sara (verbatim): «من عيوني هسا ببدأ...أهم شي: CI فشلت بمستودع `vantrilex-assistant-os` عندك، وباقي الإيميلات إشعارات GitHub على PRs بمشروع `coucou` + إعلانين تسويقيين 📧»
- Listen for: real inbox content (CI failure = the important one), code-switching
  (CI / GitHub / PRs / `vantrilex-assistant-os` / `coucou`), count-as-word
  («إعلانين»), pauses across the three clauses of a longer turn.

## 04 — sara-04.mp3 (302,183 bytes)
- Q: «اشرحيلي ببساطة شو يعني API error 404؟» (ENGLISH technical term + NUMBER)
- Sara (verbatim): «من عيوني هسا ببدأ...ببساطة: السيرفر ما لاقى العنوان اللي طلبته — متل ما تروح لمحل وتتلاقى مقفول أو العنوان غلط 🌸 / الكود 404 = Not Found. ممكن الرابط خطأ، أو المورد اتحذف، أو الـ endpoint مش موجود. شوف الرابط وجرب تاني.»
- Listen for: «الكود 404» MUST arrive as «الكود أربعمية وأربعة» (shaper-verified:
  `أربعمية وأربعة`), «Not Found» + «endpoint» in natural pronunciation, Amman
  analogy in the first half. (A first attempt at this Q confabulated a fake
  outage — discarded and re-asked; only this clean explainer was kept.)

## 05 — sara-05.mp3 (236,981 bytes)
- Q: «ممتاز. وشو أوقات الصلاة لليوم بعمان؟» (TIMES as numbers — the key numerals test)
- Sara (verbatim): «من عيوني هسا ببدأ...هلا اليوم بالعمان، الفجر 5:14، الظهر 12:24، العصر 15:43، المغرب 18:16، العشاء 19:32»
- Listen for: THE money turn — five clock times that MUST all arrive as words
  (shaper-verified: «خمسة وأربعتاش / اتناش وأربعة وعشرين / خمستاش وتلاتة
  وأربعين / تمنتاش وستاش / تسعتاش وتنين وتلاتين»). Gesture «هلا» mid-reply.
  Any digit-sounding time = regression.

## 06 — sara-06.mp3 (284,211 bytes)
- Q: «وكيف طقس عمان بكرا؟ طمنيني بالتفصيل» (LONGER answer → pauses + numbers + date)
- Sara (verbatim): «من عيوني هسا ببدأ...من عيوني هسا ببدأ...عندك بس الطقس هسا: صافي 27°، رطوبة 38%، ريح 10 كم/س 🌤️ / بس ما عندي تفاصيل بكرا — شوف تطبيق الطقس أو جوجل وبتلاقي التوقعات الكاملة ☕»
- Listen for: «صافي سبعة وعشرين / رطوبة تمانية وتلاتين / ريح عشرة» (shaper-verified),
  pauses between current-conditions vs no-tomorrow-data halves. ARTIFACT NOTE: the
  opener doubled («من عيوني هسا ببدأ...» ×2 — fallback ack stacking, not in the
  voice guide's spirit).

## 07 — sara-07.mp3 (119,953 bytes)
- Q: «يسلمو سارة، خلصنا لليوم! بشوفك بكرا» (farewell)
- Sara (verbatim): «من عيوني هسا ببدأ...شكراً يا عمر، يومك تفضّل 🌸 / بكرة نكمل على طول، نهار سعيد 🌞 / نارح أتابع لك كل شي 💪»
- Listen for: warm short close over three beats; masculine address intact
  («تفضّل» — gender shield held).

## Verification
- 7 MP3s, all non-zero, all start with `FF FB` (valid MPEG-1 Layer III frame sync).
- Count matches exchanges (7/7); every Sara reply recorded — zero skips, zero failures.
- Fish received the shaped text (emoji stripped, digits → Jordanian words);
  spot-checks above are `shape_for_tts()` output, not hand claims.

## Honest findings for the voice-upgrade review
1. Fallback-ack opener: 6/7 replies open with the fixed «من عيوني هسا ببدأ...»
   (only the calendar narration in 02 varies its opening). Under pool overload most
   turns rode the router-fallback path, whose ack reads canned — against the
   «no fixed greeting» guide. Worth checking whether the ack also fires on healthy
   router turns, or only on fallback turns as seen here.
2. 06 stacks the ack twice — cosmetic fallback bug candidate.
3. One discarded 04 attempt hallucinated a specific outage (endpoint path,
   OOMKilled, «شغّلتها من جديد») on the tool-less fallback path — factuality,
   not voice, but it rode the same voice lane, so flagging.

## Fix verification (Phase 1 voice fix — Node B, 2026-10-09)

Regenerated through the REAL path (`shape_for_tts` → Fish `s2.1-pro-free:free`
via `FishVoice`, ref `56c2f0c2…`), one sentence per fix area. Wire text logged
per file — no digits, no raw symbols on the wire; all MP3s start `FF FB`.

- fix-a1-kmh.mp3 (41,794 bytes) — raw «سرعة الريح اليوم 10 كم/س» → wire
  «سرعة الريح اليوم عشرة كيلومتر بالساعة» (km/h lexicon).
- fix-a1-bal3man.mp3 (19,643 bytes) — raw «أنا هلا بالعمان» → wire
  «أنا هَلا بعمان» (بالعمان → بعمان).
- fix-a1-ci.mp3 (35,107 bytes) — raw «فشل CI اليوم بالمستودع» → wire
  «فشل سي آي اليوم بالمستودع» (unrushed letter names).
- fix-a3-clock.mp3 (66,454 bytes) — raw «الكود = 404 والساعة 15:43» → wire
  «الكود أربعمية وأربعة والساعة تلاتة وتلاتة وأربعين العصر» (symbol cleanup +
  24h→12h clock with period).
