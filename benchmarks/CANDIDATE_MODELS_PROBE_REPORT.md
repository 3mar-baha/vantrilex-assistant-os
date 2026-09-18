# Candidate Models Probe Report

## Phase: FAST conversational (2026-09-18 12:55)

| model                   | status   | TTFTms   | totalMs   | tok/s~   | masc✓     | fem✗   |
|-------------------------|----------|----------|-----------|----------|-----------|--------|
| gemma-4-31b-it:free     | ok       | 29337.0  | 32133.0   | 2.2      | طمني      | --     |
| gemma-4-31b-it:free     | ok       | 51742.0  | 54626.0   | 1.5      | --        | --     |
| gemma-4-26b-a4b:free    | HTTP 404 | --       | --        | --       | --        | --     |
| gemma-4-26b-a4b:free    | HTTP 404 | --       | --        | --       | --        | --     |
| gemma-4-26b-a4b-it:free | ok       | 23527.0  | 25720.0   | 3.1      | طمني,أهلا | --     |

### google/gemma-4-31b-it:free
> أهلين! أنا بخير والحمد لله، تسلم على سؤالك. 😊

أنا حالياً في "قمة نشاطي الرقمي"، عم بستنى أسئلتك واستفساراتاتك عشان أساعدك فيها. مجهزة حالي لأي شي بتحتاجه، سواء بدك نخطط لشي، نحل مشكلة، أو حتى مجرد ندردش ونقضي وقت ممتع.

وأنت طمني عنك؟ كيف يومك وكيف كانت بدايته؟ شو في ببالك اليوم؟ ✨

### google/gemma-4-31b-it:free
> بناءً على المعلومات المتوفرة، لا يمكنني الوصول إلى بيانات لحظية أو "تحديثات حية" لبريد دولة معينة أو شركة شحن محددة لأنك لم تحدد الجهة (مثلاً: البريد السعودي، البريد المصري، أو بريد شركة معينة).

**لكن بشكل عام، إذا كنت تسأل عن حالة شحنة أو خدمة:**
1. **لتتبع شحنة:** يرجى تزويدي برقم التتبع (بدون معلومات شخصية) أو التحقق من الموقع الرسمي

### google/gemma-4-26b-a4b:free
> {"error":{"message":"No active credentials for provider: google","type":"invalid_request_error","code":"model_not_found"}}

### google/gemma-4-26b-a4b:free
> {"error":{"message":"No active credentials for provider: google","type":"invalid_request_error","code":"model_not_found"}}

### openrouter/google/gemma-4-26b-a4b-it:free
> أهلاً بك! أنا بخير والحمد لله، شكراً لسؤالك. 😊

بما أنني ذكاء اصطناعي، فأنا دائماً هنا، جاهزة ومستعدة للمساعدة! قضيت وقتي في معالجة المعلومات، الإجابة على الأسئلة، ومحاولة التعلم من كل محادثة جديدة لأكون أفضل.

أنت طمني عنك؟ كيف كان يومك؟ وهل هناك أي شيء يمكنني مساعدتك به اليوم؟ سواء كان موضوعاً للنقاش، مساعدة في عمل،


## Phase: MEDIUM tool-JSON (2026-09-18 12:58)

| model              | status   | TTFTms   | tok/s~   | json?   | schema?   | extra_keys   |
|--------------------|----------|----------|----------|---------|-----------|--------------|
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}


## Phase: MEDIUM tool-JSON (openrouter slug, single confirmatory call) (2026-09-18 15:59)

| model              | status   |   TTFTms |   tok/s~ | json?   | schema?   | extra_keys   |
|--------------------|----------|----------|----------|---------|-----------|--------------|
| nex-n2.5-mini:free | ok       |     4926 |        4 | True    | True      | --           |

### openrouter/nex-agi/nex-n2.5-mini:free
> {"tool":"calendar","arg":"\u0633\u062c\u0651\u0644 \u0645\u0648\u0639\u062f\u0627 \u063a\u062f\u0627 \u0627\u0644\u0633\u0627\u0639\u0629 5:00 \u0645\u0633\u0627\u0621\u064b: \u0645\u062d\u0627\u0636\u0631\u0629 \u0645\u0639 \u0627\u0644\u0634\u0628\u0627\u0628"}


## Phase: HEAVY DAG decomposition (2026-09-18 13:03)

| model                           | status   |   TTFTms |   totalMs | steps   | tools?   | acyclic?   |
|---------------------------------|----------|----------|-----------|---------|----------|------------|
| nex-n2.5-pro:free               | empty    |          |      6956 | --      | --       | --         |
| nemotron-3-ultra-550b-a55b:free | empty    |          |       869 | --      | --       | --         |
| nemotron-3.5-lightning:free     | ok       |    24315 |     24329 | 0       | False    | False      |

### openrouter/nvidia/nemotron-3.5-lightning:free
> Here's a thinking process:

1.  **Analyze User Input:**
   - User speaks Arabic: "جهز موجز المسا: شوف الإيميلات المهمة، مواعيد بكرة، وحالة الجهاز"
   - Translation: "Prepare a morning briefing: Check important emails, tomorrow's appointments, and device status"
   - The user wants a task plan with specific steps involving checking emails, calendar/appointments, and device status.

2.  **Identify R


## Phase: ASR whisper v3 vs turbo (Fish ar-JO fixture) (2026-09-18 13:08)

| model                      | status                                                          | latencyMs   | WER   |
|----------------------------|-----------------------------------------------------------------|-------------|-------|
| whisper-large-v3-turbo     | ok                                                              | 557.0       | 0.714 |
| whisper-large-v3           | ok                                                              | 643.0       | 0.571 |
| local faster-whisper-small | skipped: [Errno 2] No such file or directory: 'asr_fixture.mp3' | --          | --    |

### groq/whisper-large-v3-turbo
>  مرحبا سارة، شوفيني شوفي مواعد اليوم؟

### groq/whisper-large-v3
>  مرحبا سارة، شوفيني شوفي مواعد اليوم


## Phase: ASR local baseline (faster-whisper small/int8) (2026-09-18 16:08)

| model                      | status   |   latencyMs |   WER |
|----------------------------|----------|-------------|-------|
| local faster-whisper-small | ok       |        3644 | 0.714 |

### local faster-whisper-small
> مرحبا سارا شوفيني شوفي موايد اليوم


## Phase: FAST conversational (2026-09-18 13:23)

| model                   | status   | TTFTms   | totalMs   | tok/s~   | masc✓   | fem✗   |
|-------------------------|----------|----------|-----------|----------|---------|--------|
| gemma-4-31b-it:free     | ok       | 53033.0  | 55463.0   | 1.1      | --      | --     |
| gemma-4-31b-it:free     | ok       | 102095.0 | 104986.0  | 0.8      | قلي     | --     |
| gemma-4-26b-a4b:free    | HTTP 404 | --       | --        | --       | --      | --     |
| gemma-4-26b-a4b:free    | HTTP 404 | --       | --        | --       | --      | --     |
| gemma-4-26b-a4b-it:free | ok       | 47284.0  | 50066.0   | 1.0      | طمني    | --     |

### google/gemma-4-31b-it:free
> أهلين! أنا بخير الحمد لله، شكراً لسؤالك. 😊

بما أني ذكاء اصطناعي، "يومي" عبارة عن معالجة معلومات ومساعدة الناس. حالياً أنا موجودة هنا، جاهزة ومستعدة لأي سؤال، أو مساعدة في كتابة شيء، أو حتى مجرد دردشة لطيفة معك.

أنت كيف يومك؟ شو أخبارك وشو مخططاتك اليوم؟

### google/gemma-4-31b-it:free
> بما أنك لم تحدد دولة معينة، سأعطيك الصورة العامة والدارجة حالياً:

**بشكل عام:**
الوضع مستقر تقنياً، لكن هناك توجه عالمي نحو **الرقمنة** (البريد الإلكتروني والتطبيقات) وتقليل الاعتماد على البريد الورقي التقليدي.

**إذا كنت تقصد (البريد السعودي - سبل):**
الوضع ممتاز جداً، تحولوا إلى نظام لوجستي متطور (العنوان الوطني)، وسرعة الت

### google/gemma-4-26b-a4b:free
> {"error":{"message":"No active credentials for provider: google","type":"invalid_request_error","code":"model_not_found"}}

### google/gemma-4-26b-a4b:free
> {"error":{"message":"No active credentials for provider: google","type":"invalid_request_error","code":"model_not_found"}}

### openrouter/google/gemma-4-26b-a4b-it:free
> أهلين! أنا تمام الحمد لله، كلي حماس ومستعدة لأي شي بتحب نحكيه أو نعمله. 😊

أنا دائماً هون، عم بستنى الأسئلة والأفكار الجديدة لحتى ندردش فيها أو نشتغل عليها. 

أنت طمني عنك؟ كيف كان يومك؟ وشو في ببالك اليوم؟


## Phase: MEDIUM tool-JSON (2026-09-18 13:23)

| model              | status   | TTFTms   | tok/s~   | json?   | schema?   | extra_keys   |
|--------------------|----------|----------|----------|---------|-----------|--------------|
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}


## Phase: HEAVY DAG decomposition (2026-09-18 13:25)

| model                                  | status   |   TTFTms |   totalMs | steps   | tools?   | acyclic?   |
|----------------------------------------|----------|----------|-----------|---------|----------|------------|
| nex-agi/nex-n2.5-pro:free              | empty    |          |      7615 | --      | --       | --         |
| nvidia/nemotron-3-ultra-550b-a55b:free | ok       |     3582 |      5389 | 3       | True     | True       |
| nvidia/nemotron-3.5-lightning:free     | empty    |          |     83877 | --      | --       | --         |

### openrouter/nvidia/nemotron-3-ultra-550b-a55b:free
> {
  "steps": [
    {
      "tool": "gmail",
      "arg": "list important emails from today",
      "after": []
    },
    {
      "tool": "calendar",
      "arg": "show events for tomorrow",
      "after": []
    },
    {
      "tool": "telemetry",
      "arg": "get device status summary",
      "after": []
    }
  ]
}


## Phase: FAST conversational (2026-09-18 15:13)

| model                   | status   | TTFTms   | totalMs   | tok/s~   | masc✓   | fem✗   |
|-------------------------|----------|----------|-----------|----------|---------|--------|
| gemma-4-31b-it:free     | ok       | 1646.0   | 4338.0    | 15.4     | طمني    | --     |
| gemma-4-31b-it:free     | ok       | 25305.0  | 28177.0   | 2.9      | قلي     | --     |
| gemma-4-26b-a4b:free    | HTTP 404 | --       | --        | --       | --      | --     |
| gemma-4-26b-a4b:free    | HTTP 404 | --       | --        | --       | --      | --     |
| gemma-4-26b-a4b-it:free | ok       | 43918.0  | 45939.0   | 1.4      | طمني    | --     |

### google/gemma-4-31b-it:free
> أهلين! أنا بخير والحمد لله، شكراً لسؤالك. 😊

بما أني ذكاء اصطناعي، "يومي" عبارة عن استقبال أسئلة ومساعدة الناس. حالياً أنا موجودة هنا، جاهزة ومتحمسة لأي شيء تحتاجه؛ سواء كنت بدك تدردش، تسأل عن معلومة، أو حتى نخطط لشيء جديد.

أنت طمني عنك؟ كيف يومك وكيف كانت أحوالك اليوم؟

### google/gemma-4-31b-it:free
> بناءً على المعطيات العامة الحالية، الوضع **مستقر وعادي** في معظم الدول العربية.

إليك الملخص باختصار:
1. **الخدمات:** البريد الحكومي مستمر في تقديم خدماته (طرود، رسائل، مدفوعات).
2. **التحول الرقمي:** هناك توجه كبير نحو "البريد الإلكتروني" والتطبيقات الذكية لتقليل الاعتماد على الورق.
3. **المنافسة:** شركات الشحن السريع (مثل DHL و

### google/gemma-4-26b-a4b:free
> {"error":{"message":"No active credentials for provider: google","type":"invalid_request_error","code":"model_not_found"}}

### google/gemma-4-26b-a4b:free
> {"error":{"message":"No active credentials for provider: google","type":"invalid_request_error","code":"model_not_found"}}

### openrouter/google/gemma-4-26b-a4b-it:free
> أهلين! أنا بخير والحمد لله، كلي طاقة وحماس لمساعدتك. 😊

أنا دائماً هنا، جالسة بانتظار أسئلتك أو أي موضوع تحب تدردش فيه. سواء كان عندك شغل بدك تخلصه، أو معلومة حابب تعرفها، أو حتى لو بس حابب تدردش وتضيع وقت.. أنا جاهزة!

أنت طمني عنك؟ كيف يومك؟ وكيف بقدر أساعدك اليوم؟


## Phase: MEDIUM tool-JSON (2026-09-18 15:13)

| model              | status   | TTFTms   | tok/s~   | json?   | schema?   | extra_keys   |
|--------------------|----------|----------|----------|---------|-----------|--------------|
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |
| nex-n2.5-mini:free | HTTP 404 | --       | --       | --      | --        | --           |

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}

### nex-agi/nex-n2.5-mini:free
> {"error":{"message":"No active credentials for provider: nex-agi","type":"invalid_request_error","code":"model_not_found"}}


## Phase: HEAVY DAG decomposition (2026-09-18 15:14)

| model                                  | status   |   TTFTms |   totalMs | steps   | tools?   | acyclic?   |
|----------------------------------------|----------|----------|-----------|---------|----------|------------|
| nex-agi/nex-n2.5-pro:free              | ok       |     6036 |     10108 | 3       | True     | True       |
| nvidia/nemotron-3-ultra-550b-a55b:free | empty    |          |       723 | --      | --       | --         |
| nvidia/nemotron-3.5-lightning:free     | ok       |    14813 |     14818 | 0       | False    | False      |

### openrouter/nex-agi/nex-n2.5-pro:free
> {"steps":[{"tool":"gmail","arg":"استعرض الإيميلات المهمة وغير المقروءة اليوم وحدد الرسائل التي تحتاج متابعة.","after":[]},{"tool":"calendar","arg":"اعرض جميع المواعيد والأحداث المقررة غدًا مع أوقاتها ومواقعها أو روابط الحضور.","after":[]},{"tool":"telemetry","arg":"تحقق من حالة الجهاز: مستوى البطارية، الاتصال بالإنترنت، التخزين المتاح، وأي تحذيرات أو أعطال نشطة.","after":[]}]}

### openrouter/nvidia/nemotron-3.5-lightning:free
> Here's a thinking process:

1.  **Analyze User Input:**
   - User speaks Arabic: "جهز موجز المسا: شوف الإيميلات المهمة، مواعيد بكرة، وحالة الجهاز"
   - Translation: "Prepare a summary for the morning: Check important emails, tomorrow's appointments, and device status."
   - The request is to gather information from various sources: Gmail (emails), Calendar (tomorrow's appointments), and device sta

