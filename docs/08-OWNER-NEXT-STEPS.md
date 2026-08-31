# 08 — خطوات المالك التالية (Owner Next Steps)

> آخر تحديث: 2026-08-31 — بعد إطلاق v1.0.0. هذا الملف يخبرك بالضبط: **ماذا أريد منك**،
> بالترتيب، وبأوامر جاهزة للنسخ. القيم السرية كلها في `.env` المحلي (خارج Git) —
> لن تجد أي قيمة سرية في ملف موثّق، بالتصميم.

---

## قرار سريع تحتاج حسمه أولاً ⚠️

| الخيار | التوصية |
|---|---|
| **HF Space** (المعمارية الملزمة ADR-15 — موثّقة، مختبرة، keep-alive جاهز) | ✅ **الموصى به** |
| Render.com (اقتراح خارجي وصلني من مساعد آخر) | الحاوية محايدة المضيف وتعمل نظرياً، لكن كل التوثيق والاختبارات والـ keep-alive مستهدفة لـ HF — سيتطلب تحويل الأهداف رسمياً |

كل الخطوات أدناه مكتوبة على أساس **HF Space**.

---

## المرحلة A — رقعة v1.0.1 (شغلي أنا، تحتاج موافقتك فقط) 🔧

اكتشفت أثناء التحقق النشرية فجوة واحدة في v1.0.0: **OmniRoute تطبيق Node/npm**
(`npm install -g omniroute` ثم `omniroute run` على المنفذ 20128) بينما صورة الحاوية
`python:3.12-slim` **بدون Node** — أي أن المشرف لن يستطيع تشغيل بوابة الدماغ داخل الـ Space.

**الحل** (سأنفذه كـ v1.0.1 عندما تقول «التالي»):
1. إضافة `nodejs npm` إلى طبقة apt في الـ Dockerfile + تثبيت omniroute عند البناء
2. تثبيت `OMNIROUTE_CMD=omniroute run` في خطوات النشر
3. رفع نسخة الاختبار العقدي للـ Dockerfile (اختبار أحمر أولاً) + تحديث RUNBOOK
4. bump إلى `1.0.1` + CHANGELOG + وسم جديد (سياسة الإصدار: وسم موجود = bump patch، لا force)

⏱️ نصف ساعة عمل. **بدون هذه الرقعة، الـ Space سيقلع ويفشل فحص gateway في deploy_smoke.**

---

## المرحلة B — إنشاء الـ Space ونشر v1.0.1 (يدوي أنت، ~20 دقيقة) 🚀

نفّذ بالترتيب في Git Bash (أو أخبرني وأنفذها لواجهة HF عبر المتصفح):

### B1. أنشئ Space خاصاً
1. افتح https://huggingface.co/new-space
2. Space name: `sara-os` · License: MIT · **Select the Space SDK: Docker** → Blank
   · Visibility: **Private** (إلزامي — هذا بوتك الشخصي)
3. أنشئ Access Token بصلاحية **write** إن لم يكن لديك: https://huggingface.co/settings/tokens

### B2. جهّز مجلد النشر من الوسم
```bash
# نسخة نظيفة من شجرة الوسم (تستثني .env و.git تلقائياً لأنها untracked)
git clone --depth 1 --branch v1.0.1 https://github.com/3mar-baha/vantrilex-assistant-os.git /tmp/vos-tag

# استنسخ OmniRoute بجانب المشرف (قبل البناء — RUNBOOK §4 خطوة 2)
git clone --depth 1 https://github.com/diegosouzapw/OmniRoute.git /tmp/vos-tag/scripts/omniroute

# استنسخ مستودع الـ Space وانسخ الشجرة إليه
git clone https://<HF_USER>:<HF_WRITE_TOKEN>@huggingface.co/spaces/<HF_USER>/sara-os /tmp/sara-space
cp -r /tmp/vos-tag/* /tmp/vos-tag/.dockerignore /tmp/sara-space/
rm -f /tmp/sara-space/.env   # تأكيد مضاعف: لا ملف بيئة في مستودع الـ Space
```

### B3. ارفع
```bash
cd /tmp/sara-space
git add -A && git commit -m "Vantrilex Assistant OS v1.0.1 — Sara" && git push
```
البناء سيبدأ تلقائياً ويعرض سجلاته في تبويب **Logs** بالـ Space.

---

## المرحلة C — المتغيرات والأسرار في الـ Space (بعد أول push) 🔐

من صفحة الـ Space → **Settings** → **Variables and secrets** → New:

### Variables (غير سرية)
| الاسم | القيمة | ملاحظة |
|---|---|---|
| `OMNIROUTE_CMD` | `omniroute run` | بعد رقعة v1.0.1 — يحدد أمر إقلاع البوابة |
| `VAULT_GITHUB_REPO` | قيمة `VAULT_GITHUB_REPO` من `.env` | |
| `CORE_CMD` | (اتركه فارغاً) | الافتراضي `python -m src.main` صحيح |

### Secrets (سرية — انسخ القيم من ملف `.env` المحلي، سطراً بسطر)
| الاسم (Secret) | من أين تأخذ القيمة |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `.env` → `TELEGRAM_BOT_TOKEN` |
| `AUTHORIZED_USER_ID` | `.env` → `AUTHORIZED_USER_ID` |
| `OMNIROUTE_API_KEY` | `.env` → `OMNIROUTE_API_KEY` |
| `GROQ_API_KEY` | `.env` → `GROQ_API_KEY` (تصل بوابة OmniRoute عبر توريث بيئة الحاوية) |
| `OPENROUTER_API_KEY` | `.env` → `OPENROUTER_API_KEY` (نفس المبدأ) |
| `VAULT_ENC_KEY` | `.env` → `VAULT_ENC_KEY` |
| `VAULT_GITHUB_TOKEN` | `.env` → `VAULT_GITHUB_TOKEN` |
| `BRIDGE_TOKEN` | `.env` → `BRIDGE_TOKEN` |
| `FAST_MODEL` / `MEDIUM_MODEL` / `HEAVY_MODEL` + `_FALLBACKS` | من `.env` (أو تُترك — الحاوية لا تقرأ `.env`؛ بدائل: bake في README أو secrets) |

> ⚠️ انتبه: الحاوية على HF لا تملك ملف `.env` — كل قيمة يحتاجها النواة يجب أن تدخل
> كـ Variable أو Secret أعلاه. القائمة الكاملة للأسماء في `.env.example`.

### Secret في مستودع المشروع (للـ keep-alive)
```bash
gh secret set SPACE_URL --body "https://<HF_USER>-sara-os.hf.space"
```
هذا يشغّل `.github/workflows/keepalive.yml` (نبضة كل 10 دقائق على `/health`).

---

## المرحلة D — تفعيل pools الدماغ 🧠

1. بعد إقلاع الـ Space، افتح لوحة OmniRoute عبر سجلات الـ Space (أو الأداة الخاصة بها)
2. تأكد أن pools المزودين (Groq + OpenRouter بالمفاتيح أعلاه) مفعّلة والنماذج
   المثبّتة ظاهرة: `gpt-oss-20b` · `minimax-m2.7:free` · `gpt-oss-120b` ·
   `nemotron-3-ultra-550b-a55b:free` (كلها تحققت محلياً ✓ — انظر HANDOFF §3)

---

## المرحلة E — جهازك (جسر PC) 💻

1. حدّث `BRIDGE_SERVER_URL` في `.env` المحلي إلى: `wss://<HF_USER>-sara-os.hf.space/bridge`
2. شغّل الدايمن: `make run-bridge` (وأضفه مهمة auto-start لاحقاً)
3. فحص WoL الواقعي من الشبكة (RUNBOOK §5 reality check)

---

## المرحلة F — أول تشغيل (من تلغراف، مرة واحدة) 🎙️

1. أرسل `/start` — يجب أن يرد تحية سارة بصوت عماني
2. `/enroll-voice` + أرسل ملاحظة صوتية — تسجيل بصمتك (تتخزن مشفّرة في الـ vault)
3. موافقة Google OAuth — **تنبيه صادق**: هذه تحتاج ملف OAuth client JSON الذي
   لا يدخل صورة الـ Space عمداً (قاعدة أمنية). **ميزات Google تعمل محلياً الآن**،
   وعلى الـ Space هي فجوة موثقة (HANDOFF §9.4) — قرار v1.1: آلية B64 secret أو إبقاء
   Google محلياً.

---

## المرحلة G — التحقق النهائي (يغلق AC8) ✅

```bash
curl -m 5 https://<HF_USER>-sara-os.hf.space/health        # → 200
.venv/Scripts/python.exe scripts/deploy_smoke.py          # → exit 0 = سارة حية
```
ثم إعادة بناء الحاوية من الوسم + إعادة فحص الدخان (حلقة tagged-vs-running).

---

## المرحلة H — عقبة Google 403 (من سبرنت 1) ⚠️

المشروع `vantrilex-assistant-2008` على Google Cloud كان محجوباً من جوجل
("project denied access"). افتح console.cloud.google.com → فعّل
Generative Language API وتأكد من حالة المشروع/المفتاح. (جيميناي تقاعدت من الدماغ،
لكن نفس المشروع يستضيف OAuth لبريدك وتقويمك.)

---

## المرحلة I — تدوير المفاتيح (مُوصى به، اختياري) 🔄

المفاتيح الحقيقية عُلقت في محادثتين على الأقل (هذه + مساعد آخر أنتج جدول Render):
- GitHub PAT: أنشئ جديداً fine-grained وحدّث `.env` + الـ Secrets
- Telegram API_HASH: من my.telegram.org
- Groq/OpenRouter: من لوحاتهما
بعدها حدّث `.env` محلياً + Secrets الـ Space (أخبرني وأنا أدير التحديث محلياً).

---

## ملخص الترتيب

**A (موافقتك على v1.0.1) → B (Space) → C (Secrets) → D (pools) → E (جسر) → F (تسجيل صوت) → G (تحقق)**
+ H وI بالتوازي متى شئت. كل خطوة موثقة أعمق في `docs/04-RUNBOOK.md` §4، والسياق الكامل
في `docs/07-HANDOFF.md`.
