# 09 — دليل النشر على Oracle Cloud Always Free (المرجع النهائي للمالك)

> اعتمد المالك هذه المنصة 2026-08-31 (تعديل ADR-15): HF أصبحت Docker فيها مدفوعاً ($9/شهر)،
> وRender/Koyeb المجانية (512MB) لا تحمل حزمة سارة الكاملة. Oracle Always Free = VM حقيقية
> **لا تنم أبداً** وتحمل كل شيء بـ $0.00.
> المتطلبات: بطاقة للتحقق فقط (لا خصم) · قرارات المالك المرتبطة: `docs/03-DECISIONS.md` ADR-15.

---

## لماذا Oracle؟ (الحق كاملاً)

| البند | التفصيل |
|---|---|
| المورد المجاني | Ampere ARM: حتى **4 OCPU + 24GB RAM** (تقسيم حر) + 200GB تخزين |
| النوم | **لا يوجد** — VM دائم التشغيل، بلا pinger وبلا keep-alive |
| التكلفة | **$0.00 دائماً** (Always Free لا ينتهي بـ 12 شهراً — ليس trial) |
| عيوب صادقة | إدارة يدوية (تحديثات/أمان) · المنطقة تُختار عند التسجيل **نهائياً** · أوراكل قد تستبدل مثيلات شبه خاملة (سارة النشطة بأمان غالباً؛ والاستبدال = إعادة نشر، لا فقدان بيانات — كل شيء في الخزنة) |

---

## المرحلة 1 — إنشاء الحساب (≈10 دقائق)

1. افتح https://signup.cloud.oracle.com واختر **Start for free**
2. **المنطقة (Home Region) — قرار نهائي لا يتغير**: اختر الأقرب المتاح: `me-abudhabi-1`
   (أبوظبي) ثم `eu-frankfurt-1`. كل شيء يُبنى داخلها.
3. أدخل بياناتك + البطاقة (تحقق فقط، لا خصم على Always Free) → فعّل الحساب بعد رسالة التأكيد

### إذا رُفضت البطاقة ("Your credit card has been declined") 💳

حدث فعلياً (2026-08-31). في الغالب السبب **من البنك وليس أوراكل** — أوراكل تمرر تحقق
$1 يُلغى تلقائياً ويتطلب بطاقة مقبولة للمعاملات الأونلاين الدولية:

1. **من البنك/التطبيق**: فعّل "المعاملات الأونلاين" + "المعاملات الدولية" على البطاقة
   (مقفلة افتراضياً في كثير من البنوك الأردنية) وتأكد أن 3D Secure/OTP يعمل.
2. الاسم والعنوان في نموذج أوراكل **يطابق حرفياً** ما لدى البنك.
3. بدون VPN + متصفح نظيف (incognito/آخر).
4. فشلت مرتان؟ انتظر 24 ساعة وأنشئ الحساب بإيميل جديد (المحاولات المتتالية تعلّم الجلسة).
5. بطاقة أخرى حقيقية (Visa عادة أنجح؛ لا بطاقات رقمية/مسبقة الدفع). بطاقة أحد الأفراد
   تصلح — **لا يُخصم منها شيء أبداً** ($1 يُلغى وAlways Free لا يحوّل أبداً).
6. عند التسجيل: اختر **Personal** لا Business (إلا إن كان لديك سجل تجاري).

## المرحلة 2 — إنشاء الـ VM (≈5 دقائق)

1. القائمة ☰ → **Compute → Instances → Create Instance**
2. Name: `sara-os`
3. Image: **Ubuntu 24.04** (Minimal يكفي) · Shape: **Ampere** → `VM.Standard.A1.Flex` →
   **2 OCPU / 12 GB RAM** (يوسَّع لاحقاً حتى 4/24 مجاناً) · Boot volume: 50 GB
4. SSH keys: **Generate a key pair** → نزّل المفتاح الخاص واحفظه (لن يُعرض مرة أخرى!)
5. Before Create: وسّع شبكة الـ VNIC → Security List → **Add Ingress Rules**:
   `TCP 22` (SSH، موجودة عادة) · `TCP 80` · `TCP 443` (المصدر `0.0.0.0/0`)
6. Create → سجّل **Public IP** من صفحة الـ Instance

## المرحلة 3 — دومين مجاني لشهادة TLS (≈5 دقائق)

جسر الـ PC يتصل بـ `wss://` (TLS إلزامي)، وLet's Encrypt يحتاج اسماً:
1. سجّل في https://www.duckdns.org (مجاني) → أنشئ subdomain مثل `sara-os.duckdns.org`
2. ضع فيه عنوان الـ **Public IP** من المرحلة 2

## المرحلة 4 — تجهيز الخادم (أول اتصال SSH)

```bash
ssh -i <المفتاح-الخاص>.key ubuntu@<PUBLIC_IP>

# تحديث + Docker
sudo apt update && sudo apt -y upgrade
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && newgrp docker
docker --version   # يجب أن يعمل بلا sudo
```

## المرحلة 5 — كود v1.0.1 + بناء الصورة

```bash
git clone https://github.com/3mar-baha/vantrilex-assistant-os.git sara
cd sara && git checkout v1.0.1
# استنساخ OmniRoute — الصورة تثبته عالمياً من هذا الاستنساخ (تثبيت نسخة البوابة)
git clone --depth 1 https://github.com/diegosouzapw/OmniRoute.git scripts/omniroute

docker build -t sara-os .
# أول بناء ≈ 5-8 دقائق (Node 24 + pip + npm)
```

## المرحلة 6 — ملف البيئة على الخادم (لا يرفع لأي مستودع)

```bash
mkdir -p ~/sara-secrets && chmod 700 ~/sara-secrets
nano ~/sara-secrets/sara.env
```
انسخ إليه **نفس الـ 21 متغيراً** الموثقة في `docs/08-OWNER-NEXT-STEPS.md`
(تلك نفسها التي أضفتها لـ Render — منها في `.env` المحلي). أضف سطراً واحداً إضافياً:

```env
PORT=8080
```

(على Oracle لا أحد يضخ `PORT` — نحددها يدوياً؛ Caddy سيمرر 443→8080)

> **ميزة الـ VM على HF**: ملف `config/google_oauth_client.json` (عميل OAuth) يُنسخ
> إلى الخادم — الـ VM دائمة فتشتغل ميزات Google كاملة هنا (كانت مستحيلة داخل
> حاوية HF لأسباب أمنية). `scp -i <key> config/google_oauth_client.json ubuntu@<IP>:~/sara/config/`

## المرحلة 7 — التشغيل + Caddy للـ TLS (docker compose)

أنشئ `~/sara/deploy/compose.yaml`:

```yaml
services:
  sara:
    image: sara-os
    container_name: sara-core
    env_file: /home/ubuntu/sara-secrets/sara.env
    restart: unless-stopped
    # لا حاجة لنشر المنفذ للعالم — Caddy يتحدث معه داخلياً
    expose:
      - "8080"

  caddy:
    image: caddy:2-alpine
    container_name: sara-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
volumes:
  caddy_data:
```

و`~/sara/deploy/Caddyfile` (بدّل الاسم لدومينك):

```
sara-os.duckdns.org {
    reverse_proxy sara:8080
}
```

شغّل:

```bash
cd ~/sara/deploy && docker compose up -d
docker compose logs -f sara     # راقب إقلاع المشرف: سطرا OMNIROUTE ثم core
```

`restart: unless-stopped` = إقلاع تلقائي بعد أي انقطاع — هذا بديل keep-alive: **الخادم لا ينم أصلاً**.

## المرحلة 8 — التحقق النهائي (يغلق AC8)

```bash
curl -m 5 https://sara-os.duckdns.org/health          # → {"status":"ok"}
# من جهازك المحلي:
.venv/Scripts/python.exe scripts/deploy_smoke.py      # عدّل OMNIROUTE_BASE_URL؟ لا —
# deploy_smoke يفحص محلياً؛ على الخادم بدلها بفحص الحاوية:
ssh ubuntu@<IP> "docker logs --tail 20 sara-core"
```
ثم من تلغرام: `/start` → تحية سارة العمانية → `/enroll-voice` + ملاحظة صوتية →
موافقة Google (تعمل الآن على الـ VM).

## المرحلة 9 — ربط جهازك (جسر PC)

في `.env` المحلي على جهازك:
```env
BRIDGE_SERVER_URL=wss://sara-os.duckdns.org/bridge
```
ثم `make run-bridge` (وأضفه مهمة auto-start). فحص WoL من الشبكة: RUNBOOK §5.

---

## الصيانة المختصرة

| المهمة | الأمر |
|---|---|
| سجلات سارة | `docker logs -f sara-core` |
| إعادة تشغيل | `cd ~/sara/deploy && docker compose restart sara` |
| ترقية لإصدار جديد | `cd ~/sara && git fetch --tags && git checkout v<جديد> && docker build -t sara-os . && docker compose up -d --force-recreate sara` |
| تحديثات أمنية شهرية | `sudo apt update && sudo apt -y upgrade && sudo reboot` |
| نسخ احتياطي | **مدمج بالتصميم** — كل الحالة الدائمة في خزنة GitHub (ADR-15)؛ ملفات الخادم كلها قابلة لإعادة البناء |

## الأعطال الشائعة

| العرض | السبب | الحل |
|---|---|---|
| الحاوية تعيد التشغيل دورياً | `sara.env` ناقص متغير مطلوب — السجل يسمّيه | أكمل المتغير (§6) |
| `omniroute: not found` في السجل | بنيت قبل استنساخ `scripts/omniroute` | أعد `docker build` بعد الاستنساخ |
| Caddy لا يحصل على شهادة | الدومين لا يشير لعنوان VM أو منفذ 80 مقفل | حدّث DuckDNS + Ingress Rules §2.5 |
| تلغرام صامت والحاوية حية | توكن/معرّف خاطئ في `sara.env` | `docker exec sara-core python -m src.main --health` |
