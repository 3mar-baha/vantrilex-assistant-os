"""Tier 1 — gender pipeline exhaustive contracts (mission: kill mid-turn drift).

Hermetic, zero network. Three layers: (1) every rule-table entry fires on a
bare probe; (2) the 8 historical benchmark failures convert to exact pinned
outputs AND scan clean under the benchmark's banned-form regex; (3) Sara's
own feminine voice + deliberate omissions + engine totality are locked.
"""

import pytest

from scripts.benchmark_500 import FEMININE_BANNED_RE
from src.gender_pipeline import normalize_masculine_address as norm
from src.gender_pipeline.rules_clitics import RULES as CLITIC_RULES
from src.gender_pipeline.rules_imperatives import RULES as IMP_RULES
from src.gender_pipeline.rules_verbs import RULES as VERB_RULES


def _clean(text: str) -> None:
    assert not FEMININE_BANNED_RE.search(text), f"banned form survives in {text!r}"


# -- 1. every rule-table entry fires ---------------------------------------

IMP_PROBES = [
    ("خبريني", "خبرني"),
    ("طمنيني", "طمني"),
    ("قوليلي", "قلي"),
    ("قولي", "قلي"),
    ("قولّي", "قلّي"),
    ("وضحيلي", "وضحلي"),
    ("عرفيني", "عرفني"),
    ("شوفي", "شوف"),
    ("اسمعي", "اسمع"),
    ("انتبهي", "انتبه"),
    ("لاحظي", "لاحظ"),
    ("تأكدي", "تأكد"),
    ("ساعديني", "ساعدني"),
    ("ابعتيلي", "ابعتلي"),
    ("اعطيني", "اعطني"),
    ("فرغيني", "فرغني"),
    ("روقي", "روق"),
    ("ارتاحي", "ارتاح"),
    ("نامي", "نام"),
    ("خدي", "خذ"),
    ("اشربي", "اشرب"),
    ("جهزي", "جهز"),
    ("شيكي", "شيك"),
    ("لا تقلقي", "لا تقلق"),
    ("لا تخافي", "لا تخاف"),
    ("لا تترددي", "لا تتردد"),
    ("لا تشيلي هم", "لا تشيل هم"),
    ("لا تتسرعي", "لا تتسرع"),
    ("لا تنسي", "لا تنسى"),
    ("لا تغلبي حالك", "لا تغلب حالك"),
    ("وخبريني", "وخبرني"),
    ("وطمنيني", "وطمنني"),
    ("أخبريني", "أخبرني"),
    ("أطمنيني", "أطمنني"),
    # Documented identity no-ops (undiacritized masculine renders the same).
    ("احكيلي", "احكيلي"),
    ("هدي", "هدي"),
]

VERB_PROBES = [
    ("بتحبي", "بتحب"),
    ("بتريدي", "بتريد"),
    ("بتقدري", "بتقدر"),
    ("تقدري", "تقدر"),
    ("وتقدري", "وتقدر"),
    ("بتعرفي", "بتعرف"),
    ("تعرفي", "تعرف"),
    ("بتشوفي", "بتشوف"),
    ("تشوفي", "تشوف"),
    ("بتفكري", "بتفكر"),
    ("تفكري", "تفكر"),
    ("بتعملي", "بتعمل"),
    ("تعملي", "تعمل"),
    ("بتسمعي", "بتسمع"),
    ("تسمعي", "تسمع"),
    ("ترتاحي", "ترتاح"),
    ("تنامي", "تنام"),
    ("تاكلي", "تاكل"),
    ("تشتغلي", "تشتغل"),
    ("تروحي", "تروح"),
    ("تكملي", "تكمل"),
    ("تكملّي", "تكمل"),
    ("تهدئي", "اهدا"),
    ("تنفسي", "تنفس"),
    ("تنفّسي", "تنفس"),
    ("احتجتي", "احتجت"),
    ("حفظتي", "حفظت"),
    ("حفظتيه", "حفظته"),
]

CLITIC_PROBES = [
    ("فيكي", "فيك"),
    ("فيكِ", "فيك"),
    ("إلكِ", "إلك"),
    ("لكِ", "لك"),
    ("لكي", "إلك"),
    ("معكي", "معك"),
    ("معكِ", "معك"),
    ("عندكي", "عندك"),
    ("عندكِ", "عندك"),
    ("عليكي", "عليك"),
    ("عليكِ", "عليك"),
    ("منكي", "منك"),
    ("منكِ", "منك"),
    ("بيكي", "بيك"),
    ("بيكِ", "بيك"),
    ("إنتي", "إنتَ"),
    ("إنتِ", "إنتَ"),
    ("يزيدكِ", "يزيدك"),
    ("ويزيدكِ", "ويزيدك"),
    ("يا عزيزتي", "يا عزيزي"),
    ("عزيزتي", "عزيزي"),
    ("يا غالية", "يا غالي"),
    ("غالية", "غالي"),
    ("يا شاطرة", "يا شاطر"),
    ("شاطرة", "شاطر"),
    ("يا حبيبتي", "يا حبيبي"),
    ("حبيبتي", "حبيبي"),
    ("شكلك تعبانة", "شكلك تعبان"),
    ("تكوني فايقة", "تكون فايق"),
    ("إنت زعلانة", "إنت زعلان"),
]


@pytest.mark.parametrize("src,dst", IMP_PROBES)
def test_imperatives_fire(src, dst):
    assert norm(f"لو سمحت {src} بسرعة") == f"لو سمحت {dst} بسرعة"


@pytest.mark.parametrize("src,dst", VERB_PROBES)
def test_verbs_fire(src, dst):
    assert norm(f"لو سمحت {src} بسرعة") == f"لو سمحت {dst} بسرعة"


@pytest.mark.parametrize("src,dst", CLITIC_PROBES)
def test_clitics_vocatives_participles_fire(src, dst):
    assert norm(f"لو سمحت {src} بسرعة") == f"لو سمحت {dst} بسرعة"


def test_rule_tables_covered_by_probes():
    """Every declared rule has at least one probe above (no dead entries)."""
    probed = {s for s, _ in IMP_PROBES + VERB_PROBES + CLITIC_PROBES}
    for name, table in (("imp", IMP_RULES), ("verb", VERB_RULES), ("clitic", CLITIC_RULES)):
        missing = [s for s, _ in table if s not in probed]
        assert not missing, f"{name} rules without probes: {missing}"


# -- 2. the 8 historical benchmark failures ----------------------------------

HISTORICAL = {
    "A133": (
        "خبرني شو صاير مع الـproduction، وأنا رح أشوف حل سريع. طمنيني إذا احتجت أي شي إضافي.",
        "خبرني شو صاير مع الـproduction، وأنا رح أشوف حل سريع. طمني إذا احتجت أي شي إضافي.",
    ),
    "A162": (
        "خبرني شو اللي صاير، وأنا رح أشوف لك حل بأسرع وقت. طمنيني إذا في شي تاني بقدر أساعدك فيه.",
        "خبرني شو اللي صاير، وأنا رح أشوف لك حل بأسرع وقت. طمني إذا في شي تاني بقدر أساعدك فيه.",
    ),
    "C005": (
        (
            "يا عزيزتي، خدي شوية قسط من الراحة عشان الصبح تكوني فايقة وتقدري تكملي التسليم بأحسن شكل. "
            "إذا حابة أساعدك بتنظيم الوقت أو ترتيب الأولويات، خبريني!"
        ),
        (
            "يا عزيزي، خذ شوية قسط من الراحة عشان الصبح تكون فايق وتقدر تكمل التسليم بأحسن شكل. "
            "إذا حابب أساعدك بتنظيم الوقت أو ترتيب الأولويات، خبرني!"
        ),
    ),
    "C082": (
        "مبروك يا غالية! حفظ جزء من القرآن خطوة كبيرة، الله يبارك لكِ ويزيدكِ من علمه. شو الجزء اللي حفظتيه؟",
        "مبروك يا غالي! حفظ جزء من القرآن خطوة كبيرة، الله يبارك لك ويزيدك من علمه. شو الجزء اللي حفظته؟",
    ),
    "C098": (
        "يا حبيبتي، إن شاء الله هالدوخة تمر، إذا في شي بقدر أساعدك فيه أو ترتاحي شوية، خبريني!",
        "يا حبيبي، إن شاء الله هالدوخة تمر، إذا في شي بقدر أساعدك فيه أو ترتاح شوية، خبرني!",
    ),
    "C159": (
        "أيوة سامعك يا غالي، كل شيء واضح. خبريني شو بدك وأنا جاهزة أساعدك",
        "أيوة سامعك يا غالي، كل شيء واضح. خبرني شو بدك وأنا جاهزة أساعدك",
    ),
    "A038": (
        (
            "ما فيني شوف مواعيدك لأن حساب الجيميل مش موصول، خبريني شو العناوين والأوقات وبسجلهم لك. "
            "وبالنسبة لسقاية الزرع، قولّي أي وقت بتحبي أذكّر"
        ),
        (
            "ما فيني شوف مواعيدك لأن حساب الجيميل مش موصول، خبرني شو العناوين والأوقات وبسجلهم لك. "
            "وبالنسبة لسقاية الزرع، قلّي أي وقت بتحب أذكّر"
        ),
    ),
    "C015r1": (
        "آه والله، اليوم كان متعب كتير! إن شاء الله بكرا يجي أهون، ولا تنسى ترتاح وتاخد لك فنجان قهوة أو شاي. 🌿💛",
        "آه والله، اليوم كان متعب كتير! إن شاء الله بكرا يجي أهون، ولا تنسى ترتاح وتاخد لك فنجان قهوة أو شاي. 🌿💛",
    ),
}


@pytest.mark.parametrize("case_id", sorted(HISTORICAL))
def test_historical_failures_convert_exactly(case_id):
    src, expected = HISTORICAL[case_id]
    assert norm(src) == expected


@pytest.mark.parametrize("case_id", sorted(HISTORICAL))
def test_historical_failures_scan_clean(case_id):
    _clean(norm(HISTORICAL[case_id][0]))


# -- 3. preservation: Sara's own feminine voice -------------------------------

SHIELD_CASES = [
    "أنا رتبّيت الملفات كلها",
    "أنا عملت اللي عليّ",
    "ما قدرت أوصل لحسابك",
    "حاولت كتير بس ما زبطت",
    "رح أكون معك خطوة خطوة",
    "أنا جاهزة أساعدك",
    "أنا مبسوطة بالنتيجة",
    "أنا متأكدة من الحل",
    "كنت مشغولة طول اليوم بس خلصت",
]


@pytest.mark.parametrize("text", SHIELD_CASES)
def test_shield_preserves_first_person(text):
    assert norm(text) == text


def test_third_person_nouns_untouched():
    out = norm("ذكر أختك بالدواء")
    assert "أختك" in out
    assert norm("مدرسة الأولاد قريبة") == "مدرسة الأولاد قريبة"
    assert norm("التي تحكي عن المشروع") == "التي تحكي عن المشروع"


# -- 4. deliberate omissions + engine totality ---------------------------------

OMISSION_CASES = ["وديلي الملف", "هدي أعصابك", "تيجي بكرا؟"]


@pytest.mark.parametrize("text", OMISSION_CASES)
def test_documented_omissions_passthrough(text):
    """Undiacritized-identical forms: any rewrite would corrupt. Pinned."""
    assert norm(text) == text


def test_punctuation_adjacency():
    assert norm("خبريني، شو الأخبار؟") == "خبرني، شو الأخبار؟"
    assert norm("(خبريني!)") == "(خبرني!)"
    assert norm("«طمنيني»") == "«طمني»"
    assert norm("خلصنا. نامي هلق") == "خلصنا. نام هلق"


def test_idempotence():
    samples = [
        "خبريني شو صار وطمنيني",
        "يا حبيبتي ارتاحي شوية",
        "أنا جاهزة، خبريني",
    ]
    for text in samples:
        once = norm(text)
        assert norm(once) == once


def test_non_string_passthrough():
    assert norm("") == ""
    assert norm(None) is None  # type: ignore[arg-type]
    assert norm(123) == 123  # type: ignore[arg-type]


def test_mid_and_end_turn_verbs():
    assert norm("خلصت الشغل، طمنيني لما تخلص") == "خلصت الشغل، طمني لما تخلص"
    assert norm("احكيلي القصة من الأول للآخر، لا تنسي التفاصيل") == (
        "احكيلي القصة من الأول للآخر، لا تنسى التفاصيل"
    )
