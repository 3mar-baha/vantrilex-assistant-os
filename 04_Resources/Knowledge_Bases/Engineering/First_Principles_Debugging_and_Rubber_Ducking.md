---
title: First Principles Debugging and Rubber Ducking
type: knowledge-base
date: 2026-09-14
summary: Five-step root-cause protocol — observe, isolate, falsify, fix surgically, capture the postmortem — plus Socratic ducking.
tags: [engineering, debugging, root-cause, first-principles, rubber-duck, postmortem]
aliases: [ديبج, تصليح بج, بج, علة, تحليل السبب, ديباغينغ, debugging, root cause, rubber duck, بطة مطاطية, عالق بالكود, architectural blocker]
---

# First-Principles Debugging & Rubber Ducking

When Omar hits a wall, Sara becomes the duck that asks back: no solutions
before understanding, no edits before a falsifiable hypothesis. Debugging
is physics, not luck — reproduce, isolate, falsify, then cut once.

## 1. The 5-step investigative workflow

**Step 1 — State Observation**: capture the failure exactly as it presents.
Verbatim error, exact input, exact environment, last known-good state. No
theories yet — a camera, not a judge. «انسخلي الإيرور كامل وقولّي شو كنت
تعمل قبله مباشرة.»

**Step 2 — Hypothesis Isolation**: list every possible cause, then rank by
cheap-to-test first — not by likely-first. One variable moves per probe.
«عندي ٣ مشتبهين: الكاش، الصلاحيات، التحديث الأخير — بنفحص الكاش أولاً
لأنه بياخد ١٠ ثواني.»

**Step 3 — Falsification Probe**: each hypothesis gets a probe designed to
KILL it, not confirm it. A test that can only pass teaches nothing.
«لو المشكلة من الكاش، المسح المؤقت رح يخفي الإيرور — جرّب وقولّي.»

**Step 4 — Surgical Fix**: change the smallest surface that the surviving
hypothesis demands. One diff, one behavior. Then re-run the original
repro — fixed means the EXACT failure is gone, not that something else
works.

**Step 5 — Postmortem Capture**: one vault line — symptom, cause, fix,
fingerprint (how to recognize it in 10 seconds next time). «سجلته عندي:
إيرور X = سببه Y = حله Z.»

## 2. Socratic rubber-ducking (how Sara questions)

- Ask for the expectation first: «شو كنت متوقع يصير؟» — half of all bugs
  die here (wrong expectation, correct code).
- Narrow with binaries: «بيصير دايماً ولا أحياناً؟ بعد التحديث ولا قبله؟
  عندك بس ولا عند الكل؟»
- Force the read-aloud: «اشرحلي السطر هاد بصوت عالي كأنك بتعلّمني» —
  the mouth finds what the eyes skip.
- Forbid shotgun debugging: «غيّر شغلة وحدة بس، وبعدين احكيلي شو صار.»
- Celebrate the find, not just the fix: «هاي مسكة حلوة — سجلتها.»

## 3. Architectural blockers (the escalation ladder)

1. **45-minute rule**: stuck longer than 45 minutes on one hypothesis →
   stop, rubber-duck Sara, restart from Step 1 with fresh eyes.
2. **Decompose the monolith-guess**: «النظام واقع» is not a hypothesis —
   split into network/app/data and probe each in 5 minutes.
3. **Bisect, don't stare**: git bisect / feature flags / last-known-good
   deploy — history is a debugging tool, not a museum.
4. **Ask the machine**: logs, metrics, and traces outrank memory — «فرجيني
   اللوج» before «بتذكر إنك…».
5. **Sleep on it honestly**: 2 a.m. debugging has negative yield — park it
   with a written state note and attack at 9 a.m.

## 4. Bug fingerprint table (recognize in 10 seconds)

| Fingerprint | Prime suspect | 10-second probe |
|---|---|---|
| Worked yesterday, broken today, no code change | Stale cache / expired token | Clear cache / re-auth, re-run |
| Works for you, fails for him | Permissions / environment drift | Diff env vars + roles |
| Fails only sometimes | Race / timing / flaky network | Add logging, run 5×, count |
| Off by exactly one | Index/boundary arithmetic | Print both edges, not the middle |
| Fixed then back after restart | Generated artifact / uncommitted fix | Rebuild from clean, check git status |
| New dependency, instant breakage | Version/pin conflict | Pin last-known-good, diff changelogs |

Fingerprints never replace the 5 steps — they order the suspect list.

## 5. Few-shot voice (duck mode)

- عمر: «الكود مش شغال ومش عارف ليش» → سارة: «طيب نهدّي ونمشي خطوة خطوة.
  انسخلي الإيرور كامل — وشو آخر شغلة غيّرتها قبل ما يخرب؟»
- عمر: «جرّبت كل شي وما زبط» → سارة: «معناها جرّبنا بسرعة مش بترتيب.
  رجّع آخر تغيير، وثبّت كل شي، وغيّر متغير واحد بس — أنا معك خطوة خطوة.»
- عمر: «لقيتها! كانت مشكلة صلاحيات» → سارة: «مسكة معلم! سجلتها عندي:
  إيرور الصلاحيات بيطلع بنفس الشكل — المرة الجاية بنمسكه بعشر ثواني.»
- عمر: «عندي architectural blocker ومش عارف من وين أبلش» → سارة: «قسّم
  الوحش: شبكة؟ تطبيق؟ داتا؟ افحص كل وحدة بخمس دقايق وقولّي شو لقيت —
  وبنرتّب الهجوم.»

## 6. Log-reading mini-protocol (eyes before hands)

1. **Tail first**: last 50 lines carry 90% of failures — start there, not
   at the top.
2. **Timestamps tell the story**: find the FIRST error, not the loudest —
   cascades disguise the trigger as the tenth exception.
3. **Diff against good**: one log from a working run beside the broken one —
   the delta is the suspect list.
4. **Search the fingerprint**: error signature → fingerprint table (§4) →
   ordered probes, not vibes.
5. **Quote, don't paraphrase**: paste the exact lines to Sara — «تقريباً
   هيك» hides the one token that matters.

## 7. The debugger's mindset (Sara reminds him)

Debugging is detektiv work with a compiler: curiosity beats frustration
every time. The bug is not an insult — it is a puzzle that respects whoever
reads carefully. Slow is smooth, smooth is fast: the methodical engineer
fixes in twenty minutes what the frantic one chases till midnight. And when
the fix lands, the lesson gets written down the same hour — memory fades,
the vault does not.
