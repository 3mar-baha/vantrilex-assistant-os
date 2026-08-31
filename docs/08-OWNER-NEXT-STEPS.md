# 08 — خطوات المالك التالية (Owner Next Steps)

> آخر تحديث: 2026-08-31 — بعد إطلاق v1.0.1 واعتماد **Oracle Cloud Always Free** كمسكن
> إنتاجي (تعديل ADR-15). **الدليل التفصيلي خطوة-بخطوة (يدك اليد): `docs/09-ORACLE-DEPLOY.md`** —
> هذا الملف يحمل المرجع المختصر: قرارات ما بعد الإطلاق، قالب المتغيرات الكامل للخادم،
> وعقبات Google وتدوير المفاتيح. لن تجد أي قيمة سرية في ملف موثّق، بالتصميم — القيم
> كلها في `.env` المحلي (خارج Git).

---

## القرار: أين تعيش سارة؟ — محسوم ✅

| الخيار | النتيجة |
|---|---|
| **Oracle Cloud Always Free** (قرارك 2026-08-31) | ✅ **المعتمد** — VM حقيقية لا تنم أبداً، Ampere A1 حتى 4 OCPU/24GB، $0.00 دائماً |
| HF Space | ✗ Docker/Gradio أصبح مدفوعاً PRO ($9/شهر) — يكسر قاعدة $0.00 |
| Render / Koyeb مجاني | ✗ 512MB/0.1vCPU + سبات — لا يحمل whisper + البصمة + البوابة + النواة |
| Cloud Run مجاني | ✗ نفس سقف 512MB للخدمة الدائمة |

---

## المرحلة A — رقعة v1.0.1: **منجزة** ✅

اكتشفنا أن OmniRoute تطبيق Node/npm (engines: node >=22.22) بينما الصورة `python:3.12-slim`
بدون Node — البوابة لم تكن ستقلع أبداً. **v1.0.1 حلّها**: طبقة Node 24 (NodeSource) +
تثبيت البوابة عالمياً من الاستنساخ المورَّد + `ENV OMNIROUTE_CMD="omniroute run"`
(صفر إعدادات). موثقة باختبار أحمر→أخضر في `tests/test_packaging.py::test_dockerfile_contract`.

**دورك الآن: المرحلة B فقط.**

---

## المرحلة B — النشر على Oracle (يدوي أنت) 🚀

اتبع `docs/09-ORACLE-DEPLOY.md` من أوله لآخره (حساب → VM → DuckDNS → Docker → بناء →
تشغيل → تحقق → ربط جهازك). الوحيد الذي تحتاج إعداده بعناية هو ملف البيئة على الخادم:

### قالب `~/sara-secrets/sara.env` — الـ 21 متغيراً (انسخ القيم من `.env` المحلي)

```env
TELEGRAM_BOT_TOKEN=<من .env>
AUTHORIZED_USER_ID=<من .env>
TELEGRAM_API_ID=<من .env>
TELEGRAM_API_HASH=<من .env>
OMNIROUTE_BASE_URL=http://localhost:20128/v1
OMNIROUTE_API_KEY=<من .env>
GROQ_API_KEY=<من .env>
OPENROUTER_API_KEY=<من .env>
FAST_MODEL=groq/openai/gpt-oss-20b
FAST_MODEL_FALLBACKS=openrouter/minimax/minimax-m2.7:free
MEDIUM_MODEL=groq/openai/gpt-oss-20b
MEDIUM_MODEL_FALLBACKS=openrouter/minimax/minimax-m2.7:free,groq/openai/gpt-oss-120b
HEAVY_MODEL=openrouter/nvidia/nemotron-3-ultra-550b-a55b:free
HEAVY_MODEL_FALLBACKS=groq/openai/gpt-oss-120b
VAULT_ENC_KEY=<من .env>
VAULT_GITHUB_REPO=<من .env>
VAULT_GITHUB_TOKEN=<من .env>
VAULT_BRANCH=main
BRIDGE_TOKEN=<من .env>
TZ=Asia/Amman
PORT=8080
```

> لا تضع `BRIDGE_SERVER_URL` على الخادم — هي متغير جهازك أنت (الجسر يتصل بواتسابق
> للخادم، والعكس غير مطلوب). ميزة الـ VM: انسخ `config/google_oauth_client.json`
> إلى `~/sara/config/` (scp) — ميزات Google تعمل كاملة على الخادم.

---

## المرحلة C — أول تشغيل (من تلغراف، مرة واحدة) 🎙️

1. `/start` — تحية سارة الأردنية
2. `/enroll-voice` + ملاحظة صوتية — تسجيل بصمتك (مشفر في الـ vault)
3. موافقة Google OAuth — **تعمل الآن على الـ VM** (كانت مستحيلة داخل حاوية HF)
4. «شو وضع الجهاز؟» بعد تشغيل الجسر على جهازك — إجابة تelemترية حية

---

## عقبة Google 403 (من سبرنت 1) ⚠️

المشروع `vantrilex-assistant-2008` على Google Cloud كان محجوباً من جوجل
("project denied access"). جيميناي تقاعدت من الدماغ، لكن نفس المشروع يستضيف عميل
OAuth لبريدك وتقويمك — إذا واجهت 403 عند الموافقة: console.cloud.google.com →
فعّل Generative Language API وتأكد من حالة المشروع.

---

## تدوير المفاتيح (مُوصى به، اختياري) 🔄

المفاتيح الحقيقية عُلقت في محادثتين على الأقل (هذه + مساعد آخر أنتج جدول Render):
- GitHub PAT: أنشئ جديداً fine-grained وحدّث `.env` + `sara.env`
- Telegram API_HASH: من my.telegram.org
- Groq/OpenRouter: من لوحاتهما
بعدها حدّث `.env` محلياً + `sara.env` على الخادم (أخبرني وأنا أدير التحديث محلياً).

---

## ملخص الترتيب

**B (Oracle — docs/09) → C (أول تشغيل)** ثم عقبة Google/تدوير المفاتيح بالتوازي متى شئت.
السياق الكامل: `docs/07-HANDOFF.md` · التفاصيل التشغيلية: `docs/04-RUNBOOK.md` §4.
