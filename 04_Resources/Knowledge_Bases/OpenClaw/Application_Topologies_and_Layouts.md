---
title: Application Topologies and Layouts
aliases: [نافذة, نوافذ, window layout, application layout, خريطة التطبيق, خريطة الواجهة, واجهة, landmarks, معالم الواجهة, UI map, شريط المهام, taskbar, الشريط الجانبي, sidebar, شريط العناوين, address bar, omnibox, activity bar, شريط الحالة, status bar, لوحة الأوامر, علامات التبويب, tab strip]
tags: [openclaw, ui-topology, windows, accessibility, landmarks]
date: 2026-09-14
type: knowledge-base
summary: Structural maps of common Windows app windows — stable navigation landmarks for the planner before any pixel-level action.
---

# Application Topologies & Layouts — Landmark Maps

**Doctrine: landmarks before pixels.** Every automation goal resolves against
these structural maps first. A landmark (named region with a stable access
path) beats a coordinate; coordinates rot, landmarks persist across themes,
scaling, and window sizes.

## 1. Windows shell

- **شريط المهام**: زر ابدأ يساراً (أو وسطاً حسب المحاذاة)، التطبيقات المثبتة،
  صينية النظام يميناً (الساعة، الشبكة، الصوت، البطارية) — زر السهم يكشف
  الأيقونات المخفية.
- **مستكشف الملفات**: جزء التنقل يساراً (وصول سريع، هذا الجهاز)، المحتوى
  وسطاً، شريط الأوامر أعلى (جديد، قص، نسخ، لصق، إعادة تسمية)، شريط البحث
  يميناً، شريط الحالة أسفلاً (عدد العناصر).
- **الإعدادات**: بحث أعلى، فئات يساراً (النظام، البلوتوث، الشبكة، الحسابات)،
  التفاصيل يميناً — البحث أسرع من التصفح اليدوي دائماً.

## 2. Google Chrome

- **علامات التبويب** أعلى (الشريط) — زر `+` للجديد، `x` للإغلاق، النقر
  الأوسط يغلق.
- **شريط العناوين (omnibox)** تحت التبويبات: بحث + تنقل + لصق روابط —
  المدخل الأول لأي مهمة ويب.
- **شريط المفضلة** (اختياري الظهور)، أزرار الإضافات يمين العناوين، ملف
  المستخدم (الصورة) أقصى اليمين، قائمة النقاط الثلاث للإعدادات.
- **أدوات المطور**: لوحات Elements / Console / Network — الكونسول يكشف
  أخطاء الصفحة الحية.

## 3. VS Code

- **activity bar** أقصى اليسار: المستكشف، البحث، المصدر، التشغيل، الإضافات.
- **الشريط الجانبي** بجانبه يعرض محتوى الأيقونة المختارة.
- **مجموعات المحرر** وسطاً (تقسيم يمين/أسفل)، **اللوحة** أسفلاً (الطرفية،
  المشاكل، الإخراج)، **شريط الحالة** بالأسفل (الفرع، الأخطاء، اللغة).
- **لوحة الأوامر** (`Ctrl+Shift+P`) تتجاوز كل التنقل البصري — أمر واحد
  بدل خمس نقرات.

## 4. Windows Terminal / Task Manager

- **Terminal**: التبويبات أعلى، السهم للملفات الشخصية (PowerShell / CMD)،
  تقسيم الأجزاء (`Alt+Shift+D`)، البحث (`Ctrl+Shift+F`).
- **إدارة المهام**: تبويبات العمليات/الأداء/سجل التطبيقات، بحث أعلى
  العمليات، زر «إنهاء المهمة» يمين — للتشخيص قبل أي إغلاق قسري.

## 5. Dialog anatomy (read-only map)

- شريط العنوان يسمّي القرار · النص يشرح العواقب · الأزرار مرتبة:
  الإجراء الرئيسي، البديل، الإلغاء · `Enter` = الافتراضي، `Esc` = التراجع.
  (قواعد التعامل نفسها في `Popups_and_Interrupt_Recovery.md`.)

## 6. Planner rules

1. Name the landmark chain explicitly in the plan
   (e.g. «Chrome → omnibox → type → Enter») — no bare coordinates.
2. Prefer universal entries (search boxes, command palettes) over menu dives.
3. If a landmark is missing (custom skin, collapsed bar), expand via its
   hotkey (`Ctrl+B` للشريط الجانبي) before escalating to vision.
