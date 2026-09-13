# BENCHMARK 500 — Full Report (mission Stage-4)

Date: 2026-09-13T17:43:23+03:00 · commit: 36869b8 · LLM chain: fallback-direct [groq/openai/gpt-oss-120b]
Turns executed: 500 · live replies: 345 · throttled/skipped: 155
Routing runs on real code paths (classify_weight + deduce + bare registry);
verbatim replies are single live FAST narrations. THROTTLED turns carry
gender/tone N/A — missing data is never scored as FAIL.

## Executive Summary

- Total Scenarios: **500 / 500**
- Gender Integrity Rate: **311/345 = 90.1%** (target 100%)
- Average Latency (live turns): **880.5ms** (p95 1047.5ms)
- Tool Success Rate (registry never raised): **500/500**
- Task Weight Accuracy: **500/500 = 100.0%**
- Tool-Set Accuracy: **500/500 = 100.0%**
- DAG Execution Rate (todo transcript present): **500/500**

## Tone rubric (mechanical heuristic, documented)

- Critical/emergency: zero emoji or FAIL. C turns: emoji or warmth-lexicon hit or FAIL.
- A/B turns: reply ≥30 chars or FAIL. Empty reply: N/A across the board.

## Known routing-divergence classes (contract fidelity, kept as labeled evidence)

- Roleplay verbs collide with tool markers (دور→web_search, أكل→places, شغل→launch, طقس→weather).
- Everyday nouns collide (صوت→media/volume, بطيء→telemetry, اجتماع→calendar, شغل→launch).
- Emergency text naming a readable tool keeps critical weight with the tool traced.
- Production LLM router may resolve these differently; deduce is the deterministic safety net.

## Detailed Findings Table

| ID | Category | Weight | Tools Used | Gender Check | Vibe & Tone Summary | Verbatim Response |
|---|---|---|---|---|---|---|
| A001 | A/multi | 4 | gmail,create_event,schedule | PASS | FAIL+neutral+0emoji+16ch | مع الأسف ما فيني |
| A002 | A/multi | 4 | gmail,create_event,schedule | PASS | PASS+neutral+0emoji+91ch | ما قدرت أوصل لحساب الجيميل هلق، فمحتاج إني أشتغل على الإيميلات بعد ما نربط الحساب.   قوليلي |
| A003 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A004 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A005 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A006 | A/multi | 4 | gmail,create_event,schedule | FAIL | PASS+neutral+0emoji+136ch | يا هلا! للأسف ما قدرت أوصل لجيميلك أو تقويمك هلق، فمش ممكن أشوف الإيميلات ولا أحجز الموعد مباشرة. خبريني بس وقت وتاريخ موعد طبيب الأسنان |
| A007 | A/multi | 4 | gmail,create_event,schedule | PASS | PASS+neutral+0emoji+42ch | مع الأسف ما قدرنا نوصل لحساب الجيميل والتق |
| A008 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A009 | A/multi | 4 | gmail,create_event,schedule | PASS | PASS+neutral+0emoji+57ch | ما فيني أطلع الإيميلات أو أسجل الموعد لأن حساب الجيميل مش |
| A010 | A/multi | 4 | tasks,gmail,schedule | PASS | PASS+neutral+0emoji+189ch | أهلاً عمر،   - بالنسبة للمهام، للأسف ما في عندي وصول لحسابك حالياً فمش قادر أطلع لك القائمة.   - الإيميلات كمان مش متصلة، ما قدرت أفتح الجيميل.    خبرني شو الوقت اللي بتحب تذكّر فيه دواءك ( |
| A011 | A/multi | 4 | tasks,gmail,schedule | PASS | PASS+neutral+0emoji+94ch | هلا عمر! للأسف ما قدرت أجيب لك المهام ولا الإيميلات لأن حساب الجيميل والتقويم مو متصلين حالياً |
| A012 | A/multi | 4 | tasks,gmail,schedule | PASS | PASS+neutral+0emoji+68ch | ما في مهام ولا إيميلات حالياً لأن الجيميل مش متصل—إذا بدك تسجلي مهمة |
| A013 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A014 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A015 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A016 | A/multi | 4 | tasks,gmail,schedule | PASS | FAIL+neutral+0emoji+25ch | هلا يا عمار، ما قدرت أوصل |
| A017 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A018 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A019 | A/multi | 3 | telemetry,gmail | PASS | FAIL+neutral+0emoji+4ch | يا ه |
| A020 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A021 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A022 | A/multi | 3 | telemetry,gmail | PASS | PASS+emojied+1emoji+127ch | حاضر يا عمر، الجسر غير متصل حالياً وحساب الجيميل والتقويم كمان مش متصلين. رح أشتغل على ربطهم وأخبرك فوراً إذا صارت أي تطورات. 🌟 |
| A023 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A024 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A025 | A/multi | 3 | telemetry,gmail | PASS | FAIL+neutral+0emoji+11ch | هلا يا غالي |
| A026 | A/multi | 3 | telemetry,gmail | PASS | PASS+neutral+0emoji+33ch | هلا يا غالي!   للأسف حالياً الجسر |
| A027 | A/multi | 3 | calendar,tasks | FAIL | PASS+neutral+0emoji+124ch | مع الأسف ما قدرت أوصل لحسابك على جيميل/تقويم اليوم، فمش قادر أجيب لك المواعيد والمهام. إذا بتحبي توصليهم، خبريني وأنا جاهزة! |
| A028 | A/multi | 3 | calendar,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A029 | A/multi | 3 | calendar,tasks | PASS | PASS+neutral+0emoji+48ch | يا هلا عمر! للأسف ما قدرت أوصل لتقويمك ولا مهامك |
| A030 | A/multi | 3 | calendar,tasks | PASS | PASS+neutral+0emoji+125ch | مع الأسف ما قدرت أوصل لتقويمك ولا لمهامك هالمرّة. إذا بتساعدني توصل حساب جيميلك أو تدلّني على تفاصيل الاجتماع والمهام، بقدر أ |
| A031 | A/multi | 3 | calendar,tasks | PASS | PASS+neutral+0emoji+85ch | مع الأسف ما قدرت أوصل لتقويمك ولا لمهامك هاللحظة، إذا بتقدر تربط حساب الجيميل، بقدر أ |
| A032 | A/multi | 3 | calendar,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A033 | A/multi | 3 | calendar,tasks | PASS | PASS+neutral+0emoji+161ch | يا هلا! للأسف ما قدرت أوصل لتقويمك ومهامك لأن حساب جيميل مش متصل حالياً. إذا حابة توصليني، ممكن تشغلي الاتصال أو تعطييني صلاحية الوصول، وأنا أجيب لك كل شي فوراً! |
| A034 | A/multi | 3 | calendar,schedule | PASS | PASS+neutral+0emoji+108ch | يا هلا! ما قدرت أوصل لتقويمك هلق، قولي لي شو المواعيد اللي حابة تسجليها لبكرا ومع أي دواء بدك تذكير، وأنا بظ |
| A035 | A/multi | 3 | calendar,schedule | PASS | FAIL+neutral+0emoji+28ch | هلا يا غالية! للأسف حساب الج |
| A036 | A/multi | 3 | calendar,schedule | PASS | PASS+neutral+0emoji+45ch | مع الأسف ما قدرت أوصل لتقويمك هلّأ، فخبرني شو |
| A037 | A/multi | 3 | calendar,schedule | PASS | FAIL+neutral+0emoji+26ch | يا هلا! للأسف ما قدرت أوصل |
| A038 | A/multi | 3 | calendar,schedule | FAIL | PASS+neutral+0emoji+133ch | ما فيني شوف مواعيدك لأن حساب الجيميل مش موصول، خبريني شو العناوين والأوقات وبسجلهم لك. وبالنسبة لسقاية الزرع، قولّي أي وقت بتحبي أذكّ |
| A039 | A/multi | 3 | calendar,schedule | FAIL | PASS+neutral+0emoji+65ch | يا هلا! للأسف ما فيني أوصل لتقويمك هلق، فمحتاج منك تخبريني شو الم |
| A040 | A/multi | 3 | calendar,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A041 | A/multi | 3 | calendar,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A042 | A/multi | 5 | gmail,create_event,schedule,tasks | PASS | PASS+neutral+0emoji+133ch | يا هلا، للأسف ما قدرت أوصل لجيميلك ولا لتقويمك هالمرّة. إذا بتقوليلي عنوان موعد الدكتور والوقت، بعمله لك، وكمان أذكرك بالدواء، وبنظّم |
| A043 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A044 | A/multi | 5 | gmail,create_event,schedule,tasks | PASS | PASS+neutral+0emoji+43ch | أهلاً عمر، ما قدرت أوصل لجيميلك ولا للتقويم |
| A045 | A/multi | 5 | gmail,create_event,schedule,tasks | FAIL | PASS+emojied+1emoji+172ch | يا هلا! للأسف ما قدرت أوصل لجيميلك الآن، فمحتاج منك عنوان موعد الدكتور وتاريخ/وقت عشان أضيفه، وكمان خبريني شو المهام اللي بدك أحطها لك. وبنذكّرك بمكالمة أيمك وقت ما تحبّ! 🌸 |
| A046 | A/multi | 5 | gmail,create_event,schedule,tasks | PASS | PASS+neutral+0emoji+56ch | يا هلا عمر! للأسف ما قدرت أوصل لجيميلك ولا للجدول، فقلّي |
| A047 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A048 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A049 | A/multi | 5 | gmail,create_event,schedule,tasks | FAIL | PASS+neutral+0emoji+165ch | يا هلا وسهلا! للأسف ما قدرت أوصل لحسابك بالجيميل أو التقويم هلق، فمحتاج منك تفاصيل موعد الأسنان وعنوان المكالمة مع أمك حتى أقدر أضيفهم وأذكّرك. خبريني شو بدك بالضبط! |
| A050 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A051 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A052 | A/multi | 3 | schedule,tasks | PASS | PASS+neutral+0emoji+84ch | طبعاً، بدي أعرف متى موعد استحقاق فاتورة الكهربا حتى أحط لك تذكير.   وبالنسبة لمهامك، |
| A053 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A054 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A055 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A056 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A057 | A/multi | 3 | schedule,tasks | PASS | PASS+emojied+1emoji+145ch | أهلاً عمر، لا تنسى تدفع الإيجار اليوم إذا ما خلصت، ولا تتركه يتأخر. 😊   هلق خبرني شو المهام اللي بدك تسجّلها (العنوان والوقت)، وأنا رح أضيفها لك. |
| A058 | A/multi | 3 | schedule,tasks | FAIL | PASS+neutral+0emoji+92ch | أكيد! لا تنسى تنظّف المكتب اليوم قبل ما تبلّش شغلك، وبعدها خبريني شو المهام اللي حابب تشوفها |
| A059 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A060 | A/multi | 3 | schedule,tasks | PASS | FAIL+neutral+0emoji+25ch | أكيد، متى حابب أذكّرك بال |
| A061 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A062 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A063 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A064 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A065 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A066 | A/systems | 2 | web_search | PASS | FAIL+neutral+0emoji+27ch | أكيد يا أستاذ!   **Load Bal |
| A067 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+77ch | أهلاً يا عمر! باختصار، الـ API rate limits هي حدود على عدد الطلبات اللي بتقدر |
| A068 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+86ch | أهلاً عمر، الـ Message Queues هي أنظمة بتنقل الرسائل بين التطبيقات بطريقة غير متزامنة، |
| A069 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A070 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A071 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A072 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A073 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A074 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A075 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+149ch | Feature flags أو الـ “toggles” هي طريقة لتشغيل/إيقاف ميزات التطبيق من غير ما تحتاج تنشر كود جديد؛ بتساعدك تطلق تجارب A/B، تحكم بالتدريج في التحديثات، |
| A076 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A077 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+213ch | Event sourcing هو نمط لتخزين البيانات بيحفظ كل تغيير كـ "حدث" مستقل بدل ما يحدّث السجلات مباشرة؛ هالطريقة بتسمح لك تعيد بناء الحالة الحالية من السجل الكامل، وتسهّل الـ audit، وتدعم الـ replay والـ temporal queries |
| A078 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A079 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A080 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A081 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A082 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A083 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A084 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+113ch | Observability يعني قدرتك تشوف حالة النظام من بره، وتعتمد على ثلاث ركائز أساسية: **القياسات (metrics)**، **السجلات |
| A085 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A086 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A087 | A/systems | 2 | web_search | PASS | FAIL+neutral+0emoji+27ch | Connection pooling هو تجميع |
| A088 | A/systems | 2 | web_search | PASS | PASS+emojied+1emoji+223ch | الـ **Read Replicas** هي نسخ للـ database تُستخدم لقراءة البيانات بس بدون كتابة؛ بتوزّع الحمل وتسرّع الاستعلامات، بتساعد على التوافر العالي وتقلل الضغط على الـ primary، بس لازم تنتبه لتأخر الـ replication وتحديث البيانات. 🌟 |
| A089 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A090 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A091 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A092 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+60ch | التقسيم الأفقي بيقسم السوق حسب الفئات أو الاحتياجات المشابهة |
| A093 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A094 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+228ch | استخدم الـ queue لما بدك تفصل العملية وتخليها تُنَفَّذ بوقت لاحق أو بكمية مُتحكم فيها (مثلاً معالجة رسائل أو مهام خلفية). أما الـ direct call فـِه مناسب للطلبات اللي لازم ترد فوراً وتكون سريعة، وما في داعي لتأخير أو توزيع الحمل. |
| A095 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+267ch | أهلاً عمر! للفرقة الصغيرة، خلّي الـ `main` للنسخة المستقرة، وعملوا فرع `develop` لكل التطوير. كل مبرمج يفتح فرع `feature/اسم‑الميزة` من `develop`، وبعد ما يخلص يرفع Pull Request للـ `develop`، ولما تجهّزوا نسخة جاهزة تدمجوها بالـ `main` وتعملوا Release. هيك بيكون الش |
| A096 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+213ch | أحلى طريقة عمل نسخة احتياطي يومية هي إنك تشغّل برنامج نسخ تلقائي (مثل Backblaze أو Acronis) يرفع ملفاتك للـ cloud كل ليلة، وتضيف كمان نسخة على هارد خارجي وتبدلها كل أسبوع. هيك بتضمن أمان البيانات بدون ما تشيل همّ. |
| A097 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+236ch | أهلاً عمر، لتكتشف الـ bottleneck بالسيرفر، أول شي شوف الـ CPU و الـ RAM باستخدام `top` أو `htop`، بعدين راقب الـ I/O مع `iostat` أو `iotop`، وأخيراً راقب الـ network بـ `iftop` أو `netstat`. إذا وحدة من هالمقاييس دايمًا عالية، هيدي غالب |
| A098 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+181ch | دُكَر بيشتغل كحاوية خفيفة بتشارك نظام تشغيل الـ host، فبيكون أسرع وأقل استهلاك للموارد؛ أما الـ VM فهو جهاز افتراضي كامل بيحتوي نظام تشغيل مستقل، فبيحتاج موارد أكتر وبيكون أبطأ شوي. |
| A099 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+224ch | الـ **blue‑green deployment** هو طريقة لنشر نسخة جديدة من التطبيق بدون ما يوقف الخدمة. بنحافظ على بيئتين: وحدة “أزرق” (النسخة الحالية) ووحدة “خضراء” (النسخة الجديدة). بعد ما نتأكد إن الخضراء شغّالة تمام، نحول حركة المستخدمين |
| A100 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+171ch | اختار الـSQL إذا بياناتك منظمة وعلاقاتها ثابتة، ولازم تقارير دقيقة؛ أما الـNoSQL إذا كنت تتعامل مع بيانات غير مهيكلة، حجم كبير أو تغيّر سريع، وتحتاج مرونة وسرعة في التوسع. |
| A101 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A102 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A103 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+183ch | أول شي، إرجعي للـ backup أو الـ rollback فوراً لتأمين الداتا، بعدين شيّكي الـ logs وتحددي الخطأ، وتعلمي الفريق من اللي صار. وإذا احتجتي مساعدة إضافية أو تنسيق مع الـ DevOps، أنا جاهزة |
| A104 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+153ch | خوارزميات الـLoad Balancer بتوزّع الطلبات على السيرفرات، أشهرها: **Round Robin** (بدور كل سيرفر بالتتابع)، **Least Connections** (بيختار السيرفر اللي عند |
| A105 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A106 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A107 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+291ch | أهلاً عمر، باختصار، في ثلاث استراتيجيات رئيسية للـ caching:    1. **LRU (Least Recently Used)** – بتشيل أقدم البيانات اللي ما إستخدمناها.   2. **LFU (Least Frequently Used)** – بتشيل اللي استُخدمت أقل عدد مرات.   3. **TTL (Time‑to‑Live)** – كل عنصر عنده وقت محدد يظل فيه مخزن، وبعده ينحذف أو |
| A108 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+162ch | إيه، الـ “eventual consistency” يعني إنو البيانات بتتغيّر وتنتشر على كل الأنظمة شوي شوي، فممكن تشوف قيمة قديمة لفترة قصيرة، بس بالنهاية كل شي بيصير متطابق ومحدّث. |
| A109 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+105ch | أحسن طريقة إنك تحط توثيق قوي (API keys أو OAuth) وتحدّ عدد الطلبات لكل مستخدم (rate‑limiting) وتراقب السج |
| A110 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A111 | A/systems | 1 | — | PASS | PASS+emojied+1emoji+181ch | الترانزاكشن (Transaction) هو مجموعة من العمليات على قاعدة البيانات بتنُفّذ ككتلة وحدة، يا إما كلّها تنجح وتُحفظ، يا إما إذا صار أي خطأ تنسحب كلّها وتُرجع البيانات لحالتها الأصلية. 🌟 |
| A112 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A113 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+107ch | TCP هو بروتوكول موثوق وبنظام اتصال، بيضمن توصيل البيانات بترتيبها وصحة وصولها، بس بيكون أبطأ شوي؛ أما UDP ف |
| A114 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+134ch | تنسيق الحاويات (container orchestration) هو إدارة وتنظيم مجموعة حاويات Docker أو غيرها بشكل أوتوماتيكي—بتشغّلها، بتوزّعها، بتوسّعها وت |
| A115 | A/systems | 1 | — | PASS | FAIL+neutral+0emoji+17ch | أول شي تأكّد إنّك |
| A116 | A/systems | 1 | — | PASS | PASS+emojied+1emoji+165ch | سرّ المانجمنت هو طريقة منظمة لتخزين وإدارة المفاتيح، الباسوردات، والبيانات الحساسة بطريقة مشفرة وآمنة، بحيث يقدر الفريق يوصل لها بس لما يحتاج وبأقل مخاطر الاختراق. 🌟 |
| A117 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A118 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+75ch | مشان تتابع استهلاك الذاكرة، على ويندوز افتح “Task Manager” (Ctrl + Shift +  |
| A119 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+171ch | المونوثيلك هو تطبيق واحد كبير فيه كل الوظايف مع بعض، بينما الـmicroservices بيقسم التطبيق لعدة خدمات صغيرة كل وحدة بتشتغل لحالها وبـAPI الخاص فيها، فبيسهل الصيانة والتوسع. |
| A120 | A/systems | 1 | — | PASS | PASS+emojied+1emoji+204ch | تقنيًا "الديون التقنية" يعني التراكمات اللي بنعملها بالمشروع لتسرّع شغلة اليوم، مثل كود غير منظم أو حلول مؤقتة، وبعدين بندفعها لاحقًا بصيانة، إعادة كتابة الكود، أو تحسين البنية عشان ما تعطلنا بالمستقبل. 😊 |
| A121 | A/systems | 1 | — | PASS | FAIL+neutral+0emoji+25ch | اكتب Dockerfile من صورة خ |
| A122 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+285ch | أكيد! باختصار، فيك تستخدم **Git Flow** (main، develop، feature، release، hotfix) إذا المشروع كبير ومعقد، أو **GitHub Flow** (main + short-lived feature branches) للمشاريع السريعة، و**Trunk‑Based** إذا الفريق بحب يدمج كل شي على الـmain باستمرار. كل طريقة لها هدفها حسب حجم وتعقيد الشغل. |
| A123 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+193ch | اختبارات الاندماج (Integration Tests) هي اختبارات بتشوف كيف الوحدات (Modules) أو المكونات الصغيرة بتشتغل مع بعض بعد ما ندمجها، يعني نتأكد إن كل جزء يربط مع التاني بدون مشاكل قبل ما نطلق النظام. |
| A124 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+135ch | أول شي شوف شو الملفات المتصادمة بـ `git status`، افتحها ودور على العلامات <<<<<<< / ======= / >>>>>>>. قرّر أي تغيّر تبقيه، احذف العلام |
| A125 | A/systems | 1 | — | PASS | FAIL+neutral+0emoji+1ch | ق |
| A126 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+126ch | أهلاً عمر! الـ Observability pillars يعني الأعمدة الأساسية لتتبع الأنظمة: **المقاييس (Metrics)** لتعرف الأداء، **السجلات (Logs |
| A127 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A128 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A129 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+158ch | الـ **vertical scaling** يعني إنك تعلي سعة السيرفر الموجود (زيد الـ CPU، الـ RAM، أو الـ SSD)؛ يعني تكبر الشجرة من جذورها.   أما **horizontal scaling** فهو تض |
| A130 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+170ch | أهلاً عمر، لتقدير تكلفة سيرفر تقريبية اتبع الخطوات السريعة هادي:  1. حدد الموارد اللي بدك ياها (CPU، RAM، مساحة تخزين، نقل بيانات).   2. شوف أسعارها عند مزودي الخدمة (AWS |
| A131 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+92ch | أكيد، رح أتواصل مع فريق التقنية حالاً وأبلّغك بأسرع ما يمكن. إذا في شي إضافي تحتاجه، خبريني. |
| A132 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+1ch | أ |
| A133 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+75ch | حاضر، رح أتواصل مع فريق التقنية فورًا وأتابع الوضع. رح أخبرك بأسرع ما يمكن. |
| A134 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+70ch | أوكي، رح أتواصل مع فريق الـ IT حالاً وأبلغك بأسرع وقت عن حالة القاعدة. |
| A135 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+106ch | أوكي، تأكدي إن الاتصال بالإنترنت شغال وجربي تعيدي تشغيل الـ API أو تفحصي الـ endpoint. إذا استمر، ابعتي لي |
| A136 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+136ch | مسا الخير، خبريني أي نسخة من التطبيق عم يواجهوا المشكلة وشو الخطأ اللي بيظهر أو الخطوات اللي بتوصلهم لهالخطأ، حتى نقدر نحدد السبب بسرعة. |
| A137 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A138 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A139 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A140 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+58ch | معكِ سارة، رح أتأكد من الرابط وأعيد تحميل الصور، إذا استمر |
| A141 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+122ch | أهلاً، في أي صفحة أو تطبيق عم تواجه مشكلة تسجيل الدخول؟ وإذا في رسالة خطأ أو اسم المستخدم، خبرني حتى أقدر أساعدك بأسرع حل. |
| A142 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+146ch | أهلاً عمر، أول شي تأكّد إنّو إشعارات التطبيق مفعّلة من إعدادات الجوال، ثم جرّب تعيد تشغيل الجهاز. إذا ما زبط، خبرني أي برنامج أو نظام بتستعمله لنش |
| A143 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+127ch | أكيد يا عمر، خبرني أي نظام كان فيه النسخ (سيرفر، قاعدة بيانات أو ملفات) وأي رسالة خطأ ظهرت، وبنقعد نراجع السجلات ونشوف حل سريع. |
| A144 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+112ch | الشهادة الأمنية انتهت، لازم تجددها أو تتواصل مع فريق الـ IT لتحديثها بأسرع وقت. إذا احتاجت مساعدة إضافية خبريني. |
| A145 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+98ch | أهلاً عمر، فيك تشاركني تفاصيل الخطأ أو اللوجز اللي ظهروا؟ هيك بقدر أساعدك بسرعة ونشوف حلّ للمشكلة. |
| A146 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A147 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+65ch | حاضر، رح أتابع الـ pipeline وأخبرك فور ما يتحسن أو يصير أي تغيير. |
| A148 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+114ch | أوكي، رح أتحقق من تفاصيل الفشل فوراً وأعطيك تحديث خلال دقائق. إذا في أي ملفات أو رسائل خطأ معينة، ابعتها لي حالاً. |
| A149 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+45ch | أكيد، خبريني شو الرسالة أو الخطأ اللي ظهر بال |
| A150 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+59ch | أهلاً عمر، إذا ممكن تشارك تفاصيل الرسالة أو الـ log اللي بي |
| A151 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A152 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+144ch | تأكد إنّك سويت `git pull --rebase` قبل كل `push` وحل أي تعارض ظهر، بعدين جرب `git push -f` إذا كان الـ branch محمي ولازم تعيد كتابة التاريخ. إذا |
| A153 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A154 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+123ch | حاول تسكّر التطبيق وتفتحه من جديد، إذا استمر الكراش امسح الكاش من إعدادات التطبيق أو سحب التطبيق من الخلفية، وإذا ما نفع عا |
| A155 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A156 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A157 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A158 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+147ch | أوكي، جرّبي تمسحي المتصفحات المفتوحة وتغلقي البرامج اللي ما بتستعمليها، وإذا استمرّ الحال أعدي على إعادة تشغيل الجهاز؛ هالخطوة بتنظف الذاكرة وتخفّف |
| A159 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A160 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+90ch | أكيد، خبريني شو بالضبط المشكلة وأي نظام أو جهاز متأثر، وأنا بأتواصل مع فريق التقنية فوراً. |
| A161 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A162 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+114ch | أوكي، أول شي جرّب تعيد تشغيل الجهاز أو تسكبه من التيار وتعيد تشغيله، إذا استمر الحال خبرني بالتفصيل لنشوف حل ثاني. |
| A163 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A164 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+66ch | شو نوع التنبيه؟ وين ظهر؟ خبريني تفاصيل أكتر حتى أقدر أساعدك بسرعة. |
| A165 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+127ch | الداشبورد لونه أحمر، رح أتحقق من المشكلة فوراً وأرجع لك بأسرع وقت. إذا في أي تفاصيل إضافية أو رسائل خطأ، خبريني لتسريع العملية. |
| A166 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A167 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A168 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+85ch | إذا فيك تشوف أي نشاط غير مألوف على حسابك، غير كلمة السر فوراً وفعل المصادقة الثنائية، |
| A169 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+29ch | البورتات مسكرة؟ جرّب تتأكد من |
| A170 | A/emergency | 5!CRIT | telemetry | PASS | PASS+neutral+0emoji+74ch | مستنية شوية، الجسر مش متصل حالياً وعم نشتغل على إصلاحه. رح أعلمك فوراً لما |
| A171 | A/emergency | 5!CRIT | screen_ocr | PASS | PASS+neutral+0emoji+50ch | أكيد، رح أرجع لك النسخة القديمة وأتأكد إن الجسر مت |
| A172 | A/emergency | 5!CRIT | screenshot | PASS | PASS+neutral+0emoji+23ch | تأكد إن الكابل مو مفصول |
| A173 | A/emergency | 5!CRIT | telemetry | N/A | N/A+neutral+0emoji+0ch |  |
| A174 | A/emergency | 5!CRIT | telemetry | PASS | PASS+neutral+0emoji+88ch | الرامات خلصت، بس حالياً الجسر مو متصل، رح أتابع مع فريق التقنية وأخبرك فور ما يصير متاح. |
| A175 | A/emergency | 5!CRIT | network_status | FAIL | PASS+neutral+0emoji+127ch | مستعدة أتحقق من الاتصال فور ما يرجع السيرفر، جربي تعيدي الاتصال بعد شوية وإذا استمر العطل خبريني عشان أرفع الطلب للفريق التقني. |
| B001 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+77ch | أهلاً عمر، إذا كان السرعة الابتدائية 20 م/ث والزاوية 45°، المدى بيطلع تقريباً |
| B002 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B003 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+150ch | يا هلا! لما تقترب من سرعة الضوء، الوقت بيصير يبطئ كتير على حسب اللي عم يتحرك، يعني الساعات عندك رح تشتغل أبطأ من اللي عند اللي واقف على الأرض، ولما تو |
| B004 | B/physics | 1 | — | PASS | PASS+emojied+1emoji+60ch | التيار = V/R = 5 فولت ÷ 10 أوم = 0.5 أمبير، يعني نص أمبير. 😊 |
| B005 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B006 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+59ch | أهلاً، الشغل اللي بتسويه برفع جسم هو \(W = m·g·h\)؛ يعني اض |
| B007 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+158ch | الحث الكهرومغناطيسي يعني إنّه لما تمرّ حركة مغناطيس أو تغير في المجال المغناطيسي حوالين سلك، بيولد تيار كهربائي داخل السلك، يعني "مغناطيس بيخلق كهربا" ببساطة. |
| B008 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B009 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B010 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+213ch | مبدأ عدم اليقين بيقول إنّه كل ما حاولنا نحدد موقع جسيم بدقة، بيصير صعب نعرف سرعته، والعكس صحيح؛ يعني ما فينا نعرف الاتنين بنفس الدقة بنفس الوقت. هالشي بيظهر لأن القياس نفسه بيأثر على الجسيم، فالدقة دايمًا لها حدّ. |
| B011 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B012 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B013 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B014 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+189ch | الاحتكاك هو القوة اللي بتمنع أو تبطئ حركة جسمين وهم بيلمسوا بعض، وفيه كذا نوع: احتكاك سكوني (لما الجسم ثابت) واحتكاك حركي أو انزلاقي (لما يتحرك)، كمان احتكاك تدحرجي (مثل العجل) واحتكاك سائل |
| B015 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+214ch | الموجات الطولية هي اللي بيهزّوا الجسيمات بنفس اتجاه انتشار الموجة، متل الصوت اللي بيهتز الهواء قدّام. أما الموجات العرضية فبتحرك الجسيمات بزاوية ٩٠ درجة عن اتجاه الموجة، زي الموجة اللي بتنتشر على سطح المي أو الضوء. |
| B016 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B017 | B/physics | 1 | — | PASS | FAIL+neutral+0emoji+4ch | المس |
| B018 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+184ch | الجاذبية هي القوة اللي بتخلّي كل شي على الأرض يظل ثابت، يعني بتسحب الأشياء لتحت مثل ما بتسحبنا الأرض لتحت لما نرمي شيء أو نقف. هي السبب إنّو القمر بيدور حولنا وإحنا ما بنطير من الفضاء! |
| B019 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+182ch | العزم هو القوة اللي بتدور شي حوالين نقطة أو محور. بنحسبه بضرب القوة في المسافة اللي بتكون بين نقطة التطبيق ونقطة اللف، وبنضيف زاوية الاتجاه:   \[ \displaystyle \tau = r \times F \;\; |
| B020 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+173ch | المحرك الكهربائي بيشتغل لما يمر التيار عبر ملفات ملفوفة حوالين مغناطيس، بيخلق مجال مغناطيسي يدور ويخلّي العمود (الروتور) يدور، وهالدوارة هي اللي بنستفيد منها لتشغيل الأجهزة. |
| B021 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+177ch | أهلاً يا عمر! كفاءة أي محرك حراري بسيط بتحسبها بـ η = 1 – (Tc/Th) ، يعني لازم تحط درجات الحرارة للمنطقة الباردة (Tc) والساخنة (Th) بالكلفن وتطرح النسبة من الواحد. إذا عطيتني الق |
| B022 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B023 | B/physics | 1 | — | PASS | PASS+emojied+1emoji+158ch | المجال المغناطيسي هو المنطقة حوالين أي مغناطيس أو تيار كهربائي بيأثر فيها على أي معدن أو شحنة متحركة، يعني بيخلّي إبرة البوصلة تدور أو يرفع أشياء من الحديد. 🌟 |
| B024 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B025 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B026 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B027 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B028 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+202ch | شدة الزلزال بنقيسها بمقياس ريختر لل magnitude (قوة الزلزال) ومقياس شدة ماغنوس للـ intensity (الأثر على البشر والبنايات). ريختر بيعطي رقم ثابت، أما ماغنوس بيعتمد على التقارير الميدانية من الناس والمباني. |
| B029 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+131ch | أهلاً وسهلاً! تردد الموجة بيعتمد على سرعتها، فالعلاقة هي \(f = \frac{v}{\lambda}\). إذا عرفت سرعة الموجة (مثلاً سرعة الضوء ≈ \(3×10 |
| B030 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+83ch | الرنين هو ظاهرة إنو الجسم أو النظام بيهتز بأكبر قدر ممكن لما تكون قوة الدفع اللي بت |
| B031 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B032 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+176ch | أهلاً وسهلاً! لتشغّل الليزر، أول شي تأكّد إنك لابست نظارة الحماية، شغّل الطاقة، واضبط القوة والسرعة حسب المهمة، وبعدين اضغط زر التشغيل. ولا تنسى تتبع تعليمات الصانع عشان السلام |
| B033 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+179ch | أكيد، عشان أحسب لك عزم القوة على الباب لازم أعرف: شدة القوة (F) والمسافة من محور الباب (r) وزاوية القوة مع الخط العمودي على الباب (θ). العزم = F × r × sin θ. إذا عندك هالأرقام خبر |
| B034 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B035 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+144ch | الفراغ مش بس "فاضي" من الأشياء، هو مساحة بين الأشياء، لحظة بتخلينا نوقف نفكّر ونرتّب أفكارنا. فـ هو فعلاً فاضي من الشكل، بس مليان فرص وإمكانيات. |
| B036 | B/physics | 1 | — | PASS | PASS+emojied+2emoji+219ch | الأقمار الصناعية بتطلع للفضا على صاروخ، وبعد ما توصل مدارها بتستقبل إشارات (صوت، بيانات، صور) من الأرض أو من أقمار تانية، وتعيد إرسالها للجهات المعنية؛ يعني بتشتغل كجسر بين الأرض والفضا لتوصيل المعلومات بسرعة وسهولة. 🌍🚀 |
| B037 | B/physics | 1 | — | PASS | PASS+emojied+1emoji+79ch | أهلاً عمر! 😊   سرعة المدار التقريبية حوالين الأرض بتعتمد على الارتفاع، لكن للمد |
| B038 | B/physics | 1 | — | PASS | PASS+emojied+1emoji+184ch | المد والجزر هو حركة ارتفاع وانخفاض سطح البحر اللي بتحصل كل شوية بسبب جاذبية القمر والشمس. لما القمر بيكون قريب مننا، بيجرّ البحر وبيصير المد؛ ولما يبعد، بيرجع البحر يهبط ويصير الجزر. 😊 |
| B039 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+50ch | النجوم بتتكوّن أساساً من غاز الهيدروجين اللي بيصير |
| B040 | B/physics | 1 | — | PASS | FAIL+neutral+0emoji+10ch | بتشتغل الث |
| B041 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B042 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B043 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B044 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B045 | B/physics | 2 | web_search | PASS | PASS+emojied+1emoji+93ch | هلا! 🌟 الليزر الطبي بيستخدم بكتير مجالات: عيون (تصحيح النظر وجراحة الشبكية)، جلد (إزالة الوحم |
| B046 | B/physics | 2 | web_search | PASS | PASS+neutral+0emoji+55ch | الطاقة المظلمة هي قوة غامضة بتسارع توسّع الكون، ومُقدّر |
| B047 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B048 | B/physics | 2 | web_search | PASS | PASS+neutral+0emoji+123ch | النسبية العامة، اللي طرحها آينشتاين، بتقول إن الجاذبية مش قوة تقليدية، بل هي انحناء الزمكان بسبب الكتلة والطاقة؛ كل شي بيتح |
| B049 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B050 | B/physics | 2 | web_search | PASS | FAIL+neutral+0emoji+12ch | هلا! إذا بدك |
| B051 | B/math | 1 | — | PASS | PASS+neutral+0emoji+199ch | المشتقة هي “سرعة” أيّ شي بيتغيّر؛ يعني إذا عندك منحنى، المشتقة بتقلك كل نقطة على المنحنى كم هو الميل أو السرعة لحظةً بلحظة. كل ما تغير المنحنى بسرعة، المشتقة تكون أكبر، وكل ما يثبت، المشتقة تصير صفر. |
| B052 | B/math | 1 | — | PASS | PASS+neutral+0emoji+202ch | أهلاً يا غالي! لتلاقي النهاية العظمى، إشتق الدالة، خليك على القيم اللي بتخلي المشتقة صفر أو ما تنعرف، بعدين قيم الدالة عند هالقيم وشوف أي وحدة أعطت أكبر قيمة. إذا كان المجال غير محدود، تأكد كمان من سلوك |
| B053 | B/math | 1 | — | PASS | FAIL+neutral+0emoji+3ch | الم |
| B054 | B/math | 1 | — | PASS | PASS+neutral+0emoji+96ch | القيم الذاتية يعني الأعداد اللي بتطلعلك لما تحل معادلة المصفوفة (det(A‑λI)=0) وبتقلك شو “قوة” أو |
| B055 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B056 | B/math | 1 | — | PASS | PASS+neutral+0emoji+160ch | التكامل هو ببساطة طريقة بنحسب فيها مساحة المنطقة اللي تحت منحنى الدالة، يعني متل ما بنرسم شكل على ورقة وبنقيس مساحته، بس بنستعمل حسابات رياضية بدلاً من المسطرة. |
| B057 | B/math | 1 | — | PASS | PASS+neutral+0emoji+191ch | التوافيق (الكمبينايشن) بتهمّك بس بمجموعة العناصر، ما بهيك ترتيب، يعني {أ، ب، ج} وحدة. أما التباديل (البرميتيشن) فبتقيس كل ترتيب ممكن للعناصر، فـ {أ، ب، ج}، {أ، ج، ب}، {ب، أ، ج}… كل وحدة بتعد! |
| B058 | B/math | 1 | — | PASS | PASS+neutral+0emoji+106ch | لحساب الاحتمال الشرطي بتستعمل الصيغة : \(P(A/B)=\frac{P(A\cap B)}{P(B)}\)  بشرط إنّ \(P(B)>0\). يعني بنقسم |
| B059 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B060 | B/math | 1 | — | PASS | PASS+emojied+1emoji+159ch | المتسلسلة اللانهائية هي مجموع عدد لا نهائي من الحدود، يعني بنضيف أعداد (أو تعابير) إلى ما لا نهاية، وبدنا نعرف إذا هالمجموع بيوصل لقيمة ثابتة (يتقارب) أو لا. 🌟 |
| B061 | B/math | 1 | — | PASS | PASS+neutral+0emoji+180ch | هلا! لتثبت بالاستقراء، أول شي بنثبت القاعدة للـ n=1 (أو أول قيمة)، بعدين بنفترض إنو العبارة صحيحة لـ n=k، وبنوري إنو بتصير صحيحة كمان لـ n=k+1. بهالطريقة بنغطي كل الأعداد الطبيعية. |
| B062 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B063 | B/math | 1 | — | PASS | PASS+neutral+0emoji+179ch | الفضاء المتجهي هو مجموعة من العناصر (نقدر نسميها "متجهات") فيها بنقدر نجمع متجهين مع بعض ونضربهم بأعداد (سكالارات) وبنلتزم بمجموعة قواعد (مثل التبديل، التجميع، وجود العنصر المحايد |
| B064 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B065 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B066 | B/math | 1 | — | PASS | PASS+emojied+1emoji+195ch | الدوال الأسية هي الدوال اللي المتغيّر فيها بيطلع أو بنزل حسب قوة ثابتة، يعني الشكل \(y = a^{x}\) (مع \(a>0\) ومش \(a=1\)). إذا كان الأساس \(a>1\) بيزيد بسرعة، وإذا كان \(0<a<1\) بيقلّ تدريجياً. 😊 |
| B067 | B/math | 1 | — | PASS | PASS+neutral+0emoji+185ch | أهلاً! لتشتق دالة مركبة، استعمل قاعدة السلسلة: إشتق الدالة الخارجية على المتغيّر الداخلي، وبعدين إضربها في مشتقة المتغيّر الداخلي. يعني إذا كان y = f(g(x)) فـ y' = f'(g(x))·g'(x). موفق! |
| B068 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B069 | B/math | 1 | — | PASS | PASS+neutral+0emoji+208ch | التكامل بالتعويض هو طريقة بنستبدل فيها المتغيّر بمتغيّر تاني أسهل، يعني بنحط \(u=g(x)\) وبنكتب \(dx\) بالنسبة لـ \(du\)، بعدين نكمل التكامل بـ \(u\) وبنرجع للمتغيّر الأصلي بالنهاية. باختصار، بنسوّس العملية لت |
| B070 | B/math | 1 | — | PASS | PASS+neutral+0emoji+239ch | هلا! فيك تقيس الوقت اللي ياخده كل خوارزم بـ **الـ “benchmark”**: شغّلهم على نفس المدخلات (نفس الـ input size) واستخدم `time` أو `System.nanoTime()` (حسب اللغة) لتسجّل الزمن. بعدين قارن المتوسطات أو الـ “big‑O” إذا بدك تحليل نظري. بالتوفيق! |
| B071 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B072 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B073 | B/math | 1 | — | PASS | PASS+neutral+0emoji+196ch | أهلا يا عمر! لتقدّر تعقيد loop متداخلة، عدّ عدد مرات تنفيذ الـ inner loop لكل iteration من الـ outer، فالتعقيد بيصير O(n × m) إذا كان الـ outer بيشتغل n مرة والـ inner m مرة (أو O(n²) لو كانوا نفس |
| B074 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B075 | B/math | 1 | — | PASS | PASS+neutral+0emoji+172ch | البرمجة الديناميكية هي طريقة لحل المشاكل الكبيرة بتقسيمها لمشكلات صغار، بنحسب كل جزء مرة وحدة وبنخزن النتيجة عشان ما نعيد الحساب مرة تانية. هالطريقة بتخلّي الحل أسرع وأكفأ. |
| B076 | B/math | 1 | — | PASS | PASS+emojied+1emoji+176ch | هلا! البحث الثنائي بيشتغل إذا كان القايمة مرتبة؛ بنقسمها نصّين، بنقارن العنصر المطلوب مع العنصر النصّي، وبنستبعد النصف اللي ما فيه، ونكرر العملية لحد ما نلاقيه أو يخلص البحث. 🚀 |
| B077 | B/math | 1 | — | PASS | PASS+neutral+0emoji+182ch | أوكي، الـ Quicksort بيقسم القايمة لمجموعة أصغر من العناصر اللي أصغر من عنصر "ال pivot " ومجموعة أكبر، وبيرتب كل مجموعة بنفس الطريقة لحد ما يخلص، فبالعربي بنحصل على ترتيب سريع وفعّال. |
| B078 | B/math | 1 | — | PASS | FAIL+neutral+0emoji+5ch | الهاش |
| B079 | B/math | 1 | — | PASS | PASS+neutral+0emoji+199ch | مشان تقيس دقة النموذج، احسب “accuracy” (نسبة التوقعات الصحّة) أو استعمل مقاييس تانية مثل precision، recall و F1‑score، وكمان ممكن تعمل cross‑validation لتأكد إن الأداء ثابت على مجموعات بيانات مختلفة. |
| B080 | B/math | 1 | — | PASS | FAIL+neutral+0emoji+14ch | الانحدار الخطي |
| B081 | B/math | 1 | — | PASS | PASS+neutral+0emoji+69ch | المصفوفة المعكوسة هي مصفوفة بنضربها بالمصفوفة الأصلية بنحصل على مصفوف |
| B082 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B083 | B/math | 1 | — | PASS | PASS+neutral+0emoji+277ch | المتجه هو شيء عنده مقدار (طول) واتجاه، يعني متل السهم اللي بنرسمه على الخريطة. الضرب القياسي (الـ dot product) بيجمع المتجهين عن طريق ضرب مكوّناتهم المتقابلة وجمع النتايج، وبيعطيك رقم يوضح قديش المتجهين "موجهين" لنفس الاتجاه (إذا الرقم كبير يعني قريبين، وإذا صفر يعني عموديين). |
| B084 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B085 | B/math | 1 | — | PASS | PASS+emojied+1emoji+159ch | أهلاً عمر، إذا عندك المشتقة f′(x) بس سهل، بتكاملها (∫f′(x)dx) وبتضيف ثابت التكامل C. إذا عارف قيمة الدالة بنقطة معينة، استبدلها لتحدد C وتطلع الدالة الأصلية. 🌟 |
| B086 | B/math | 1 | — | PASS | PASS+emojied+1emoji+197ch | أهلاً! النهايّة (limit) بتقلك شو بيقرب قيمة دالة من نقطة معينة إذا قربنا من هالنقطة، والاستمرارية (continuity) معناها إن الدالة ما فيها «قفزات» أو «انقطاعات»؛ يعني بنقدر نرسمها بلا ما نفصل القلم. 🌟 |
| B087 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B088 | B/math | 1 | — | PASS | PASS+neutral+0emoji+159ch | لحساب مساحة تحت المنحنى بتستعمل التكامل المحدد ∫ f(x) dx بين نقطتين a و b. إذا ما عندك صيغة تحليليّة، فيك تستعمل طرق عددية مثل قاعدة شبه المنحرف أو طريقة سيمبس |
| B089 | B/math | 1 | — | PASS | PASS+neutral+0emoji+243ch | يا هلا! تخيلي إنو اختبار للسكري يطلع إيجابي ٩٠٪ للمرضى الحقيقيين، وبيطلع إيجابي ٥٪ للناس اللي ما عندهم. إذا نسبة انتشار السكري عندنا ١٪، فبعد ما يطلع الاختبار إيجابي، احتمال إنو الشخص فعلاً مريض بيكون تقريباً ١٦٪ بس. هالشي هو تطبيق قاعدة بايز. |
| B090 | B/math | 1 | — | PASS | PASS+neutral+0emoji+221ch | التوزيع الطبيعي هو شكل بيظهر كمنحنى “جرس” بيكون أعلى بوسطه (المتوسط) وبيقلّ تدريجياً على الجانبين، وكل نقطة بتمثل احتمال حدوث قيمة معينة حسب الانحراف المعياري. يعني باختصار، هو طريقة إحصائية لتوقع كيف بتنتشر البيانات حوال |
| B091 | B/math | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B092 | B/math | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B093 | B/math | 2 | web_search | PASS | PASS+neutral+0emoji+64ch | أكيد يا عزيزتي! هادي مجموعة من أشهر مسائل الـ NP‑Complete:  - مس |
| B094 | B/math | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B095 | B/math | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B096 | B/math | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B097 | B/math | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B098 | B/math | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B099 | B/math | 2 | web_search | PASS | PASS+neutral+0emoji+70ch | أكيد! فيك تستفيد من Wolfram Alpha (النسخة المجانية)، SageMath، Maxima، |
| B100 | B/math | 2 | web_search | PASS | PASS+neutral+0emoji+160ch | أكيد، الإحصاء البايزي هو طريقة لتحديث احتمالات الفرضيات بناءً على الأدلة الجديدة، يعني بنجمع “ما نعرفه قبل” مع “البيانات اللي بنحصل عليها” لنطلع توقعات أدق. إذا |
| B101 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B102 | B/british | 1 | — | PASS | FAIL+neutral+0emoji+6ch | يا هلا |
| B103 | B/british | 1 | — | PASS | PASS+neutral+0emoji+94ch | يا هلا وسهلا! خلينا نفاوض على السعر ونلاقي لك أحلى صفقة، وبنفس الوقت نتمتع بأجواء لندن الحلوة. |
| B104 | B/british | 1 | — | PASS | PASS+neutral+0emoji+44ch | أهلاً وسهلاً! أنا سارة، مساعدة عمر، وعم بدرس |
| B105 | B/british | 1 | — | PASS | PASS+neutral+0emoji+105ch | يا سلام! تاكسي لندن والسلطان عم يحكي قصصه عن الضباب والبرج إيل، وكأننا جالسين على قهوة عربية بوسط المدينة |
| B106 | B/british | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B107 | B/british | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B108 | B/british | 2 | places | PASS | PASS+emojied+3emoji+100ch | يا هلا! خلينا نطلب fish and chips مع شاي بالنعناع، ونستمتع بأجواء لندن مع لمسة من الدفء الأردني. 🍟☕️ |
| B109 | B/british | 2 | launch | N/A | N/A+neutral+0emoji+0ch |  |
| B110 | B/british | 2 | weather | PASS | PASS+neutral+0emoji+74ch | يا هلا! الجو بإنجلندا اليوم غيوم كثيفة ومطر خفيف، والرياح بتلعب بالباراشوت |
| B111 | B/british | 1 | — | PASS | PASS+neutral+0emoji+101ch | أكيد! “Spot on” معناها “تماماً” أو “على صواب”. مثلاً: “تعليقك كان spot on، يعني حددت المشكلة بالضبط”. |
| B112 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B113 | B/british | 1 | — | PASS | PASS+neutral+0emoji+171ch | أكيـد! لو بدك ترتب قائمة بالأرقام أو النصوص، استعمل `sorted()` هيك:  ```python الأرقام = [5, 2, 9, 1] مرتّبة = sorted(الأرقام)   # النتيجة: [1, 2, 5, 9]  كلمات = ["محمود", |
| B114 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B115 | B/british | 1 | — | PASS | PASS+neutral+0emoji+150ch | أكيد! مثلاً: “فكرة المشروع كانت **brilliant**، يعني عبقرية وفوق توقعاتنا.”   هنا بنستعمل “brilliant” بدل “عبقري” أو “ممتاز” لتضيف لمسة إنجليزية عصرية. |
| B116 | B/british | 1 | — | PASS | FAIL+neutral+0emoji+10ch | أكيد! كلمة |
| B117 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B118 | B/british | 1 | — | PASS | PASS+neutral+0emoji+101ch | كلمة “dodgy” معناها “مشبوه” أو “مش موثوق”. مثال: “هالمحلّ بيبيع سلع dodgy، ما بضمن إنو الجودة منيحة”. |
| B119 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B120 | B/british | 1 | — | PASS | PASS+emojied+1emoji+171ch | أكيد! “Fancy a coffee?” معناها “حابب/حابّة تشرب قهوة؟”   مثلاً: “صباح الخير يا سارة، Fancy a coffee قبل ما نبلّش الشغل؟” أو “بعد ما خلصنا الاجتماع، Fancy a coffee سوا؟”  😊 |
| B121 | B/british | 1 | — | PASS | PASS+neutral+0emoji+147ch | "Spot on" يعني تمامًا على الصح، أو بالضبط ما بدنا. يعني شيّك أو رأيك أو توقعك كان دقيق ومضبوط 100٪. مثال: "إجابتك كانت spot on، ما في أحسن من هيك!" |
| B122 | B/british | 1 | — | PASS | PASS+neutral+0emoji+107ch | "Chuffed" كلمة بريطانية عامية، معناها تكون مبسوط أو فخور حيل بشغلة عملتها أو بشي حصل لك. يعني "مسرور كتير". |
| B123 | B/british | 1 | — | PASS | PASS+neutral+0emoji+188ch | Sorted يعني بترتب العناصر. هو دالة بتاخد أي iterable (قائمة، tuple، إلخ) وبتطلعلك نسخة مرتبة من غير ما تغيّر الأصل، وبتقدر تحدد إذا بدك ترتب تصاعدي أو تنازلي أو تستخدم key لتحديد معيار الت |
| B124 | B/british | 1 | — | PASS | PASS+neutral+0emoji+117ch | "gutted" بالإنجليزي معناها إنك تحس بحزن شديد أو خيبة أمل مِستوى القاع، يعني "مكسر القلب" أو "محبط كتير". كمان ممكن يِ |
| B125 | B/british | 1 | — | PASS | PASS+emojied+1emoji+94ch | "Brilliant" معناها "متلّع" أو "متألق"؛ يعني شيّ فائق الذكاء، أو رائع جدًا، أو بيلمع كالنّور. 😊 |
| B126 | B/british | 1 | — | PASS | PASS+neutral+0emoji+86ch | "Cheeky" معناها شقي أو جريء بطريقة ظريفة؛ يعني شخص بيقول أو يعمل شي بجرأة وفكاهة، كأنه |
| B127 | B/british | 1 | — | PASS | PASS+emojied+1emoji+113ch | "Knackered" كلمة بريطانية معناها إنك تعبان كتير أو مرهق لحد ما ما فيك تتحرك، يعني كأنك "مِسْهَر" أو "مِهْنُوق". 😅 |
| B128 | B/british | 1 | — | PASS | PASS+emojied+1emoji+119ch | كلمة “dodgy” معناها شيّ مش واضح أو مش موثوق فيه، يعني مشبوه، ممكن يكون خطر أو غير أمين، أو حتى شيّ مش متأكد من جودته. 😊 |
| B129 | B/british | 1 | — | PASS | PASS+neutral+0emoji+201ch | "Proper" يعني "مناسب" أو "صحيح" أو "مضبوط" حسب السياق. يعني الشيء يكون على الشكل أو الطريقة المتوقعة أو المطلوبة، مثل: "proper attire" يعني لبس مناسب للمناسبة، و"proper usage" يعني استعمال صحيح للكلمة. |
| B130 | B/british | 1 | — | PASS | PASS+emojied+2emoji+92ch | يعني "حابب/حابّة تشرب قهوة؟" أو "مِشتاق/مِشتاقة لكوب قهوة". بسؤال بسيط إذا بدك تشرب قهوة. ☕️ |
| B131 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B132 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B133 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B134 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B135 | B/british | 1 | — | PASS | PASS+neutral+0emoji+111ch | - سارة: يا عمر، الفكرة اللي قدمتها اليوم كانت **brilliant**!   - عمر: مشكور يا سارة، وأنا متأكد إنو الفريق رح ي |
| B136 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B137 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B138 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B139 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B140 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B141 | B/british | 1 | — | PASS | PASS+neutral+0emoji+55ch | الصيغة الصح هي: **I have gone to London**.   هالـ"gone" |
| B142 | B/british | 1 | — | PASS | PASS+neutral+0emoji+91ch | الجملة الصحيحة: **She doesn’t like tea.** (بدّل “don’t” بـ “doesn’t” لأن الفاعل مفرد مؤنث). |
| B143 | B/british | 1 | — | PASS | PASS+neutral+0emoji+139ch | أحسن تقول: **“Better than before.”**   كلمة “more” ما بتنحتاج معها “better” لأن “better” أصلاً صفة مقارنة. فبهيك بتصير الجملة صحيحة وواضحة. |
| B144 | B/british | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B145 | B/british | 1 | — | PASS | PASS+neutral+0emoji+120ch | الجملة الصح: **He goes to work every day.** (بهذا الشكل بنستعمل “goes” مع “He”، وكلمة “every day” منفصلة عن “everyday”). |
| B146 | B/british | 1 | — | PASS | PASS+neutral+0emoji+111ch | الجملة الصح: **This information is useful.** (أو “These pieces of information are useful” إذا بدك تدل على جمع). |
| B147 | B/british | 1 | — | PASS | FAIL+neutral+0emoji+4ch | العب |
| B148 | B/british | 1 | — | PASS | PASS+neutral+0emoji+86ch | الجملة الصحيحة: **She married him.** (ما في داعي "with" بعد الفعل "marry" بالإنجليزي.) |
| B149 | B/british | 1 | — | PASS | PASS+neutral+0emoji+77ch | الجملة الصح: “I have been waiting for two hours.”   يعني بدال “since” بنستعمل |
| B150 | B/british | 1 | — | PASS | PASS+neutral+0emoji+89ch | الجملة الصحيحة: **It depends on you**.   (يعني "الاعتماد عليك" أو "المسألة بتعتمد عليك".) |
| C001 | C/night | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C002 | C/night | 1 | — | PASS | PASS+emojied+1emoji+75ch | يا حبيبتي، خدي لك دقيقة تنفّسي، شربي شاي أو ماء، ورجعي تكملين بأحلى طاقة! 🌟 |
| C003 | C/night | 1 | — | PASS | PASS+emojied+3emoji+92ch | يا ربّ يصحّيك، خذ لك شوية استراحة، فنجان قهوة أو مشي قصير، وبعدين بنرجع نكمّل الشغل سوا. 🌿☕️ |
| C004 | C/night | 1 | — | PASS | PASS+emojied+2emoji+105ch | يا ريت تهدِّي شوي وتاخد لك فنجان قهوة قبل ما تنام، إذا في شي بقدر أساعدك أو ترتّب لك مهام الصبح خبرني! 🌙☕ |
| C005 | C/night | 1 | — | FAIL | FAIL+neutral+0emoji+145ch | يا عزيزتي، خدي شوية قسط من الراحة عشان الصبح تكوني فايقة وتقدري تكملي التسليم بأحسن شكل. إذا حابة أساعدك بتنظيم الوقت أو ترتيب الأولويات، خبريني! |
| C006 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+7ch | يا غالي |
| C007 | C/night | 1 | — | FAIL | FAIL+neutral+0emoji+84ch | يا سلام! تعبك ما راح هالكم، استاهلِت الراحة. إذا في شي تاني أقدر أساعدك فيه، خبريني. |
| C008 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+157ch | يا هلا! اليوم الليل بيطول لأن الشمس عم تميل بزاوية أقَلّ من الصيف، فـ الأرض ما بتستقبل ضوء الشمس كثير، وبيصير الظلام يطول. باختصار، الفصول وتغيّر زاوية الأرض |
| C009 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+119ch | يا خيي، خذ لك شوية استراحة، شرب ميّة دافية أو قهوة خفيفة، وخلّي النوم يريحك. بعدين رح ترجع تركّز وتكمّل شغلك بأحسن صورة |
| C010 | C/night | 1 | — | PASS | PASS+warm+1emoji+83ch | ما تشيل هم، إن شاء الله رح تخلص وتوصل للنتيجة اللي بدك ياها، وأنا معك خطوة بخطوة! 🌟 |
| C011 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+52ch | يا ريت تريحِّي شوي وتدفي نفسك بشاي بالنعناع، وبس ترو |
| C012 | C/night | 1 | — | PASS | PASS+emojied+1emoji+80ch | يا سلام، تعبك ما بيروح هدر! إذا بدك مساعدة أو ترتيب لمهامك الجايّة، أنا جاهزة. 🌟 |
| C013 | C/night | 1 | — | PASS | PASS+emojied+2emoji+86ch | تمام يا عمر، خذ قسطك من النوم وسوي لك منبه على ساعتين، وبعد ما تصحى نكمل الشغل سوا. 🌙💼 |
| C014 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+74ch | يا سلام، الليالي الهادية تحلى بحديثك! إذا حابب تحكي أو تحتاج شيء، أنا هون. |
| C015 | C/night | 1 | — | PASS | PASS+emojied+2emoji+103ch | آه والله، اليوم كان متعب كتير! إن شاء الله بكرا يجي أهون، ولا تنسى ترتاح وتاخد لك فنجان قهوة أو شاي. 🌿💛 |
| C016 | C/night | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C017 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+93ch | ايه يا غالي، السهر بيخلّي الصبح تعبان. جرّب تحط منبه لطيف وتنام بدري، الصبح بنشاط بيكون أحلى! |
| C018 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+73ch | خد لك وقت ترتاح فيه، استمتع بالهدوء.   نحنا جاهزين نرجع لك لما تكون جاهز! |
| C019 | C/night | 1 | — | FAIL | FAIL+neutral+0emoji+89ch | أيوه، يومك كان متعب فعلاً. إذا في شي أقدر أساعدك فيه أو تحتاج ترتّب شي بعد اليوم، خبريني! |
| C020 | C/night | 1 | — | FAIL | FAIL+neutral+0emoji+58ch | يا هلا! شو حابّة تكملّي هالساعة؟ خبريني وأنا جاهزة أساعدك. |
| C021 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+130ch | يا ريت تاخد لك استراحة صغيرة، شرب شاي بالنعناع وتنفس بعمق، وبعدين رجّع تفكّر بهدوء. إذا بدك أي مساعدة أو ترتيب لمهامك، أنا موجودة! |
| C022 | C/night | 1 | — | PASS | PASS+emojied+3emoji+70ch | أكيد يا غالي، رح أجهّز لك القهوة الثالثة حالًا لتصحى وتكمّل نشاطك! ☕️✨ |
| C023 | C/night | 1 | — | PASS | PASS+emojied+2emoji+116ch | أهلاً يا غالي، تعب اليوم بيقلبنا على أصعب! خد لك فنجان قهوة أو شاي، وخلّي نفسك ترتاح شوي، رح يرجع لك هدوءك بسرعة. 🌿💛 |
| C024 | C/night | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C025 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+94ch | يا سلام، السهرة صارت ماراثون! إن شاء الله بنرتاح بكرا ونكمل شغلنا. إذا احتجتي أي شي أو بدك ترت |
| C026 | C/night | 1 | — | FAIL | FAIL+neutral+0emoji+83ch | يا هلا، خذي لك لحظة استراحة، النوم بيجدد الطاقة. إذا بدك أي شي قبل ما تنام، خبريني! |
| C027 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+124ch | يا هلا، خذ لك قسط من الراحة أو فنجان قهوة خفيفة، النوم الكويس بيرجع لك التركيز. إذا بدك أي مساعدة أو ترتّب لك شي، أنا حاضرة! |
| C028 | C/night | 1 | — | PASS | PASS+emojied+1emoji+88ch | يا سلام! إنتِ قدها وقدود، كل خطوة صغيرة بتقربك من هدفك. شدّي حيلك، وإحنا معكِ على طول! 🌟 |
| C029 | C/night | 1 | — | PASS | PASS+emojied+2emoji+114ch | يا ربّ، الليل ساعات يطوّل، بس تذكّر إن الصبح بيجي ومعاه أمل جديد، وإحنا دايمًا هون إذا بدك تحكي أو تحتاج أي شي. 🌙💛 |
| C030 | C/night | 1 | — | PASS | PASS+emojied+1emoji+84ch | الله يعطيك العافية! تعبك ما يروح، وإنجازك يفرح القلب، استرح شوي وخليك فخور بجهودك. 🌟 |
| C031 | C/night | 1 | — | PASS | PASS+warm+1emoji+68ch | مبروك يا عمر! إذا بدك أي تعديل أو مساعدة إضافية، خبرني وأنا جاهزة. 🌟 |
| C032 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+67ch | يا سلام، الصبح بدري والشمس طالعة! إن شاء الله يومك يكون مليان نشاط. |
| C033 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+32ch | تفضلي، إغمضي عيونك وخدي خمس دقاي |
| C034 | C/night | 1 | — | PASS | PASS+emojied+1emoji+56ch | يا ريت يخلص بسرعة وتلاقي شوية راحة، وإحنا معك كل خطوة! 🌟 |
| C035 | C/night | 1 | — | PASS | PASS+emojied+1emoji+102ch | يا هلا، تعبك واضح! خدي لك فنجان قهوة أو شاي، وقليل من الراحة، وإن شاء الله يروح التعب وتستعيد نشاطك. 🌸 |
| C036 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+95ch | يا هلا، خليك مرتاح وخد لك فنجان قهوة أو شاي، وإلا إذا حاب تنام شوي، خذ قيلولة خفيفة؛ النوم نصفه |
| C037 | C/night | 1 | — | PASS | FAIL+neutral+0emoji+23ch | أهلا وسهلا! إذا حابب تح |
| C038 | C/night | 2 | launch | PASS | FAIL+neutral+0emoji+12ch | يا عمر، جرّب |
| C039 | C/night | 2 | screen_ocr | PASS | FAIL+neutral+0emoji+52ch | أهلاً يا غالي، بعرف قديش هالليلة صعبة لما الكود يعلق |
| C040 | C/night | 2 | close | N/A | N/A+neutral+0emoji+0ch |  |
| C041 | C/night | 2 | launch | N/A | N/A+neutral+0emoji+0ch |  |
| C042 | C/night | 2 | screenshot | N/A | N/A+neutral+0emoji+0ch |  |
| C043 | C/night | 2 | launch | PASS | FAIL+neutral+0emoji+84ch | يا ريت تاخدي لك فاصل صغير، حتى لو فنجان قهوة أو شاي، رح يرجعلك النشاط. وإنتِ أقوى من |
| C044 | C/night | 2 | screen_ocr | N/A | N/A+neutral+0emoji+0ch |  |
| C045 | C/night | 2 | screen_ocr | PASS | FAIL+neutral+0emoji+6ch | يا هلا |
| C046 | C/banter | 1 | — | PASS | PASS+warm+1emoji+62ch | مبروك يا أبطال! فرحتوا معنا، والله إنكم تستاهلوا كل هالفرحة! 🎉 |
| C047 | C/banter | 1 | — | PASS | PASS+warm+0emoji+80ch | يا سلام! مبروك يا عمر، تعبك ما راح هالفاضي. إذا بدك ترتاح أو تحتاج أي شي، خبرني! |
| C048 | C/banter | 1 | — | PASS | PASS+warm+1emoji+57ch | يا بطل/ة! مبروك يا نجمة الصف، تستاهل كل الفرح والتهنئة! 🎉 |
| C049 | C/banter | 1 | — | PASS | PASS+warm+1emoji+70ch | ألف مبروك يا غالي! 🎉 تستاهل كل النجاح، وإن شاء الله دايمًا فوق وتقدّم! |
| C050 | C/banter | 1 | — | PASS | PASS+warm+1emoji+73ch | يا سلام! ما شاء الله، مبروك حلّ المشكلة بعد أسبوع! استرخي هلق واحتفلّي 🎉. |
| C051 | C/banter | 1 | — | PASS | PASS+warm+1emoji+79ch | مبروك يا بطل! 🎉 خلينا نخطط احتفال صغير مع الشباب، بس ما تنسى تدلّهم على شطارتك! |
| C052 | C/banter | 1 | — | PASS | PASS+warm+1emoji+88ch | ألف مبروك يا بطل! 🎉 أول PR مقبول خطوة كبيرة، وأنا متأكدة إنك رح تتقدم أكتر وأكتر. استمر! |
| C053 | C/banter | 1 | — | PASS | PASS+warm+1emoji+67ch | يا سلام! مبروك هالإنجاز، الله يبارك لك ويخليك دايمًا بصحة وعافية! 🌟 |
| C054 | C/banter | 1 | — | PASS | PASS+warm+4emoji+144ch | يا سلام! ألف مبروك يا بطل، ما في أحلى من إنك تكمل أول ماراثون وتثبت إنك قادر على كل شي! 🎉🏃♂️ استمتع بالإنجاز وخليك دايمًا على هالطاقة الإيجابية. |
| C055 | C/banter | 1 | — | PASS | PASS+warm+2emoji+89ch | مبروك يا غالية! 🎉 والله فرحتني خبرك، خطوة كبيرة وإن شاء الله النجاح يظل معك في كل خطوة! 🚀 |
| C056 | C/banter | 1 | — | PASS | PASS+warm+2emoji+55ch | يا هلا وسهلا! مبروك من كل قلبي، فرحتكم بتسعدنا كلنا! 🎉🏆 |
| C057 | C/banter | 1 | — | PASS | PASS+warm+2emoji+83ch | مبروك يا بطل! أول بيع بيفتح لك باب النجاح، الله يبارك لك كل خطوة وتزيد المبيعات! 🎉🚀 |
| C058 | C/banter | 1 | — | PASS | PASS+warm+3emoji+65ch | مبروك يا بطل! 🎉 الله يسهل لك الطريق وتكون دايمًا بأمان وسلامة. 🚗💨 |
| C059 | C/banter | 1 | — | PASS | PASS+warm+0emoji+99ch | يا سلام! مبروك إنك خلصت الكتاب الصعب، أكيد حسيت بفخر كبير! شو رأيك بالكتاب؟ حابب/ة تحكيلي أكتر عنو؟ |
| C060 | C/banter | 1 | — | PASS | PASS+warm+1emoji+93ch | ألف مبروك يا بطل! 🎉 ما شاء الله، هالإنجاز بيستحق كل الفرح، وعقبال ما تروح بأمان على كل دروبك! |
| C061 | C/banter | 1 | — | PASS | PASS+warm+1emoji+50ch | يا سلام! ألف مبروك، أكيد العرض رح يبهركوا كلّهم! 🌟 |
| C062 | C/banter | 1 | — | PASS | PASS+warm+2emoji+79ch | مبروك يا بطل! فوزك بيسعدنا كلنا، وعقبال ما تشوف إنجازات أكبر وأحلى بالبرمجة! 🎉🚀 |
| C063 | C/banter | 1 | — | PASS | PASS+warm+1emoji+92ch | يا سلام! مبروك يا بطل، تستاهل كل الفرح والتهنئة 🎉. يلا احتفلوا وخلينا نعرف شو الخطوة الجاية! |
| C064 | C/banter | 1 | — | PASS | PASS+warm+3emoji+65ch | مبروك يا عمر! 🚗💨 إن شاء الله تكون رحلاتك فيها كل الفرح والراحة. 🎉 |
| C065 | C/banter | 1 | — | PASS | PASS+emojied+3emoji+105ch | يا سلام! أول سفرة لحالك خطوة كبيرة وممتعة. إن شاء الله تكون رحلة مليانة تجارب حلوة وذكريات ما تنساها! 🌍✈️ |
| C066 | C/banter | 1 | — | PASS | PASS+warm+3emoji+55ch | يا سلام! مبروك على النجاح، أكيد الطعم كان ولا أروع! 🎉🍽️ |
| C067 | C/banter | 1 | — | PASS | PASS+warm+2emoji+96ch | مبروك يا بطل! فوزك بهالتحدي بيستاهل كل التصفيق، استمر بهالروح وخلينا نشوفك دايمًا بأعلى طاقة! 🎉💪 |
| C068 | C/banter | 1 | — | PASS | PASS+warm+1emoji+87ch | يا سلام! مبروك إنك خلصت الكورس، تستاهل كل الفخر! 🎉 خلينا نحتفل ونخطط للخطوة الجاية سوا. |
| C069 | C/banter | 1 | — | PASS | PASS+warm+1emoji+88ch | مبروك يا بطل! 🎉 عرضك كان ممتاز، إذا بدك مساعدة بأي شي بعده أو تحضير للمتابعة، أنا حاضرة! |
| C070 | C/banter | 1 | — | PASS | FAIL+neutral+0emoji+80ch | يا ريت كل يوم يجي معك هالفرح! فرحتك بعيون أمّك هي أحلى هدية، الله يديم هالسعادة. |
| C071 | C/banter | 1 | — | PASS | PASS+warm+3emoji+146ch | يا سلام! مبروك يا بطلة، أكيد فرحتِ أبوك كمان! 🎉♟️ استمتعي بالانتصار وتذكري إنّو الشطرنج بيعلمنا الصبر والاستراتيجية، وإنتِ أبدًا بتعرفي كيف تفوزي! |
| C072 | C/banter | 1 | — | PASS | FAIL+neutral+0emoji+39ch | يا هلا! والله البيت صار يلمع من نظافتك. |
| C073 | C/banter | 1 | — | PASS | PASS+warm+1emoji+69ch | يا فرحة! مبروك يا بطل، تستاهل كل التهاني، وشو أحلى إحساس بعد الفوز؟ 🎉 |
| C074 | C/banter | 1 | — | PASS | PASS+warm+1emoji+67ch | يا سلام! مبروك إنك خلّصت بدري، استمتع بوقتك وخلّي نفسك ترتاح شوي. 🌟 |
| C075 | C/banter | 1 | — | FAIL | PASS+emojied+2emoji+58ch | يا سلام! أكيد فرحته ما بتتوصف، خبريني شو كانت المفاجأة 🎉💖. |
| C076 | C/banter | 1 | — | PASS | PASS+warm+2emoji+57ch | يا سلام! مبروك من القلب، تستاهلي كل الفرح والاحتفال! 🎉✨   |
| C077 | C/banter | 1 | — | PASS | PASS+warm+2emoji+71ch | مبروك يا بطل! 💪🏼 ما أحلى إنك بتقهر التحديات وتفاجئ نفسك، استمر بهالروح! |
| C078 | C/banter | 1 | — | PASS | PASS+warm+1emoji+62ch | يا سلام! مبروك يا بطل، شدّينا نطلع على الشعار ونشوف الإبداع! 🌟 |
| C079 | C/banter | 1 | — | PASS | PASS+warm+1emoji+73ch | مبروك يا بطل! أول موقع خطوة كبيرة، وإحنا متحمسين نشوف إبداعك يطير أعلى. 🚀 |
| C080 | C/banter | 1 | — | PASS | PASS+warm+0emoji+94ch | يا سلام! مبروك عالتعلم، هيك بتفتح لك أبواب جديدة. إذا بدك أي مساعدة أو موارد إضافية، أنا حاضر! |
| C081 | C/banter | 1 | — | PASS | PASS+warm+1emoji+96ch | مبروك يا بطل! تستاهل الجائزة وبكل فخر بنفتخر فيك 🎉. استمتع باللحظة وخليها دافع للإنجازات الجاية! |
| C082 | C/banter | 1 | — | FAIL | PASS+warm+1emoji+101ch | مبروك يا غالية! حفظ جزء من القرآن خطوة كبيرة، الله يبارك لكِ ويزيدكِ من علمه. شو الجزء اللي حفظتيه؟ 🌹 |
| C083 | C/banter | 1 | — | PASS | PASS+warm+2emoji+52ch | يا سلام! مبروك على الحفلة، واضح إنك نجمتي السهرة! 🎉✨ |
| C084 | C/banter | 1 | — | PASS | PASS+warm+1emoji+93ch | يا سلام! مبروك يا فخر، أول بودكاست خطوة كبيرة! 🎉 خبرينا شو كان الموضوع وكيف حسيتِ أول ما نزل؟ |
| C085 | C/banter | 1 | — | PASS | PASS+warm+1emoji+80ch | مبروك يا رب! 🎉 إذا بدك مساعدة بتنظيم أي شي أو تخطيط لمصروفات الجائزة، أنا حاضرة! |
| C086 | C/banter | 1 | — | PASS | PASS+warm+0emoji+103ch | يا سلام! مبروك على الشغل المتقن، أكيد الغرفة صارت أروع! إذا بدك أي مساعدة في ترتيب أو تجهيز، أنا حاضرة. |
| C087 | C/banter | 2 | launch | PASS | PASS+warm+1emoji+71ch | يا سلام! هالمديح من المدير قدام الكل بيخلينا نفخر بشغلنا، مبروك عليك! 🎉 |
| C088 | C/banter | 2 | read_page | PASS | PASS+warm+1emoji+86ch | مبروك يا بطل! أول خطوة هي الأصعب، وإحنا واثقين إن مقالاتك الجاية رح تكون أحلى وأقوى 🌟. |
| C089 | C/banter | 2 | media | PASS | FAIL+neutral+0emoji+26ch | يا سلام! برافو عليك، هالإن |
| C090 | C/banter | 2 | media | PASS | PASS+warm+1emoji+78ch | مبروك يا بطل! 🎉 أول فيديو على القناة خطوة كبيرة، وإن شاء الله بيجذب متابعين كت |
| C091 | C/vent | 1 | — | FAIL | PASS+emojied+1emoji+101ch | يا عيني، والله إنّو الأيام الصعبة بتعدّي، إذا في شي فيني أساعدك أو أرتّب لك شي لتخفّف عليك، خبريني. 🌷 |
| C092 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+84ch | يا حبيبة قلبي، هالشي صعب ومؤلم، إذا بدك تحكي أو تحتاج أي مساعدة، أنا هون وبكل ودّ. 🌸 |
| C093 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+123ch | يا غالي، ما في شي بحدود الفشل، كلنا بنمر بأوقات صعبة. صدقني، إنت أقوى من ما تتصور، وخطوة صغيرة اليوم بتفتح لك باب كبير غداً |
| C094 | C/vent | 1 | — | PASS | PASS+warm+0emoji+122ch | يا حبيبي، كلنا بنمر بأوقات صعبة، وأنا هون عشان أسمعك وأساعدك بأي شي تحتاجه. خبرني شو أكتر شي مضايقك، ونشوف سوا حلّ يناسبك. |
| C095 | C/vent | 1 | — | FAIL | FAIL+neutral+0emoji+92ch | يا غالية، أحيانًا الناس بيخلّونا نحس إنّ الدنيا ثقيلة، خدي لكِ لحظة تنفّسي فيها وتروحي لمكان |
| C096 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+108ch | يا غالي، خذ لك نفس عميق، وحاول ترتّب أولوياتك خطوة بخطوة. إذا بدك شي أساعدك بتنظيم أو حتى أسمعك، أنا موجودة! |
| C097 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+82ch | ما تشيل هم، أنا معاك دايمًا وإذا حاب تحكي أو تحتاج أي مساعدة، أنا هون وبقلب مفتوح! |
| C098 | C/vent | 1 | — | FAIL | PASS+emojied+1emoji+87ch | يا حبيبتي، إن شاء الله هالدوخة تمر، إذا في شي بقدر أساعدك فيه أو ترتاحي شوية، خبريني! 🌸 |
| C099 | C/vent | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C100 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+93ch | يا غالي، ما تشيل همّ كتير، كلنا بنمر بهالمرحلة. خليك عم تتخطى خطوة خطوة، وأنا جنبك إذا بدك أي |
| C101 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+130ch | يا غالي، الواحد أحيانًا بيحس بالوحدة حتى وإحنا محاطين بالناس. إذا حاب تحكي أو تحتاج مساندة، أنا موجودة، وما في شي أحلى من إنك تشعر |
| C102 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+91ch | أهلا يا غالي، كلنا بنمر بأوقات صعبة، وإذا حاب تحكي أو تحتاج مساعدة بأي شي، أنا موجودة لك. 🌷 |
| C103 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+96ch | يا عزيزتي، خدي نفس عميق وركزي على شغلة بسيطة تفضّل بالك. إذا حابة تحكي أو تحتاجي نصيحة، أنا هون. |
| C104 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+69ch | ما تخاف، إنتِ أكيد رح تعمليها! شدّي حيلك، ركّزي، وكل شي بيجي بوقته. 🌟 |
| C105 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+72ch | يا زلمة، البيت دايمًا فيه شغلات، بس إذا بدك مساعدة أو نصيحة، أنا حاضر! 🌟 |
| C106 | C/vent | 1 | — | PASS | PASS+warm+0emoji+114ch | يا حبيبي، كلنا بنمر بأوقات ضايعة، خليك واثق إن الطريق راح يوضح مع خطوة بخطوة. إذا بدك أي مساعدة أو نصيحة، أنا هون! |
| C107 | C/vent | 1 | — | FAIL | PASS+emojied+2emoji+142ch | صحيح، التعب النفسي بيقعد يركّب على القلب أكتر من أي وجع جسدي. خدي لكِ شوية وقت تهدّئي، تنفّسي بعمق، وحاولي تمارسي شي بتحبيه حتى يخفّ الضغط. 🌿💛 |
| C108 | C/vent | 1 | — | PASS | PASS+warm+1emoji+90ch | يا حبيبي، خذ نفس عميق وحاول تهدّئ قلبك. إذا بدك تحكي أو تحتاج مساعدة، أنا هون وإيدك معك. 🌹 |
| C109 | C/vent | 1 | — | FAIL | PASS+emojied+1emoji+91ch | يا هلا، خدي نفس عميق وارتاحي شوي، إذا في شي بقدر أساعدك فيه أو أرتب لك وقت للراحة خبريني. 🌿 |
| C110 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+102ch | أعرف شعورك، الدنيا أحياناً بتكون صعبة، بس إذا في شي أقدر أساعدك فيه أو تحتاجي تنفسي شوي، أنا موجودة! 🌸 |
| C111 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+26ch | يا غالي، بحسّ معاك هالضيق، |
| C112 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+50ch | يا غالية، خدي نفس عميق وفكري إنك مش لحالك، أنا جنب |
| C113 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+91ch | يا غالي، أحيانًا القريب بيجرّح أكتر، خذ لك شوية وقت تهدّى وتفكّر، وإذا حاب تحكي أنا موجودة. |
| C114 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+121ch | يا غالي، ما تخاف! كلنا إلنا توقيتنا الخاص، وإنت دايمًا ببالغ وتستاهل كل خير. خليك صبور، وإن شاء الله بتوصل للّي بدك إياه. |
| C115 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+111ch | يا حبيبتي، ما تخلي المقارنات تسلب منكِ فرحتك، إنتِ مميزة بطريقتك الخاصة، وكل خطوة بتقدميها هي إنجاز بحد ذاته. 🌸 |
| C116 | C/vent | 1 | — | FAIL | FAIL+neutral+0emoji+50ch | يا عزيزتي، خدي لكِ هالوقت اللي بدك إياه، وأنا رح أ |
| C117 | C/vent | 1 | — | PASS | PASS+emojied+2emoji+76ch | يا غالي، بسمعك وقلبي معك، إذا بتحب نتكلم أو أساعدك بشي يخفف عنك، أنا هون. 🌿💛 |
| C118 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+27ch | يا غالي، ما في شي بيستاهل ي |
| C119 | C/vent | 1 | — | PASS | PASS+emojied+2emoji+104ch | يا عزيزتي، خدي شوية نفس عميق، جرّبي تشربي شاي بالبابونج قبل ما تنامي، وإن شاء الله النوم ييجيك بسرعة. 🌙💤 |
| C120 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+60ch | أنا معاك، احكيلي كل شي بدون أي حكم، وأنا أسمعك من كل قلبي. 🌷 |
| C121 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+49ch | يا غالي/غالية، إنت/إنتِ أكتر من كفاية، وإحنا كلنا |
| C122 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+105ch | يا غالية، خدي نفس عميق وفكري إنك دايمًا أقوى من الخوف. إذا بدك تحكي أو ترتبي شغلات بكرا، أنا موجودة جنبك! |
| C123 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+131ch | يا غالي، كلنا بنمر بأوقات ما بنحس فيها إنو الشغل له معنى، جرّب توقف شوي، فكّر شو الأشياء اللي بتفرحك وإيش بتحب تعطي فيها وقتك، يمكن |
| C124 | C/vent | 1 | — | PASS | PASS+emojied+3emoji+103ch | يا غالي، بعرف إنو الإحباط بيقلب الدنيا، بس تذكر إنو كل سحابة فيها شمس، وإحنا دايمًا معاك نرفعك فوق. 🌤️💪 |
| C125 | C/vent | 1 | — | PASS | FAIL+neutral+0emoji+46ch | يا عيني، فهمانك، إذا بدك تحكي أو تحتاج شي، أنا |
| C126 | C/vent | 1 | — | PASS | PASS+emojied+1emoji+101ch | يا غالي، إذا قلبك تقيل، خذ لك نفس عميق وفكّ شوي. إذا في شي أقدر أساعدك فيه أو تحكي معي، أنا موجودة. 🌹 |
| C127 | C/vent | 1 | — | FAIL | PASS+emojied+1emoji+70ch | ما في مشكلة، إذا احتجتي أي شي أو حابة أي مساعدة، أنا موجودة هون لكِ. 🌷 |
| C128 | C/vent | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C129 | C/vent | 2 | convert_currency | PASS | FAIL+neutral+0emoji+31ch | يا غالي، إنت مش عبء أبداً، إحنا |
| C130 | C/vent | 2 | telemetry | PASS | FAIL+neutral+0emoji+26ch | ما تشيل همّ، خذ وقتك على م |
| C131 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+144ch | صباح الخير! اليوم كان مشغول شوي مع مواعيد عمر، رتبت له اجتماعات، جهزت تقارير، وبعد الظهر خدت قهوة سريعة مع الزملاء وتكلمنا عن خطط الأسبوع. الحمد |
| C132 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C133 | C/masc | 1 | — | PASS | PASS+emojied+1emoji+108ch | صراحةً، بحس إن الفكرة ممتازة وإنه إذا بدّكِ تدعمّيها بخطوات واضحة، رح توصلين للنتيجة اللي بتستحقيها بسرعة. 🌟 |
| C134 | C/masc | 1 | — | PASS | PASS+emojied+1emoji+122ch | اليوم كنت مشغولة بترتيب جدول عمر، حضرت اجتماع مهم، وجبت له قهوة الصبح، وبعدها رتبنا شوية ملفات وطلّعنا شوية طلبات سريعة. 😊 |
| C135 | C/masc | 1 | — | PASS | PASS+emojied+1emoji+130ch | ههههه، في مرة واحد سأل القهوة: "ليش ما بتسهر؟" ردت القهوة: "لأنها دايمًا على فنجانها!" 😄  إن شاء الله ضحكة خفيفة ترفع لك معنوياتك! |
| C136 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+45ch | أهلاً! هالأيام التقنية عم تتسارع: الذكاء الاص |
| C137 | C/masc | 1 | — | PASS | PASS+emojied+2emoji+128ch | اليوم فطرت فلافل مع شاورما صغنونة، وبعد الظهر أكلت شاورما لحم مع صحن حمص ولبن، وبالليل جبت شطيرة جبنة وزيتون مع شاي بالنعناع. 🍽️ |
| C138 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C139 | C/masc | 2 | calendar | PASS | FAIL+neutral+0emoji+30ch | أهلاً عمر، أي اجتماع تقصد؟ خبر |
| C140 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+24ch | الفكرة حلوة كتير ومليانة |
| C141 | C/masc | 1 | — | PASS | PASS+emojied+1emoji+57ch | يا هلا! فكرة حلوة، يلا نرتب المشوار ونشوف وين بدك تروح. 🌟 |
| C142 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C143 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+110ch | يا هلا، بعتقد إنو القرار خطوة قوية ومبنية على تفكيرك الحكي، وإن شاء الله يفتح لك أبواب النجاح اللي بتستاهليها! |
| C144 | C/masc | 1 | — | PASS | PASS+emojied+1emoji+126ch | يا هلا! فكرة حلوة، خلينا نحدد مع بعض هدف واقعي وخطة مرنة تناسب جدولك، وبنحط لك شوية نصايح غذائية سريعة عشان تبقى على المسار. 🌿 |
| C145 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C146 | C/masc | 1 | — | PASS | PASS+emojied+1emoji+83ch | يا هلا! إذا بتشاركني الخبر أو تفاصيله، بقدر أعطيك رأيي بصراحة وبالدارجة الأردنية. 🌟 |
| C147 | C/masc | 1 | — | FAIL | FAIL+neutral+0emoji+113ch | بالنسبة إلي، الأفضل نأجل السفرة لتقليل الضغط على جدولنا. خبريني إذا فيه موعد ثاني يناسبك، وأنا أضبط كل الترتيبات. |
| C148 | C/masc | 2 | launch | N/A | N/A+neutral+0emoji+0ch |  |
| C149 | C/masc | 2 | schedule | N/A | N/A+neutral+0emoji+0ch |  |
| C150 | C/masc | 2 | schedule | PASS | PASS+emojied+1emoji+55ch | أكيد يا غالي، شو الوقت اللي بتحب يجيك التذكير؟ 🌸 (مثلاً |
| C151 | C/masc | 2 | schedule | FAIL | PASS+emojied+1emoji+71ch | أكيد! خبريني شو عنوان الموعد وتاريخ ووقت الحجز، وأنا رح سجل لك تذكير. 😊 |
| C152 | C/masc | 2 | schedule | N/A | N/A+neutral+0emoji+0ch |  |
| C153 | C/masc | 2 | schedule | PASS | FAIL+neutral+0emoji+75ch | أكيد يا عمر، خبرني متى حابب أضيف التذكير، وعنوانه بالضبط، وأنا رح أرتبه لك! |
| C154 | C/masc | 2 | schedule | PASS | PASS+emojied+1emoji+66ch | أكيد، خلّي أضيف لك تذكير. شو عنوان المهمة ومتى حابب تراجع الدرس؟ 🌟 |
| C155 | C/masc | 2 | schedule | PASS | FAIL+neutral+0emoji+54ch | يلا يا عمر، خليك تنام بدري هالليلة، بدك تصحى نشيط بكرا |
| C156 | C/masc | 2 | schedule | N/A | N/A+neutral+0emoji+0ch |  |
| C157 | C/masc | 2 | schedule | N/A | N/A+neutral+0emoji+0ch |  |
| C158 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C159 | C/masc | 1 | — | FAIL | FAIL+neutral+0emoji+64ch | أيوة سامعك يا غالي، كل شيء واضح. خبريني شو بدك وأنا جاهزة أساعدك |
| C160 | C/masc | 1 | — | FAIL | FAIL+neutral+0emoji+121ch | يا هلا، المشروع ماشي تمام وعلى المسار المطلوب، كل شي متتابع حسب الجدول. إذا حابة تفاصيل إضافية أو أي تعديل، خبريني فوراً! |
| C161 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C162 | C/masc | 1 | — | FAIL | PASS+emojied+1emoji+31ch | يلا خبريني، شو صار معك اليوم؟ 😊 |
| C163 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+46ch | سمعتك، قولّي شو بدك هالمرة، وأنا جاهزة أساعدك! |
| C164 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+59ch | ما في صورة مرفقة، فيك تحمّلها مرة تانية أو توصفلي إياها؟ رح |
| C165 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+80ch | أكيد يا غالي، خبرني شو المشكلة بالضبط أو تفاصيلها، وأنا بساعدك بحلّها بأسرع وقت! |
| C166 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C167 | C/masc | 1 | — | PASS | PASS+warm+1emoji+39ch | الحمد لله، كله تمام! إنت كيفك يا بطل؟ 😊 |
| C168 | C/masc | 1 | — | PASS | PASS+emojied+1emoji+48ch | هلا وغلا! أنا هون، جاهزة أساعدك بأي شي تحتاجه. 😊 |
| C169 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+92ch | هلا وغلا! اليوم شغّال على ترتيب مواعيد عمر وتحضير التقارير، وبنقّش شوية أمور جديدة. إنت كيف؟ |
| C170 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+77ch | يا هلا! كان يومي مشغول شوية، بس الحمد لله كل شي تمام. وإنت/إنتِ كيف كان يومك؟ |
| C171 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+103ch | هلا وغلا! ما في شي جديد غير شغلات عمر اللي ما بتنتهي، بس دايمًا بحاول أخلي كل شي يمشي بسلاسة. إنت كيفك؟ |
| C172 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+20ch | أنا سارة، مساعدة عمر |
| C173 | C/masc | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| C174 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+136ch | اليوم جهزت لك جدول الاجتماعات الصبح، تقارير المشروع، ومراجعة البريد الوارد، وكمان ترتيب للغداء مع الفريق. إذا في شي تاني بدك إياه خبرني! |
| C175 | C/masc | 1 | — | PASS | FAIL+neutral+0emoji+48ch | الحمد لله، معنوياتي تمام! كيف فيني أساعدك اليوم؟ |
