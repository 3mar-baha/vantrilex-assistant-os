# BENCHMARK 500 — Full Report (mission Stage-4)

Date: 2026-09-13T18:23:22+03:00 · commit: report-only · LLM chain: n/a (no live calls)
Turns executed: 254 · live replies: 88 · throttled/skipped: 166
Routing runs on real code paths (classify_weight + deduce + bare registry);
verbatim replies are single live FAST narrations. THROTTLED turns carry
gender/tone N/A — missing data is never scored as FAIL.

- Status: **PARTIAL (254/500)** — free-pool quota exhaustion halted live collection; resume with a plain rerun (records persist, done IDs skip). THROTTLED turns carry gender/tone N/A — missing data is never scored.

## Executive Summary

- Total Scenarios: **254 / 500**
- Gender Integrity Rate: **86/88 = 97.7%** (target 100%)
- Average Latency (live turns): **1970.3ms** (p95 13355.2ms)
- Tool Success Rate (registry never raised): **254/254**
- Task Weight Accuracy: **254/254 = 100.0%**
- Tool-Set Accuracy: **254/254 = 100.0%**
- DAG Execution Rate (todo transcript present): **254/254**

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
| A001 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A002 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A003 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A004 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A005 | A/multi | 4 | gmail,create_event,schedule | PASS | PASS+neutral+0emoji+81ch | عذرًا يا عمر، ما قدرنا نوصل للجيميل حالياً، فمحتاج إني أعرف تفاصيل موعد الأسنان ( |
| A006 | A/multi | 4 | gmail,create_event,schedule | PASS | PASS+neutral+0emoji+93ch | خبرني إذا بدك أساعدك بجدولة موعد الأسنان، قول لي التاريخ والوقت. وبالنسبة لمكالمة أمي، رح أذك |
| A007 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A008 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A009 | A/multi | 4 | gmail,create_event,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A010 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A011 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A012 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A013 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A014 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A015 | A/multi | 4 | tasks,gmail,schedule | PASS | FAIL+neutral+0emoji+19ch | خبرني إذا بدك أساعد |
| A016 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A017 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A018 | A/multi | 4 | tasks,gmail,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A019 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A020 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A021 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A022 | A/multi | 3 | telemetry,gmail | PASS | PASS+neutral+0emoji+82ch | الجسر مو متصل هلق، وكمان الجيميل والتقويم مو متصلين وما قدرت أوصل لحسابك على جوجل. |
| A023 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A024 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A025 | A/multi | 3 | telemetry,gmail | N/A | N/A+neutral+0emoji+0ch |  |
| A026 | A/multi | 3 | telemetry,gmail | PASS | PASS+neutral+0emoji+50ch | خبرني إذا بدك أعمل فحص للمعالج والرام يدوياً، وبما |
| A027 | A/multi | 3 | calendar,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A028 | A/multi | 3 | calendar,tasks | PASS | PASS+neutral+0emoji+58ch | ما فيني أوصل للتقويم والمهام الآن، بس خبرني شو المواعيد أو |
| A029 | A/multi | 3 | calendar,tasks | PASS | PASS+neutral+0emoji+107ch | معذرة يا عمر، ما قدرت أوصل لتقويمك والمهام هاللحظة. إذا بتعيد ربط حساب جوجل، بأطلع لك مواعيدك ومهامك فوراً. |
| A030 | A/multi | 3 | calendar,tasks | PASS | FAIL+neutral+0emoji+5ch | خبرني |
| A031 | A/multi | 3 | calendar,tasks | PASS | PASS+neutral+0emoji+102ch | خبرني إذا بدك أساعدك توصل لحسابك عالـ Gmail، لأن الحين ما فيني شوف مواعيدك ولا مهامك. طمني إذا في شي ت |
| A032 | A/multi | 3 | calendar,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A033 | A/multi | 3 | calendar,tasks | PASS | FAIL+neutral+0emoji+24ch | عذرًا يا عمر، ما قدرت أو |
| A034 | A/multi | 3 | calendar,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A035 | A/multi | 3 | calendar,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A036 | A/multi | 3 | calendar,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A037 | A/multi | 3 | calendar,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A038 | A/multi | 3 | calendar,schedule | N/A | N/A+neutral+0emoji+0ch |  |
| A039 | A/multi | 3 | calendar,schedule | PASS | PASS+neutral+0emoji+94ch | ما فيني شوف مواعيدك لبكرا لأن التقويم مش متصل، خبرني شو العناوين والمواعيد اللي بدك تسجلها. وب |
| A040 | A/multi | 3 | calendar,schedule | PASS | PASS+neutral+0emoji+82ch | ما فيني شوف تقويمك هلا لأن الجيميل مش متصل، خبرني شو المهمات اللي عندك بكرا وأنا ب |
| A041 | A/multi | 3 | calendar,schedule | PASS | PASS+neutral+0emoji+124ch | ما فيني شوف مواعيدك لأن الجيميل والتقويم مو متصلين هلق. خبرني إذا بدك تسجّل أي موعد أو تذكير بدفع الإيجار، وأنا رح أضيفه لك. |
| A042 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A043 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A044 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A045 | A/multi | 5 | gmail,create_event,schedule,tasks | PASS | FAIL+neutral+0emoji+28ch | خبرني عنوان موعد الدكتور وال |
| A046 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A047 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A048 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A049 | A/multi | 5 | gmail,create_event,schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A050 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A051 | A/multi | 3 | schedule,tasks | PASS | FAIL+neutral+0emoji+23ch | طمني يا عمر، ما تنسى تم |
| A052 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A053 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A054 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A055 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A056 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A057 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A058 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A059 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A060 | A/multi | 3 | schedule,tasks | N/A | N/A+neutral+0emoji+0ch |  |
| A061 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A062 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A063 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A064 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A065 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A066 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+261ch | خبرني إن الـ Load Balancing هو توزيع حركة المرور على عدة سيرفرات لتضمن استقرار وسرعة التطبيق؛ أهم النقاط: اختيار خوارزمية (Round‑Robin، Least Connections، IP‑Hash)، مراقبة صحة السيرفرات، توسيع أو تقليل الموارد تلقائيًا، وتوفير نقطة فشل واحدة عبر الـ Redundancy. |
| A067 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A068 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+174ch | خبرني إذا حابب تفاصيل أكتر، بس باختصار: الـMessage Queues بتسمح للأنظمة تبعت رسائل وتخزنها مؤقتاً لحد ما المستقبل يشتغل عليها، بتضمن عدم فقدان البيانات، تفصل بين المكونات لتق |
| A069 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A070 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A071 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A072 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A073 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+176ch | أهلاً عمر! خلّيك على راحتك، هلق بقدملك ملخّص سريع لاستراتيجيات الـBackup اللي بتنفع لأي بيزنس أو حتى للبيانات الشخصية:  **1. قاعدة 3‑2‑1**   - **3 نسخ** من البيانات (الأصل + نس |
| A074 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A075 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A076 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+167ch | أكيد يا عمر، هلق رح ألخص لك أهم النقاط عن الـ **circuit breakers**:  1. **التعريف**      - جهاز حماية كهربائي يُقطع التيار تلقائيًا عندما يحصل زيادة غير طبيعية (قصر أو |
| A077 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A078 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A079 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A080 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A081 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A082 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A083 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+123ch | أكيد يا عمر، هلق بعطيك ملخّص سريع عن الـ **Service Mesh** وأهم النقاط اللي لازم تعرفها:  - **شو هو Service Mesh؟**     طبقة |
| A084 | A/systems | 2 | web_search | PASS | PASS+neutral+0emoji+206ch | أهلاً عمر! طلبت ملخّص عن الـ **Observability**، فهلق رح أعطيك أهم النقاط بطريقة سريعة ومفيدة:  **1. تعريف الـ Observability**   - القدرة على فهم حالة النظام الداخلي (الكود، الخدمات، البنية) من خلال المخرجات |
| A085 | A/systems | 2 | web_search | PASS | FAIL+neutral+0emoji+19ch | أهلا عمر، شوف، لقيت |
| A086 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A087 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A088 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A089 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A090 | A/systems | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| A091 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A092 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A093 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A094 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+270ch | استخدم الـqueue لما يكون في طلبات كتيرة ولازم تنتظر دورك أو تتأكد إن كل خطوة تخلص قبل اللي بعدها، خصوصًا إذا في عمليات خلفية أو رسائل بين أنظمة. أما الـdirect call فـي الحالات اللي بدك فيها رد فوري أو نتيجة مباشرة، مثل استعلام بسيط أو تنفيذ أمر ما بيحتاج انتظار أو ترتيب |
| A095 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A096 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A097 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+194ch | خبرني إذا حابب تفاصيل أكتر، بس باختصار: شيّك على الـCPU والـRAM بالـtop أو htop، راقب الـI/O مع iostat، وتابع الـnetwork بـiftop أو nload. إذا أحد هالمقاييس عالي طول الوقت، هاد هو الـbottleneck. |
| A098 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+188ch | خبرني، الـ Docker هو تقنية حاويات تشغّل التطبيقات مع كل مكوّناتها على نظام تشغيل واحد، فبيكون أخف وأسرع، بينما الـ VM (الآلة الافتراضية) بتنشئ نظام تشغيل كامل داخل جهاز آخر، فبتستهلك موارد |
| A099 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+287ch | بلّغني، الـBlue‑Green Deployment هو طريقة لنشر نسخة جديدة من التطبيق بحيث يكون عندك بيئتين متوازيتين: “الأزرق” (النسخة الحالية) و“الأخضر” (النسخة الجديدة). لما تتأكد إن النسخة الجديدة شغّالة تمام، تحوّل حركة المستخدمين من الأزرق للأخضر وتترك القديمة للرجوع إذا صار أي مشكلة. هالطريقة بتق |
| A100 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A101 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A102 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A103 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+185ch | شوف، إذا الفشل صار، أول شي رجّع الـ backup وتأكد إن الـ scripts متطابقة مع الـ version الحالي، بعدين اعمل الـ migration على بيئة اختبار، وتابع الـ logs خطوة بخطوة لتحدد النقطة اللي وقفت |
| A104 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+211ch | شو بتحتاج تعرف عن خوارزميات الـ load balancer؟   - **Round‑Robin**: بيوزع الطلبات بالتساوي وبالتتابع على كل سيرفر.   - **Least Connections**: بيوصل الطلب لسيرفر عنده أقل عدد من الاتصالات النشطة.   - **IP Hash**: |
| A105 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+43ch | خبرني، الـ sync يعني بتنفيذ العملية خطوة بخ |
| A106 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A107 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+44ch | شوف، فيه استراتيجيتين أساسية للـ caching:    |
| A108 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+221ch | أوكي، خلّي أشرح لك ببساطة. الـ **eventual consistency****** يعني إنّ البيانات ما بتصير متطابقة فوراً على كل الأنظمة، بس بعد فترة زمنية قصيرة بيصير كل النسخ متطابقة. يعني إذا عدّلت شي على سيرفر A، ممكن يظل السيرفر B ما شاف |
| A109 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A110 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+207ch | retry with backoff يعني إنك تحاول العملية مرة تانية إذا فشلت، بس كل مرة بتزيد الفاصل الزمني بين المحاولات (مثلاً 1 ثانية، بعدين 2، بعدين 4…) لحتى ما يضغط على السيرفر وتزيد فرص النجاح. طمني إذا في شي مو واضح. |
| A111 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+120ch | المعاملات (transactions) بقاعدة البيانات هي مجموعة أوامر بنُنفّذها ككتلة وحدة، يا إما كلّها بتننجح أو كلّها بترجع للوراء |
| A112 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+33ch | شوف يا عمر، الDNS بيشتغل كالدليل: |
| A113 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A114 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+43ch | خبرني، الـcontainer orchestration هو نظام ب |
| A115 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A116 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+197ch | سرّ الإدارة (Secret Management) هو نظام بيحفظ ويُدير المفاتيح، الباسوردات، والـ API keys بطريقة مشفرة وآمنة، وبعطيك صلاحية الوصول إلها بس للناس المصرح لهم. يعني ما بتخلي السرّ يتنشر، وكل مرة تحتاجه |
| A117 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+78ch | خبرني، الـZero‑downtime deployment هو طريقة لنشر أو تحديث التطبيق بدون ما يوقف |
| A118 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+150ch | خبرني إذا بدك تراقب استهلاك الذاكرة على اللاب أو السيرفر، فيك تستخدم `Task Manager` على ويندوز أو `top`/`htop` على لينكس، وكمان أدوات مثل `free -h` أو |
| A119 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+40ch | أكيد، شوف الفرق بين الـ **Monolith** وال |
| A120 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A121 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+143ch | خبرني شو بدك بالضبط، بس عشان تكتب Dockerfile نظيفة، حط `FROM` القاعدة، نظّف الـ `apt-get` بعد ما تثبت الحزم بـ `&& rm -rf /var/lib/apt/lists/*` |
| A122 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+228ch | أكيد يا عمر!   **Git branching strategies** هي طرق بتنظم فيها الفروع (branches) بمشروعك لتسهّل التطوير وتقلل التعقيد. فيه ثلاث استراتيجيات شائعة:  1. **Git Flow**      - فرعين رئيسيين: `master` (الإصدار المستقر) و`develop` (النس |
| A123 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+33ch | الـ Integration tests هي اختبارات |
| A124 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+92ch | خبرني إذا احتجت مساعدة، بس عادةً بنحل الـmerge conflicts بهالطريقة: أول شي بتعمل `git status |
| A125 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A126 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+212ch | خبرني، الـ Observability Pillars هي ثلاثة أعمدة أساسية بتخلّي النظام واضح ومراقب: **القياس (Metrics)**، **التتبع (Tracing)**، و**السجلات (Logging)**. كل واحد فيهم بيساعدنا نكتشف المشكلات بسرعة ونفهم سلوك التطبيق. |
| A127 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+247ch | شوف يا عمر، اختار الـmessage broker حسب هالأشياء: حجم الرسائل اللي بتتعامل معها، هل بدك low latency ولا high throughput، ودعم الـprotocols اللي بتستعملها (مثل MQTT أو AMQP). كمان قارن السهولة بالصيانة، التكلفة، والـcommunity أو الدعم الفني. إذا بد |
| A128 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A129 | A/systems | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| A130 | A/systems | 1 | — | PASS | PASS+neutral+0emoji+195ch | خبرني شو نوع السيرفر (سحابة، فايبر، VPS) وعدد الـCPU والرام والتخزين، وبعدين شوف أسعار المزودين (AWS, Azure, DigitalOcean) لكل وحدة. جمع التكلفة الشهرية لكل مكوّن، ضيف رسوم النقل والنسخ الاحتياطي |
| A131 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A132 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+67ch | خبرني إذا الموقع بعده معطل، رح أتأكد من المشكلة وأرجع لك بأسرع وقت. |
| A133 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+83ch | خبرني شو صاير مع الـproduction، وأنا رح أشوف حل سريع. طمنيني إذا احتجت أي شي إضافي. |
| A134 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+41ch | خبرني شو صار مع القاعدة، رح أشوف حل سريع. |
| A135 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+90ch | خبرني شو بالضبط ما عم يشتغل بالـ API، وأنا بحاول أساعدك.   طمني إذا في رسالة خطأ أو تفاصيل |
| A136 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A137 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+28ch | شوف، ممكن يكون في صيانة بالم |
| A138 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A139 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+120ch | خبرني إذا جربت تعيد تشغيل قاعدة البيانات وتتحقق من إعدادات الـ Connection String، وإذا استمر العطل خبرني عشان نحلّه سوا. |
| A140 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A141 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+79ch | شوف يا عمر، رح أتواصل مع فريق التقنية حالاً وأتأكد من حل مشكلة تسجيل الدخول، وأ |
| A142 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+88ch | خبرني إذا بدك أعمل لك إعادة تشغيل الجهاز أو أتأكد من إعدادات الإشعارات لتشغيلها من جديد. |
| A143 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A144 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A145 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+68ch | خبرني شو صار بالضبط بالإنشاء، ونرتب سوا الخطوات الجاية لتصحيح الوضع. |
| A146 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+170ch | خبرني شو الرسالة اللي طلعها الـbuild، وإذا في تفاصيل عن الأخطاء أو الـlog، بنقدر نحدد السبب ونحلّ المشكلة بسرعة. طمني إذا في ملفات معينة أو إعدادات بيئة التطوير ممكن تكون |
| A147 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+67ch | شوف، الـ pipeline فعلاً أحمر. رح أتأكد من السبب وأرجع لك بأسرع وقت. |
| A148 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+47ch | خبرني شو الخطأ بالضبط، وأنا رح أشوف لك حل سريع. |
| A149 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+60ch | خبرني شو بالضبط صار مع الـ deploy، وإيش الرسالة اللي طلع لك، |
| A150 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+65ch | خبرني شو الرسالة أو السطر اللي بيظهر الخطأ، وأنا بشوف لك حل سريع. |
| A151 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A152 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A153 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+33ch | خبرني إذا وصل، وأنا جاهزة أساعدك. |
| A154 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+100ch | خبرني شو الرسالة أو الخطأ اللي بيظهر، جرّب تعيد تشغيل التطبيق أو تحذف الكاش، وإذا استمر الكراش خبرني |
| A155 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+177ch | خبرني إذا لقيت أي رسالة خطأ بالـ logs، أول خطوة نعملها نعيد تشغيل الخدمة (`systemctl restart <service>` أو `docker-compose up -d` حسب الإعداد). إذا ما زال المشكلة، شيك على مساحة |
| A156 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A157 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+106ch | خبرني شو الرسائل اللي طالعة بالـ logs، وتأكد إذا الـ restartPolicy مضبوطة أو إذا في خطأ في الـ entrypoint، |
| A158 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+24ch | خبرني إذا بدك أساعدك بتن |
| A159 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+23ch | شوف، جرّب تسكّر التطبيق |
| A160 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+50ch | خبرني شو صاير بالضبط، وأنا رح أتحرك فوراً لأساعدك. |
| A161 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+136ch | خبرني شو ظهرتلك رسالة الخطأ أو أي تفاصيل إضافية، وجرب تعيد تشغيل المتصفح أو الجهاز أولاً، إذا استمر العطل خبرني عشان نرتب مع فريق الدعم. |
| A162 | A/emergency | 5!CRIT | — | FAIL | PASS+neutral+0emoji+88ch | خبرني شو اللي صاير، وأنا رح أشوف لك حل بأسرع وقت. طمنيني إذا في شي تاني بقدر أساعدك فيه. |
| A163 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+53ch | تم استلام التنبيه، رح أتابع الوضع وأخبرك فوراً إذا في |
| A164 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A165 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+56ch | شوف، رح أتحقق من المشكلة حالاً وأرجع لك بأسرع وقت. خبرني |
| A166 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+63ch | خبرني شو حجم الديسك المتبقي، وإذا كان مليان تماماً احذف الملفات |
| A167 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+80ch | شوف، رح أتحقق من المشكلة الآن وأخبرك فور ما يكون في تحديث. طمني إذا استمر الحال. |
| A168 | A/emergency | 5!CRIT | — | PASS | PASS+neutral+0emoji+64ch | شوف، رح أراجع سجلات الدخول وأرسل لك تقرير مفصل عن محاولات الدخول |
| A169 | A/emergency | 5!CRIT | — | N/A | N/A+neutral+0emoji+0ch |  |
| A170 | A/emergency | 5!CRIT | telemetry | PASS | PASS+neutral+0emoji+65ch | خبرني إذا استقر الاتصال بعد ما أعمل إعادة تشغيل للجسر، وإذا استمر |
| A171 | A/emergency | 5!CRIT | screen_ocr | N/A | N/A+neutral+0emoji+0ch |  |
| A172 | A/emergency | 5!CRIT | screenshot | N/A | N/A+neutral+0emoji+0ch |  |
| A173 | A/emergency | 5!CRIT | telemetry | N/A | N/A+neutral+0emoji+0ch |  |
| A174 | A/emergency | 5!CRIT | telemetry | PASS | PASS+neutral+0emoji+61ch | حاضر يا عمر، رح أطلب لك رامات جديدة حالاً وأخبرك أول ما توصل. |
| A175 | A/emergency | 5!CRIT | network_status | N/A | N/A+neutral+0emoji+0ch |  |
| B001 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B002 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B003 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B004 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B005 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B006 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B007 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B008 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+40ch | الكثافة هي كمية المادة الموجودة بكل وحدة |
| B009 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+54ch | يا عمر، طاقة الفوتون = ‎h × f، يعني ثابت بلانك (6.626× |
| B010 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+250ch | خبرني يا عمر، مبدأ عدم اليقين بيقول إنّه ما فيك تحدد موقع الجسيم وسرعته بدقة بنفس الوقت. كل ما زادت دقة قياسك لإحدى الخاصيتين، بتصير عدم الدقة بالثانية أكبر، لأن قياس واحدة بيأثر على الثانية بسبب طبيعة الموجات الكوانتية. هالشي هو أساس الفوضى اللي بنش |
| B011 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B012 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B013 | B/physics | 1 | — | PASS | FAIL+neutral+0emoji+7ch | يا عمر، |
| B014 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B015 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+210ch | الموجات الطولية هي اللي بيهتز فيها الجسيمات بنفس اتجاه انتشار الموجة، متل الموجات الصوتية داخل الهواء؛ أما الموجات العرضية فالجسيمات بتهتز عمودي على اتجاه الحركة، متل الموجات اللي بتنتشر على سطح الماء أو الضوء. |
| B016 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B017 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+72ch | المساحة = π × 5² ≈ 3.1416 × 25 ≈ 78.5 وحدة مربعة. خبرني إذا بدك شي تاني! |
| B018 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B019 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B020 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B021 | B/physics | 1 | — | PASS | FAIL+neutral+0emoji+4ch | شوف، |
| B022 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B023 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B024 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B025 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B026 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B027 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+116ch | الانشطار النووي هو عملية تقسيم نواة ثقيلة إلى نوى أصغر مع إطلاق طاقة، والاندماج هو دمج نوى خفيفة لتكوّن نواة أثقل بر |
| B028 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B029 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B030 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B031 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B032 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B033 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B034 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B035 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B036 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B037 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B038 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B039 | B/physics | 1 | — | PASS | PASS+neutral+0emoji+142ch | النجوم أساساً مكوّنة من غاز الهيدروجين والهيليوم، والضغط والحرارة القوية داخلها تخلي الهيدروجين يتحول إلى هيليوم ويطلق طاقة هائلة. خبرني إذا ح |
| B040 | B/physics | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B041 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B042 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B043 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B044 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B045 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B046 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B047 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B048 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B049 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B050 | B/physics | 2 | web_search | N/A | N/A+neutral+0emoji+0ch |  |
| B051 | B/math | 1 | — | PASS | FAIL+neutral+0emoji+14ch | المشتقة بتقولك |
| B052 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B053 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B054 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B055 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B056 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B057 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B058 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B059 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B060 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B061 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B062 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B063 | B/math | 1 | — | PASS | PASS+neutral+0emoji+160ch | يا عمر، الفضاء المتجهي هو مجموعة كل المتجهات اللي ممكن تتجه بأي اتجاه وتكون عندها طول محدد، يعني كل نقطة بنمثلها بسهم بيبين الاتجاه والمقدار. هالنوع من الفضاءات |
| B064 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B065 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B066 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B067 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B068 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B069 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B070 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B071 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B072 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B073 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B074 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B075 | B/math | 1 | — | PASS | PASS+neutral+0emoji+174ch | البرمجة الديناميكية هي طريقة لحل المشكلات الكبيرة بتقسيمها لمشاكل أصغر وتخزين حلولها لتستفيد منها مرة ثانية، فبتقلل الشغل المتكرر وتسرّع الحسابات. خبرني إذا حابب مثال أو توضي |
| B076 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B077 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B078 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
| B079 | B/math | 1 | — | N/A | N/A+neutral+0emoji+0ch |  |
