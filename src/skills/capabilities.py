"""First-class autonomous tool capabilities (2026-09-12 Principles-over-Rules).

Each entry lets Sara DISCOVER tools by human goal — not by keyword trigger:
goal prose (what the owner achieves), concept markers (scoring seeds shared
with `src/cognition.py`), reversibility (irreversible actions need the
clarification gate), backend needs (honest offline lines when unmet), and
chaining affinities (which tools combine into multi-step plans).

Zero src imports — `src/cognition.py` merges these markers into its scoring.
"""

from __future__ import annotations

from typing import Final

# needs: bridge (PC daemon) | google (Workspace OAuth) | network (public web)
#        | vault (Obsidian client) | local (on-box only) | none (pure chat skill)
_CAPABILITIES: Final[dict[str, dict]] = {
    "multi_task": {
        "goals": "تنفيذ عدة طلبات مختلفة برسالة واحدة",
        "markers": ("و بعدين", "ثم", "كمان", "بعدها"),
        "reversible": True,
        "needs": "none",
        "chains_with": ("launch", "close", "schedule", "volume"),
    },
    "gmail": {
        "goals": "معرفة البريد الوارد والرسائل الجديدة",
        "markers": ("جيميل", "بريد", "ايميل", "إيميل", "رسائل", "inbox", "mail"),
        "reversible": True,
        "needs": "google",
        "chains_with": ("brief", "tasks", "schedule"),
    },
    "calendar": {
        "goals": "معرفة المواعيد والالتزامات القادمة",
        "markers": ("موعد", "مواعيد", "تقويم", "اجتماع", "calendar"),
        "reversible": True,
        "needs": "google",
        "chains_with": ("create_event", "brief", "list_reminders"),
    },
    "tasks": {
        "goals": "معرفة المهام المستحقة",
        "markers": ("مهام", "مهمة", "مستحق", "tasks", "todo"),
        "reversible": True,
        "needs": "google",
        "chains_with": ("create_task", "schedule", "list_reminders"),
    },
    "telemetry": {
        "goals": "معرفة حالة الجهاز (معالج/رام/أقراص)",
        "markers": ("جهاز", "رام", "معالج", "بطيء", "حالة", "telemetry", "cpu"),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("running_apps", "app_sessions", "network_status"),
    },
    "launch": {
        "goals": "فتح برنامج على جهاز المالك",
        "markers": ("افتح", "شغل", "شغ", "launch", "open", "start"),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("whitelist_apps", "running_apps", "close"),
    },
    "close": {
        "goals": "إيقاف برنامج شغال على الجهاز",
        "markers": ("سكر", "اغلق", "أغلق", "اطف", "وقف", "قفل", "close", "kill"),
        "reversible": False,
        "needs": "bridge",
        "chains_with": ("running_apps", "telemetry"),
    },
    "screenshot": {
        "goals": "رؤية ما على الشاشة الآن",
        "markers": ("شاشة", "لقطة", "سكرين", "صوري", "screenshot"),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("screen_ocr", "telemetry"),
    },
    "screen_ocr": {
        "goals": "قراءة النص/الكود الظاهر على الشاشة",
        "markers": (
            "اقرأ",
            "اقرئيلي",
            "اقرأي",
            "استخرج",
            "استخرجيلي",
            "كود",
            "نص الشاشة",
            "النص الظاهر",
            "ocr",
        ),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("screenshot", "telemetry"),
    },
    "volume": {
        "goals": "التحكم بصوت الجهاز — أي صياغة لرفع الصوت أو تخفيضه أو كتمه أو مستواه",
        "markers": (
            "صوت",
            "اكتم",
            "كتم",
            "ارفع",
            "وطي",
            "علي الصوت",
            "نصي الصوت",
            "الصوت عالي",
            "الصوت واطي",
            "mute",
            "volume",
        ),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("media",),
    },
    "media": {
        "goals": "تشغيل مقطع صوتي أو مرئي — أي صياغة لطلب أغنية أو موسيقى أو فيديو",
        "markers": (
            "فيديو",
            "اغنية",
            "أغنية",
            "شغلي",
            "موسيقى",
            "سبوتيفاي",
            "مقطع",
            "تشغيل",
            "media",
        ),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("volume",),
    },
    "schedule": {
        "goals": "عدم نسيان التزام مستقبلي (تذكير حقيقي بوقته)",
        "markers": ("ذكر", "نبه", "تذكير", "مهمة جديدة", "سجلي مهمة", "remind", "schedule"),
        "reversible": True,
        "needs": "local",
        "chains_with": ("create_task", "list_reminders", "calendar"),
    },
    "list_reminders": {
        "goals": "عرض التذكيرات المسجلة",
        "markers": ("تذكيراتي", "تذكيرات", "التذكيرات", "مسجلة", "المسجلة", "قائمة", "reminders"),
        "reversible": True,
        "needs": "local",
        "chains_with": ("cancel_reminder", "schedule"),
    },
    "cancel_reminder": {
        "goals": "إلغاء تذكير مسجل",
        "markers": ("الغي", "امسح", "شيلي التذكير", "cancel"),
        "reversible": False,
        "needs": "local",
        "chains_with": ("list_reminders",),
    },
    "weather": {
        "goals": "معرفة طقس مدينة",
        "markers": ("طقس", "حرارة", "weather"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("brief", "web_search"),
    },
    "web_search": {
        "goals": "بحث حي بالإنترنت بمصادر",
        "markers": ("بالنت", "في النت", "ابحث", "دور", "search"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("deep_search", "read_page"),
    },
    "youtube": {
        "goals": "بحث فيديوهات يوتيوب",
        "markers": ("يوتيوب", "youtube"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("web_search",),
    },
    "read_page": {
        "goals": "قراءة/تلخيص رابط أو مقال",
        "markers": ("رابط", "مقال", "صفحة", "لخص", "http"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("web_search", "deep_search"),
    },
    "prayer_times": {
        "goals": "معرفة مواقيت الصلاة/الأذان",
        "markers": ("صلاة", "اذان", "أذان", "مواقيت", "prayer"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("brief",),
    },
    "crypto_price": {
        "goals": "معرفة أسعار العملات الرقمية",
        "markers": ("بيتكوين", "اثيريوم", "كريبتو", "crypto"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("convert_currency",),
    },
    "convert_currency": {
        "goals": "تحويل/معرفة أسعار العملات",
        "markers": ("دولار", "يورو", "دينار", "حول", "currency"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("crypto_price",),
    },
    "file_fetch": {
        "goals": "إرسال ملف من الجهاز للهاتف",
        "markers": ("ملف", "ابعثيلي ملف", "ارسلي ملف", "file"),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("drive",),
    },
    "create_folder": {
        "goals": "إنشاء مجلد جديد بالخزينة",
        "markers": ("فولدر", "مجلد", "folder"),
        "reversible": True,
        "needs": "vault",
        "chains_with": ("knowledge_graph",),
    },
    "knowledge_graph": {
        "goals": "استكشاف شبكة المعرفة والروابط بين المذكرات",
        "markers": ("شبكة المعرفة", "مين بيحكي", "روابط", "graph"),
        "reversible": True,
        "needs": "vault",
        "chains_with": ("create_folder",),
    },
    "running_apps": {
        "goals": "معرفة التطبيقات الشغالة الآن",
        "markers": ("مفتوح", "شغال", "التطبيقات", "running"),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("telemetry", "close", "launch"),
    },
    "whitelist_apps": {
        "goals": "معرفة البرامج المعتمدة بقائمة سارة",
        "markers": ("مسموح", "معتمد", "قائمة", "صلاحية", "whitelist"),
        "reversible": True,
        "needs": "local",
        "chains_with": ("launch", "running_apps"),
    },
    "brief": {
        "goals": "الإحاطة اليومية الشاملة",
        "markers": ("إحاطة", "احاطة", "نشرة", "brief"),
        "reversible": True,
        "needs": "none",
        "chains_with": ("calendar", "tasks", "gmail", "weather"),
    },
    "app_sessions": {
        "goals": "تقرير استخدام البرامج اليوم بالدقائق",
        "markers": ("استخدمت", "جلسات", "استخدام البرامج", "sessions"),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("telemetry", "running_apps"),
    },
    "drive": {
        "goals": "البحث في ملفات غوغل درايف",
        "markers": ("درايف", "drive"),
        "reversible": True,
        "needs": "google",
        "chains_with": ("file_fetch",),
    },
    "contacts": {
        "goals": "معرفة جهات الاتصال",
        "markers": ("جهات الاتصال", "معلوماتي", "contacts"),
        "reversible": True,
        "needs": "google",
        "chains_with": (),
    },
    "create_event": {
        "goals": "تسجيل موعد جديد بالتقويم",
        "markers": ("سجلي موعد", "ضيفي اجتماع", "create event"),
        "reversible": False,
        "needs": "google",
        "chains_with": ("calendar", "schedule"),
    },
    "create_task": {
        "goals": "تسجيل مهمة جديدة",
        "markers": ("ضيفي مهمة", "مهمة جديدة", "create task"),
        "reversible": False,
        "needs": "google",
        "chains_with": ("tasks", "schedule"),
    },
    "places": {
        "goals": "اقتراح أماكن (كافيه/مطعم/دراسة)",
        "markers": ("كافيه", "مطعم", "اماكن", "places"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("web_search",),
    },
    "deep_search": {
        "goals": "بحث متقدم متعدد المصادر",
        "markers": ("بجوجل", "بحث متقدم", "deep search"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("web_search", "read_page"),
    },
    "fitness": {
        "goals": "معرفة النشاط الرياضي (خطوات/سعرات)",
        "markers": ("مشيت", "خطوات", "سعرات", "fitness"),
        "reversible": True,
        "needs": "google",
        "chains_with": (),
    },
    "network_status": {
        "goals": "معرفة حالة الشبكة وعنوان IP",
        "markers": ("ايبي", "شبكة", "ip", "network"),
        "reversible": True,
        "needs": "bridge",
        "chains_with": ("telemetry",),
    },
    "tech_trending": {
        "goals": "معرفة أخبار التقنية",
        "markers": ("اخبار التقنية", "أخبار التكنولوجيا", "tech news"),
        "reversible": True,
        "needs": "network",
        "chains_with": ("web_search", "deep_search"),
    },
}

TOOL_CAPABILITIES: Final[dict[str, dict]] = dict(_CAPABILITIES)

# Tools whose backend NEEDS map (for honest-offline narration + chaining plans).
IRREVERSIBLE_TOOLS: Final[frozenset[str]] = frozenset(
    tool for tool, cap in TOOL_CAPABILITIES.items() if not cap["reversible"]
)


def markers_for(tool: str) -> tuple[str, ...]:
    return tuple(TOOL_CAPABILITIES.get(tool, {}).get("markers", ()))


def chains_for(tool: str) -> tuple[str, ...]:
    return tuple(TOOL_CAPABILITIES.get(tool, {}).get("chains_with", ()))
