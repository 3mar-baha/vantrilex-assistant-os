---
title: Physics and Math Reasoning
aliases: [physics, math, فيزيا, رياضيات, STEM, science reasoning, first principles, Feynman, حساب التفاضل, ميكانيكا]
tags: [stem, reasoning, science, math, physics]
date: 2026-09-13
type: knowledge-base
summary: Curated first-principles science reference — Feynman explanations, Socratic breakdowns, classical theorems.
---

# Physics & Math Reasoning — First-Principles Reference

Curated synthesis of public-domain classical results and standard pedagogical
patterns (Newtonian mechanics, electromagnetism, thermodynamics, quantum
basics, linear algebra, calculus). A reasoning playbook, not a textbook.

## 1. The Feynman Explanatory Framework (mandatory shape for hard answers)

1. **Intuition first, in plain words** — one paragraph a bright teenager
   follows, zero jargon, one everyday analogy.
2. **Name the moving parts** — list quantities and what each means physically.
3. **Then the formula** — introduce symbols only after intuition lands, with
   units attached to every term.
4. **One worked micro-example** — tiny numbers, all steps shown, result
   sanity-checked against intuition ("does 3 m/s make sense here?").
5. **Boundary check** — where the model breaks (frictionless? non-relativistic?
   steady-state?). Never present a formula without its domain of honesty.

## 2. Socratic inquiry pattern (no hand-waving)

- Decompose: "what are we actually asked?" → knowns → unknowns → governing law.
- Ask one question at a time; each answer unlocks exactly one next step.
- When stuck: shrink the problem (1D before 3D, static before dynamic,
  discrete before continuous), solve small, generalize explicitly.
- Name every assumption out loud before using it.

## 3. Classical theorem index (working knowledge, not derivations)

- **Newtonian mechanics**: F=ma; projectile range R = v²sin2θ/g; circular
  motion a=v²/r; work-energy W=ΔK; momentum conserved absent external impulse.
- **Electromagnetism**: Coulomb F=kq₁q₂/r²; Ohm's law V=IR; power P=VI;
  Faraday induction ε=−dΦ/dt (sign = Lenz opposition).
- **Thermodynamics**: 1st law ΔU=Q−W; entropy non-decreases in isolation;
  Carnot ceiling η=1−Tc/Th (no engine beats it, ever).
- **Quantum basics**: E=hf; Heisenberg Δx·Δp≥ℏ/2 (measurement disturbance,
  not just ignorance); superposition collapses on measurement.
- **Linear algebra**: matrix = linear map; eigenvectors = directions the map
  only scales; determinant = volume scaling factor (zero = collapse).
- **Calculus**: derivative = instantaneous rate; integral = accumulated area;
  chain rule for nesting; optimization = derivative zero + endpoint check.

## 4. Complexity & sanity toolkit

- Big-O by counting dominant loops; state best/average/worst separately.
- Dimensional analysis as a free error check (units must balance both sides).
- Order-of-magnitude estimation before precise calculation (Fermi habit).
