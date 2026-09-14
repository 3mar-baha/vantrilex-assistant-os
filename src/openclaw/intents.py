"""OpenClaw intent definitions (Phase 2): the four tool specs.

Router-prompt lines, keyword-net candidate patterns, and representative
samples live here — NOT yet wired into the dispatcher (Phase 3 insertion,
with live collision review against the existing net). Each entry carries
(samples) that must match and the patterns must be compilable; the
collision test in test_openclaw_core.py guards the existing tools.

Pattern scoping rule: OpenClaw owns EXPLICIT computer-operation phrasing
(move/click/type in a window, drive the browser, fetch a page body).
Bare topic words stay with their current owners (screenshot, read_page,
launch, close) — the Phase-3 insertion review re-checks every line.
"""

from __future__ import annotations

from typing import Final

VALID_OPENCLAW_TOOLS: Final[tuple[str, ...]] = (
    "openclaw_browse",
    "openclaw_desktop",
    "openclaw_fetch",
    "openclaw_inspect",
)

# Router-prompt fragments (Phase-3 insertion into _ROUTER_PROMPT_AR).
ROUTER_TOOL_LINES: Final[dict[str, str]] = {
    "openclaw_browse": (
        "openclaw_browse=تشغيل المتصفح والتفاعل مع صفحة ويب (نقر/تعبئة/تنقل) "
        'مع وصف المهمة في "arg"، '
    ),
    "openclaw_desktop": (
        'openclaw_desktop=تحريك/نقر/كتابة داخل نافذة على سطح المكتب مع الخطوة في "arg"، '
    ),
    "openclaw_fetch": (
        'openclaw_fetch=جلب نص صفحة ويب قراءةً فقط بدون فتح المتصفح مع الرابط في "arg"، '
    ),
    "openclaw_inspect": (
        'openclaw_inspect=فحص عناصر النافذة/الشاشة الحالية (شجرة الوصول) مع المطلوب في "arg"، '
    ),
}

# (tool, regex, representative samples that MUST match).
INTENT_PATTERNS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    (
        "openclaw_browse",
        (
            r"(?:حرّكي?|حركي?|انقري?|اكبسي?)\s+(?:الماوس\s+)?(?:على\s+|فوق\s+)?"
            r"(?:زر|رابط|خانة|قائمة)\s+.+"
        ),
        (
            "حرّكي الماوس على زر الإرسال",
            "انقري على رابط التحميل",
            "اكبسي على خانة البحث",
        ),
    ),
    (
        "openclaw_desktop",
        (
            r"(?:اكتبي?|اكتب)\s+(?:بالنافذة|في النافذة|بالحقل)\s+.+"
            r"|(?:افتحي?|افتح)\s+(?:قائمة ابدأ|مدير المهام بالنافذة)\b.+"
        ),
        (
            "اكتبي بالنافذة التقرير النهائي",
            "اكتبي بالحقل الاسم الكامل",
            "افتحي قائمة ابدأ من الكيبورد",
        ),
    ),
    (
        "openclaw_fetch",
        (
            r"(?:اجلبي?|اجلب|استخرجي?|اسحبي?)\s+(?:محتوى|نص|متن)\s+(?:الصفحة|الموقع|الرابط)\s*"
            r"(https?://\S+)?"
        ),
        (
            "اجلبي محتوى الصفحة https://example.com/x",
            "استخرجي نص الموقع https://example.com",
            "اسحبي متن الرابط https://example.com/y",
        ),
    ),
    (
        "openclaw_inspect",
        r"(?:افحصي?|افحص|اعرضي?|اعرض)\s+(?:عناصر|مكونات|شجرة)\s+(?:النافذة|الشاشة|الصفحة)",
        (
            "افحصي عناصر النافذة",
            "اعرضي مكونات الشاشة",
            "افحص شجرة الصفحة",
        ),
    ),
)
