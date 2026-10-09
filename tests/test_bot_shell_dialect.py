r"""Decision 1 — Terminal 1 must answer in authentic Amman dialect (ar-JO).

MEASURED DEFECT (Directive 3, re-derived from the tree, not from the brief):
`src/bot_shell.py:124` calls `self._front_door.handle(text, history=...)` and never
passes `system`. `FrontDoorDispatcher._plain_messages` (`src/dispatcher.py:1200`)
emits NO system message at all when `system` is falsy, so the FAST conversation
call leaves the model with a bare user turn and it answers in MSA. The seam is
already there and already used by Telegram (`src/bot.py:654` builds the persona,
`:728` passes it as `handle(..., system=system)`); Terminal 1 just never supplies it.

The guards below, in the order they bite:

  1. `build_shell` grows a `system` keyword — the pinned name is `system`,
     matching `handle`'s own keyword, so the terminal and Telegram spell the
     same contract identically. Injected like `gateway` / `settings`, not
     constructed inside the shell.
  2. every turn hands that EXACT prompt to `handle` (identity, not equality:
     a per-turn rebuild would silently drift the dialect mid-session).
  3. the prompt reaches the gateway as `messages[0]["system"]` — the end-to-end
     proof that Terminal 1 is not running on the front door's default.
  4. the import boundary is NARROWED, deliberately and exactly: `src.persona`
     is no longer fully banned (`tests/test_bot_shell_repl.py:173` asserted the
     blanket ban), but exactly ONE symbol is permitted — `build_persona_joda`,
     the single-sourced dialect + gender builder. The literals
     (`SARA_PERSONA_AR`, `JODA_EXEMPLARS_AR`, `JODA_EXEMPLARS_HEADER_AR`) and
     `build_persona` stay banned: the builder is the contract, a copy of the
     literal is the thing that drifts. `src.gender_pipeline`, `src.voice_policy`,
     `src.tools`, `src.pc_actions` and `bridge.executor` stay banned outright.
  5. the masculine-address anchor stays byte-invariant (the Leader's explicit
     condition on this decision).

NON-DUPLICATION (Directive 5). Already pinned elsewhere, NOT re-asserted here:
  * `tests/suite/tier1_resilience/test_persona_extract.py` sha256-pins
    `SARA_PERSONA_AR` (len 4782) and re-pins on every owner-ordered edit;
  * `test_persona_gender.py::test_base_context_locks_masculine_address` and
    `::test_banned_feminine_imperatives_cited_once_as_prohibition` assert the
    anchor words inside the CORE;
  * `test_persona_gender.py::test_omar_lines_masculine_address` checks the
    exemplars only with the loose regex `شوف\w*` — which `شوفيه` still matches.
What is NOT covered anywhere, and is asserted here: (a) the anchor reaches the
COMPOSED JODA prompt — the exact string Terminal 1 will carry once wired, and
(b) the five exemplar lines that address Omar, byte for byte, which no regex can
pin. A feminine-address drift inside an exemplar (`شوفه` -> `شوفيه`) slips past
every existing guard; it does not slip past this one.

Hermetic: no socket, no HTTP, no clock. The end-to-end guard drives a real
`FrontDoorDispatcher` over an `httpx.MockTransport` script, copied from the
established style in `tests/test_dispatcher.py:120-139`.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from src import dispatcher as dispatcher_mod
from src.dispatcher import DEFAULT_ACK_AR
from src.gateway import OmniRouteClient, Tier
from src.persona import JODA_EXEMPLARS_HEADER_AR, build_persona, build_persona_joda
from tests.test_omniroute_gateway import _chunk, _collect, _Scripted, _sse

SHELL_PATH = Path(__file__).resolve().parents[1] / "src" / "bot_shell.py"

# Exactly one symbol of src.persona may reach this module. See module docstring.
PERMITTED_PERSONA_SYMBOL = "build_persona_joda"

# The literals and the raw composer stay out: the builder IS the dialect +
# gender contract, and a copied literal is exactly what drifts.
BANNED_PERSONA_SYMBOLS = (
    "SARA_PERSONA_AR",
    "JODA_EXEMPLARS_AR",
    "JODA_EXEMPLARS_HEADER_AR",
    "build_persona",
)

# Unchanged from tests/test_bot_shell_repl.py — the narrowing above relaxes ONE
# module, not the rest of the boundary.
BANNED_MODULES = ("src.gender_pipeline", "src.voice_policy", "src.tools", "src.pc_actions")

# Chains mirroring tests/test_dispatcher.py:11-32; slug shape is irrelevant here,
# the assertion is about the system message, not the routing.
CHAINS = {
    Tier.FAST: ["groq/openai/gpt-oss-120b", "google/gemma-4-31b-it:free"],
    Tier.MEDIUM: ["nex-agi/nex-n2.5-mini:free"],
    Tier.HEAVY: ["nex-agi/nex-n2.5-pro:free", "groq/openai/gpt-oss-120b"],
}


# The masculine-address anchor, byte-locked. Read from src/persona.py, not
# invented: the sentence from SARA_PERSONA_AR (lines 15-16) and the five Omar
# lines from JODA_EXEMPLARS_AR (lines 102-123).
CORE_ANCHOR_SENTENCE_AR = (
    "وعمر مذكر دايماً: بتخاطبيه بصيغة المذكر المفرد (خبرني، طمني، شوف) — "
    "وعمرك ما تستخدمي صيغة المؤنث معه (خبريني، طمنيني، شوفي)."
)
OMAR_EXEMPLAR_LINES_AR = (
    "بكرا بخلص التقرير إن شاء الله، شوفه لما تفضى",
    "يا ريت نطلع مشوار الجمعة، اعمل حسابك",
    "ماشي، اتفقنا، ذكرني بكرا",
    "مش عارف شو أعمل بالموضوع هاد، ساعدني",
    "الحمد لله خلصت الامتحان، طمني شو رأيك",
)

# The byte-exact fragments that must appear in the COMPOSED prompt.
ANCHOR_FRAGMENTS = (
    pytest.param(CORE_ANCHOR_SENTENCE_AR, id="core-anchor-sentence"),
    *(
        pytest.param(f"عمر: {line}", id=f"omar-line-{index}")
        for index, line in enumerate(OMAR_EXEMPLAR_LINES_AR, start=1)
    ),
)


def _router_verdict(route: str = "direct", ack: str = DEFAULT_ACK_AR) -> httpx.Response:
    body = json.dumps({"route": route, "ack": ack}, ensure_ascii=False)
    return httpx.Response(200, content=_sse(_chunk(body)))


def _shell_mod():
    """Import inside the test body so each guard fails on its own contract."""
    try:
        return importlib.import_module("src.bot_shell")
    except ModuleNotFoundError as exc:  # pragma: no cover -- the module ships
        pytest.fail(f"src/bot_shell.py is not importable: {exc}")


def _shell_source() -> str:
    return SHELL_PATH.read_text(encoding="utf-8")


def _persona_symbols(source: str) -> set[str]:
    """Every `src.persona` symbol the source BINDS, in either spelling.

    Catches the direct form (`from src.persona import build_persona_joda`) and
    the laundered one (`from src import persona` then `persona.SARA_PERSONA_AR`),
    which a plain alias scan would miss. A docstring or comment cannot pass:
    neither is an alias or an attribute.
    """
    tree = ast.parse(source)
    bound: set[str] = set()
    laundered: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        for alias in node.names:
            local = alias.asname or alias.name
            if node.module == "src.persona":
                bound.add(local)
            elif node.module == "src" and alias.name == "persona":
                laundered.add(local)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in laundered
        ):
            bound.add(node.attr)
    return bound


def _imported_modules(source: str) -> set[str]:
    """Dotted module names any import mentions; `from src import x` -> `src.x`."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names if module)
    return names


class _HandleSpy:
    """Front-door double: records the EXACT kwargs of every `handle` call.

    Callable as a factory so `build_shell`'s `FrontDoorDispatcher(...)`
    construction is captured too, and reused as the front door itself.
    """

    def __init__(self, deltas: tuple[str, ...] = ("يا عمر",)) -> None:
        self.deltas = list(deltas)
        self.calls: list[dict] = []
        self.constructions: list[dict] = []

    def __call__(self, *args, **kwargs) -> _HandleSpy:
        bound = dict(zip(("gateway", "settings"), args))
        bound.update(kwargs)
        self.constructions.append(bound)
        return self

    async def handle(self, user_text: str, **kwargs):
        self.calls.append({"user_text": user_text, **kwargs})
        for delta in self.deltas:
            yield delta


def _front_door(monkeypatch, shell_mod, spy: _HandleSpy) -> None:
    """Intercept the class on both import spellings bot_shell might use."""
    monkeypatch.setattr(dispatcher_mod, "FrontDoorDispatcher", spy)
    monkeypatch.setattr(shell_mod, "FrontDoorDispatcher", spy, raising=False)


def _bound_system(shell_mod, args: tuple, kwargs: dict) -> object:
    """Resolve the `system` argument by NAME, so position or keyword both pass."""
    bound = inspect.signature(shell_mod.build_shell).bind(*args, **kwargs)
    bound.apply_defaults()
    return bound.arguments.get("system")


# --- 1. the injection seam ------------------------------------------------------


def test_build_shell_declares_a_system_keyword() -> None:
    """RED: `build_shell(gateway, settings)` has no system prompt parameter.

    The keyword is pinned as `system` to match `FrontDoorDispatcher.handle`
    (`src/dispatcher.py:914`) and the Telegram call site (`src/bot.py:728`), so
    one word names the same contract on both surfaces.
    """
    params = inspect.signature(_shell_mod().build_shell).parameters
    assert "system" in params, (
        "build_shell must accept an injected system prompt; "
        f"its parameters are {list(params)}. Pin the name `system` to match handle()."
    )


async def test_every_turn_hands_the_injected_prompt_to_handle(make_settings, monkeypatch) -> None:
    """RED: the prompt is dropped on the floor — `handle` gets no `system` at all.

    Two typed lines, two identical handovers. Asserted by IDENTITY: a per-turn
    rebuild of the prompt would drift the dialect mid-session while every
    equality check still passed.
    """
    shell_mod = _shell_mod()
    spy = _HandleSpy()
    _front_door(monkeypatch, shell_mod, spy)
    prompt = build_persona_joda()
    shell = shell_mod.build_shell(object(), make_settings(), system=prompt)

    for line in ("مرحبا يا سارة", "شو رأيك"):
        await _collect(shell.turn(line))

    assert [call["user_text"] for call in spy.calls] == ["مرحبا يا سارة", "شو رأيك"]
    assert [call.get("system") for call in spy.calls] == [prompt, prompt]
    assert all(call.get("system") is prompt for call in spy.calls), (
        "the shell must forward the very prompt it was handed, not rebuild it per turn"
    )
    assert len(spy.constructions) == 1, f"front door rebuilt per turn: {spy.constructions}"


async def test_the_prompt_reaches_the_gateway_as_the_system_message(make_settings) -> None:
    """RED: the FAST conversation call carries NO system message at all.

    This is the defect itself, observed the way `tests/test_dispatcher.py:136-138`
    observes it: read the recorded request body. With `system=None`,
    `_plain_messages` (`src/dispatcher.py:1200`) emits only the user turn, so the
    model has no persona and answers in MSA.
    """
    shell_mod = _shell_mod()
    prompt = build_persona_joda()
    script = _Scripted(
        _router_verdict(),
        httpx.Response(200, content=_sse(_chunk("يا عمر"), _chunk(" شو رأيك"))),
    )
    gateway = OmniRouteClient(
        "http://gw.test/v1", "test-key", chains=CHAINS, transport=script.transport()
    )
    async with gateway:
        shell = shell_mod.build_shell(gateway, make_settings(), system=prompt)
        out = await _collect(shell.turn("شو رأيك"))

    assert out[0] == DEFAULT_ACK_AR, f"router ack missing: {out}"
    messages = json.loads(script.requests[-1].content)["messages"]
    assert messages[0] == {"role": "system", "content": prompt}, (
        "the terminal's prompt must be the first message on the wire; got "
        f"{messages[0]!r} — with no system message the model answers in MSA, "
        "not ar-JO"
    )
    assert messages[-1] == {"role": "user", "content": "شو رأيك"}


# --- 2. the narrowed contract boundary (ast, as tests/test_bot_shell_repl.py) ---


def test_shell_binds_exactly_the_permitted_persona_symbol() -> None:
    """RED: the module binds nothing from `src.persona` — no dialect at all.

    The permit list is exactly one symbol. This asserts the PERMIT (the builder
    must actually be used, or the terminal keeps answering in MSA) and the
    EXACTNESS (a second symbol is a second, drifting source of the contract).
    """
    bound = _persona_symbols(_shell_source())
    assert bound == {PERMITTED_PERSONA_SYMBOL}, (
        f"src/bot_shell may bind exactly {{{PERMITTED_PERSONA_SYMBOL!r}}} from "
        f"src.persona; it binds {sorted(bound)}"
    )


@pytest.mark.parametrize("symbol", BANNED_PERSONA_SYMBOLS)
def test_shell_never_binds_a_persona_literal_or_the_raw_composer(symbol: str) -> None:
    """The builder is the single-sourced dialect + gender contract; the literal
    is the thing that can drift. `build_persona` is banned alongside the literals
    because it is the core-only route — a shell wired to it drops the JODA
    exemplars and answers in MSA again."""
    bound = _persona_symbols(_shell_source())
    assert symbol not in bound, (
        f"src/bot_shell must not bind {symbol!r} from src.persona; import "
        f"{PERMITTED_PERSONA_SYMBOL} instead and let the builder own the dialect"
    )


@pytest.mark.parametrize("module", BANNED_MODULES)
def test_narrowing_did_not_reopen_the_rest_of_the_boundary(module: str) -> None:
    """Relaxing ONE module must not relax the rest: gender, voice, tools and the
    PC coordinator stay unreachable, or the safety floor depends on discipline."""
    reachable = _imported_modules(_shell_source())
    assert module not in reachable, (
        f"src/bot_shell must not import {module} — presentation only, the "
        "confirmation gate lives in the dispatcher"
    )


# --- 3. the Leader's condition: the masculine anchor stays byte-invariant ------


@pytest.mark.parametrize("fragment", ANCHOR_FRAGMENTS)
def test_composed_joda_prompt_keeps_the_masculine_anchor_bytes(fragment: str) -> None:
    """The anchor must survive COMPOSITION, byte for byte.

    Bytes read from `src/persona.py` into `CORE_ANCHOR_SENTENCE_AR` and
    `OMAR_EXEMPLAR_LINES_AR` above; nothing here is invented.

    This is a regression lock, GREEN today on purpose — the defect in this
    decision is a MISSING prompt, not a drifted one. What no existing guard
    covers: these fragments inside `build_persona_joda()`'s output, the exact
    string Terminal 1 will carry. `test_persona_gender.py` checks the exemplars
    with `شوف\\w*`, which `شوفيه` still satisfies; only bytes catch that.
    """
    composed = build_persona_joda()
    assert fragment in composed, (
        f"masculine-address anchor drifted out of the composed JODA prompt: "
        f"{fragment!r}. It is byte-locked in src/persona.py and needs owner "
        "sign-off to change."
    )


def test_composed_joda_prompt_still_carries_the_identity_core_and_header() -> None:
    """The dialect is an ADDITION to the identity core, never a replacement for
    it: the composed prompt is the core, then the JODA few-shot block."""
    core = build_persona([])
    composed = build_persona_joda()
    assert composed.startswith(core), "the JODA builder must not rewrite the identity core"
    assert JODA_EXEMPLARS_HEADER_AR in composed
    assert "عمر:" in composed and "سارة:" in composed


# --- 4. production wiring: the terminal's own default must be ar-JO -------------


def test_live_terminal_prompt_carries_the_persona_and_the_joda_exemplars(monkeypatch) -> None:
    """RED: `_live_shell()` supplies no prompt, so the terminal answers in MSA.

    `_live_shell` is the SOLE production constructor of this shell
    (`main` -> `_session` -> `_repl(_live_shell())`, behind `sara.bat -Chat`).
    If the prompt is only ever injected by a test, Terminal 1 stays persona-free
    and this file's other guards pass while the owner still reads MSA.

    Hermetic: `Settings` and `OmniRouteClient` are doubled, so the real `.env`
    is neither read nor required and no socket is opened.
    """
    shell_mod = _shell_mod()
    captured: dict = {}
    real_build_shell = shell_mod.build_shell
    signature = inspect.signature(real_build_shell)

    def _spy_build_shell(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        captured.update(bound.arguments)
        return "SHELL-SENTINEL"

    monkeypatch.setattr(shell_mod, "build_shell", _spy_build_shell)
    monkeypatch.setattr(shell_mod, "OmniRouteClient", lambda *a, **k: object())
    monkeypatch.setattr(
        "src.config.Settings",
        lambda *a, **k: SimpleNamespace(
            omniroute_base_url="http://gw.test/v1",
            omniroute_api_key="test-key",
            fast_chain=CHAINS[Tier.FAST],
            medium_chain=CHAINS[Tier.MEDIUM],
            heavy_chain=CHAINS[Tier.HEAVY],
        ),
    )

    assert shell_mod._live_shell() == "SHELL-SENTINEL"

    system = captured.get("system")
    assert system, (
        "_live_shell built the terminal shell with no system prompt, so "
        "`sara.bat -Chat` runs on the front door's default and answers in MSA. "
        f"Pass system={PERMITTED_PERSONA_SYMBOL}() here."
    )
    assert system.startswith(build_persona([])), (
        "the terminal prompt must carry Sara's identity core"
    )
    assert JODA_EXEMPLARS_HEADER_AR in system, (
        "the terminal prompt must carry the JODA ar-JO exemplars, or the reply "
        "is MSA with a colloquial preamble"
    )
