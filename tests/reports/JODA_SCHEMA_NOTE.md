# JODA Schema Note (Phase-0 spike)

Date: 2026-09-13T13:44:32+0300 · commit: 2e11142
Repo: `Gheith-Abandah/JODA` (Jordanian↔MSA pair corpus, JJCIT 2025).
License: **GPL-3.0** — posture is derive-once-locally: raw xlsx lives
only in gitignored `data/joda/`; the only committed artifact downstream
is the derived markdown encyclopedia. Cite Abandah et al., JJCIT 2025;
diacritized version credit R. Otoum, MSc thesis, Univ. of Jordan 2025.

## Upstream listing

| Name | Type | Size | SHA (12) |
|---|---|---|---|
| Diacritized Version | dir | 0 | dd8ed766c756 |
| LICENSE | file | 35149 | f288702d2fa1 |
| README.md | file | 726 | b46faaa9699d |
| test_set.xlsx | file | 242330 | 9762bd7ab05c |
| train_set.xlsx | file | 5196511 | 6d3f1656d4b8 |
| valid_set.xlsx | file | 244353 | 29428315727d |

## Diacritized Version/ contents

- diacritized_test_set.xlsx (399971 bytes)
- diacritized_train_set.xlsx (8622429 bytes)
- diacritized_valid_set.xlsx (404576 bytes)

## train_set.xlsx (downloaded 5196511/5196511 bytes, sha `6d3f1656d4b8`)

- sheet `Sheet1`: rows=54136 cols=5
  headers:  | Source | Text | Has Error | Text Corrected

Samples (Jordanian side, ≤120ch):

1. «ليست بريئة ،»
2. «أو الذي يطمئن على أحوالي من فترة لأخرى،»
3. «يلي واثق من حاله وإجاباته روح ع بيته ولا فتح فيس يشكي ولا يوتيوب يبكي عليه ،»
4. «وشكلو قرر ينام عندهم لانو كان الوقت متأخرر»
5. «الله يهدي بال الجميع»

## valid_set.xlsx (downloaded 244353/244353 bytes, sha `29428315727d`)

- sheet `Sheet1`: rows=2501 cols=5
  headers:  | Source | Text | Has Error | Text Corrected

Samples (Jordanian side, ≤120ch):

1. «بتخليها تحمل ابنك بقولو داعس ع مرتو ومعذبها»
2. «اشي بيسدد النفس ولله»
3. «​ ونصيب وفير ههه»
4. «كلماتك ليست مربوطه»
5. «يا عمي من اول مأعرفك خليك عالشخصيه الطبيعيه تبعتك فيها اشي ليش تمثل انك الشب المثالي هو انا خطيبتك»

## test_set.xlsx (downloaded 242330/242330 bytes, sha `9762bd7ab05c`)

- sheet `Sheet1`: rows=2501 cols=5
  headers:  | Source | Text | Has Error | Text Corrected

Samples (Jordanian side, ≤120ch):

1. «قالت له أنا والله لا اتصلت فيك ولا حكيت معك ولا عندي تلفون أصلا»
2. «مقصرة او لا»
3. «فإذا خرجت بطلب زوجها لأنه لا يستطيع بمجهوده وحده توفير النفقات اللازمة للأسرة ،»
4. «و الله يبلاك انت و اولادك بمصيبك تلف تلف ما تلقى الها حل»
5. «كم بتكلف الرحله من مثلث الهنيني للخربه مع العلم انو معي كود خصم ٣٠ %»

## Pair-shape verdict

Layout is `| # | Source | Text | Has Error | Text Corrected|` — `Text` carries the Jordanian sentence, `Text Corrected` its MSA correction, `Has Error` flags whether correction was needed. 59,135 data rows total ((54136-1)+(2501-1)+(2501-1)).

**PASS** — Jordanian↔MSA pair mining viable on (Text, Text Corrected).
