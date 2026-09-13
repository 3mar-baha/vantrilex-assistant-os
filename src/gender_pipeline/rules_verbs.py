"""Stage 2 — 2nd-person present & conditional verbs (addressee = Omar).

All keys are ي-suffixed 2nd-person-feminine forms, which are unambiguous:
3rd-person feminine present shares the masculine spelling (بتعمل), so these
patterns can NEVER match third-party references. Applied UNSCOPED (no إذا/لو
gate): every Sara reply addresses Omar, and scoping only loses recall.

Deliberate deviations from the mandate draft, both audited:
- تقدري -> تقدر (NOT بقدر: بقدر flips person 2nd->1st, corrupting meaning).
- تيجي omitted (masculine تيجي renders identically — any rewrite is wrong).
"""

from __future__ import annotations

from typing import Final

RULES: Final[tuple[tuple[str, str], ...]] = (
    ("بتحبي", "بتحب"),
    ("بتريدي", "بتريد"),
    ("بتقدري", "بتقدر"),
    ("تقدري", "تقدر"),
    ("وتقدري", "وتقدر"),  # glued و full-token form (attested C005; never strip و blindly)
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
    # تهدئي is instruction-shaped in the wild ("تهدئي، تنفّسي بعمق") → the
    # masculine imperative اهدا (not present-tense تهدأ).
    ("تهدئي", "اهدا"),
    ("تنفسي", "تنفس"),
    ("تنفّسي", "تنفس"),
    ("احتجتي", "احتجت"),
    ("حفظتي", "حفظت"),
    ("حفظتيه", "حفظته"),
)

# Context-scoped raw patterns (already include their own boundaries): for
# forms that are ALSO valid 1st-person feminine (حابة after كنت = Sara
# herself), conversion fires only inside unambiguous 2nd-person frames
# (إذا/لو/شو + حابة = "if you want"). Bare حابة stays untouched.
REGEX_RULES: Final[tuple[tuple[str, str], ...]] = (
    # Boundaries inlined (engine wraps only the plain RULES table).
    (r"(?:^|(?<=[\s«\"'(\[]))((?:إذا|لو|شو)\s+)حابة(?=[\s.,!؟…:;،»\"')\]}]|$)", r"\1حابب"),
)
