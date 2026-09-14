# Discovery & Improvements — Cognitive Shadow Report

- Date (UTC): 2026-09-14 09:08 UTC
- Mirrored live files: 14
- Retrieval: top-1 13/14, top-3 14/14, mean 2.64ms, p95 3.02ms (target ≤5ms)
- Weight accuracy: 8/8
- Persona: hash OK (ec6acc69, len 4782), emoji checks 4/4

## Retrieval catalog

| Query | Expected | Top-1 | Top-3 | ms |
|---|---|---|---|---|
| شو اختصار النسخ؟ | Keyboard_Shortcuts_and_Accelerator | HIT | HIT | 2.92 |
| أمان التحرك | Reversibility_and_Safety_Boundarie | HIT | HIT | 2.64 |
| بوب أب غريب | Popups_and_Interrupt_Recovery.md | HIT | HIT | 2.65 |
| خريطة واجهة الفيجوال | Application_Topologies_and_Layouts | HIT | HIT | 2.71 |
| لهجة أردنية | JODA_Jordanian_Patterns.md | HIT | HIT | 2.50 |
| نكش مخ | Ammani_Urban_Humor_and_Banter.md | HIT | HIT | 2.46 |
| بروفايل عمر | Omar_Executive_Profile_and_Rhythms | HIT | HIT | 2.59 |
| عمر مشتت اليوم وبده يركز، كيف يتصرف؟ | Deep_Work_and_Attention_Sovereignt | HIT | HIT | 2.64 |
| علة بالكود ومش عارف السبب | First_Principles_Debugging_and_Rub | HIT | HIT | 2.71 |
| معمارية الأنظمة | System_Architecture_and_Scale.md | HIT | HIT | 2.50 |
| اشرحلي فيزيا | Physics_and_Math_Reasoning.md | HIT | HIT | 2.49 |
| علمني انجليزي بريطاني | British_Conversational_English.md | HIT | HIT | 2.49 |
| شو اختصارات الكروم؟ | Keyboard_Shortcuts_and_Accelerator | HIT | HIT | 2.67 |
| شغل عميق بدون مقاطعة | Deep_Work_and_Attention_Sovereignt | Popups_and_Interrupt_Recovery.md | HIT | 3.02 |

## Weight accuracy

- [OK] «مرحبا سارة» exp=(1, False) got=(1, False) tools=[]
- [OK] «شو الطقس بعمان؟» exp=(2, False) got=(2, False) tools=['weather']
- [OK] «ذكّريني أشرب مي بعد ساعة» exp=(2, False) got=(2, False) tools=['schedule']
- [OK] «شو الطقس وذكّريني أشرب مي بعد ساعة» exp=(3, False) got=(3, False) tools=['weather', 'schedule']
- [OK] «السيرفر واقع الحقني» exp=(5, True) got=(5, True) tools=[]
- [OK] «عطل كبير بالنظام، ساعدني بسرعة» exp=(5, True) got=(5, True) tools=[]
- [OK] «افتحي المفكرة وسكري الحاسبة» exp=(3, False) got=(3, False) tools=['launch', 'close']
- [OK] «شو أخبارك اليوم؟» exp=(1, False) got=(1, False) tools=[]

## Persona integrity

- [OK] comfort: 2 emoji (compliant=True, expected=True)
- [OK] identity-warm: 2 emoji (compliant=True, expected=True)
- [OK] brief: 0 emoji (compliant=True, expected=True)
- [OK] control-pileup: 8 emoji (compliant=False, expected=False)

## Recommendations

- R1 — Keep the boot mirror unconditional: 14 files now index live; any future 04_Resources addition is one commit from live RAG with zero code.
- R2 — Retrieval is injection-complete (top-3 14/14): the single top-1 tie (مقاطعة shared by Popups/Deep_Work) is a correct ambiguity — both docs serve the query, and the injection block carries all three. No alias surgery needed.
- R3 — Weight accuracy 8/8: any mismatch is a deduce-coverage gap, fixed by extending capability markers (the sanctioned seam), never by prompt edits.
- R4 — Emoji ceiling holds (4/4); keep the counter in the observer as the tripwire — persona prose drifts, numbers don't.
- R5 — TTFT headroom is thin at midday (~1.16s vs 1.2s bar): the next latency win is OmniRoute-side Groq key rotation (owner action), not client retries.
