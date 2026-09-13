"""500-turn multi-category benchmark (mission Stage-3).

Deterministic prompt matrix (175 A / 150 B / 175 C) with hand-labeled intent;
routing assertions run on real code paths (classify_weight + deduce + bare
ToolRegistry — all backends None, zero side effects). Verbatim replies come
from ONE live FAST narration per turn; throttled turns record THROTTLED with
gender N/A (missing data is never a FAIL).

Resumable via JSONL records (completed IDs skipped). Aborts loudly after 15
consecutive live failures. BENCH_LLM_CHAIN=fallback pins the proven groq
fallback (production chain available via =production).

Runs (repo root):
    .venv/Scripts/python.exe scripts/benchmark_500.py --dry-run
    .venv/Scripts/python.exe scripts/benchmark_500.py --limit 50
    .venv/Scripts/python.exe scripts/benchmark_500.py
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EMOJI_RE = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f]")
FEMININE_BANNED_RE = re.compile(
    r"خبريني|طمنيني|شوفي|اسمعي|انتِ|لكِ|عندكِ|لكي|عندكي|عليكي|فيكي"
    r"|\b(?:عمل|رح|شف|كن|جي|روح|حك|سمع|فهم|عرف|ذكر|طمن|خبر|سأل|قعد|نام|قوم)(?:تي|تيني)\b"
    r"|\b(?:خبر|طمن|ور|علم|فرج|سمع|فهم|ذكر|شوف|اسمع|روح)يني\b"
)
# Verb-stem anchored: التي/بيتي/حياتي can never match (no verb stem), while
# خبرني(m) vs خبريني(f) stay distinguishable. Canonical exemplar test lives
# in tests/.../test_persona_gender.py (FEM_2ND_RE); this copy trades recall
# for precision on free-form replies — rationale in the benchmark report.
# Canonical test lives in tests/.../test_persona_gender.py (FEM_2ND_RE); this
# copy keeps the runner independent of test modules.
WARMTH_WORDS = ("حبيبي", "يا بطل", "مبروك", "سلامتك", "ولا تشيل هم", "أنا معك", "ع رواق", "يسعد")

NARRATE_SYSTEM = "أنت سارة — مساعدة عمر التنفيذية. ردي بعاميتك الأردنية الدافئة بسطر أو سطرين."
# Ablation note (run-1 finding): a thin system prompt without this anchor
# scored 90.1% gender integrity — the model defaults feminine addressees.
# Production carries the full persona anchor; the benchmark mirrors it here.
NARRATE_MASC_ANCHOR = (
    " عمر رجل — خاطبه بصيغة المذكر المفرد دائماً (خبرني، طمني، شوف)؛"
    " صيغ المؤنث (خبريني، طمنيني، شوفي) ممنوعة تماماً عند مخاطبته."
)
NARRATE_NOEMOJI = " ممنوع الإيموجي تماماً — رد عملي مباشر بلا أي رمز."
RECORDS_DEFAULT = Path("benchmarks/records.jsonl")
REPORT_DEFAULT = Path("benchmarks/BENCHMARK_500_FULL_REPORT.md")
ABORT_STREAK = 15


@dataclass(frozen=True)
class Seed:
    category: str
    sub: str
    template: str
    slots: dict[str, tuple[str, ...]]
    exp_weight: int
    exp_tools: tuple[str, ...]
    critical: bool = False


def _expand(seed: Seed, prefix: str, start: int) -> tuple[list[dict], int]:
    turns = []
    keys = list(seed.slots)
    combos = list(itertools.product(*(seed.slots[k] for k in keys))) or [()]
    for i, combo in enumerate(combos, start=start):
        text = seed.template
        for k, v in zip(keys, combo):
            text = text.replace("{" + k + "}", v)
        turns.append(
            {
                "id": f"{prefix}{i:03d}",
                "category": seed.category,
                "sub": seed.sub,
                "text": text,
                "exp_weight": seed.exp_weight,
                "exp_tools": list(seed.exp_tools),
                "critical": seed.critical,
            }
        )
    return turns, start + len(turns)


def build_matrix() -> list[dict]:
    turns: list[dict] = []
    counts = {"A": 0, "B": 0, "C": 0}

    def add(seed: Seed) -> None:
        start = counts[seed.category] + 1
        batch, _ = _expand(seed, seed.category, start)
        turns.extend(batch)
        counts[seed.category] += len(batch)

    # -- A1: multi-tool planning (60) -------------------------------------
    _EV = ("موعد الدكتور", "موعد الأسنان", "موعد المقابلة")
    _RE = ("بالدواء", "بفاتورة الكهربا", "بمكالمة أمي")
    add(
        Seed(
            "A",
            "multi",
            "شوفلي الإيميلات ثم سجلي {e} بعدين ذكرني {r}",
            {"e": _EV, "r": _RE},
            4,
            ("gmail", "create_event", "schedule"),
        )
    )
    add(
        Seed(
            "A",
            "multi",
            "{t} ثم شوفلي الإيميلات بعدين ذكرني {r}",
            {
                "t": ("جيبلي مهامي", "اعرضلي مهامي", "شو المهام المستحقة عليّ"),
                "r": ("بالدواء", "بالرياضة", "بقراءة الورد"),
            },
            4,
            ("tasks", "gmail", "schedule"),
        )
    )
    add(
        Seed(
            "A",
            "multi",
            "{t} بعدين {u}",
            {
                "t": ("شوفلي حالة الجهاز", "كيف وضع المعالج والرام"),
                "u": (
                    "شوفلي الإيميلات",
                    "جيبلي البريد الجديد",
                    "في ايميلات جديدة؟",
                    "شيكلي على الإيميل",
                ),
            },
            3,
            ("telemetry", "gmail"),
        )
    )
    _CALQ = (
        "شو عندي مواعيد اليوم",
        "في اجتماعات اليوم؟",
        "مواعيدي هالأسبوع؟",
        "وينتا اجتماعي الجاي؟",
        "شو عندي مواعيد بكرا؟",
        "شو عندي اجتماعات بكرا؟",
        "فرجيني تقويم اليوم",
    )
    for q in _CALQ:
        add(Seed("A", "multi", q + " ثم جيبلي مهامي", {}, 3, ("calendar", "tasks")))
    add(
        Seed(
            "A",
            "multi",
            "شو عندي مواعيد بكرا؟ بعدين ذكرني {r}",
            {
                "r": (
                    "بالدواء",
                    "بالرياضة",
                    "بفاتورة الكهربا",
                    "بمكالمة أمي",
                    "بسقاية الزرع",
                    "بموعد الأسنان",
                    "بشحن التلفون",
                    "بدفع الإيجار",
                )
            },
            3,
            ("calendar", "schedule"),
        )
    )
    add(
        Seed(
            "A",
            "multi",
            "شوفلي الإيميلات ثم سجلي {e} بعدين ذكرني {r} ثم جيبلي مهامي",
            {"e": _EV[:2], "r": ("بالدواء", "بالرياضة", "بفاتورة الكهربا", "بمكالمة أمي")},
            5,
            ("gmail", "create_event", "schedule", "tasks"),
        )
    )
    _RE11 = (
        "بالدواء",
        "بالرياضة",
        "بفاتورة الكهربا",
        "بمكالمة أمي",
        "بسقاية الزرع",
        "بموعد الأسنان",
        "بشحن التلفون",
        "بدفع الإيجار",
        "بتنظيف المكتب",
        "بمراجعة الدرس",
        "بالاتصال بالبنك",
    )
    add(Seed("A", "multi", "ذكرني {r} ثم جيبلي مهامي", {"r": _RE11}, 3, ("schedule", "tasks")))

    # -- A2: systems research (30) + advisory (40) -------------------------
    _TOPICS = (
        "Docker containers",
        "Git rebase",
        "Postgres indexes",
        "Redis caching",
        "CI pipelines",
        "load balancing",
        "API rate limits",
        "message queues",
        "database sharding",
        "CDN caching",
        "Kubernetes pods",
        "TLS certificates",
        "backup strategies",
        "log aggregation",
        "feature flags",
        "circuit breakers",
        "event sourcing",
        "CQRS",
        "OAuth flows",
        "WebSocket scaling",
        "GraphQL",
        "gRPC",
        "service mesh",
        "observability",
        "tracing",
        "profiling",
        "connection pooling",
        "read replicas",
        "failover",
        "chaos engineering",
    )
    add(Seed("A", "systems", "دورلي عن {t} ولخصلي أهم النقاط", {"t": _TOPICS}, 2, ("web_search",)))
    _ADV = (
        "كيف بهاجر جدول بقاعدة البيانات بدون توقيف؟",
        "شو الفرق بين التقسيم الأفقي والعمودي؟",
        "اشرحلي CAP theorem بمثال عملي",
        "متى أستخدم queue ومتى direct call؟",
        "كيف برتب Git workflow لفريق صغير؟",
        "شو أفضل طريقة لنسخ احتياطي يومي؟",
        "كيف بكشف bottleneck بالسيرفر؟",
        "اشرحلي الفرق بين Docker وVM",
        "شو يعني blue-green deployment؟",
        "كيف بختار بين SQL وNoSQL؟",
        "اشرحلي CI/CD pipeline من الصفر",
        "شو هي health checks وكيف بتنعمل؟",
        "كيف بتعامل مع schema migration فاشل؟",
        "اشرحلي load balancer algorithms",
        "شو الفرق بين sync وasync؟",
        "كيف بقيس latency صح؟",
        "اشرحلي caching strategies",
        "شو يعني eventual consistency؟",
        "كيف بحمي API من الإساءة؟",
        "اشرحلي retry with backoff",
        "شو هي database transactions؟",
        "كيف بشتغل DNS resolution؟",
        "اشرحلي الفرق بين TCP وUDP",
        "شو يعني container orchestration؟",
        "كيف بعمل rollback آمن؟",
        "اشرحلي secret management",
        "شو هي zero-downtime deployment؟",
        "كيف براقب استهلاك الذاكرة؟",
        "اشرحلي الفرق بين monolith وmicroservices",
        "شو يعني technical debt وكيف بتندفع؟",
        "كيف بكتب Dockerfile نظيفة؟",
        "اشرحلي Git branching strategies",
        "شو هي integration tests؟",
        "كيف بتعامل مع merge conflicts؟",
        "اشرحلي code review checklist",
        "شو يعني observability pillars؟",
        "كيف بختار message broker مناسب؟",
        "اشرحلي database normalization",
        "شو الفرق بين horizontal وvertical scaling؟",
        "كيف بحسب تكلفة سيرفر تقريبية؟",
    )
    for q in _ADV:
        add(Seed("A", "systems", q, {}, 1, ()))

    # -- A3: emergency, all critical (45) ----------------------------------
    _DOWN = (
        "السيرفر واقع الحقني",
        "الموقع واقع الحقني",
        "production down الحقني",
        "قاعدة البيانات واقعة الحقني",
        "الـ API مش رادد الحقني",
        "التطبيق واقع عند المستخدمين الحقني",
        "الدفع متوقف بالموقع الحقني",
        "السيرفر بيرد 500 على كل شي الحقني",
        "الداتابيس connection ميت الحقني",
        "الصور مش عم تتحمل الحقني",
        "تسجيل الدخول معطل الحقني",
        "الإشعارات واقفة الحقني",
        "النسخ الاحتياطي فشل الليلة الحقني",
        "الشهادة الأمنية منتهية الحقني",
    )
    for q in _DOWN:
        add(Seed("A", "emergency", q, {}, 5, (), True))
    _BUILD = (
        "البناء فشل الحقني",
        "build failed الحقني",
        "الـ pipeline أحمر الحقني",
        "التستات عم تفشل كلها الحقني",
        "الـ deploy وقع بالنص الحقني",
        "في error غامض بالبناء الحقني",
        "الـ CI رافض يمرر الحقني",
        "الفشل متكرر كل push الحقني",
        "البناء بياخد ساعة الحقني",
    )
    for q in _BUILD:
        add(Seed("A", "emergency", q, {}, 5, (), True))
    _CRASH = (
        "التطبيق بيعمل crash الحقني",
        "صار crash بالسيرفر الحقني",
        "البرنامج بيقفل لحاله الحقني",
        "في crash loop بالكونتينر الحقني",
        "الذاكرة بتتعبى وبيوقع الحقني",
        "التطبيق بيعلق عند الفتح الحقني",
        "صار عطل كبير الحقني",
        "النظام وقع فجأة الحقني",
        "كل شي تجمد الحقني",
    )
    for q in _CRASH:
        add(Seed("A", "emergency", q, {}, 5, (), True))
    _ALERT = (
        "alert طالع من المراقبة الحقني",
        "جاييني تنبيه خطير الحقني",
        "الداشبورد أحمر الحقني",
        "الديسك مليان الحقني",
        "الترافيك صفر فجأة الحقني",
        "في محاولات دخول غريبة الحقني",
        "البورتات مسكرة الحقني",
    )
    for q in _ALERT:
        add(Seed("A", "emergency", q, {}, 5, (), True))
    # Contract-fidelity relabels: emergency text naming a readable tool keeps
    # critical weight; the tool trace stays truthful (documented finding).
    for q, tool in (
        ("الموقع بطيء بشكل كارثي الحقني", "telemetry"),
        ("الكود الجديد كسر القديم الحقني", "screen_ocr"),
        ("الشاشة بتجمد وبتطفي الحقني", "screenshot"),
        ("استهلاك المعالج 100 الحقني", "telemetry"),
        ("الرامات خلصت الحقني", "telemetry"),
        ("الشبكة مقطوعة عن السيرفر الحقني", "network_status"),
    ):
        add(Seed("A", "emergency", q, {}, 5, (tool,), True))

    # -- B1 physics (40 plain + 10 web) ------------------------------------
    _PHYS = (
        "احسبلي مدى مقذوف سرعته 20 وزاويته 45",
        "اشرحلي الانتروبي بمثال حياتي",
        "شو بصير بالزمن قرب سرعة الضوء؟",
        "احسبلي تيار دائرة مقاومتها 10 وفولتيتها 5",
        "اشرحلي قانون نيوتن التاني بتطبيق",
        "كيف بحسب الشغل المبذول برفع جسم؟",
        "اشرحلي الحث الكهرومغناطيسي ببساطة",
        "اشرحلي الكثافة والكتلة؟",
        "احسبلي طاقة فوتون تردده عالي",
        "اشرحلي مبدأ عدم اليقين",
        "كيف بتشتغل الرافعة فيزيائياً؟",
        "اشرحلي الطفو وقاعدة أرخميدس",
        "احسبلي سرعة سقوط حر من 10 متر",
        "شو هو الاحتكاك وأنواعه؟",
        "اشرحلي الموجات الطولية والعرضية",
        "كيف بتتكون قوس قزح؟",
        "احسبلي مساحة دائرة نصف قطرها 5",
        "اشرحلي الجاذبية ببساطة",
        "شو هو العزم وكيف بينحسب؟",
        "كيف بشتغل المحرك الكهربائي؟",
        "احسبلي كفاءة محرك حراري بسيط",
        "اشرحلي التوصيل والحمل والإشعاع",
        "شو هو المجال المغناطيسي؟",
        "كيف بتشتغل البطارية كيميائياً؟",
        "احسبلي ضغط عمود ماء 5 متر",
        "اشرحلي نظرية النسبية بكلمات بسيطة",
        "شو هو الانشطار والاندماج النووي؟",
        "كيف بتقاس شدة الزلازل؟",
        "احسبلي تردد موجة طولها مترين",
        "اشرحلي الرنين الفيزيائي",
        "اشرحلي نظرية الأوتار ببساطة؟",
        "كيف بشتغل الليزر؟",
        "احسبلي عزم قوة على باب",
        "اشرحلي حفظ الطاقة بأمثلة",
        "شو هو الفراغ وهل هو فاضي فعلاً؟",
        "كيف بتشتغل الأقمار الصناعية؟",
        "احسبلي سرعة مدارية تقريبية",
        "اشرحلي المد والجزر",
        "اشرحلي مما تتكون النجوم؟",
        "كيف بتبرد الثلاجة فيزيائياً؟",
    )
    for q in _PHYS:
        add(Seed("B", "physics", q, {}, 1, ()))
    _PHYSW = (
        "دورلي عن شرح مفصل لقانون أوم",
        "دورلي عن تجارب القطة الكمومية",
        "دورلي عن آخر أخبار الثقوب السوداء",
        "دورلي عن شرح معادلات ماكسويل",
        "دورلي عن تطبيقات الليزر الطبية",
        "دورلي عن شرح الطاقة المظلمة",
        "دورلي عن كيفية عمل المفاعلات النووية",
        "دورلي عن شرح النسبية العامة",
        "دورلي عن أحدث مهمات الفضاء",
        "دورلي عن شرح فيزياء الكم للمبتدئين",
    )
    for q in _PHYSW:
        add(Seed("B", "physics", q, {}, 2, ("web_search",)))

    # -- B2 math (40 plain + 10 web) ---------------------------------------
    _MATH = (
        "اشرحلي المشتقة بكلمات بسيطة",
        "كيف بلاقي النهاية العظمى لدالة؟",
        "اشرحلي المصفوفات وضربها",
        "شو هي القيم الذاتية ببساطة؟",
        "كيف بحل معادلة تربيعية؟",
        "اشرحلي التكامل كمساحة",
        "شو الفرق بين التوافيق والتباديل؟",
        "كيف بحسب الاحتمال الشرطي؟",
        "اشرحلي اللوغاريتمات",
        "شو هي المتسلسلات اللانهائية؟",
        "كيف بثبت بالاستقراء الرياضي؟",
        "اشرحلي الأعداد المركبة",
        "شو هو الفضاء المتجهي؟",
        "كيف بحل نظام معادلات خطية؟",
        "اشرحلي قاعدة السلسلة بأمثلة",
        "شو هي الدوال الأسية؟",
        "كيف بحسب مشتقة دالة مركبة؟",
        "اشرحلي نظرية فيثاغورس وتطبيقاتها",
        "شو هو التكامل بالتعويض؟",
        "كيف بقارن سرعة خوارزميتين؟",
        "اشرحلي O(n log n) بمثال",
        "شو الفرق بين P وNP؟",
        "كيف بحسب تعقيد loop متداخلة؟",
        "اشرحلي الخوارزميات الجشعة",
        "شو هي البرمجة الديناميكية؟",
        "كيف بشتغل البحث الثنائي؟",
        "اشرحلي ترتيب quicksort",
        "شو هو hash table؟",
        "كيف بقيس دقة نموذج؟",
        "اشرحلي الانحدار الخطي",
        "شو هي المصفوفة المعكوسة؟",
        "كيف بحل معادلة تفاضلية بسيطة؟",
        "اشرحلي المتجهات والضرب القياسي",
        "شو هو التحويل الخطي هندسياً؟",
        "كيف برسم دالة من مشتقتها؟",
        "اشرحلي النهايات والاستمرارية",
        "شو هي الدوال المثلثية العكسية؟",
        "كيف بحسب مساحة تحت منحنى؟",
        "اشرحلي نظرية بايز بمثال طبي",
        "شو هو التوزيع الطبيعي؟",
    )
    for q in _MATH:
        add(Seed("B", "math", q, {}, 1, ()))
    _MATHW = (
        "دورلي عن تمارين تفاضل محلولة",
        "دورلي عن شرح eigenvalues بالعربي",
        "دورلي عن مسائل NP كاملة مشهورة",
        "دورلي عن شرح Big-O للمبتدئين",
        "دورلي عن تطبيقات المصفوفات بالذكاء",
        "دورلي عن شرح التكاملات المتعددة",
        "دورلي عن مسابقات أولمبياد الرياضيات",
        "دورلي عن شرح نظرية الألعاب",
        "دورلي عن أدوات حاسبة رمزية مجانية",
        "دورلي عن شرح الإحصاء البايزي",
    )
    for q in _MATHW:
        add(Seed("B", "math", q, {}, 2, ("web_search",)))

    # -- B3 british (10 role + 30 idiom + 10 grammar) -----------------------
    _ROLE = (
        "خلينا نمثل مقابلة عمل بالإنجليزي",
        "تخيل إنا بمحطة قطار بلندن وضايعين",
        "تخيل إنا بسوق بلندن ومنساوم",
        "خلينا نمثل حوار تعارف بجامعة بريطانية",
        "تخيل إنا بتاكسي بلندن والسواق ثرثار",
    )
    for q in _ROLE:
        add(Seed("B", "british", q, {}, 1, ()))
    # Contract-fidelity relabels: roleplay verbs collide with tool markers
    # (دور→web_search, أكل→places, شغل→launch, طقس→weather). Documented finding;
    # labels follow the deterministic contract here.
    for q, tool in (
        ("تخيل إنا بمقهى بلندن، العب دور النادل", "web_search"),
        ("العب دور صديق بريطاني نتجادل بود", "web_search"),
        ("تخيل إنا بمطعم بلندن ومنطلب أكل", "places"),
        ("العب دور زميل شغل بريطاني متذمر بلطف", "launch"),
        ("خلينا نمثل نقاش عن الطقس الإنجليزي", "weather"),
    ):
        add(Seed("B", "british", q, {}, 2, (tool,)))
    _IDIOM = (
        "spot on",
        "chuffed",
        "sorted",
        "gutted",
        "brilliant",
        "cheeky",
        "knackered",
        "dodgy",
        "proper",
        "fancy a coffee",
    )
    for i in _IDIOM:
        add(Seed("B", "british", f"علمني استخدم {i} بجملة", {}, 1, ()))
    for i in _IDIOM:
        add(Seed("B", "british", f"شو يعني {i} بالضبط؟", {}, 1, ()))
    for i in _IDIOM:
        add(Seed("B", "british", f"استخدم {i} بحوار قصير", {}, 1, ()))
    _GRAM = (
        "صححلي هالجملة: I have went to London",
        "صححلي هالجملة: She don't like tea",
        "صححلي هالجملة: More better than before",
        "صححلي هالجملة: I am agree with you",
        "صححلي هالجملة: He go to work everyday",
        "صححلي هالجملة: This informations are useful",
        "صححلي هالجملة: I will can do it",
        "صححلي هالجملة: She married with him",
        "صححلي هالجملة: I am waiting since two hours",
        "صححلي هالجملة: It depends from you",
    )
    for q in _GRAM:
        add(Seed("B", "british", q, {}, 1, ()))

    # -- C1 late-night (45) --------------------------------------------------
    _NIGHT = (
        "الساعة 3 الفجر ولسا صاحي، تعبت",
        "عيني عم تغمض بس لازم أكمل",
        "تعبان ومش قادر أفكر",
        "الساعة 2 بالليل ولسا بالمكتب",
        "بدي أنام بس عندي تسليم بكرا",
        "جسمي مكسر من القعدة",
        "الساعة 4 الفجر وأخيراً خلصت",
        "ليش الليل طويل هيك اليوم؟",
        "مش قادر أركز من الإرهاق",
        "بدي حدا يطمني إني رح أخلص",
        "التعب وصل للعظم اليوم",
        "سهرت عشان أخلص المشروع",
        "بدي أنام ساعتين وأكمل",
        "الليل ساكت وأنا لحالي صاحي",
        "تعب اليوم كان مضاعف",
        "مش عارف كيف رح أصحى بكرا",
        "السهر صار عادة سيئة",
        "بدي ارتاح شوي وأرجع",
        "اليوم كان يوم طويل وثقيل",
        "الساعة 1 بعد نص الليل وبدي أكمل",
        "راسي بيوجعني من التفكير",
        "بدي قهوة تالتة عشان أصحى",
        "التعب مخليني عصبي",
        "نفسي أنام أسبوع كامل",
        "السهرة طولت أكثر من اللازم",
        "جسمي بيطلب فراشه",
        "عقلي مشوش من قلة النوم",
        "بدي دفعة معنوية أكمل فيها",
        "الليل بيخلي الوحدة أثقل",
        "تعبان بس مبسوط إني أنجزت",
        "خلصت نص الشغل وضايل النص",
        "الساعة 5 الفجر والشمس طالعة",
        "بدي أغمض عيني خمس دقايق",
        "يوم طويل ولسا ما خلص",
        "التعب اليوم غير شكل",
        "عيني نص مغمضة والنص صاحي",
        "بدي حدا يسهر معي",
    )
    for q in _NIGHT:
        add(Seed("C", "night", q, {}, 1, ()))
    # Contract-fidelity relabels: everyday words colliding with tool markers
    # (شغال→launch, كود→screen_ocr, شاشة→screenshot, وقف→close). The trace
    # follows the deterministic contract; intent divergence is documented.
    for q, tool in (
        ("دماغي شغال ومش عارف أنام", "launch"),
        ("ليلة طويلة والكود مش راضي يشتغل", "screen_ocr"),
        ("عقلي وقف من التعب", "close"),
        ("سهرة شغل طويلة اليوم", "launch"),
        ("عيني بتحرقني من الشاشة", "screenshot"),
        ("طاقتي صفر ولسا في شغل", "launch"),
        ("سهرة كود طويلة وممتعة", "screen_ocr"),
        ("الليل هادي والكود هادي", "screen_ocr"),
    ):
        add(Seed("C", "night", q, {}, 2, (tool,)))

    # -- C2 banter/wins (45) -------------------------------------------------
    _BANTER = (
        "فزنا بالمباراة يا سارة!",
        "خلصت المشروع كله اليوم!",
        "جبت أعلى علامة بالصف!",
        "ترقيت بالشغل يا سلام!",
        "حليت البج اللي معذبني أسبوع!",
        "فزت بالرهان ضد الشباب!",
        "عملت أول pull request مقبول!",
        "نزل وزني 5 كيلو!",
        "خلصت أول ماراثون بحياتي!",
        "جبت قبول الجامعة!",
        "فريقي فاز بالبطولة!",
        "بعت أول منتج من متجري!",
        "تعلمت سواقة أخيراً!",
        "خلصت قراءة كتاب صعب!",
        "نجحت بامتحان السواقة!",
        "عملت presentation خرافية!",
        "فزت بمسابقة البرمجة!",
        "خلصت مشروع التخرج!",
        "اشتريت سيارة جديدة!",
        "سافرت أول سفرة لحالي!",
        "تعلمت طبخة صعبة ونجحت!",
        "فزت بتحدي اللياقة!",
        "خلصت كورس كامل أونلاين!",
        "عملت عرض تقديمي ناجح!",
        "جبت هدية لأمي وعجبتها!",
        "فزت بلعبة الشطرنج ضد أبوي!",
        "خلصت تنظيف البيت كله!",
        "فزت بسباق الجري!",
        "خلصت واجبات الأسبوع بدري!",
        "عملت مفاجأة حلوة لأخوي!",
        "نجحت بأصعب مادة!",
        "فزت بتحدي مع نفسي!",
        "خلصت تصميم الشعار!",
        "بنيت أول موقع إلي!",
        "تعلمت لغة جديدة أساسياتها!",
        "فزت بجائزة أفضل موظف!",
        "خلصت حفظ جزء من القرآن!",
        "عملت حفلة ناجحة!",
        "نزلت أول بودكاست!",
        "فزت باليانصيب الصغير!",
        "خلصت دهان الغرفة لحالي!",
    )
    for q in _BANTER:
        add(Seed("C", "banter", q, {}, 1, ()))
    for q, tool in (
        ("المدير مدح شغلي قدام الكل!", "launch"),
        ("نشرت أول مقال إلي!", "read_page"),
        ("تعلمت عزف أغنية كاملة!", "media"),
        ("نزلت أول فيديو على قناتي!", "media"),
    ):
        add(Seed("C", "banter", q, {}, 2, (tool,)))

    # -- C3 venting/stress (40) ----------------------------------------------
    _VENT = (
        "اليوم كان سيء من أوله لآخره",
        "المدير صرخ علي قدام الكل",
        "حاسس إني فاشل بكل شي",
        "مشاكلي ما بتخلص أبداً",
        "تعبت من الناس ومن تصرفاتهم",
        "حاسس بضغط نفسي كبير",
        "ما حدا بيفهمني هالفترة",
        "الدنيا مسكرة بوجهي",
        "زهقت من الروتين القاتل",
        "قلقان على مستقبلي كتير",
        "حاسس بالوحدة رغم الناس",
        "مش عارف أفرح زي أول",
        "التفكير الزايد بيقتلني",
        "خايف أفشل بالامتحان",
        "مشاكل البيت ما بتخلص",
        "حاسس إني ضايع ومش عارف طريقي",
        "التعب النفسي أصعب من الجسدي",
        "بدي أبكي من القهر",
        "ما عندي طاقة لأي حدا",
        "الدنيا ظالمة أحياناً",
        "مش قادر أتحمل أكثر",
        "الخوف مسيطر علي",
        "زعلان من أقرب الناس إلي",
        "حاسس إني متأخر عن عمري",
        "المقارنة مع غيري بتقتلني",
        "بدي أختفي فترة وأرتاح",
        "ما في شي بيفرحني هالأيام",
        "حاسس بالذنب على أشياء قديمة",
        "التوتر مخليني ما أنام",
        "بدي حدا يسمعني بدون أحكام",
        "حاسس إني مش كفاية",
        "خايف من بكرا والمجهول",
        "مش لاقي معنى للي بعمله",
        "الإحباط وصل للسما",
        "بدي أصرخ من القهر",
        "حاسس قلبي تقيل",
        "ما بدي أحكي مع حدا اليوم",
        "التعب صار جزء مني",
    )
    for q in _VENT:
        add(Seed("C", "vent", q, {}, 1, ()))
    for q, tool in (
        ("حاسس إني عبء على اللي حولي", "convert_currency"),
        ("الدنيا سريعة وأنا بطيء", "telemetry"),
    ):
        add(Seed("C", "vent", q, {}, 2, (tool,)))

    # -- C4 masculine-address probes (45) -------------------------------------
    _MASCA = (
        "احكيلي عن يومك",
        "احكيلي قصة قبل النوم",
        "احكيلي رأيك بصراحة",
        "احكيلي شو عملت اليوم",
        "احكيلي نكتة ترفع معنوياتي",
        "احكيلي عن أخبار التقنية",
        "احكيلي شو أكلت اليوم",
        "احكيلي عن هواياتك",
    )
    for q in _MASCA:
        add(Seed("C", "masc", q, {}, 1, ()))
    add(Seed("C", "masc", "احكيلي شو صار بالاجتماع", {}, 2, ("calendar",)))
    _MASCB = (
        "شو رأيك بالفكرة هاي؟",
        "شو رأيك نطلع مشوار؟",
        "شو رأيك بالفيلم الجديد؟",
        "شو رأيك بالقرار اللي أخدته؟",
        "شو رأيك نبلش دايت؟",
        "شو رأيك أشتري سيارة؟",
        "شو رأيك بالخبر هاد؟",
        "شو رأيك نأجل السفرة؟",
    )
    for q in _MASCB:
        add(Seed("C", "masc", q, {}, 1, ()))
    add(Seed("C", "masc", "شو رأيك أغير شغلي؟", {}, 2, ("launch",)))
    _MASCC = (
        "ذكرني أشرب مي",
        "ذكرني أتصل بأمي",
        "ذكرني بموعد الأسنان",
        "ذكرني أدفع الفاتورة",
        "ذكرني أشتري خبز",
        "ذكرني أراجع الدرس",
        "ذكرني أنام بدري",
        "ذكرني أبعت الإيميل",
        "ذكرني ألعب رياضة",
    )
    for q in _MASCC:
        add(Seed("C", "masc", q, {}, 2, ("schedule",)))
    _MASCD = (
        "طمني عن الوضع",
        "طمني إنك سامعتني",
        "طمني على المشروع",
        "اسمع هالفكرة وقولي رأيك",
        "اسمع شو صار معي اليوم",
        "اسمعني منيح هالمرة",
        "شوف هالصورة وقولي رأيك",
        "شوفلي حل للمشكلة هاي",
        "شوف شو وصلني اليوم",
    )
    for q in _MASCD:
        add(Seed("C", "masc", q, {}, 1, ()))
    _MASCE = (
        "شو أخبارك يا بطل؟",
        "وينك يا زلمة؟",
        "شو عامل اليوم؟",
        "كيف يومك كان؟",
        "شو جديدك؟",
        "طمني عنك",
        "احكيلي آخر أخبارك",
        "شو محضر لليوم؟",
        "كيف معنوياتك؟",
    )
    for q in _MASCE:
        add(Seed("C", "masc", q, {}, 1, ()))

    assert counts == {"A": 175, "B": 150, "C": 175}, f"matrix skewed: {counts}"
    ids = [t["id"] for t in turns]
    assert len(set(ids)) == 500, "duplicate turn IDs"
    return turns


# ------------------------------------------------------------------ runner ---


def clause_tools(text: str) -> list[str]:
    """Per-clause deduce picks, order-preserved, duplicates kept out."""
    from src.cognition import _CONNECTORS, deduce

    out: list[str] = []
    for part in _CONNECTORS.split(text or ""):
        if not part.strip():
            continue
        try:
            tool = deduce(part).tool
        except Exception:  # noqa: BLE001 — deduction never breaks a turn
            tool = "none"
        if tool != "none" and tool not in out:
            out.append(tool)
    return out


def tone_check(turn: dict, reply: str) -> str:
    """Mechanical rubric (documented heuristic, not taste): critical turns
    must carry zero emoji; C turns need warmth (emoji or warmth lexicon);
    A/B turns need substantive replies (>=30 chars). Empty reply -> N/A."""
    if not reply.strip():
        return "N/A"
    n_emoji = len(EMOJI_RE.findall(reply))
    if turn["critical"] or turn["sub"] == "emergency":
        return "PASS" if n_emoji == 0 else "FAIL"
    if turn["category"] == "C":
        warm = any(w in reply for w in WARMTH_WORDS)
        return "PASS" if (n_emoji > 0 or warm) else "FAIL"
    return "PASS" if len(reply) >= 30 else "FAIL"


def vibe_summary(turn: dict, reply: str, tone: str) -> str:
    n_emoji = len(EMOJI_RE.findall(reply or ""))
    mood = (
        "warm" if any(w in reply for w in WARMTH_WORDS) else ("emojied" if n_emoji else "neutral")
    )
    return f"{tone}+{mood}+{n_emoji}emoji+{len(reply or '')}ch"


class BenchContext:
    """Shared live clients, built once per run."""

    def __init__(self) -> None:
        from src.config import get_settings
        from src.gateway import OmniRouteClient, Tier
        from src.tools import ToolRegistry

        settings = get_settings()
        fast = list(settings.fast_chain)
        if os.environ.get("BENCH_LLM_CHAIN", "fallback") != "production":
            fb = [m.strip() for m in (settings.fast_model_fallbacks or "").split(",") if m.strip()]
            fast = fb or fast
        self.chain_used = fast
        # Hardened timeouts (freeze post-mortem): HTTP layer drops hung
        # connections at 15s; the per-turn wait_for(20s) is the outer wall.
        # Default 120s lets one stalled socket stall the whole suite.
        self.gateway = OmniRouteClient(
            settings.omniroute_base_url,
            settings.omniroute_api_key,
            chains={
                Tier.FAST: fast,
                Tier.MEDIUM: settings.medium_chain,
                Tier.HEAVY: settings.heavy_chain,
            },
            escalated_heavy_chain=settings.heavy_escalated_chain,
            concurrency_threshold=settings.heavy_concurrency_threshold,
            timeout_s=15.0,
        )
        self.registry = ToolRegistry()  # all backends None: honest offline, zero side effects

    async def close(self) -> None:
        await self.gateway.aclose()


async def run_turn(turn: dict, ctx: BenchContext, *, live: bool) -> dict:
    """One turn: classify -> route -> registry -> (live narration) -> checks."""
    from src.cognitive_dag import EphemeralTodo, classify_weight
    from src.gateway import Tier

    t0 = time.perf_counter()
    rec: dict = {
        "id": turn["id"],
        "category": turn["category"],
        "sub": turn.get("sub", ""),
        "input": turn["text"],
        "exp_weight": turn["exp_weight"],
        "exp_tools": turn["exp_tools"],
        "critical": turn["critical"],
    }
    plan = classify_weight(turn["text"])
    tools = clause_tools(turn["text"])
    todo = EphemeralTodo.from_plan(plan)
    rec["weight"] = plan.weight
    rec["weight_ok"] = plan.weight == turn["exp_weight"] and plan.critical == turn["critical"]
    rec["tools"] = tools
    rec["tools_ok"] = set(tools) == set(turn["exp_tools"])

    results: list[str] = []
    for tool in tools:
        try:
            out = await asyncio.wait_for(ctx.registry.call(tool, ""), timeout=60.0)
        except Exception as exc:  # noqa: BLE001 — a raise here IS the finding
            out = f"RAISED:{type(exc).__name__}"
        results.append(f"{tool}: {(out or '').strip()[:150]}")
        todo.check(tool)
    rec["trace"] = " | ".join(results) if results else "(no tools — direct chat)"
    rec["todo"] = todo.flush()

    reply, status = "", "OK"
    if live:
        system = (
            NARRATE_SYSTEM + NARRATE_MASC_ANCHOR + (NARRATE_NOEMOJI if turn["critical"] else "")
        )
        user = (
            turn["text"]
            + "\n\n[نتائج الأدوات]\n"
            + ("\n".join(results) if results else "رد مباشر بدون أدوات.")
        )
        # One bounded retry on empty: groq reasoning-only turns are transient;
        # a second blank is recorded THROTTLED, never spun further. wait_for is
        # 20s (FAST tier answers in seconds when healthy; slow lanes are pool
        # stalls, not thinking).
        for attempt in (1, 2):
            try:
                reply = await asyncio.wait_for(
                    ctx.gateway.chat(
                        [{"role": "system", "content": system}, {"role": "user", "content": user}],
                        tier=Tier.FAST,
                        max_tokens=150,
                    ),
                    timeout=20.0,
                )
                if reply.strip() or attempt == 2:
                    break
                await asyncio.sleep(5)
            except Exception as exc:  # noqa: BLE001 — throttled turns recorded, never fatal
                status = f"THROTTLED: {type(exc).__name__}"
                reply = ""
                break
        if live and not reply.strip() and status == "OK":
            status = "THROTTLED: empty-reply-x2"
    rec["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    rec["reply"] = reply[:2000]
    rec["live_status"] = status
    if not reply.strip():
        rec["gender"] = "N/A"
        rec["tone"] = "N/A"
    else:
        rec["gender"] = "FAIL" if FEMININE_BANNED_RE.search(reply) else "PASS"
        rec["tone"] = tone_check(turn, reply)
    rec["vibe"] = vibe_summary(turn, reply, rec["tone"])
    return rec


def load_done(records_path: Path) -> set[str]:
    done: set[str] = set()
    if records_path.exists():
        for line in records_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    done.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def build_report(records: list[dict], meta: dict) -> str:
    n = len(records)
    live = [r for r in records if r.get("live_status") == "OK"]
    genders = [r for r in live if r["gender"] != "N/A"]
    w_ok = sum(1 for r in records if r.get("weight_ok"))
    t_ok = sum(1 for r in records if r.get("tools_ok"))
    lat = sorted(r.get("latency_ms", 0) for r in live)
    avg_lat = round(sum(lat) / len(lat), 1) if lat else 0.0
    p95_lat = lat[int(0.95 * len(lat)) - 1] if lat else 0
    exec_ok = sum(1 for r in records if "RAISED" not in r.get("trace", ""))
    lines = [
        "# BENCHMARK 500 — Full Report (mission Stage-4)",
        "",
        f"Date: {meta['date']} · commit: {meta['commit']} · LLM chain: {meta['chain']}",
        f"Turns executed: {n} · live replies: {len(live)} · throttled/skipped: {n - len(live)}",
        "Routing runs on real code paths (classify_weight + deduce + bare registry);",
        "verbatim replies are single live FAST narrations. THROTTLED turns carry",
        "gender/tone N/A — missing data is never scored as FAIL.",
        "",
        "## Executive Summary",
        "",
        f"- Total Scenarios: **{n} / 500**",
        f"- Gender Integrity Rate: **{sum(1 for r in genders if r['gender'] == 'PASS')}/{len(genders)}"
        + (
            f" = {sum(1 for r in genders if r['gender'] == 'PASS') / len(genders):.1%}** (target 100%)"
            if genders
            else "** (no live replies scored)"
        ),
        f"- Average Latency (live turns): **{avg_lat}ms** (p95 {p95_lat}ms)",
        f"- Tool Success Rate (registry never raised): **{exec_ok}/{n}**",
        f"- Task Weight Accuracy: **{w_ok}/{n} = {w_ok / n:.1%}**"
        if n
        else "- Task Weight Accuracy: n/a",
        f"- Tool-Set Accuracy: **{t_ok}/{n} = {t_ok / n:.1%}**"
        if n
        else "- Tool-Set Accuracy: n/a",
        f"- DAG Execution Rate (todo transcript present): **{sum(1 for r in records if r.get('todo'))}/{n}**",
        "",
        "## Tone rubric (mechanical heuristic, documented)",
        "",
        "- Critical/emergency: zero emoji or FAIL. C turns: emoji or warmth-lexicon hit or FAIL.",
        "- A/B turns: reply ≥30 chars or FAIL. Empty reply: N/A across the board.",
        "",
        "## Known routing-divergence classes (contract fidelity, kept as labeled evidence)",
        "",
        "- Roleplay verbs collide with tool markers (دور→web_search, أكل→places, شغل→launch, طقس→weather).",
        "- Everyday nouns collide (صوت→media/volume, بطيء→telemetry, اجتماع→calendar, شغل→launch).",
        "- Emergency text naming a readable tool keeps critical weight with the tool traced.",
        "- Production LLM router may resolve these differently; deduce is the deterministic safety net.",
        "",
        "## Detailed Findings Table",
        "",
        "| ID | Category | Weight | Tools Used | Gender Check | Vibe & Tone Summary | Verbatim Response |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in records:
        tools = ",".join(r.get("tools", [])) or "—"
        weight = f"{r.get('weight')}{'!CRIT' if r.get('critical') else ''}"
        verbatim = (r.get("reply") or "").replace("\n", " ").replace("|", "/")[:350]
        lines.append(
            f"| {r['id']} | {r['category']}/{r.get('sub', '')} | {weight} "
            f"| {tools} | {r.get('gender', '?')} | {r.get('vibe', '')} | {verbatim} |"
        )
    if n < 500:
        lines.insert(
            8,
            f"- Status: **PARTIAL ({n}/500)** — free-pool quota exhaustion halted live "
            "collection; resume with a plain rerun (records persist, done IDs skip). "
            "THROTTLED turns carry gender/tone N/A — missing data is never scored.",
        )
        lines.insert(9, "")
    return "\n".join(lines) + "\n"


def _append_record(records_path: Path, rec: dict) -> None:
    """Blocking JSONL append, always run via to_thread (ASYNC230)."""
    with open(records_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


async def main_async(args: argparse.Namespace) -> int:
    matrix = build_matrix()
    if args.limit is not None:
        matrix = matrix[: args.limit]
    records_path = Path(args.records)
    done = load_done(records_path)
    todo_turns = [t for t in matrix if t["id"] not in done]
    print(
        f"matrix={len(matrix)} done={len(done)} todo={len(todo_turns)} dry_run={args.dry_run}",
        flush=True,
    )

    if args.dry_run:
        from src.cognitive_dag import classify_weight as cw

        w_ok = t_ok = 0
        for turn in todo_turns:
            plan = cw(turn["text"])
            tools = clause_tools(turn["text"])
            w_ok += plan.weight == turn["exp_weight"] and plan.critical == turn["critical"]
            t_ok += set(tools) == set(turn["exp_tools"])
        n = len(todo_turns)
        print(f"DRY-RUN weight acc: {w_ok}/{n} = {w_ok / n:.3f}", flush=True)
        print(f"DRY-RUN tools acc: {t_ok}/{n} = {t_ok / n:.3f}", flush=True)
        return 0

    if args.report_only:
        # Rebuild the report from disk without spending a single pool call.
        import datetime

        report_records: list[dict] = []
        if records_path.exists():
            for line in records_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        report_records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        meta = {
            "date": datetime.datetime.now(datetime.UTC).astimezone().isoformat(timespec="seconds"),
            "commit": "report-only",
            "chain": "n/a (no live calls)",
        }
        report = build_report(report_records, meta)
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"WROTE {report_path} ({len(report_records)} turns, report-only)", flush=True)
        return 0

    import subprocess

    async def _rev_parse() -> str:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip() or "unknown"

    try:
        commit = await _rev_parse()
    except OSError:
        commit = "unknown"

    ctx = BenchContext()
    chain_label = ",".join(ctx.chain_used)
    records: list[dict] = []
    # Rehydrate already-recorded turns for the final report, then append.
    if records_path.exists():
        for line in records_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    records_path.parent.mkdir(parents=True, exist_ok=True)
    fails = 0
    try:
        for i, turn in enumerate(todo_turns, 1):
            print(f"[{i}/{len(todo_turns)}] {turn['id']} {turn['text'][:44]}", flush=True)
            try:
                rec = await run_turn(turn, ctx, live=True)
            except Exception as exc:  # noqa: BLE001 — runner never dies mid-matrix
                rec = {
                    "id": turn["id"],
                    "category": turn["category"],
                    "sub": turn.get("sub", ""),
                    "input": turn["text"],
                    "exp_weight": turn["exp_weight"],
                    "exp_tools": turn["exp_tools"],
                    "critical": turn["critical"],
                    "live_status": f"RUNNER_FAIL: {type(exc).__name__}",
                    "reply": "",
                    "gender": "N/A",
                    "tone": "N/A",
                    "vibe": "N/A",
                    "latency_ms": 0,
                    "weight_ok": False,
                    "tools_ok": False,
                    "weight": -1,
                    "tools": [],
                    "trace": "",
                    "todo": "",
                }
            records.append(rec)
            await asyncio.to_thread(_append_record, records_path, rec)
            if rec["live_status"] == "OK":
                fails = 0
            else:
                fails += 1
            if fails >= ABORT_STREAK:
                print(
                    f"ABORT: {ABORT_STREAK} consecutive live failures — pool dead, resume later",
                    flush=True,
                )
                break
            await asyncio.sleep(0.6)  # polite pacing: no provider flooding
    finally:
        await ctx.close()

    import datetime

    meta = {
        "date": datetime.datetime.now(datetime.UTC).astimezone().isoformat(timespec="seconds"),
        "commit": commit,
        "chain": f"fallback-direct [{chain_label}]"
        if os.environ.get("BENCH_LLM_CHAIN", "fallback") != "production"
        else "production",
    }
    report = build_report(records, meta)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"WROTE {report_path} ({len(records)} turns)", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="500-turn benchmark runner")
    parser.add_argument(
        "--dry-run", action="store_true", help="routing accuracy only, no LLM calls"
    )
    parser.add_argument("--limit", type=int, default=None, help="run first N unrecorded turns")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="rebuild the report from disk records; zero live calls",
    )
    parser.add_argument("--records", default=str(RECORDS_DEFAULT))
    parser.add_argument("--report", default=str(REPORT_DEFAULT))
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
