---
title: JODA Jordanian Patterns
type: knowledge-base
date: 2026-09-14
summary: Comprehensive empirical catalog of urban Jordanian dialect morphology, discourse markers, conversational pacing, and phonology extracted from 59,135 live sentences.
tags: [dialect, ar-jo, ammani, joda, phonology]
aliases: [لهجة أردنية, حكي أردني, عامية عمانية, JODA, ar-JO, مصطلحات أردنية]
---

# JODA Jordanian Patterns — distilled dialect encyclopedia (Phase-5)

Date: 2026-09-13T14:49:06+0300 · commit: 7852720
Corpus: Gheith-Abandah/JODA train+valid+test = **59135** pairs (train_set.xlsx:54135, valid_set.xlsx:2500, test_set.xlsx:2500; 0 skipped).
Method: deterministic stdlib mining (Counter sorts, no randomness, no LLM).
License: raw corpus GPL-3.0, gitignored under `data/joda/` — this file is
derived original expression. Cite Abandah et al., JJCIT 2025; diacritized
credit R. Otoum, MSc thesis, Univ. of Jordan 2025.
Tiers: VERIFIED (count≥threshold) vs SINGLETON (below threshold, excluded).

## 1. High-frequency collocations

### Bigrams (min count 5)

| Collocation | Count |
|---|---|
| شاء الله | 452 |
| ما في | 248 |
| و انا | 242 |
| ان شاء | 208 |
| الله عليه | 199 |
| و ما | 194 |
| اكثر من | 187 |
| حسبي الله | 186 |
| ونعم الوكيل | 183 |
| الله ونعم | 180 |
| بارك الله | 168 |
| كل ما | 165 |
| في كل | 163 |
| يا رب | 156 |
| صلى الله | 153 |
| جزاك الله | 151 |
| الله لا | 147 |
| كل شي | 146 |
| و لا | 145 |
| عليه وسلم | 144 |
| ما شاء | 141 |
| من كل | 140 |
| الحمد لله | 138 |
| حتى لو | 138 |
| كل واحد | 137 |
| كل يوم | 134 |
| في هذا | 133 |
| ما كان | 132 |
| و هو | 132 |
| في البيت | 131 |
| ما حدا | 128 |
| على كل | 127 |
| بس ما | 123 |
| يا ريت | 119 |
| الله فيك | 116 |
| قبل ما | 116 |
| في ناس | 115 |
| مش عارف | 115 |
| بعد ما | 113 |
| والله ما | 113 |

### Trigrams (min count 5)

| Collocation | Count |
|---|---|
| ان شاء الله | 197 |
| الله ونعم الوكيل | 175 |
| صلى الله عليه | 151 |
| الله عليه وسلم | 144 |
| ما شاء الله | 136 |
| حسبي الله ونعم | 118 |
| بارك الله فيك | 95 |
| جزاك الله خيرا | 63 |
| إن شاء الله | 61 |
| الرجال قوامون على | 57 |
| قوامون على النساء | 55 |
| النبي صلى الله | 40 |
| لا حول ولا | 39 |
| كل الاحترام والتقدير | 38 |
| جزاك الله خير | 37 |
| الرسول صلى الله | 36 |
| حسبنا الله ونعم | 35 |
| حول ولا قوة | 33 |
| الله صلى الله | 32 |
| الله عز وجل | 32 |

## 2. Sentence starters (first-2-token patterns)

| Starter | Count |
|---|---|
| جزاك الله | 108 |
| بارك الله | 104 |
| حسبي الله | 90 |
| ما شاء | 85 |
| الحمد لله | 74 |
| يا ريت | 71 |
| ماشاء الله | 69 |
| والله انك | 60 |
| كل الاحترام | 59 |
| والله ما | 59 |
| الله لا | 58 |
| ان شاء | 55 |
| و انا | 55 |
| ما في | 54 |
| اقسم بالله | 53 |
| سبحان الله | 53 |
| شو يعني | 53 |
| والله يا | 51 |
| يا الله | 48 |
| ليش ما | 47 |

## 3. Colloquial discourse markers (position-initial)

| Marker | Count |
|---|---|
| و | 1630 |
| انا | 1163 |
| شو | 1064 |
| لا | 896 |
| بس | 890 |
| ما | 867 |
| الله | 834 |
| والله | 784 |
| يا | 721 |
| كل | 609 |
| يعني | 600 |
| من | 552 |
| في | 423 |
| انت | 397 |
| مش | 374 |
| لو | 350 |
| ولا | 335 |
| هذا | 333 |
| طيب | 318 |
| ليش | 304 |

## 4. Polysemy matrix (JO form → distinct MSA glosses)

### Mandate seeds

- **شغال** → خادمة(39), الخادمة(9), يعمل(9), أما(6), أنت(6), المرأة(6), ولا(6), أشغال(5)
- **ماشي** → حسنا(47), يمشي(12), حسنا،(9), أمشي(8), تمشي(7), لك(7), وهو(7), يا(7)
- **فضيت** → أتحدث(1), أتفرغ،(1), أرى(1), أعشب(1), انشغلت(1), حبيبتي،(1), دعيني(1), عزمت،(1)
- **فاضي** → دون(93), فائدة(44), جدوى(41), فارغ(37), كلام(24), بلا(22), فائدة،(21), الفارغ(17)
- **ع راسي** → رأسي(16), إلي(2), الخلف(2), نفسا(2), وصار(2), آخد(1), أبي(1), أجل(1)
- **يا دوب** → بالكاد(16), وبالكاد(5), أحد(2), الآن(2), الأردن(2), فقط(2), فلا(2), وبدأت(2)

### Discovered candidates (freq≥20, ≥2 glosses @count≥3)

| JO token | #glosses | top MSA glosses |
|---|---|---|
| الله | 1237 | الله،, يا, شاء, -صلى, أنت |
| انا | 1163 | لي, أعرف, يا, أريد, ماذا |
| الي | 778 | لي, شيء, يا, أنت, له |
| ولا | 683 | شيء, إلا, ولم, أحد, أنت |
| اللي | 625 | أنت, يا, أنه, شيء, مثل |
| كان | 499 | هناك, أنه, يكن, شيء, وكان |
| انو | 472 | أنه, هناك, لي, إنه, شيء |
| يعني | 438 | أعني, ماذا, أي؛, أنت, أنه |
| والله | 436 | والله،, يا, إنك, أنت, شيء |
| اشي | 396 | شيء, شيئا, شيء،, هناك, يوجد |
| لما | 351 | حين, إلا, أنه, حتى, لي |
| حتى | 304 | ولا, أنه, أنت, يا, شيء |
| الناس | 303 | الناس،, يا, أنت, ماذا, هناك |
| هذا | 302 | المقطع, يا, أنت, أنه, وهذا |
| اذا | 298 | أنت, أردت, إلا, وإذا, كنت |

## 5. Gender markers (corpus audit grounding persona exemplar tests)

- Feminine first-person attestations: **11** (`أنا جاهزة` `أنا بقدر` `رح أعمل` `أنا سارة` `بدي أحكي`)
- Masculine address attestations: **1494** (`بدك` `شو رأيك` `عمر` `شغلك` `يومك`)
- Persona rule (enforced by unit test, not by corpus majority): Sara speaks
  feminine first-person (أنا جاهزة/رح أعمل); Omar is addressed masculine
  (بدك/عمر) — second-person-feminine forms are rejected in exemplar lines.

_Mined in 9.9s; content deterministic given identical inputs (header date excluded)._
