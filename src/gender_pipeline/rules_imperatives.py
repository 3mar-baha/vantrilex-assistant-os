"""Stage 1 — imperatives & prohibitions (addressee = Omar, masculine).

Bare (source, target) pairs; engine.py wraps each in word boundaries and
applies longest-first. Deliberate identity entries are documented, not bugs:

- احكيلي -> احكيلي: undiacritized masculine/feminine identical — no-op kept
  as auditable intent (never corrupts).
- هدي -> هدي: same — masculine هدّي renders identically undiacritized.
- وديلي: OMITTED (mandate listed وديلي->ودلي, but dropping the ي corrupts;
  undiacritized masculine renders وديلي anyway, so any rewrite is wrong).
"""

from __future__ import annotations

from typing import Final

RULES: Final[tuple[tuple[str, str], ...]] = (
    # Inquiries & informing.
    ("خبريني", "خبرني"),
    ("أخبريني", "أخبرني"),
    ("وخبريني", "وخبرني"),  # glued و full-token form (never strip و blindly)
    ("طمنيني", "طمني"),
    ("وطمنيني", "وطمنني"),
    ("أطمنيني", "أطمنني"),
    ("احكيلي", "احكيلي"),  # identity: spellings coincide undiacritized
    ("قوليلي", "قلي"),
    ("قولي", "قلي"),
    ("قولّي", "قلّي"),
    ("وضحيلي", "وضحلي"),
    ("عرفيني", "عرفني"),
    # Perception & attention.
    ("شوفي", "شوف"),
    ("اسمعي", "اسمع"),
    ("انتبهي", "انتبه"),
    ("لاحظي", "لاحظ"),
    ("تأكدي", "تأكد"),
    # Action & requests.
    ("ساعديني", "ساعدني"),
    ("ابعتيلي", "ابعتلي"),
    ("اعطيني", "اعطني"),
    ("فرغيني", "فرغني"),
    # Wellbeing & pace.
    ("روقي", "روق"),
    ("هدي", "هدي"),  # identity: spellings coincide undiacritized
    ("ارتاحي", "ارتاح"),
    ("نامي", "نام"),
    ("خدي", "خذ"),
    ("اشربي", "اشرب"),
    ("جهزي", "جهز"),
    ("شيكي", "شيك"),
    # Negative imperatives (exact phrases; longest-match wins in engine).
    ("لا تشيلي هم", "لا تشيل هم"),
    ("لا تغلبي حالك", "لا تغلب حالك"),
    ("لا تقلقي", "لا تقلق"),
    ("لا تخافي", "لا تخاف"),
    ("لا تترددي", "لا تتردد"),
    ("لا تتسرعي", "لا تتسرع"),
    ("لا تنسي", "لا تنسى"),
)
