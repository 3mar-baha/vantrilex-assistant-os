# Cross-Framework Analysis & the "Mojito" Self-Evolution Blueprint

**Status:** design blueprint. Nothing in §3–§6 is implemented.
**Scope:** architectural mapping of 24 external resources onto Sara's runtime, plus a
five-stage self-evolution specification that adopts the *spirit* of
[TimeLovercc/mojito](https://github.com/TimeLovercc/mojito) while closing the safety hole
mojito's own `SECURITY.md` admits it has.
**Date:** 2026-09-30 · **Branch:** `main` · **Baseline commit:** `755c490` (CI green,
`windows-latest`)

---

## 0. How to read this document

Three markers are used throughout, and they are load-bearing:

| Marker | Meaning |
|---|---|
| **VERIFIED** | Read out of this repository's source, or fetched from a linked upstream file during the session that produced this document. Line numbers are current at commit `755c490`. |
| **PROPOSED** | Does not exist yet. The name is a specification, not an API. It will be created in the phase named beside it. |
| **ADOPT / ADAPT / REJECT** | The standing disposition rule for external resources. Nothing enters `requirements.txt` on the strength of a row in §2 — see §2.2. |

Every specific claim in this document — a number, a quoted sentence, an upstream API, a
line reference into this repository — was checked against a source during the authoring
session, and §9 lists exactly which sources. Where a row is an architectural reference
rather than a verified quotation, it says so. Where the dossier and the upstream disagree,
§8 records the disagreement and this document follows the upstream.

---

## 1. Verified baseline (the facts the rest of the document rests on)

Everything in this table was read from source during the authoring session.

| Anchor | Value | Location |
|---|---|---|
| Tool catalog | **42** capabilities, each `{goals, markers, reversible, needs, chains_with}` | `src/skills/capabilities.py:350` |
| Irreversible tools | **6** (`cancel_reminder`, `close`, `create_event`, `create_task`, `openclaw_browse`, `openclaw_desktop`) | `src/skills/capabilities.py:353` |
| Tool execution seam | `ToolRegistry.call(tool, arg)` → `getattr(self, f"_do_{tool}")`, unknown tool ⇒ `TOOL_FAIL_AR` | `src/tools.py:90`, `:137` |
| Router vocabulary | `_TOOL_GOALS` — a **static literal**, not derived from the capabilities registry | `src/cognition.py:30` |
| Dispatcher allow-list | `_VALID_TOOLS` — a **second** static tuple | `src/dispatcher.py:123` |
| Verdict cache | `CompositionCache(read_only_tools, ttl_s)`; dispatcher pins `ttl_s=1800.0` over 6 cacheable tools | `src/cognition.py:205`, `src/dispatcher.py:119`, `:774` |
| Evolution module | `distill_chains`, `verify_proposal_code`, `format_proposal`, `evaluate_proposal`, `promotion_decision`, `PROMOTABLE_TOOLS` (8 tools), `PromotionReport` | `src/evolution.py` |
| AST allow-list | 8 stdlib modules; forbidden calls `eval, exec, compile, __import__, open` | `src/evolution.py:18`, `:21` |
| Overlay sandbox | `OverlayVault(real_root, shadow_root)`; shadow-first reads, `_rel` raises `ValueError` on `..` traversal | `tests/live_harness/overlay.py:13` |
| Confirmation law | `confirmation_id` minted per PC action, 10-minute `PENDING_TTL` | `src/pc_actions.py:277`, `:23` |
| Memory primitives | `upsert_fact`, `resolve_current_facts`, `filter_superseded_rows`, `DailySummarizer` | `src/memory.py` |
| Hybrid retrieval | `src/bm25.py` (`score`, `rank`) is **built, tested, and unwired** — no `src/` module imports it | `src/bm25.py`, `src/associative.py` |
| Injection ceiling | `INJECT_MAX_CHARS = 600`, `MAX_DOC_CHARS = 8000` | `src/associative.py` |
| Model tiers | `Tier.FAST / MEDIUM / HEAVY`; escalation at `heavy_concurrency_threshold = 3` | `src/gateway.py`, `src/config.py:47` |
| Dialect evolution (existing) | `SelfEvolutionWorker` — nightly, **notes proposals only**, never registers | `src/skills/self_evolution.py:45` |
| Coverage gates | 98.0% per core module, 90.0% overall | `scripts/check_tiered_coverage.py` |
| Docs gate | 16 canonical files must exist | `scripts/docs_guard.py:11` |

### 1.1 The four invariants this blueprint must not break

1. **ar-JO immersion** — every user-visible string, including a synthesized tool's
   reply text, is Amman colloquial. `src/persona.py` is reformat-locked.
2. **Masculine address** — Omar is addressed in masculine forms; unit-tested, not asserted.
3. **Fish-only voice** — `src/voice_policy.py:assert_no_edge`; no Edge-TTS anywhere.
4. **Zero unconfirmed commands** — anything irreversible carries a `confirmation_id`
   minted by `src/pc_actions.py`. A synthesized tool may not mint its own.

Plus the standing constraint: **$0.00**. Any design that needs a paid endpoint is out of
scope, and `src/gateway.py:PaidModelBlockedError` enforces it at the gateway seam.

---

## 2. Framework analysis matrix

### 2.1 The matrix

| # | Resource | Key architectural innovation | Concrete application in Sara | Sara source file(s) |
|---|---|---|---|---|
| 1 | [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | One orchestration vocabulary over four topologies (sequential, concurrent, group chat, handoff) | Split the existing one-shot turn into named topologies. Concurrent already exists in spirit; handoff is how HEAVY→FAST escalation should be expressed instead of ad-hoc tier switching | `src/agent_manager.py:95`, `src/gateway.py` |
| 2 | [Restate orchestrator-worker](https://docs.restate.dev/ai/patterns/workflow-orchestrator) | Durable, non-blocking workflow handles; workers are replayable | Bounded-concurrency tool fan-out with per-step receipts, so a Gmail probe that stalls cannot hold the Calendar probe hostage | `src/agent_manager.py:191` (`_run_line`, `asyncio.gather` at `:247`) |
| 3 | [LangGraph](https://github.com/langchain-ai/langgraph) | Cyclic state graph with checkpointed time-travel | Retry-with-remembered-failure: the healing budget already records failures; a checkpoint would let a turn resume with prior observations rather than restart | `src/decision_loop.py:71` (`HealingBudget`), `:185` (`Scratchpad`) |
| 4 | [Agno Workflows](https://agno.mintlify.app/workflows/overview) | Declarative flow schema serialized separately from execution | Give the dispatcher's tool chain a serializable declaration so a plan is inspectable data, not a list built inline | `src/dispatcher.py:995` (`_tool_lane`), `src/cognitive_dag.py:classify_weight` |
| 5 | [HyperAgents](https://github.com/facebookresearch/HyperAgents) (arXiv:2603.19461) | *"Self-referential self-improving agents that can optimize for any computable task"* — the agent improves the code that improves the agent | The verification half of a self-evolution loop: dry-run a synthesized tool against a simulated owner before it is offered for real. **Runtime rejected** — its setup requires `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`, which the $0.00 invariant forbids | PROPOSED `src/skills/dynamic/sandbox.py` (§3.3) |
| 6 | [Google ADK](https://github.com/google/adk-docs) | Native MCP client plus cloud tool connectors | Not adopted. Sara already has first-party Google clients; an MCP hop would add a network dependency for zero new capability at $0.00 | — (rejected, §2.2) |
| 7 | Fleet-manager pattern — dossier names `ComposioHQ/agent-orchestrator`, `mechanicus`, `drizzy-agent`, `opencode-teamwork` (**repo names not independently verified in this session**) | Worker isolation and lifecycle managed by an orchestrator rather than by the worker | The synthesis worker (§3.2) is exactly this shape: one job, isolated process, no shared mutable state with the live bot | PROPOSED `scripts/evolution_worker.py` |
| 8 | [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) | Hook lifecycle around tool execution; granular permission sets | Direct ancestor of the AST gate + promotion gate. Sara's version is stricter: the permission set is an allow-list of 8 stdlib modules, not a hook chain | `src/evolution.py:18`, `src/pc_actions.py:130` |
| 9 | [ScaleMCP](https://arxiv.org/abs/2505.06416) | MCP servers as single source of truth; a retriever that adds tools to the agent's own memory; TDWA weighted tool-document embeddings | The *pattern* of a registry whose source of truth is external and synchronized is rejected; the *insight* that tool descriptions are retrieval keys is adopted — a synthesized tool's `markers` field is what makes it reachable | `src/skills/capabilities.py:350` (`markers`) |
| 10 | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | Small tracing + guardrail surface | The receipt idea: every promotion decision leaves an append-only line. Sara's equivalent already ships in the daily friction section | `src/memory.py:DailySummarizer`, `src/cognition.py:191` (`render_ledger_block`) |
| 11 | [Mem0](https://github.com/mem0ai/mem0) | Continuous preference extraction with a dynamic profile | The LLM triple-emission path: on each turn the model may emit a durable fact, and `upsert_fact` writes it. Deferred, because it touches the prompt | `src/memory.py:upsert_fact`, `resolve_current_facts` |
| 12 | [Zep](https://github.com/getzep/zep) | Temporal knowledge graph — edges carry validity intervals, not just facts | A fact superseded today must not be deleted; it must be closed. `filter_superseded_rows` already implements the temporal read; the graph write is the missing half | `src/memory.py:filter_superseded_rows`, `src/skills/knowledge_graph.py` |
| 13 | [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) | Five primitives (Intelligence, Engine, Agents, Tools, Learning) with nothing else | A useful audit lens: Sara's five folders map 1:1 (gateway / bot / agent_manager / tools / evolution+self_evolution). Confirms no missing subsystem | `src/gateway.py`, `src/bot.py`, `src/agent_manager.py`, `src/tools.py`, `src/evolution.py` |
| 14 | [obsidian-memory-for-ai](https://github.com/jrcruciani/obsidian-memory-for-ai) | Associative linking in a plain Markdown vault | Already native: `zettel_link` and the note graph. No work; listed so the ADR-21 knowledge-graph decision is traceable to a source | `src/vault.py:318`, `src/skills/knowledge_graph.py` |
| 15 | [traceAI](https://github.com/future-agi/traceAI) / [Langfuse](https://github.com/langfuse/langfuse) | OpenTelemetry GenAI semantic conventions: session, trace, LLM/tool/reasoning spans | Adopt the *span taxonomy*, not the vendor. The console tracer already exists as a shadow sink; making it OTel-shaped is a naming change, not a dependency | `src/telemetry.py`, `scripts/live_shadow_tracer.py` |
| 16 | [LAYAA / laya](https://github.com/NandhaKishorM/laya) | Non-autoregressive System-1 decision model: typed decisions with a probability distribution, one forward pass, no generation | A local reflexive pre-filter that decides *which tier* answers, before any network call. Sub-10 ms was the dossier's claim; the repo states **33 ms** for a single forward pass (§8.1) | PROPOSED `src/skills/reflex_gate.py` — deliberately **not** adopted as a dependency; see §2.2 |
| 17 | [JevRouter](https://github.com/BillionsBobby/JevRouter) | *"Jev owns the decision probabilities; JevRouter owns availability, permissions, risk and confirmation."* Nothing executes implicitly; receipts carry provenance hashes | The cleanest statement of the split Sara already implements, and the sharpest available critique of it: `deduce()` currently returns a probability **and** the dispatcher decides execution in the same pass. Separating them is §5.1 | `src/cognition.py:513` (`deduce`), `src/skills/capabilities.py:353` (`IRREVERSIBLE_TOOLS`) |
| 18 | [Jev decision layer](https://github.com/qualixar/jev-decision-layer) | MCP layer that routes bounded choices and records a receipt for each; *"the model recommends; the host retains execution authority"* | The receipt-per-decision idea, made concrete in the tracer. Its speed/cost figures are vendor-published, not repo-measured (§8.1) | `scripts/live_shadow_tracer.py` |
| 19 | [ReasoningBank](https://arxiv.org/abs/2509.25140) (ICLR 2026, Google Research) | Distills generalizable strategies from **self-judged successful and failed** experiences; items stored as `{title, description, content}` | Direct upgrade to `distill_chains`, which today only counts repeated chains and drops failures. The schema is small enough to adopt verbatim | `src/evolution.py:30`, `src/cognition.py:172` (`ReflectiveTrace`) |
| 20 | [Mojito](https://github.com/TimeLovercc/mojito) | A maintainer agent session that rewrites the app from chat feedback, classifies each change `auto` or `ask`, then ships it | The blueprint in §3. Its own `CLAUDE.md` and `SECURITY.md` are the source of the comparative analysis in §4 | §3, §4 |
| 21 | OpenClaw plan tools (in-repo, `src/openclaw/`) | A single-source tool list expanded by reference rather than duplicated | Proof that the "one list" pattern works here: `*VALID_OPENCLAW_TOOLS` is spliced into `_VALID_TOOLS` instead of copied. The same trick is required for dynamic tools (§3.5) | `src/dispatcher.py:168`, `src/openclaw/intents.py` |
| 22 | `importlib` cache invalidation (Python stdlib) | A module already imported into a running process can be re-read without restarting the interpreter, provided the finder caches are invalidated first | The technical basis of hot-reload: `importlib.invalidate_caches()` then `import_module`. The honest limit — a module's globals are *not* re-executed, so a changed file needs a restart | PROPOSED `src/skills/dynamic/loader.py` |
| 23 | [pytest fixtures + `monkeypatch`](https://docs.pytest.org/en/stable/how-to/fixtures.html) | Dependency injection at the test seam; frozen clocks | The already-established reason the P1–P3 work was possible: `now_fn=` seams on every worker. A new subsystem without a clock seam is not acceptable here | `src/skills/self_evolution.py:52`, `src/tools.py:135` |
| 24 | [Coverage gating](https://coverage.readthedocs.io/) | Per-module thresholds, not a single global number | The 98%-per-core-module rule is what makes self-evolution safe: a synthesized tool lands in a repo where partial coverage fails the build | `scripts/check_tiered_coverage.py` |

### 2.2 The disposition rule

The standing rule is **zero new external packages**, and the earlier 10-repository audit
behind this programme recorded **0 ADOPT / 5 ADAPT / 1 DEFER / 4 REJECT**. This matrix
widens the same rule to 24 resources. Rows 1–24 are therefore *architectural references*,
not a dependency list. Concretely:

- **ADOPT the pattern, not the library.** JevRouter's decision/execution split, ScaleMCP's
  insight that `markers` is the reachability key, ReasoningBank's `{title, description,
  content}` schema, and Mojito's `auto`/`ask` triage are all implementable in
  ~200 lines of existing-stack code.
- **REJECT the runtime dependency.** Laya would add a model checkpoint (multi-hundred-MB)
  plus an inference stack to a repo that runs on a free tier with a hard $0.00 invariant.
  A 33 ms forward pass is irrelevant if the model load costs a restart. If the System-1
  gate is wanted, §5.1 specifies it as a deterministic scorer over features
  `cognition.evaluate_candidates` already computes in the same call — no weights, no
  network, and testable with the existing suite. Its latency is not claimed here; it
  would be measured before it mattered.
- **REJECT MCP as a tool-transport.** ScaleMCP's premise is that tools live on remote MCP
  servers. Sara's tools are local Python callables behind `ToolRegistry.call`. Adding a
  transport to reach them would add failure modes and a network hop for no new capability.

---

## 3. The Mojito pattern: Sara self-evolution blueprint

### 3.0 What mojito actually does (verified from its own docs)

Quoting structure, not prose — see the linked files for the full text.

- A **maintainer session** (a long-running Claude Code session in the user's private
  checkout) polls a hub with a `maintainer` token, picks up **feedback** items, edits
  code, checks that it builds, and ships.
- Items move `open → triaged → awaiting_approval → fixing → shipped | declined`.
- Each item carries a ship mode, `auto` or `ask`. The auto/ask rules are a table:
  UI and copy ship alone; API and data-structure changes, migrations, credentials,
  new dependencies, and deletions always ask.
- `CLAUDE.md` states: *"no test files unless explicitly asked. the release gates are type
  checks and builds."*
- `SECURITY.md` states: *"The auto/ask gate is not enforced in code"*, and the maintainer
  token can set any status, including `shipped` straight from `awaiting_approval`.

That last admission is the entire reason this blueprint is not a copy.

### 3.1 Stage 1 — gap detection and `EvolutionTask` self-generation

**Trigger (two, and only two):**

1. **Explicit.** Omar says «تعلمي كيف أسوي فلان» / «add a tool that …».
2. **Implicit.** The router's vocabulary fails. `cognition.deduce`
   (`src/cognition.py:513`) returns a hypothesis below its confidence threshold while the
   utterance contains a verb cluster matching no entry in `_TOOL_GOALS`
   (`src/cognition.py:30`).

**Those two failures are different problems and must be diagnosed differently.** A verb
cluster that *is* in the vocabulary but scored low means a marker needs one line in
`_TOOL_GOALS` — a registry fix, not a synthesis. A verb cluster that matches nothing at
all means a tool may be missing, and only *that* case becomes an `EvolutionTask`.
Conflating them is how a system ends up synthesizing forty tools it never needed
(§3.5.2).

**PROPOSED** `EvolutionTask`:

```python
@dataclass
class EvolutionTask:
    # snake_case, ^[a-z][a-z0-9_]{2,39}$, must not collide with
    # TOOL_CAPABILITIES or _VALID_TOOLS
    name: str
    # one line, Amman colloquial, the answer Sara will give
    intent: str
    # {"params": {"arg": {"type": "str"}}, "returns": "str"}
    schema: dict
    # "safe" | "sensitive" — sensitive mandates confirmation_id
    safety_tier: str
    # each becomes one assertion in the generated test
    acceptance_criteria: list[str]
    # the user turns that proved the gap (redacted, quoted)
    evidence: list[str]
    # from distill_chains
    occurrences: int
    # ISO date, drives idempotency
    created_day: str
```

**Backlog:** `State/evolution_backlog.jsonl` — `State/` is already a mandatory scaffold
directory (`src/vault.py:LOCAL_SCAFFOLD_DIRS`), so no scaffolding change is needed.
Append-only, one JSON object per line (JSONL) rather than a rewritten array: a crash
mid-write must not corrupt the queue. The nightly dialect worker already writes through
`VaultClient.upsert` with the same discipline (`src/skills/self_evolution.py:121`).

**Refusal invariant.** A task is never created for a request that is irreversible with
no owner word. `launch`, `close`, `create_event`, `create_task`, `cancel_reminder` and the
OpenClaw pair are permanently closed to synthesis — `IRREVERSIBLE_TOOLS` is the deny-list
and it is asserted disjoint from `PROMOTABLE_TOOLS` by test
(`tests/test_evolution.py::test_promotable_set_never_contains_irreversible`).

**Owner-facing string.** Amman dialect, no technical terms, no promise of completion:

> «هالميزة مش مبرمجة عندي هسا، بس جهزت مواصفات أداة جديدة باسم `xyz` ورفعتها
> لقائمة التطوير الذاتي. بتتنفذ لما توافق، وبتطلع للتجربة قبل ما تشتغل معاي.»

The claim is accurate: the task is queued, not built. Nothing in the pipeline may tell
Omar a tool is ready before §3.5 has run.

### 3.2 Stage 2 — automated synthesis

**PROPOSED** `scripts/evolution_worker.py`, one job per invocation, run **outside** the
bot process.

Isolation is the point: a synthesis worker sharing memory with the live bot can take the
bot down with it. The worker therefore imports neither the bot runtime nor
`src/evolution.py`'s callers — it receives a single `EvolutionTask` on stdin and writes
exactly two files:

- `src/skills/dynamic/<name>.py` — the tool module
- `tests/suite/dynamic_tools/test_<name>.py` — its test suite

`src/skills/dynamic/__init__.py` ships **empty in version control**. That emptiness is the
point: a directory containing synthesized code is a directory nobody reviewed. A tool
reaches `main` only through the gate in §3.4, as an ordinary reviewed commit — at which
point it is no longer a dynamic tool, and the overlay exists for the cases that genuinely
cannot be committed.

**The synthesizer is OpenCode, not a runtime call.** Sara has no business embedding a
code-generation model in her turn loop: it would put a second, ungated, un-metered
generator behind the same prompt surface. The synthesis step is a maintainer action, the
same class of action as a schema migration.

**The tool's shape** is fixed by the registry, not by the model:

```python
async def run(arg: str) -> str:   # returns Amman colloquial, never raises
```

`ToolRegistry.call` already catches every exception and returns `TOOL_FAIL_AR`
(`src/tools.py:144`), so an honest-failure contract is the existing contract, not a new
requirement.

### 3.3 Stage 3 — the AST security and integrity gate

`verify_proposal_code` (`src/evolution.py:44`) already parses the candidate and enforces
two rules. Stage 3 extends it to five, and the two new ones are the ones mojito lacks
entirely:

| Rule | Enforcement | Status |
|---|---|---|
| Import allow-list | `ast.Import` / `ast.ImportFrom` against `ALLOWED_IMPORTS` (8 stdlib modules) | **VERIFIED** — `src/evolution.py:18` |
| No dynamic execution | `eval`, `exec`, `compile`, `__import__`, `open` rejected as bare `ast.Call` on `ast.Name` | **VERIFIED** — `src/evolution.py:21` |
| No ambient authority (names + attributes) | reject `confirmation_id`, `_secrets`, `getattr`, `setattr`, `__dict__`, `globals`, `locals` as `ast.Name` / `ast.Attribute`, reason `ambient authority: <token>`; bare `id()` is excluded (would ban the innocent builtin — owner ruling pending) | **Implemented** — `src/evolution.py:AMBIENT_AUTHORITY_NAMES` |
| No secret-bearing strings | reject any string literal containing an ambient token, including `.env` (not a valid identifier, so string-only); this is what rejects `Path(".env").read_text()`; multiple violations joined with `"; "` | **Implemented** — `src/evolution.py:AMBIENT_STRING_TOKENS` |
| No dynamic import (`importlib`) | `import importlib` / `from importlib import …` rejected with `forbidden import: importlib` (closes the `__import__` bypass) | **Implemented** — `src/evolution.py:FORBIDDEN_IMPORTS` |
| Registry containment | every tool name in the chain ∈ `TOOL_CAPABILITIES`; ∩ `IRREVERSIBLE_TOOLS` = ∅ | **VERIFIED** — `src/evolution.py:104` |
| Vault read containment | every note the task cites resolves under `OverlayVault.resolve`, whose path guard rejects `..`, absolute and empty paths with `ValueError` | **VERIFIED** — `tests/live_harness/overlay.py:20` |

Two honest limits of the current gate, both inherited and neither fixable by an AST pass:

- **It does not execute code, so it cannot find a bug in code.** That is what §3.4 is for.
  A pass here means "structurally admissible", never "correct".
- **The `open` ban is trivially bypassable** by `pathlib.Path.read_text`, which is
  allow-listed. The `__import__` ban is bypassable by `importlib`. The gate is a
  speed bump against an accidental bad synthesis, not a sandbox against an adversary.
  The real containment is that synthesized code never executes in the bot process until it
  is committed, reviewed and merged.

The "no network sockets to unverified domains" requirement is satisfied by omission rather
than by inspection: `socket`, `http`, `urllib` and `requests` are not in `ALLOWED_IMPORTS`,
so any network use is rejected at the import check. The zero-cost invariant is therefore
structural.

### 3.4 Stage 4 — TDD verification and regression guard

A proposal is promotable only when **all four** hold. This is `promotion_decision`
(`src/evolution.py:151`), which today takes two booleans; Stage 4 supplies them from
real runs, not from a human's word.

| # | Gate | Command | Failure mode it catches |
|---|---|---|---|
| 1 | New tool's own tests | `pytest tests/suite/dynamic_tools/test_<name>.py` (proposed path) | The tool does not do what its acceptance criteria say |
| 2 | Full baseline | `pytest -q -p no:cacheprovider --no-cov` | The tool broke something else |
| 3 | Coverage | `scripts/check_tiered_coverage.py` | The tool landed untested |
| 4 | Lint + security | `ruff check`, `ruff format --check`, `scripts/security_gate.py` | Style drift, secret, banned import |

Mojito's release gate is *"type checks and builds"*, and its `CLAUDE.md` forbids writing
test files. That is the single sharpest difference between the two systems, and it is
worth stating plainly: **a self-rewriting agent with no test gate is not self-improving,
it is self-diverging.** The four gates above are what make "improving" a defensible word.

Gate 3 needs one addition the current script does not have: a synthesized tool in
`src/skills/dynamic/` must be added to the per-module 98% list, so a synthesized tool
cannot hide in a directory the coverage gate does not walk.

### 3.5 Stage 5 — hot-reload and live registration

This is the stage where the honest engineering is, because **registering a tool is not
one edit.** There are four independent registration points, and three of them are static:

| # | Registration point | Kind | File |
|---|---|---|---|
| 1 | `ToolRegistry._do_<name>` | `getattr` on the instance — runtime-bindable | `src/tools.py:138` |
| 2 | `TOOL_CAPABILITIES[<name>]` | dict, mutable at runtime | `src/skills/capabilities.py:350` |
| 3 | `_VALID_TOOLS` | `Final` tuple — **not** runtime-mutable | `src/dispatcher.py:123` |
| 4 | `_TOOL_GOALS[<name>]` | `Final` dict — **not** runtime-mutable | `src/cognition.py:30` |

Points 3 and 4 are the trap. A router reply naming a tool outside `_VALID_TOOLS` is
silently rewritten to `"none"` (`src/dispatcher.py:730`), and `deduce` can never *propose*
a tool whose goal vocabulary is absent — so a tool registered only in
`TOOL_CAPABILITIES` is a tool Sara can never select, and a tool spliced into
`_VALID_TOOLS` without a `_TOOL_GOALS` entry is a tool she can never reach. Neither
failure raises; both present as "the feature just doesn't work."

Therefore:

- **3.5.1 — Refactor before enabling.** A runtime-mutable overlay — `OVERLAY`, a plain
  `dict` in a new third module, `src/tool_overlay.py` — is merged onto the static base by
  two accessors, `valid_tools()` and `tool_goals()`. The five production consumers read
  through them: `src/dispatcher.py:730` (the silent `"none"` rewrite), `src/cognition.py:416`
  (`deduce`'s goal iteration), `src/decision_loop.py:217`, `src/agent_manager.py:110`, and
  `src/evolution.py:195`.

  Three properties of that placement are load-bearing, and two of them contradict the
  obvious design:

  - **The `Final` literals stay.** `_VALID_TOOLS` and `_TOOL_GOALS` keep their names,
    their types and their `Final` annotation. They are not replaced and not unfrozen —
    they remain the static base, and the refactor works *around* `Final` rather than
    removing it. Nine test modules import `_VALID_TOOLS` by name and one imports
    `_TOOL_GOALS`; renaming or retyping either breaks all ten. Only the *production*
    consumers move to the accessors; the tests keep reading the base, which is correct
    precisely because the overlay is empty.
  - **The overlay lives in a third module, not in either consumer.** `src.dispatcher`
    already imports `src.cognition`, and cognition does not import dispatcher, so neither
    can host the overlay without an import cycle. `src/tool_overlay.py` therefore imports
    the two base registries *inside* its accessors, keeping itself an import leaf.
  - **A colliding overlay key UNIONS with the static goals; it does not replace them.** A
    plain `dict(base) | overlay` is the reflexive implementation and it is wrong: on an
    accidental collision it silently *shrinks* a tool's detection vocabulary — the exact
    silent-degradation class this refactor exists to eliminate. `_goal_markers`
    (`src/cognition.py:399`) already unions two goal sources via `dict.fromkeys`, so
    `tool_goals()` follows that house convention. `valid_tools()` appends overlay keys
    *after* the base, preserving base order, and returns a `tuple` because the importing
    call sites depend on `in`, iteration and `set()` over it.

  The overlay **ships empty**. This phase registers nothing and is revertible in one
  commit; P3-D enables an actual tool. `tests/test_tool_overlay.py` pins the merge with a
  parametrized guard over all **46** routed names (the capability registry holds 42 — the
  four routed-but-uncatalogued names are `analytics`, `cloud_backup`, `none` and
  `quota_safety`), so a dropped name names itself rather than surfacing as a set difference.

  Two constraints are **latent and, today, blind to the overlay** — both are stated at
  their call sites in `src/` rather than here, and both are P3-D's to close:
  `tests/suite/tier1_resilience/test_contextual_routing.py:37` requires every valid tool to
  appear in `_ROUTER_PROMPT_AR`, which is a static literal, so an overlay tool passes that
  guard while being *unemittable by the router* — the router may only name tools its
  catalog lists; and `tests/suite/tier1_resilience/test_skill_standard.py:25` requires every
  `_TOOL_GOALS` key to exist in `TOOL_CAPABILITIES`, which would let an overlay tool skip
  the capability schema, the narration guide and the `_do_<name>` handler that
  `ToolRegistry.call` `getattr`s. Passing either guard is therefore *not* evidence the tool
  runs.
- **3.5.2 — Two distinct failure modes, two distinct fixes.** If the verb cluster *is*
  reachable but scored low, the fix is one line in `_TOOL_GOALS`. If the verb cluster is
  unreachable, it is a synthesis candidate. The classifier in §3.1 must decide which, and
  the backlog must record which it chose.
- **3.5.3 — Hot-reload mechanics.** `importlib.invalidate_caches()`, then
  `importlib.import_module`, then bind the resolved `run` into the overlay. Import happens
  in a subprocess first, so a module-level `raise` cannot take the bot down during load.
  The module is imported **exactly once per session**; a second import of a changed file
  requires a restart, and the interface says so rather than pretending otherwise.
- **3.5.4 — What hot-reload explicitly does not do.** It does not reload `persona.py`,
  `gateway.py`, `config.py` or `.env`. The production-file lock is absolute, and a
  synthesized tool has no path to those files because they are not in `ALLOWED_IMPORTS`
  and not on any write path the pipeline has.
- **3.5.5 — Runtime is not persistence.** A dynamically bound tool lives in memory until
  restart, and `CompositionCache` already models this shape correctly: in-memory, cleared on
  restart, `clear()` as a full reset. Follow it rather than inventing a second lifecycle.
- **3.5.6 — Docs and manifests move with the code.** The gate is not complete until
  `scripts/docs_guard.py` passes and the checkpoint ledger records the promotion. This is
  the same docs-before-code discipline mojito's `CLAUDE.md` mandates and does not enforce.

### 3.6 Lifecycle, mapped onto the 4-tier workflow

`docs/16-WORKFLOWS.md` already defines the four tiers and the Mandatory Skill Lock. The
evolution pipeline adopts them rather than inventing a fifth:

| Tier | Evolution work | Gate |
|---|---|---|
| DAILY | Gap detection, `EvolutionTask` creation, backlog append | Nightly tick, idempotent per day |
| LIBRARY | Synthesis, own tests, AST gate, full-suite run | The four gates in §3.4 |
| **PROMOTION** | Overlay refactor, first dynamic registration | **Owner word + all four gates green** |
| SOVEREIGN | Irreversible tier, persona, model pins, production files | Never reachable by synthesis — closed by construction |

`promotion_decision` requires `report.passed and owner_approved and suite_green`. All
three, conjunctively, with no override path. The absence of a code-enforced override is
the point: in mojito, the same gate is documented and unenforced.

---

## 4. Comparative analysis: AST-gated TDD vs unconstrained self-rewriting

| Dimension | Mojito (as documented by itself) | Sara's design | Why the difference matters |
|---|---|---|---|
| Release gate | Type check + build; `CLAUDE.md` forbids test files | Full baseline suite + new-tool suite + per-module coverage + lint + security gate | Without a test gate, a rewrite is a random walk. The single most important line in this document. |
| Auto/ask gate | **Not enforced in code.** The maintainer token can set any status, including `shipped` from `awaiting_approval` | `promotion_decision` returns a bool; there is no code path that skips it | A documented gate is a social gate. It fails under exactly the conditions that matter: when the model is confident. |
| Which files changed | *"Nothing checks which files a change touched"* | The AST gate scopes the candidate; the four registration points in §3.5 are enumerated and tested | Unconstrained edits drift into the wrong subsystem. The blast radius must be knowable before the commit, not after. |
| Model's authority | The maintainer session is *"roughly root on your devices"*; it edits and deploys | The synthesizer runs in a separate process, writes two files, and its output is a commit proposal | Separating the generator from the runtime means a bad synthesis costs a rejected file, not a running bot. |
| Tool execution | Full capability to change code, calendar, and data | `ToolRegistry.call` catches every exception; `IRREVERSIBLE_TOOLS` (6) always demands `confirmation_id`; `PaidModelBlockedError` blocks paid models | Failure containment is a property of the runtime, not of a policy document. |
| Prompt injection | Present and acknowledged in `SECURITY.md`; mitigated by "treat as data, not instructions" | Same law, same place — `src/persona.py:84` — and the same mitigation is *documented, not enforced* | Honest accounting: this is the shared residual risk, and it is the reason `synthesize` is a maintainer action, never a turn. |
| Blast radius of a mistake | Data, calendar, code, deployments | Two files in version control, gated by four commands | |

**The residual risk, stated plainly.** Both systems share one unmitigated hole: text from
email, calendar, notes and feedback is data, and both rely on the model honouring that
distinction. Sara's structural answer is that the synthesis path is not reachable from a
turn — there is no tool that spawns the synthesizer. Mojito's is that the maintainer token
is scoped. Sara's is stronger because the capability is absent rather than constrained,
but neither system has solved injection against the *dialogue* lane, and neither should
claim to have.

---

## 5. Multi-model orchestration and the System-1 gate

### 5.1 Two-layer decision, split the way JevRouter describes

JevRouter's contract — *the model owns probabilities, the router owns availability,
permissions, risk and confirmation* — is a critique of Sara's current shape, not a
praise of it. Today `FrontDoorDispatcher` holds the verdict and the execution decision
together (`src/dispatcher.py:782`, `:995`). Split them:

- **System 1 (reflex gate).** A deterministic scorer over features `deduce` already
  computes — marker hits, connector-separated action density, `ReflectiveTrace.penalty`
  (`src/cognition.py:185`), and turn count from `src/turn_counter.py:read_turn_count`.
  Output: `(tier, confidence)`. No network, no weights, no second pass over the utterance,
  and every branch is reachable from the existing suite. The three human reflexes (§5.3)
  are inputs here, not prompt text.
- **System 2 (the LLM).** Called only when System 1's confidence is below threshold, or
  when the request crosses into `IRREVERSIBLE_TOOLS`. Its output is still a *proposal*:
  the dispatcher applies availability, permission, risk and confirmation afterwards.

This is the whole of the JevRouter lesson, and it costs no dependency.

### 5.2 Tier roles as configured today

| Tier | Model (`.env.example`) | Role | Measured behaviour (probe of 2026-09-18; raw data in [the probe report](../../benchmarks/CANDIDATE_MODELS_PROBE_REPORT.md)) |
|---|---|---|---|
| FAST | `groq/openai/gpt-oss-120b`, fallback `google/gemma-4-31b-it:free` | Voice, ack, routing | 1.6 s TTFT at best, 25 s at worst — high variance |
| MEDIUM | `openrouter/nex-agi/nex-n2.5-mini:free` | Sub-agent fleet workers | **HTTP 404 on the BARE form** — the bare `nex-agi/...` slug has no route; the `openrouter/`-prefixed form of the same model answers |
| HEAVY | `openrouter/nex-agi/nex-n2.5-pro:free`, fallbacks `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`, `groq/openai/gpt-oss-120b` | Orchestrator above 3 concurrent tasks | Pro streams via the `openrouter/` fallback: 6 s, valid Arabic 3-step DAG |
| Escalation | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | 550B MoE | Returns an empty stream; quarantined |

The `nex-agi/*` failure was a **slug-form** problem, not a pool problem: the same
models answer when addressed as `openrouter/nex-agi/…`. **RESOLVED 2026-09-30** —
`MEDIUM_MODEL` and `HEAVY_MODEL` are re-pinned to the prefixed form in `.env.example`
and the live `.env`; the two tiers no longer pay a wasted 404 round trip per turn. The
probe verdict is otherwise unchanged: **hold all pins**, because FAST variance is still
too high to pin against.

Topology mapping, given what already exists:

- **Sequential** — `AgentManager._run_line` (`src/agent_manager.py:191`) already serializes
  steps within a line.
- **Concurrent** — `asyncio.gather` at `src/agent_manager.py:247`. Needs a bound; an
  unbounded fan-out against a free pool metered at 50 requests/day/account (per
  `.env.example`) is a quota event, not a feature.
- **Handoff** — HEAVY→FAST escalation should be an explicit handoff with a receipt, not a
  silent tier switch inside the gateway.
- **Group chat** — not applicable. Sara has one interlocutor.

### 5.3 The three human reflexes as System-1 inputs

These are persona behaviours, currently encoded as prompt prose in
`src/persona.py:64-69` (self-correction, the thinking pause, the relief sigh before
reporting completion, the light laugh before a joke) plus the emoji-drop rule at `:76-79`.
Encoding them twice — once as prose, once as a scorer feature — invites drift, so
System 1 must **read** the reflex state rather than re-decide it:

| Reflex | Detection (deterministic) | Effect on the turn |
|---|---|---|
| Pre-empathy sighing | Interrupting marker while a long operation is in flight (`Scratchpad` has pending observations, `src/decision_loop.py:185`) | Acknowledge first, answer after; do not cold-start the tool |
| Banter vs serious | `situational.py:SituationalState` posture + whether the last turn carried a task marker | Serious posture suppresses emoji and banter; banter posture permits them |
| Incomplete thought | No terminal verb, or a trailing conjunction, in a clause that already matched a marker | Ask one clarifying question instead of guessing an argument |

The third is the one worth building first: it is pure syntax, it is testable without a
model, and it prevents the worst failure mode in the catalogue — a confidently wrong tool
argument. `normalize_tool_arg` (`src/decision_loop.py:65`) is the existing seam.

### 5.4 Memory and RAG, honestly scoped

- **Zep-style temporal facts** — the read half is done: `upsert_fact`,
  `resolve_current_facts`, `filter_superseded_rows` (`src/memory.py`). The write-to-graph
  half is not. Cost of doing it: one call site.
- **Mem0-style preference extraction** — deferred, deliberately. It changes the prompt,
  and the prompt is where the ar-JO invariant and the injection law live. Not on the same
  branch as a self-rewriting engine.
- **BM25** — `src/bm25.py` is built, tested, and unwired. It is the cheapest
  hybrid-retrieval step available and the p95 budget is the only argument needed.
- **The ceiling is the real limit.** `compose_rag_block` runs under a 600-character
  injection ceiling (`INJECT_MAX_CHARS`) and halves it under quarantine. More retrieval
  quality will not raise it. Raise the ceiling only with a measurement.

---

## 6. Implementation roadmap

Each phase states the assertions that must exist and pass. Every phase is TDD: write the
test, watch it fail, implement, watch it pass. A phase is not done until the full gate
set is green and the checkpoint ledger is updated.

### P3-A — Gap detection and the backlog (no synthesis, no risk)

- `EvolutionTask` validates `name` against `^[a-z][a-z0-9_]{2,39}$` and rejects any name
  present in `TOOL_CAPABILITIES` or `_VALID_TOOLS`.
- `safety_tier="sensitive"` is forced for any task naming a member of `IRREVERSIBLE_TOOLS`,
  regardless of what the task declares.
- Appending two tasks with the same `name` and `created_day` is idempotent.
- A malformed JSONL line is skipped, not fatal — a corrupt queue must not stop the worker.
- A low-confidence-but-reachable utterance produces a *marker* task; an unreachable verb
  cluster produces a *tool* task. The two are never conflated.
- The owner-facing Amman string is asserted verbatim, including that it promises
  nothing about completion.

### P3-B — Synthesis sandbox and gate hardening

- The three new AST rules (§3.3) reject `confirmation_id`, `.env`, `getattr`, and
  `importlib` in synthesized source, each with a named reason string
  (`ambient authority: <token>`, `forbidden import: importlib`); a candidate
  tripping several rules joins them with `"; "` so each names its rule.
- `import socket` / `import requests` are rejected — the zero-cost invariant is
  structural, not policy.
- A candidate importing only `re` and `json` passes.
- `verify_proposal_code` on syntactically invalid source returns `(False, "syntax error: …")`
  and never raises.
- `evaluate_proposal` never executes the candidate: a module that would raise on import
  still yields a `PromotionReport`, not an exception.
- `OverlayVault.resolve` rejects `..`, absolute paths, and empty paths with `ValueError`,
  and synthesized code cannot write outside the shadow root.

### P3-C — Registration overlay refactor (ship empty)

- The merged tool set equals the static set for all **46** routed names, and the merged
  goal map equals the static map for all **37** goal keys — parametrized test over the
  whole catalog, so a refactor cannot silently drop a tool.
- `_VALID_TOOLS` and `_TOOL_GOALS` **remain** `Final` literals and remain the static base;
  the five *production* consumers read through `valid_tools()` / `tool_goals()`. They are
  not unfrozen and not renamed — ten test modules import them by name. A colliding
  overlay key unions its goal markers with the static ones rather than replacing them.
- A tool present in the overlay but absent from `TOOL_CAPABILITIES` is rejected at
  registration time.
- With an empty overlay, the full suite passes unchanged — **this phase ships with zero
  dynamic tools enabled**, and is revertible in one commit.

### P3-D — First live registration, owner-gated

- `promotion_decision` requires all three inputs; each single-input omission is tested
  independently, not as one combined case.
- A hot-loaded tool is callable within the same session with no daemon restart, and
  `importlib.invalidate_caches()` is asserted to have run.
- A module that raises at import time fails the load and leaves the previous binding
  intact — the bot keeps serving.
- `CompositionCache.clear()` and a process restart both fully reset dynamic bindings, with
  no persistence file written.
- Post-promotion: `docs_guard.py` 16/16, `check_tiered_coverage.py` PASSED, the new
  module added to the 98% list, and `docs/10-CHECKPOINT.md` updated in the same commit.
- The **four invariants are asserted, not assumed**: feminine/masculine forms, no Edge-TTS
  import in the new module, no `confirmation_id` minted, no paid model referenced.

### Explicitly not in P3

- Any edit to `src/persona.py` (reformat-locked), `src/gateway.py`, `src/config.py`,
  `.env`.
- Any new external package.
- Anything that would let a *turn* trigger synthesis.
- GraphRAG (trigger: >10k notes), native UI automation depth, fleet orchestration across
  machines — all deferred on their existing scale triggers.

---

## 7. What this document does not authorize

- It does not change a model pin. As originally scoped it left `MEDIUM_MODEL` and
  `HEAVY_MODEL` on the bare `nex-agi/*` slugs that 404 — that part was superseded
  by the Leader's 2026-09-30 decision, which re-pins both to the `openrouter/`
  form. Every other pin is still untouched.
- It does not read or modify `.env`.
- It does not create a runtime synthesizer. Synthesis is a maintainer action in a separate
  process.
- It does not register any tool. P3-C ships with an empty overlay by design.
- It does not adopt an external runtime dependency. Zero new packages, unchanged.

---

## 8. Corrections to the source dossier

Recorded because the dossier is a working document and these three claims would not
survive contact with the sources.

### 8.1 Verified discrepancies

| Dossier claim | Upstream actually says | Consequence for this design |
|---|---|---|
| LAYAA is a "sub-10ms local decision engine on CPU/DirectML via FP16 ModernBERT/mmBERT" | The [laya README](https://github.com/NandhaKishorM/laya) describes a *multilingual non-autoregressive System 1 decision engine*, "typed decisions over 100+ languages in a single forward pass — **33 ms**", trained with RLCD | The number is 33 ms, not sub-10 ms, and the architecture is a typed decision model, not a ModernBERT classifier. §5.1 therefore specifies a **deterministic scorer**, not a checkpoint — the $0.00 invariant rules out shipping weights regardless of latency |
| Jev / Jev decision layer deliver the claimed speed and cost advantages | The 193.6×/444.6× figures and the $0.042/M input price are **TypeSafe's published claims**, cited by the [qualixar repo](https://github.com/qualixar/jev-decision-layer), not measurements in it | Citable as vendor-published, not as repo-verified. Sara borrows the architecture and none of the numbers |
| The "46 cataloged capabilities" Sara has to detect gaps against | `TOOL_CAPABILITIES` contains **42** entries | §3.1's collision check tests against 42, not 46. The gap predicate is unchanged; the count was wrong |

### 8.2 Confirmed as described

- **Mojito** is real, MIT, alpha, and does exactly what the dossier says: a maintainer
  agent session that rewrites and ships the app from chat feedback, with an `auto`/`ask`
  triage. Its `SECURITY.md` and `docs/self-rebuild-loop.md` were fetched and quoted
  directly in §3.0 and §4.
- **ScaleMCP** is arXiv:2505.06416 (Lumer et al., 9 May 2025); MCP tool retriever, CRUD
  synchronization against MCP servers as single source of truth, TDWA weighted tool-document
  embeddings. §2 row 9 adopts the insight, rejects the transport.
- **ReasoningBank** is arXiv:2509.25140, ICLR 2026 poster, Google Research. It distills from
  self-judged successes **and failures**, storing `{title, description, content}`.

---

## 9. Evidence ledger

Fetched and read during authoring, 2026-09-30:

- <https://github.com/TimeLovercc/mojito> — `README.md`, `docs/self-rebuild-loop.md`,
  `SECURITY.md`, `CLAUDE.md`
- <https://github.com/NandhaKishorM/laya> — `README.md`
- <https://github.com/BillionsBobby/JevRouter> — `README.md`
- <https://github.com/qualixar/jev-decision-layer> — `README.md`
- <https://github.com/facebookresearch/HyperAgents> — `README.md`
- <https://export.arxiv.org/abs/2505.06416> — abstract
- <https://arxiv.org/abs/2509.25140> — ReasoningBank abstract and memory-extraction schema

The remaining matrix rows — the orchestration frameworks, the memory systems, the tracing
vendors, and the testing/CI rows — are architectural references read from the dossier and
from each project's public documentation. They were **not** individually fetched in this
session, and no behavioural claim about them is load-bearing for the roadmap in §6. Where a
row makes a specific claim about a specific project, it is either one of the sources
listed above, or it says on its face that it is unverified (matrix row 7).

Read from this repository at `755c490`: `src/skills/capabilities.py`, `src/evolution.py`,
`src/cognition.py`, `src/decision_loop.py`, `src/dispatcher.py`, `src/tools.py`,
`src/memory.py`, `src/bm25.py`, `src/associative.py`, `src/telemetry.py`,
`src/agent_manager.py`, `src/pc_actions.py`, `src/persona.py`, `src/vault.py`,
`src/gateway.py`, `src/config.py`, `src/cognitive_dag.py`, `src/voice_policy.py`,
`src/turn_counter.py`, `src/situational.py`, `src/openclaw/intents.py`,
`src/skills/self_evolution.py`, `src/skills/knowledge_graph.py`,
`tests/live_harness/overlay.py`, `tests/test_evolution.py`, `tests/live_harness/conftest.py`,
`tests/live_harness/test_h04_ttft_monitor.py`, `scripts/check_tiered_coverage.py`,
`scripts/docs_guard.py`, `.env.example`.

---

## 10. Related documents

- [00 — Map of architecture (MOC)](../00-MAP-OF-ARCHITECTURE.md)
- [10 — Checkpoint ledger](../10-CHECKPOINT.md) — every shipped milestone
- [16 — Workflows: 4-tier lifecycle and the Skill Lock](../16-WORKFLOWS.md)
- [04 — Architecture](../04-ARCHITECTURE.md)
- [09 — Decisions (ADRs)](../09-DECISIONS.md)
- [11 — Testing and gates](../11-TESTING.md)
- [12 — Security](../12-SECURITY.md)
