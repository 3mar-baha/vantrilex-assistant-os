"""Sprint-2 §2.4 TokenJuice compaction (M7/ADR-19): quoted reply chains,
signature blocks, legal footers and tracking boilerplate are stripped
deterministically and the body is capped to the classification budget —
pure function, tier decisions unchanged on compacted input."""

from src.email_triage import TriageClassifier, Tier, tokenjuice_compact
from tests.test_email_triage import FakeBrain, _msg, _settings

RAW = (
    "مرحبا عمر،\n\n"
    "نحتاج تقرير المشروع urgent قبل الخميس مباشرة.\n\n"
    "> في الرسالة السابقة كتبت: المشروع متأخر\n"
    "> أرسل لي التحديث\n\n"
    "-- \n"
    "أحمد مدير المنتج\n"
    "شركة التحليلات | +962 7 000 0000\n\n"
    "This email is confidential and intended for the named recipient only.\n"
)
COMPACTED = "مرحبا عمر،\n\nنحتاج تقرير المشروع urgent قبل الخميس مباشرة."


def test_signature_and_quotes_stripped():
    """M7: quoted chain + standard signature delimiter + legal footer all gone,
    the real body (with its keyword) survives verbatim."""
    assert tokenjuice_compact(RAW, max_chars=4000) == COMPACTED


def test_legal_footer_stripped_without_signature_delimiter():
    """M7: disclaimers/boilerplate are stripped even when no `--` sig line exists."""
    raw = (
        "نص أساسي مهم urgent.\n"
        "This message contains confidential information.\n"
        "If you are not the intended recipient, delete it.\n"
        "unsubscribe from these emails here\n"
    )
    assert tokenjuice_compact(raw, max_chars=4000) == "نص أساسي مهم urgent."


def test_whitespace_collapsed():
    """M7: runs of blank lines collapse to one; trailing spaces rstripped."""
    assert tokenjuice_compact("a  \n\n\n\n\nb", max_chars=4000) == "a\n\nb"


def test_body_capped_at_budget():
    """M7: body longer than max_chars is truncated with a marker inside budget."""
    body = "حرف " * 40  # 200 chars, keyword-free padding
    out = tokenjuice_compact(body, max_chars=60)
    assert len(out) <= 60
    assert out.endswith("…]") and out.startswith("حرف")


def test_keywords_survive_compaction():
    """AC8 half: compaction keeps the scoring signal — keywords in the real body
    land in the compacted output."""
    out = tokenjuice_compact(RAW, max_chars=4000)
    assert "urgent" in out and "الخميس" in out


def test_classification_unchanged_on_compacted_input(make_settings):
    """M7: tier + score are identical before vs after compaction (noise carried
    no signal, stripping it never changes the decision)."""
    classifier = TriageClassifier(_settings(make_settings), FakeBrain())
    d_raw = classifier.heuristic(_msg(subject="عاجل", body_text=RAW))
    compact = tokenjuice_compact(RAW, max_chars=4000)
    d_compact = classifier.heuristic(_msg(subject="عاجل", body_text=compact))
    assert d_raw.tier is Tier.IMPORTANT  # 0.25 subject + 0.30 body cap
    assert (d_raw.tier, round(d_raw.score, 2)) == (
        d_compact.tier,
        round(d_compact.score, 2),
    )
