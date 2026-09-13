# Fish Audio Tag Calibration (Phase-0 spike)

Date: 2026-09-13T13:41:38+0300 · commit: 2e11142
Model: `fish-audio/s2.1-pro-free:free` · endpoint: `https://openrouter.ai/api/v1/audio/speech`
Voice: tester lane (Sara ref untouched) · key source: dedicated FISH_AUDIO_API_KEY
Note: shaped production path (shape_for_tts applied); no secrets recorded.

## Results

| Variant | Input | Status | ms | opus bytes |
|---|---|---|---|---|
| control | «مرحبا عمر، هاي تجربة صوتية قصيرة» | OK | 3304.5 | 24724 |
| laughing | «[laughing] هههه يا زلمة هاي نكتة حلوة كتير» | OK | 1496.5 | 22800 |
| sigh | «تعبنا اليوم كتير [sigh] بس خلصنا كل الشغل الحمد لله» | OK | 1287.1 | 32083 |
| whispering | «[whispering] اسمعني منيح، هاد سر بيني وبينك» | OK | 1010.7 | 24307 |
| excited | «[excited] فزنا! جبنا أعلى علامة بالصف يا عمر» | OK | 1137.0 | 25853 |
| paren-sigh | «يا الله شو هالنهار الطويل (sigh) الحمد لله على كل حال» | OK | 1354.4 | 32510 |

## Verdicts

- Bracket tags: **GO** (6/6 variants OK).
- Paren cues `(sigh)`: **GO with evidence note — passthrough live; set PARALANGUAGE_PAREN_ENABLED=True** (status: OK; 32510 opus bytes vs 24724 for the comparable-length control — consistent with a rendered sigh rather than a stripped token, though byte size alone does not prove acoustic fidelity; human listen remains the final arbiter).
- Throttled variants are pool state, not tag verdicts — rerun off-peak before downgrading any tag.
