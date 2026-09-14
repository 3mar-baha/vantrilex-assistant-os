---
title: Keyboard Shortcuts and Accelerators
aliases: [اختصار, اختصارات, اختصارات الكيبورد, hotkey, hotkeys, keyboard shortcut, keyboard shortcuts, لوحة المفاتيح, كيبورد, نقر الماوس, mouse click, زر الويندوز, win key, اختصارات الكروم, اختصارات الفيجوال, chrome shortcuts, vscode shortcuts, terminal shortcuts, Ctrl, Alt+Shift]
tags: [openclaw, hotkeys, keyboard, windows, productivity]
date: 2026-09-14
type: knowledge-base
summary: High-frequency hotkeys for Windows, Chrome, VS Code, and Terminal. Doctrine — hotkeys always precede mouse clicks (T0 action tier).
---

# Keyboard Shortcuts & Accelerators — T0 Action Doctrine

**Doctrine: hotkeys always precede mouse clicks.** A hotkey is deterministic,
instant (~0ms), needs no perception pass, and never mis-clicks. The OpenClaw
planner must attempt a hotkey mapping FIRST for every goal; mouse/UI-tree
action is the fallback, never the default. (Clicking is what you do when no
hotkey exists — «نقر الماوس» is the slow path.)

## 1. Windows shell

- `Win+E` مستكشف الملفات · `Win+D` سطح المكتب · `Win+L` قفل الجهاز ·
  `Win+Tab` عرض المهام · `Win+arrows` تثبيت النوافذ يمين/يسار/تكبير ·
  `Alt+Tab` التنقل بين النوافذ · `Win+V` سجل الحافظة ·
  `Win+Shift+S` أداة القص · `Ctrl+Shift+Esc` إدارة المهام مباشرة ·
  `Win+R` تشغيل · `Win+I` الإعدادات · `Win+.` لوحة الإيموجي ·
  `Alt+F4` إغلاق النافذة الحالية · `F2` إعادة تسمية · `Ctrl+Shift+N` مجلد جديد.

## 2. Google Chrome

- `Ctrl+L` أو `F6` شريط العناوين (أهم اختصار للتصفح الآلي) ·
  `Ctrl+T` تبويب جديد · `Ctrl+W` إغلاق التبويب · `Ctrl+Shift+T` استعادة
  المغلق · `Ctrl+Tab` / `Ctrl+Shift+Tab` التنقل بين التبويبات ·
  `Ctrl+F` بحث بالصفحة · `Ctrl+D` حفظ بالمفضلة · `Ctrl+Shift+B` إظهار شريط
  المفضلة · `F12` أو `Ctrl+Shift+I` أدوات المطور · `Ctrl+Shift+Del` مسح
  البيانات · `Alt+Left` رجوع · `Ctrl+R` تحديث.

## 3. VS Code

- `Ctrl+P` فتح سريع لأي ملف · `Ctrl+Shift+P` لوحة الأوامر (المدخل الشامل) ·
  `Ctrl+`` الطرفية المدمجة · `Ctrl+/` تعليق سطر · `Ctrl+D` تحديد التالي
  المطابق (مؤشرات متعددة) · `Alt+Up/Down` تحريك السطر ·
  `Ctrl+Shift+E` المستكشف · `Ctrl+Shift+F` بحث شامل · `Ctrl+Shift+G` المصدر ·
  `F2` إعادة تسمية الرمز · `Ctrl+B` إخفاء الشريط الجانبي ·
  `Ctrl+K Ctrl+S` محرر الاختصارات نفسه.

## 4. Terminal / PowerShell

- `Ctrl+C` كسر الأمر الحالي · `Tab` إكمال تلقائي · `Ctrl+L` مسح الشاشة ·
  `F7` سجل الأوامر كنافذة اختيار · `Ctrl+Left/Right` قفز بين الكلمات ·
  `Ctrl+R` بحث عكسي بالسجل (PSReadLine) · `Up/Down` تصفح السجل ·
  `Ctrl+D` خروج من الجلسة.

## 5. Git accelerators (CLI shorthand, same spirit)

- `git st` الحالة · `git co` تبديل · `git br` الفروع · `git ci` تثبيت ·
  `git add -p` مراجعة جزئية تفاعلية · `git stash` / `git stash pop` ·
  `git log --oneline --graph -15` · `git diff --stat` قبل أي تثبيت.

## 6. Planner rules

1. Goal → hotkey table lookup before any perception call.
2. Multi-step flows compose hotkeys (`Ctrl+L`, type, `Enter`) — no pixels.
3. Unknown app? `Alt` reveals menu accelerators; `F6`/`Tab` cycles landmarks.
4. A hotkey that mutates (e.g. `Ctrl+S` overwrite, `Alt+F4` on dirty buffer)
   inherits the target's reversibility class — speed never skips the Breaker.
