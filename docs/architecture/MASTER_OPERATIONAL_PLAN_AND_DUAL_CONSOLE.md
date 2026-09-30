# Master Operational Plan & Dual Console

**Status:** plan of record. The dual-console surface is **not built**; §2 and §4 specify it
and §1 is the plan that governs building it.
**Date:** 2026-09-30 · **Branch:** `main` · **Baseline:** `755c490` +
[the agency swarm manifest](./AGENCY_SWARM_WORKFLOW.md)
**Governing contract:** [`CLAUDE.md` §5.1](../../CLAUDE.md) →
`.claude/skills/vantrilex-precision-workflow/SKILL.md`

---

## 0. Calibration decisions — now binding

The Leader adopted all ten recommended baselines (2026-09-30). These are inputs, not
suggestions; any later proposal that contradicts one is a re-scope request, not a
refinement.

| # | Decision | Consequence in this plan |
|---|---|---|
| 1 | Full coverage on a synthesized module + all four gates before it may load | §5 promotion gate |
| 2 | **No telephony escalation**; alerts surface in the tracer only | §6.3 — telephony is *out of scope by decision*, not deferred by omission |
| 3 | Deterministic reflex scorer: zero weights, zero thread bloat, `$0.00` preserved | §7 |
| 4 | In-memory ephemeral overlay only; disk persistence needs a reviewed commit | §5.4 |
| 5 | Reflex sensitivity = `SituationalState` posture + task-marker presence; no numeric threshold | §7.2 |
| 6 | The 6 irreversible tools stay permanently `confirmation_id`-gated, zero exceptions | §6.4 |
| 7 | License compatibility and recency rank above stars | [Swarm manifest](./AGENCY_SWARM_WORKFLOW.md) §1 |
| 8 | Meter **Sara's gateway calls**, per-tool counters in the tracer | §3.3 |
| 9 | 90-day daily-log retention stands | no change until an archive exists |
| 10 | HUD shows all six markers: TTFT, tool latency, tier, `$0.00` cost, Fish tags, invariant checks | §3.2 |

---

## 1. The plan artifact

Written before any code, per `CLAUDE.md` §5.1 Directive 1. A stranger can predict the diff
from this table.

| # | Item | Write-set (exclusive) | Red-first guard | Non-goal |
|---|---|---|---|---|
| A | Launcher flag `-Chat` + `--tracer` alias | `sara.bat`, `tests/test_launcher_flags.py` | A test parses `sara.bat` and asserts every declared flag maps to its target, and that no pre-existing mode was repointed | No new PowerShell logic; `sara.ps1` is untouched |
| B | `src/bot_shell.py` | `src/bot_shell.py`, `tests/test_bot_shell_repl.py` | An `ast` assertion that the shell imports **none** of `src.persona`, `src.gender_pipeline`, `src.voice_policy`, `src.tools`, `src.pc_actions` | No voice, no Telegram, no persistence |
| C | CLI field drill | `scripts/test_cli_live_drill.py`, `tests/test_cli_live_drill.py` | A test asserts an OS-launch step records the **refusal** as the expected outcome, and that every `confirmation_id` in the drill is the literal `None` | The drill never auto-confirms |
| D | Tracer invariant group + per-tool counters | `scripts/live_shadow_tracer.py`, `tests/test_shadow_tracer_markers.py` | A test asserts all six HUD markers classify from a synthetic record set | No OTel dependency |

**Write-set correction (item B), measured during the RED phase.** The plan originally
named `tests/test_bot_shell.py`. That path is **taken** — it is a 47,828-byte pre-existing
suite for the *Telegram* shell, importing `src.bot`. Overwriting it would have destroyed
someone else's work. The RED suite is therefore `tests/test_bot_shell_repl.py`. Re-scoped,
not dropped.

**The seam item B is pinned to.** A behavioural guard cannot avoid naming a seam, so the
RED suite pins two public names, and the implementation must match them:

- `build_shell(gateway, settings)` — mirrors `src.bot.build_dispatcher`, returns a `Shell`.
- `Shell.turn(text)` — an **async generator** yielding the dispatcher's deltas verbatim.

`turn` yields verbatim because that is the whole invariant guarantee: if the shell composes
or rewrites anything, there is a second code path for an invariant to leak through.

### Non-goals — what this milestone does NOT do, and why

- **No telephony, no SIP, no emergency dial.** Decision 2 rules it out, and it was already a
  recorded v1.5 deferral. Building it would contradict a decision taken today.
- **No Laya checkpoint.** A multi-hundred-MB model on a `$0.00` invariant is refused on
  principle, not on latency. Decision 3 supersedes the question entirely.
- **No MCP transport.** Sara's tools are local callables behind `ToolRegistry.call`; an
  MCP hop adds a network dependency and a failure mode for no new capability.
- **No new external packages.** Every item above is stdlib-plus-existing-stack.
- **No change to `src/persona.py`** (reformat-locked), `src/gateway.py`, `src/config.py`, `.env`.
- **No parallel writers.** `CLAUDE.md` §5 stands: one implementer thread per item.

### Owner-only — not finishable by an agent

- Rotating the `sk-or-v1-…` key in `opencode.json`. Live credential on disk; not tracked,
  not in history, but plaintext. An owner action.
- Deciding whether the tiered-coverage gate belongs in `make gate` or in the docs. Both are
  currently true and mutually inconsistent; which one is wrong is a policy call.
- The `openrouter/`-prefix switch for `MEDIUM_MODEL` / `HEAVY_MODEL`. Production file.

---

## 2. Terminal 1 — Clean Chat REPL

### What exists today: nothing

`src/bot_shell.py` **does not exist**. There is no interactive chat entry point in the
repository. `sara.bat` boots the full stack (core + bridge) via `sara.ps1`; it is not a
chat shell.

### The seam that makes this safe

The failure mode for a new chat surface is **reimplementing the invariants by accident** —
a second persona path, a second gender filter, a second confirmation gate. The design rule
is therefore a single one:

> `bot_shell` owns **presentation only**. Every turn is handed to the existing
> `FrontDoorDispatcher` (`src/dispatcher.py:744`). It may not import `src.persona`,
> may not call a tool directly, and may not emit a string the dispatcher did not produce.

This makes invariant preservation *structural* rather than a matter of discipline: there
is no second code path for an invariant to leak through. The guard for it is item B's
red-first test.

### Surface

- Line-oriented REPL, ar-JO input and ar-JO output, streamed token-by-token from the
  gateway tier the dispatcher selects.
- No audio. Voice is the Telegram lane's concern; a local REPL that spoke would need a
  playback sink and would put a Fish call on every keystroke. Out of scope by decision.
- `-Trace` may run in the second window simultaneously; the two are independent processes
  reading a shared sink.

---

## 3. Terminal 2 — Live Shadow Tracer

### What exists today: the whole thing

This is the largest divergence between the directive and reality, and it is good news.
Terminal 2 is **already delivered** as `sara.bat -Trace` (`sara.bat:11-14`), which launches
`scripts/live_shadow_tracer.py`.

Already implemented and verified in that script:

| Marker (Decision 10) | Present | Where |
|---|---|---|
| TTFT | ✅ | `ttft`, `first-token` in the generation classifier group (`:100`, `:106`) |
| Tool latency | ✅ | domain classifier + `vitals_table()` (`:246`) |
| Model tier / routing | ✅ | `gateway`, `all models` (`:105`, `:108`); `core_health()`, `gateway_models()` (`:167`, `:205`) |
| `$0.00` cost | ✅ | `paidmodel`, `cost`, `$0` (`:102-104`) |
| Fish audio tags | ✅ | audio group `fish, synth, opus, ffmpeg, expressive_audio, tts` (`:60`) |
| Invariant checks | ⚠️ partial | no dedicated classifier group; a `paidmodel` record implies the `$0.00` check but nothing names the other four |

So item D reduces to **one new classifier group** for invariant checks, plus the
per-tool counters from Decision 8.

### Per-tool call counters (Decision 8)

Decision 8 replaces the unanswerable quota question with a measurable one: count gateway
calls per tool. The counter is emitted by the tracer's existing record stream, so it
costs no new instrumentation in `src/`. It answers the question Decision 8 actually poses —
*how much of the free pool did this turn consume* — which the 50 req/day/account ceiling
recorded at `.env.example:25` makes worth knowing.

### Alias

`--tracer` is added as an alias for the existing `-Trace` so the documented command in
§6 of the directive works verbatim. Single-dash `-Trace` continues to work.

---

## 4. CLI field-test drill

### Purpose

Replace "Omar types a hundred prompts" with a reproducible multi-turn suite, so a
regression in live behaviour is a failing test rather than an anecdote.

### The seam

The drill drives `bot_shell` as a **subprocess over pipes**, exactly as a human at a CMD
prompt would. It is therefore a true end-to-end test of Terminal 1, and it inherits the
structural invariant guarantee from §2 rather than re-testing it.

### What it may and may not do

| Allowed | Forbidden |
|---|---|
| Read-only tool calls (system state, weather, mailbox counts) | Auto-confirming anything |
| `launch` **proposed**, then refused without a `confirmation_id` | Supplying a `confirmation_id` on the drill's behalf |
| Multi-turn JODA phrasings from the dialect bank | Asserting on exact wording (invariant is ar-JO, not verbatim) |
| Asserting the 5 invariants hold per turn | Mutating vault state |

The `launch` row is the point of Decision 6: the drill **demonstrates the refusal**. A
drill that could launch Chrome would be a `confirmation_id` bypass with extra steps, and
Decision 6 admits zero exceptions.

The directive's "dynamically discovering other Chrome profiles" is **not buildable from
the current surface**: `config/whitelist.json` is a static Start Menu scan (163 apps, 3
restricted actions) and no module in `src/` enumerates browser profiles. Chrome and Edge
are whitelisted applications; profiles are not modelled. Adding profile enumeration is a
new tool, which routes through the §5 pipeline rather than through a test harness.

---

## 5. Mojito self-evolution engine — current state

The five-stage pipeline is specified in
[the cross-framework blueprint](./CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md) §3.
Decisions 1 and 4 close the two open questions it carried.

| Stage | State | Blocked by |
|---|---|---|
| 1 — gap detection → `EvolutionTask` | specified | needs a build (P3-A) |
| 2 — synthesis | specified; runs out-of-process | maintainer action, never a turn |
| 3 — AST gate | **live** — `verify_proposal_code` (`src/evolution.py:44`) | 3 of 5 rules only |
| 4 — TDD + regression | **live** — `promotion_decision` (`src/evolution.py:151`) | needs real gate outputs wired in |
| 5 — hot registration | **not buildable yet** | four registration points, two are `Final` literals |

### 5.4 Overlay lifetime (Decision 4)

In-memory only. A dynamically bound tool lives until restart; `CompositionCache` already
models that shape correctly (in-memory, `clear()` as a full reset) and the overlay follows
it rather than inventing a second lifecycle. Disk persistence requires a reviewed commit —
which means it stops being a dynamic tool and becomes a static one.

### 5.1 The trap that still blocks stage 5

Registering a tool is **four** edits, and two of them are `Final` literals
(`_VALID_TOOLS` at `src/dispatcher.py:123`, `_TOOL_GOALS` at `src/cognition.py:30`). A tool
missing from either is silently unreachable — an unknown name is rewritten to `"none"`
(`src/dispatcher.py:730`) and `deduce` can never propose it. Nothing raises. The overlay
refactor therefore ships **empty** (P3-C) before any tool is enabled (P3-D).

---

## 6. Fish Audio S2.1 ecosystem

### 6.1 What is live

`src/fish_voice.py` posts to `FISH_SPEECH_URL` = `https://openrouter.ai/api/v1/audio/speech`
(`:19`) using `fish-audio/s2.1-pro-free:free` with the «سمسم-بوس» reference voice. Failure
raises `FishVoiceError` and the caller lands honest TEXT — there is no fallback voice, ever,
by `src/voice_policy.py:assert_no_edge`.

### 6.2 S2 bracket cues — already handled, partially

`src/fish_voice.py:87` strips bracket cues before speech and caps known tags per turn. So
the "S2 `[bracket]` emotion cues" requirement is **already met for the speech path**. What
is not built is the authoring side: a validated, bounded cue vocabulary that the persona
can emit deliberately rather than inherit from prose.

### 6.3 Telephony / SIP — out of scope by decision

Decision 2 removes emergency escalation. Independently, the capability does not exist:
`src/skills/live_calls.py` is PyTgCalls voice calling over Telegram, SIP is a recorded v1.5
deferral, and no SIP library appears in any requirements file. **This section is closed by
decision, not by deferral** — which is a materially different thing, and should not be
reopened as if it were pending.

### 6.4 MCP integration — not adopted

Rejected on the standing disposition rule: Sara's tools are local Python callables and an
MCP hop adds a network dependency for no new capability. Decision 6's confirmation-gating
is also cleaner in-process than across a protocol boundary, because
`src/pc_actions.py:277` mints the `confirmation_id` locally.

---

## 7. System-1 reflex scorer (Decision 3)

### 7.1 Shape

A deterministic scorer, not a model. Inputs are features `cognition.evaluate_candidates`
already computes in the same pass — marker hits, connector-separated action density,
`ReflectiveTrace.penalty` (`src/cognition.py:185`), and turn count from
`src/turn_counter.py:read_turn_count`. Output: `(tier, confidence)`.

No weights, no checkpoint, no second pass over the utterance, no network. `$0.00` holds by
construction because nothing is loaded.

### 7.2 The three reflexes (Decision 5)

| Reflex | Detection | Effect |
|---|---|---|
| Pre-empathy sighing | interrupt marker while operations are in flight (`Scratchpad`, `src/decision_loop.py:185`) | acknowledge first, answer after |
| Banter vs serious | `situational.py:SituationalState` posture + whether the last turn carried a task marker | serious suppresses emoji and banter |
| Incomplete thought | no terminal verb or trailing conjunction in a clause that already matched a marker | one clarifying question instead of a guessed argument |

**No numeric threshold** is specified, by decision. The absence is stated in the code at
the call site — a threshold nobody has measured is a number that will be wrong and that
nobody will revisit.

The third is the one to build first: pure syntax, testable without a model, and it prevents
the worst failure in the catalogue — a confidently wrong tool argument.
`normalize_tool_arg` (`src/decision_loop.py:65`) is the existing seam.

---

## 8. Ten-agent swarm registry

Roster, mandates, and — for each of the four governance rules — the mechanism that would
enforce it, are in [the manifest](./AGENCY_SWARM_WORKFLOW.md). Two facts belong here
because they bear on how much the roster can be trusted:

1. **Two of the four rules are conventions, not gates.** The Test-First Barrier and the
   Security Sign-Off have no automated tripwire. A green `make gate` is evidence the
   mechanical checks passed; it is not the auditor's certification.
2. **`make gate` does not run `check_tiered_coverage.py`.** `Makefile:40` is
   `gate: lint test security docs-guard`. The coverage gate is run by hand, which is why
   it appears in this plan's gates as a separate command and not as part of `make gate`.

---

## 9. What this document does not authorize

- No model pin change; this document predates the 2026-09-30 decision that re-pinned
  `MEDIUM_MODEL` / `HEAVY_MODEL` from the bare `nex-agi/*` slugs to the
  `openrouter/nex-agi/*` form.
- No edit to `.env`, `src/config.py`, `src/gateway.py`, or `src/persona.py`.
- No telephony, no SIP, no Laya checkpoint, no MCP transport, no new package.
- No dynamic tool registration before the overlay refactor ships empty.

---

## 10. Refuted premises in the originating directive

| Specified as | Measured | Building instead |
|---|---|---|
| `sara.bat --tracer` for Terminal 2 | **`sara.bat -Trace` already exists** (`sara.bat:11-14`) and the tracer already carries 5 of the 6 HUD markers | alias + one classifier group (§3) |
| `python -m src.bot_shell --interactive` | `src/bot_shell.py` does not exist | build it (item B) |
| Laya "sub-10ms" System-1 | upstream states **33 ms**; a checkpoint breaks `$0.00` | deterministic scorer (§7) |
| Fish Audio SIP emergency escalation | no SIP anywhere; a v1.5 deferral | **closed by Decision 2**, not deferred |
| MCP integration | adds a dependency for no capability | rejected |
| Meter sub-agent calls across the 5+5 key pools | sub-agents do not route through OmniRoute; pool is server-side | meter gateway calls per tool (Decision 8) |
| Drill to discover Chrome profiles dynamically | no profile model exists in `src/`; whitelist is a static Start Menu scan | out of harness scope; a new tool, so §5's pipeline |

**Not dropped, not built as written** — each re-scoped above with the measurement that
refuted it.

---

## 11. See also

- [Agency Swarm Roster & Workflow Manifest](./AGENCY_SWARM_WORKFLOW.md)
- [Cross-Framework Analysis & Self-Evolution](./CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md)
- [16 — Operational Workflows](../16-WORKFLOWS.md) — the 4-tier lifecycle
- [00 — Map of Architecture](../00-MAP-OF-ARCHITECTURE.md)
- [10 — Checkpoint Ledger](../10-CHECKPOINT.md)
- [11 — Testing and Gates](../11-TESTING.md)
- [12 — Security](../12-SECURITY.md)
