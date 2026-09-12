# Sara Skill Standard (production `SKILL.md` specification, 2026-09-12)

Every capability in `src/skills/` (mirrored to the vault at
`02_Areas/Profile/Sara_Skills/` via `build_skill_guides`) MUST be an
exhaustive, standalone skill file. No stubs, no summaries. This document is
the enforceable contract — `tests/suite/tier1_resilience/test_skill_standard.py`
validates it.

## 1. YAML frontmatter (required keys)

```yaml
---
name: telemetry            # = ToolRegistry tool name (dispatcher verdict)
version: 1                 # bump on behavior change
owner: sara-core
safety_class: reversible   # reversible | irreversible | read-only
needs: bridge              # bridge | google | network | vault | local | none
---
```

## 2. Governing philosophy (why the skill exists)

One paragraph: the human goal it serves, in Sara's voice context. Never a
trigger list — the philosophy is what the brain matches against intent.

## 3. Situational triggers (when to consider it)

Colloquial Jordanian trigger contexts (3+), PLUS explicit non-triggers
(near-miss phrases that belong to a sibling skill). Disambiguation beats
coverage: each sibling collision resolved in writing.

## 4. Multi-step execution workflow

Numbered steps the brain follows: arg extraction → backend call → audit-code
handling → narration shape (1-2 warm lines carrying the ground truth only).
Chaining notes: which skills combine (`chains_with` in `capabilities.py`).

## 5. Edge-case recovery

Every known failure mode with its honest line: backend offline, empty result,
ambiguous arg, partial multi-step success. Rule: a dead tool degrades to the
honest line + horizon alternative — never silence, never a hallucinated
success, never a foreign voice.

## 6. Safety boundaries

Whitelist gates, confirmation requirements, irreversible-action clarification
thresholds, untrusted-content boundary (tool output is DATA). Guest-mode
behavior where relevant.

## Exemplar

`src/skills/telemetry.SKILL.md` is the reference implementation. New skills
copy its shape; reviewers diff against it.
