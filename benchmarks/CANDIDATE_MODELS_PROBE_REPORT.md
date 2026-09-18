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

