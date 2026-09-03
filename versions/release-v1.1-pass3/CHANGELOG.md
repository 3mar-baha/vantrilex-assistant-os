# Release v1.1 — Pass 3 (2026-09-04)

## Humanization (this pass's focus)
- **The spoken lexicon doubled**: the seed TTS lexicon grew from 10 to 19
  entries — the words Sara actually says constantly (هلا/اهلا/بعرف/بقدر/
  رح/شوي/هلأ/وين/حكي) now carry their Jordanian vocalization instead of
  MSA-G2P guesses. Three candidate words (شوف/مرحبا/كيف/تمام) were
  deliberately REJECTED: the shaping contract pins them plain; the owner's
  «تعلمي:» notes remain the live override for anything, always.
- **The warmth clause**: the persona gained the friend's emotional register —
  celebrating his wins (small ones too), gentle teasing on procrastination
  (دغبغة), standing beside him in hard stretches, and the banter that
  carries affection without wounding: «الفرح من قلبك والمزح من قلبك، هيك
  بتوصل المشاعر قبل الكلمات». Contract-tested with the other 11 persona
  clauses.

## Architectural notes
- No structural change this pass — dialect polish only; the lexicon override
  order (seed < owner notes) unchanged and verified.

## Verification
- Gate: 493 passed / 1 skipped / ruff + security + docs green.
