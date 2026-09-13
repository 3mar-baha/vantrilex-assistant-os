"""Arabic gender normalization pipeline (mission: kill mid-turn drift).

Sara speaks to Omar (masculine singular). Her replies must address him with
masculine imperatives/verbs/clitics (خبرني، طمني، شوف) while she keeps her
own feminine first-person voice (أنا جاهزة، رتبّيت). Inspired by the CAMeL
Gender Rewriting architecture: shield pass first, then ordered rewrite
stages, all O(N) regex over tokens with word boundaries.

Public entry: normalize_masculine_address(text) -> str (engine.py).
Pure + total: non-string input returns unchanged; never raises.
"""

from src.gender_pipeline.engine import normalize_masculine_address

__all__ = ["normalize_masculine_address"]
