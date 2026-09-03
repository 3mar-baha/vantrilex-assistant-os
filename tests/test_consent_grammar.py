"""Remediation 1.8 (owner 2026-09-03, audit S-4): consent grammar hardening.

An affirmative must be a STANDALONE short yes (≤3 tokens) free of negation or
reservation — «نعم بس استنى» must NEVER launch a program or a power command.
Sprint-3's first-token rule treated any reply STARTING with نعم/ايه/أيوه as
consent, letting «نعم بس»/«نعم لا»/«ايه بعدين» execute guarded actions.
"""

import pytest

from common.consent import is_affirmative


@pytest.mark.parametrize(
    "reply",
    [
        "نعم",
        "أيوه",
        "ايه",
        "اكيد",
        "تمام",
        "yes",
        "ok",
        "ايه سوّيها",  # warm 2-token consent (sacred-floor fixture pins this)
        "نعم افتحها",
        "ايه يلا",
    ],
)
def test_standalone_affirmatives_accept(reply):
    assert is_affirmative(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "نعم بس استنى",  # reservation after yes — NOT consent (the S-4 headline)
        "نعم بس",
        "نعم لا",  # self-contradiction
        "ايه بس خلص حسابك",
        "ايه لا لا ألغها",
        "أيوه مش هلق",
        "نعم لسا فيني أفكر",
        "اكيد بعدين",
        "تمام بس بعدين",
        "يمكن",
        "لا",
        "مش هلق",
        "بعدين",
        "ليش",
        "",  # silence is never consent
        "    ",
    ],
)
def test_reserved_or_negative_replies_reject(reply):
    assert not is_affirmative(reply)


def test_long_tirades_starting_with_yes_reject():
    """A reply that merely OPENS with yes but runs on is not a clean yes."""
    assert not is_affirmative("نعم رح فكر بالموضوع وبعدين بردلك إذا لزم الأمر وقتها")
