"""Stage 3 — clitics, pronouns, vocatives, participles (addressee = Omar).

All keys are unambiguous 2nd-person-feminine markers: 3rd-person feminine
uses ها-forms (فيها، إلها، معها), so these patterns can NEVER match
third-party references. Undiacritized masculine spellings (فيك، إلك، معك)
are left untouched — conservative by construction.

Section E (mandate): vocatives + participle anchors live here — everything
in this file marks the ADDRESSEE, which is the single organizing principle.
"""

from __future__ import annotations

from typing import Final

RULES: Final[tuple[tuple[str, str], ...]] = (
    # 2nd-person feminine clitics -> masculine (diacritic + dialectal forms).
    ("فيكي", "فيك"),
    ("فيكِ", "فيك"),
    ("إلكِ", "إلك"),
    ("لكِ", "لك"),  # bare form with explicit kasra (undiacritized لك is masculine: untouched)
    ("لكي", "إلك"),
    ("معكي", "معك"),
    ("معكِ", "معك"),
    ("عندكي", "عندك"),
    ("عندكِ", "عندك"),
    ("عليكي", "عليك"),
    ("عليكِ", "عليك"),
    ("منكي", "منك"),
    ("منكِ", "منك"),
    ("يزيدكِ", "يزيدك"),  # verb-attached 2nd-fem object suffix (attested C082)
    ("ويزيدكِ", "ويزيدك"),
    ("بيكي", "بيك"),
    ("بيكِ", "بيك"),
    ("إنتي", "إنتَ"),
    ("إنتِ", "إنتَ"),
    # E. Vocatives & endearments -> masculine (longest-match wins in engine).
    ("يا عزيزتي", "يا عزيزي"),
    ("عزيزتي", "عزيزي"),
    ("يا غالية", "يا غالي"),
    ("غالية", "غالي"),
    ("يا شاطرة", "يا شاطر"),
    ("شاطرة", "شاطر"),
    ("يا حبيبتي", "يا حبيبي"),
    ("حبيبتي", "حبيبي"),
)

# E. 2nd-person adjective indicators: (feminine anchor, masculine anchor) +
# closed feminine->masculine adjective map. Anchors convert too (تكوني فايقة
# -> تكون فايق, never a mixed half-fix). Never blind ة-stripping: feminine
# NOUNS like مدرسة must survive untouched.
PARTICIPLE_ANCHORS: Final[tuple[tuple[str, str], ...]] = (
    ("شكلك", "شكلك"),
    ("حاسك", "حاسك"),
    ("باينك", "باينك"),
    ("شايفك", "شايفك"),
    ("إنت", "إنت"),
    ("تكوني", "تكون"),
    ("تصيري", "تصير"),
)

FEM_ADJ: Final[tuple[tuple[str, str], ...]] = (
    ("تعبانة", "تعبان"),
    ("نعسانة", "نعسان"),
    ("مبسوطة", "مبسوط"),
    ("مضغوطة", "مضغوط"),
    ("زعلانة", "زعلان"),
    ("فايقة", "فايق"),
    ("متضايقة", "متضايق"),
    ("مرتاحة", "مرتاح"),
)

# Standalone feminine predicates with no masculine-identical spelling.
# (حابة lives in rules_verbs.REGEX_RULES instead: bare حابة can be Sara's
# own 1st-person voice ("كنت حابة"), so it converts only inside إذا/لو/شو
# frames. This table stays empty as the named stage slot.)
STANDALONE_ADJ: Final[tuple[tuple[str, str], ...]] = ()
