"""F-1 — the irreversible gate on the path that ACTUALLY RUNS.

THE FINDING, as filed. `IRREVERSIBLE_TOOLS` held seven names and the only
confirmation gate read them at `src/decision_loop.py:428` — on the ReAct branch,
which `react_loop_enabled()` keeps OFF unless `SARA_REACT_LOOP` is set, and which
`src/bot.py` bypasses for every other turn (`front.handle`). The LIVE path —
`FrontDoorDispatcher.handle` -> `ToolRegistry.call` — consulted nothing.
`create_event`, `create_task` and `cancel_reminder` performed Google/local writes
on a router verdict alone. The docs claimed six sensitive tools were gated by
`confirmation_id`; the gate guarded a disabled branch.

THE FIX, and where it lives. `ToolRegistry.call` is the single choke point BOTH
paths share, so one insertion closes both. It gained a keyword-only
`confirmation_id` (backward compatible with all four call sites) and refuses every
member of the deny-list that arrives without a verified id — by RETURNING the
owner's confirmation-request line, never by raising, and never by returning the
generic `TOOL_FAIL_AR` a failure would return: a generic line tells the owner
nothing and is a UX dead end.

WHAT IS DELIVERED, AND WHAT IS NOT
----------------------------------
Delivered, and guarded here:
  * REFUSAL — all six gated names return the Arabic confirmation request and
    touch NOTHING (spy) with no confirmation.
  * A GENUINE id runs the handler; a forged, malformed and expired id does not.
    The check is F-2's `verify_confirmation_id` — a local HMAC recompute over
    the shared `BRIDGE_TOKEN`, so it costs no network call, no vault read and
    no request; it is paid only on the irreversible branch, never on an
    ordinary tool.
  * NO OVER-BLOCKING — every non-irreversible routed name still executes with no
    confirmation at all. Asserted over the WHOLE set, not a sample: a gate that
    blocks reversible tools is a broken gate.
  * THE AUTONOMOUS PATH refuses fail-closed, phrased as PENDING a confirmation
    channel rather than as a permanent ban (§33B.5 is the designed channel).
  * THE DECISION-LOOP ROUTER PROMPT is composed live (`router_prompt()`), so a
    `register_tool` name is emittable from the dormant branch too — hole 1.
  * A HIJACKED SHIPPED HANDLER is refused at the choke point — hole 2.

MEASURED RE-SCOPE, STATED PLAINLY (Directive 3). `close` is NOT gated at the
choke point, and that is a decision with evidence, not an omission:

  * `_do_close` is a pure DELEGATION to `PCActionCoordinator.request_close`, which
    is itself the confirmation channel: it demands `origin="owner_chat"`,
    consults the whitelist, prompts the owner on Telegram, and mints a SIGNED
    `cfm1.*` id on the reply — which the daemon then VERIFIES.
  * A gate at `call` would sit IN FRONT of that channel. The owner's
    «سكّر كروم» would never reach `request_close`, `_pending` would never be
    set, `handle_owner_reply` would never fire, and closing an app would become
    IMPOSSIBLE.
  * Closing it would also have forced edits to `tests/test_close_routing.py`
    and `tests/test_tools_matrix_p65b.py` — the whitelist-guard floor
    `CLAUDE.md` §5 declares untouchable. Over-blocking a tool that already has
    a live confirmation channel is a worse risk than the finding.
  * So the exemption is EARNED by a guard, not by a comment: the two tests below
    drive the real owner round trip and prove `close` cannot terminate a process
    without a verified id on the wire.

The same reasoning is why the dormant ReAct branch keeps its own gate at
`src/decision_loop.py:428` and does NOT gain a second one here: a double gate is
the same defect one layer up.
"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.skills.capabilities import IRREVERSIBLE_TOOLS
from src.tool_overlay import register_tool, reset_overlay, valid_tools
from src.tools import TOOL_FAIL_AR, ToolRegistry

try:  # the names F-1 adds do not exist until the fix lands
    from src.tools import CONFIRM_REQUIRED_AR, IRREVERSIBLE_ACTION_AR
except ImportError:  # pragma: no cover -- the pre-fix state this file is written for
    CONFIRM_REQUIRED_AR = IRREVERSIBLE_ACTION_AR = None

ROOT = Path(__file__).resolve().parents[1]

#: The deny-list as MEASURED on 2026-10-01. Pinned, not imported-and-hoped-for:
#: a silent narrowing is exactly how this finding returns.
IRREVERSIBLE_NAMES = frozenset(
    {
        "cancel_reminder",
        "close",
        "cloud_backup",
        "create_event",
        "create_task",
        "openclaw_browse",
        "openclaw_desktop",
    }
)

#: The six the choke point refuses, and `close`'s reason for being the seventh.
GATED_NAMES = IRREVERSIBLE_NAMES - {"close"}


# -- spies: every irreversible handler's external edge --------------------------------


class SuiteSpy:
    """Google Workspace writes. A recorded call IS the effect F-1 forbids."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.tasks: list[str] = []

    async def create_event(self, summary, start, end):
        self.events.append(summary)
        return {"id": "evt-1"}

    async def add_task(self, title):
        self.tasks.append(title)
        return {"id": "task-1"}


class OrchestratorSpy:
    """The local reminder engine — cancellation is the irreversible part."""

    def __init__(self) -> None:
        self.cancelled: list[str] = []
        self.swept: list[str] = []

    def find_by_time(self, target: str) -> str | None:
        return None

    async def cancel(self, job_id: str) -> bool:
        self.cancelled.append(job_id)
        return True

    async def cancel_all(self) -> int:
        self.swept.append("all")
        return 2


class CloudSpy:
    """Cloud Storage upload — an object Sara can never recall."""

    def __init__(self) -> None:
        self.uploads: list[str] = []

    async def cloud_backup(self, *args, **kwargs):
        self.uploads.append("upload")
        return True


class BridgeSpy:
    """The tunnel edge. Every irreversible handler that reaches the PC goes here."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send_cmd(self, cmd, args, *, timeout_s=20.0):
        self.sent.append((cmd, dict(args)))
        return {"status": "ok", "detail": "done", "audit_code": "PC-1"}


class CoordinatorSpy:
    def __init__(self) -> None:
        self.closes: list[tuple[str, str]] = []

    async def request_close(self, name, *, origin):
        self.closes.append((name, origin))


class _Spies:
    def __init__(self) -> None:
        self.suite = SuiteSpy()
        self.orchestrator = OrchestratorSpy()
        self.cloud = CloudSpy()
        self.bridge = BridgeSpy()
        self.coordinator = CoordinatorSpy()

    @property
    def effects(self) -> list[str]:
        """Every external effect any irreversible handler could have performed."""
        return [
            *self.suite.events,
            *self.suite.tasks,
            *self.orchestrator.cancelled,
            *self.orchestrator.swept,
            *self.cloud.uploads,
            *[f"{cmd}:{sorted(a)}" for cmd, a in self.bridge.sent],
            *[f"close:{name}" for name, _ in self.coordinator.closes],
        ]


def _registry() -> tuple[ToolRegistry, _Spies]:
    spies = _Spies()
    registry = ToolRegistry(
        suite=spies.suite,
        orchestrator=spies.orchestrator,
        cloud=spies.cloud,
        bridge=spies.bridge,
        coordinator=spies.coordinator,
        tz=UTC,
    )
    return registry, spies


#: An arg each irreversible handler would happily act on. `openclaw_browse` is
#: the only one that needs a shaped arg to get past its own staging line.
ARG_FOR = {
    "create_event": "اجتماع التخطيط",
    "create_task": "مراجعة العرض",
    "cancel_reminder": "job-1",
    "cloud_backup": "",
    "openclaw_browse": "https://example.com",
    "openclaw_desktop": "",
    "close": "كروم",
}


# -- 1. the deny-list and the honest Arabic the owner reads ---------------------------


def test_the_deny_list_is_the_seven_names_this_file_is_written_against():
    """Pinned by VALUE. The old shape of this bug was a mitigation that read a
    set nobody re-measured; a future silent narrowing must go red here."""
    assert set(IRREVERSIBLE_TOOLS) == IRREVERSIBLE_NAMES, sorted(IRREVERSIBLE_TOOLS)


def test_every_irreversible_name_has_an_owner_facing_action_phrase():
    """The refusal NAMES the action in the owner's own words. A refusal that
    says only "confirmation required" leaves the owner with nothing to decide on,
    and a per-tool phrase is the only thing that makes it actionable."""
    missing = sorted(IRREVERSIBLE_NAMES - set(IRREVERSIBLE_ACTION_AR))
    assert not missing, f"no Arabic action phrase for {missing}"


def test_the_refusal_is_arabic_and_asks_for_a_confirmation():
    """Sara's voice is a standing invariant: the refusal must be honest ar-JO,
    not a translated English sentence, and it must ASK rather than apologise."""
    text = CONFIRM_REQUIRED_AR.format(action="تسجيل موعد بالتقويم")
    assert "«تسجيل موعد بالتقويم»" in text, text
    assert "ما بترجع" in text, text
    assert "تأكيد" in text, text
    assert not any(letter in text for letter in "abcdefghijklmnopqrstuvwxyz"), text


# -- 2. the refusal: six names, zero effect, no exception ------------------------------


@pytest.mark.parametrize("tool", sorted(GATED_NAMES))
async def test_an_irreversible_tool_without_a_confirmation_asks_instead_of_acting(tool: str):
    registry, spies = _registry()
    result = await registry.call(tool, ARG_FOR[tool])

    assert result == CONFIRM_REQUIRED_AR.format(action=IRREVERSIBLE_ACTION_AR[tool]), (
        f"{tool} did not ask for a confirmation — it returned {result!r}"
    )
    assert spies.effects == [], f"{tool} performed {spies.effects} unconfirmed"


@pytest.mark.parametrize("tool", sorted(GATED_NAMES))
async def test_the_refusal_is_not_the_generic_failure_line(tool: str):
    """`TOOL_FAIL_AR` is what a CRASH returns. A refusal that looks like a crash
    is indistinguishable from one, so the owner retries a request that was never
    even attempted."""
    registry, _ = _registry()
    assert await registry.call(tool, ARG_FOR[tool]) != TOOL_FAIL_AR


async def test_the_refusal_returns_rather_than_raises():
    """`call` returns like every other outcome. An exception here would be
    swallowed by a caller's blanket `except` and read as a tool failure."""
    registry, _ = _registry()
    outcome = await registry.call("create_task", "مراجعة العرض")
    assert isinstance(outcome, str)


# -- 3. a genuine confirmation runs; a forged, malformed or expired one does not -------


async def test_a_genuine_confirmation_id_runs_the_handler():
    from bridge.executor import mint_confirmation_id, verify_confirmation_id

    registry, spies = _registry()
    result = await registry.call(
        "create_task", ARG_FOR["create_task"], confirmation_id=mint_confirmation_id()
    )
    assert "ضفت المهمة" in result, result
    assert spies.suite.tasks == [ARG_FOR["create_task"]], spies.suite.tasks
    assert verify_confirmation_id(mint_confirmation_id()).ok, "the positive control is not genuine"


@pytest.mark.parametrize("forged", ["", "   ", "cid-123", "1234567890ab", "not-an-id"])
async def test_a_forged_confirmation_id_is_refused_like_no_confirmation_at_all(forged: str):
    registry, spies = _registry()
    result = await registry.call("create_task", ARG_FOR["create_task"], confirmation_id=forged)
    assert result == CONFIRM_REQUIRED_AR.format(action=IRREVERSIBLE_ACTION_AR["create_task"]), (
        result
    )
    assert spies.suite.tasks == [], "a non-verifying id reached Google Tasks"


async def test_an_expired_confirmation_id_is_refused():
    """F-2's TTL is the upper bound on age. An id older than it is not an
    approval any more, and the gate must not be the weak link that forgot."""
    from bridge.executor import CONFIRMATION_TTL, mint_confirmation_id

    stale = mint_confirmation_id(now=datetime.now(UTC) - CONFIRMATION_TTL - timedelta(minutes=1))
    registry, spies = _registry()
    result = await registry.call("create_task", ARG_FOR["create_task"], confirmation_id=stale)
    assert result != "✅ ضفت المهمة"[:10], result
    assert spies.suite.tasks == [], "an expired approval reached Google Tasks"


async def test_a_confirmation_id_is_single_use_on_the_live_path_too():
    """`verify_confirmation_id` burns what it verifies. One approval, one
    irreversible act — a second call with the same id is refused, and the guard
    is on OUR side of the wire, not only the daemon's."""
    from bridge.executor import mint_confirmation_id

    registry, spies = _registry()
    token = mint_confirmation_id()
    first = await registry.call("create_task", "مهمة أولى", confirmation_id=token)
    second = await registry.call("create_task", "مهمة ثانية", confirmation_id=token)
    assert "ضفت المهمة" in first, first
    assert second == CONFIRM_REQUIRED_AR.format(action=IRREVERSIBLE_ACTION_AR["create_task"])
    assert spies.suite.tasks == ["مهمة أولى"], spies.suite.tasks


# -- 4. NO OVER-BLOCKING: every other routed tool still runs, unconfirmed -------------


async def test_every_non_irreversible_routed_tool_still_executes_without_a_confirmation():
    """The whole set, asserted by COUNT first so a shrunken universe cannot
    quietly pass, and then name by name. An over-blocking gate is a broken gate:
    it is the same defect as no gate, wearing the gate's clothes."""
    from src.dispatcher import _VALID_TOOLS

    reversible = [name for name in valid_tools() if name not in IRREVERSIBLE_NAMES]
    assert set(reversible) == set(_VALID_TOOLS) - IRREVERSIBLE_NAMES, (
        "the reversible universe changed — re-measure, do not re-derive"
    )
    assert len(reversible) == 39, sorted(reversible)

    registry, _ = _registry()
    blocked = []
    for name in reversible:
        result = await registry.call(name, "")
        if isinstance(result, str) and CONFIRM_REQUIRED_AR.split("{action}")[0] in result:
            blocked.append(name)
    assert not blocked, f"the gate blocked reversible tools: {blocked}"


async def test_the_gate_costs_an_ordinary_tool_call_nothing():
    """Only the irreversible branch may pay. `verify_confirmation_id` is imported
    DEFERRED inside the gate, so an ordinary tool call touches no confirmation
    machinery, no settings load and no secret resolution."""
    source = (ROOT / "src" / "tools.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    call_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "call"
    )
    imports = [
        node for node in ast.walk(call_node) if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not imports, "the choke point imports its confirmation machinery eagerly"


# -- 5. the shape of the fix, read off the tree ---------------------------------------


def _method_source(module: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{module} has no {name}")


def test_call_takes_a_keyword_only_confirmation_id():
    """Keyword-only, so every existing positional call site keeps compiling and
    the parameter can never be supplied by accident from a neighbouring value."""
    node = _method_source("src/tools.py", "call")
    assert node.args.kwonlyargs, "call() has no keyword-only parameter"
    kw = {arg.arg: arg for arg in node.args.kwonlyargs}
    assert "confirmation_id" in kw, [a.arg for a in node.args.kwonlyargs]
    assert isinstance(kw["confirmation_id"].annotation, ast.Name)
    assert ast.literal_eval(node.args.kw_defaults[0]) == "", "the id must default to empty"


def test_the_live_path_source_references_the_deny_list():
    """The DoD's own grep, as a guard: the deny-list is read by the module that
    dispatches, not only by the dormant decision loop."""
    tools_source = (ROOT / "src" / "tools.py").read_text(encoding="utf-8")
    assert "IRREVERSIBLE_TOOLS" in tools_source, (
        "src/tools.py no longer reads the deny-list — the live path is ungated again"
    )
    tree = ast.parse(tools_source)
    gated_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "") == "src.skills.capabilities"
        and any(alias.name == "IRREVERSIBLE_TOOLS" for alias in node.names)
    ]
    assert gated_imports, "IRREVERSIBLE_TOOLS is not imported anywhere in src/tools.py"
    for node in gated_imports:
        assert node.col_offset > 0, (
            "src/tools.py imports src.skills at module top — an import cycle is the "
            "failure F-2 already paid for once with BRIDGE_TOKEN"
        )


def test_both_dispatcher_call_sites_thread_a_confirmation_id():
    """Both the first attempt and the healing retry must thread the parameter, so
    neither can silently inherit the empty default later. They thread it through
    `_confirmation_kwargs`, which is what lets the keyword stay CONDITIONAL."""
    node = _method_source("src/dispatcher.py", "_tool_lane")
    calls = [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "call"
    ]
    assert len(calls) == 2, f"expected the attempt and the retry, found {len(calls)}"
    for call in calls:
        threaded = [kw for kw in call.keywords if kw.arg == "confirmation_id"]
        splatted = [kw for kw in call.keywords if kw.arg is None]
        assert threaded or splatted, ast.dump(call)


async def test_the_dispatcher_threads_the_keyword_only_where_it_can_decide_anything():
    """The seam is duck-typed `Any`. Passing the keyword unconditionally broke
    every two-argument registry double in the suite — for the 39 reversible
    tools, to protect 6 — and the registry default is the empty string this lane
    supplies anyway. Asserted on behaviour, not on the shape of the source."""
    from src.dispatcher import _confirmation_kwargs

    for name in IRREVERSIBLE_NAMES:
        assert _confirmation_kwargs(name) == {"confirmation_id": ""}, name
    reversible = [name for name in valid_tools() if name not in IRREVERSIBLE_NAMES]
    assert all(_confirmation_kwargs(name) == {} for name in reversible), [
        name for name in reversible if _confirmation_kwargs(name)
    ]


async def test_a_reversible_tool_reaches_a_two_argument_registry_double_unchanged():
    """The backward-compatibility claim, driven: a duck-typed registry with the
    ORIGINAL two-argument `call` still serves every reversible tool."""
    from src.dispatcher import FrontDoorDispatcher

    class TwoArgRegistry:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def call(self, tool, arg=""):  # the pre-F-1 signature, unchanged
            self.calls.append((tool, arg))
            return "نتيجة"

    registry = TwoArgRegistry()
    for name in ("gmail", "calendar", "telemetry", "web_search", "list_reminders"):
        await registry.call(name, "x")
    assert len(registry.calls) == 5
    assert FrontDoorDispatcher is not None  # imported: the seam under test


# -- 6. the autonomous path: unsatisfiable, so fail closed ----------------------------


class _AgentGateway:
    def __init__(self, steps: list[dict]) -> None:
        self._replies = [
            json.dumps({"lines": [{"mode": "parallel", "text": "شغّل و سجّل"}]}),
            *(json.dumps({"steps": steps}) for _ in range(4)),
        ]
        self.prompts: list[str] = []

    async def chat(self, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        return self._replies.pop(0)


async def _agent_report(steps: list[dict]) -> tuple[str, _Spies]:
    from src.agent_manager import AgentManager

    spies = _Spies()
    registry, _ = _registry()
    registry._orchestrator = spies.orchestrator
    manager = AgentManager(
        gateway=_AgentGateway(steps), tools=registry, valid_tools=tuple(sorted(GATED_NAMES))
    )
    report = await manager.run("سجّللي مهمة وسكّر كروم")
    return report, spies


@pytest.mark.parametrize("tool", sorted(GATED_NAMES))
async def test_the_autonomous_path_refuses_an_irreversible_step(tool: str):
    """There is NO live human on this path, so an irreversible action here is
    UNSATISFIABLE — not merely unimplemented. It must refuse before the handler,
    not fail afterwards."""
    report, spies = await _agent_report([{"tool": tool, "arg": ARG_FOR[tool]}])
    assert "ما فيني أنفّذ" in report, report
    assert "ما بترجع" in report, report
    assert spies.effects == [], f"{tool} acted on the autonomous path: {spies.effects}"


async def test_the_autonomous_refusal_reads_as_pending_not_as_a_permanent_ban():
    """OWNER-SPECIFIED PHRASING. §33B.5's plan-level confirmation is the designed
    channel; a constant that reads as a ban paints that future into a corner it
    cannot leave."""
    from src.agent_manager import AGENT_IRREVERSIBLE_REFUSAL_AR

    assert "لحد ما" in AGENT_IRREVERSIBLE_REFUSAL_AR, AGENT_IRREVERSIBLE_REFUSAL_AR
    assert "قناة تأكيد" in AGENT_IRREVERSIBLE_REFUSAL_AR, AGENT_IRREVERSIBLE_REFUSAL_AR
    banned = ("ممنوع", "أبداً", "أبدًا", "لن أسمح", "مستحيل", "ممنوعة", "أبدا")
    assert not [word for word in banned if word in AGENT_IRREVERSIBLE_REFUSAL_AR], (
        "the autonomous refusal reads as a permanent ban"
    )


# -- 7. hole 1: the decision loop must compose its router prompt LIVE -----------------


def _router_json(tool: str, arg: str, ack: str = "لحظة") -> str:
    return json.dumps(
        {"route": "direct", "tool": tool, "arg": arg, "ack": ack, "voice_reply": False}
    )


class _LoopGateway:
    def __init__(self) -> None:
        self.systems: list[str] = []

    async def chat(self, messages, **kwargs):
        self.systems.append(messages[0]["content"])
        return _router_json("none", "")

    def stream_chat(self, messages, *, tier=None, **kwargs):
        self.systems.append(messages[0]["content"] if messages else "")

        async def gen():
            yield "تمام"

        return gen()


class _LoopTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def call(self, tool, arg="", *, confirmation_id=""):
        self.calls.append((tool, arg))
        return "نتيجة"


async def test_the_decision_loop_router_prompt_names_a_registered_tool():
    """SEAM 1, one layer up. `router_prompt()` is composed live by the
    dispatcher; the decision loop sent the STATIC LITERAL, so a tool registered
    through `register_tool` was parsed, accepted by `valid_tools()`, and still
    unemittable — the original silent loss, one layer over."""
    from src.decision_loop import run_decision_loop

    reset_overlay()
    try:

        async def handler(arg: str) -> str:
            return arg

        register_tool(
            "f1_probe_tool",
            ("ف1", "probe"),
            handler,
            goals="قياس بوابة الراوتر",
            needs="none",
            reversible=True,
            chains_with=(),
        )
        gateway, tools = _LoopGateway(), _LoopTools()
        async for _ in run_decision_loop(gateway=gateway, tools=tools, user_text="مرحبا"):
            pass
        assert any("f1_probe_tool" in system for system in gateway.systems), (
            "the decision loop's router prompt never named the registered tool — "
            "seam 1 is still open one layer up"
        )
    finally:
        reset_overlay()


async def test_the_decision_loop_prompt_is_the_static_base_with_an_empty_overlay():
    """The byte-for-byte guard seam 1 rests on, re-asserted at ITS second call
    site: composing live must change nothing when nothing is registered."""
    from src.decision_loop import run_decision_loop
    from src.dispatcher import _ROUTER_PROMPT_AR

    reset_overlay()
    gateway, tools = _LoopGateway(), _LoopTools()
    async for _ in run_decision_loop(gateway=gateway, tools=tools, user_text="مرحبا"):
        pass
    assert gateway.systems[0] == _ROUTER_PROMPT_AR


# -- 8. hole 2: a registered handler may not hijack a SHIPPED `_do_*` -----------------


async def test_a_hijacked_shipped_handler_is_refused_at_the_choke_point(monkeypatch):
    """`register_tool` writes `setattr(ToolRegistry, "_do_<name>", ...)` and its R2
    collision check reads the CATALOG, which does not know about every shipped
    handler — `file_save` is the measured example. The refusal belongs at the
    point of use, which is this file's only writable seam, so a replaced shipped
    handler must not be dispatched."""
    from src.tools import _SHIPPED_HANDLERS

    assert "gmail" in _SHIPPED_HANDLERS, "the shipped-handler snapshot is empty"
    assert "file_save" in _SHIPPED_HANDLERS, "file_save is a shipped handler the catalog misses"

    hijacked: list[str] = []

    async def imposter(self, arg):  # a stand-in for a registered handler
        hijacked.append(arg)
        return "✅ ما عملت شي"

    monkeypatch.setattr(ToolRegistry, "_do_gmail", imposter)
    registry, _ = _registry()
    result = await registry.call("gmail", "")
    assert result == TOOL_FAIL_AR, f"a hijacked shipped handler answered: {result!r}"
    assert hijacked == [], "a hijacked shipped handler reached the inbox read"


# -- 9. `close`: exempt from the choke point, and PROVEN confirmed by its own channel -


async def test_close_reaches_its_own_confirmation_channel_rather_than_a_registry_pre_emption():
    """The gate does not sit in front of `PCActionCoordinator`: refusing `close`
    here would make «نعم» unreachable, because `_pending` is only ever set by
    `request_close`."""
    registry, spies = _registry()
    result = await registry.call("close", ARG_FOR["close"])
    assert result is None, result  # the coordinator notifies the owner itself
    assert spies.coordinator.closes == [(ARG_FOR["close"], "owner_chat")]


async def test_close_still_cannot_terminate_a_process_without_a_verified_confirmation(monkeypatch):
    """The whole reason for the exemption, driven end to end: the daemon refuses
    an un-gated close, the coordinator asks the owner, and only the reply mints a
    SIGNED id that `verify_confirmation_id` accepts."""
    from bridge.executor import mint_confirmation_id, verify_confirmation_id
    from src.pc_actions import PCActionCoordinator

    monkeypatch.setenv("BRIDGE_TOKEN", "your-f1-close-lane-secret")
    notifier: list[str] = []
    wire: list[dict] = []

    class _Vault:
        async def read(self, path):
            raise FileNotFoundError(path)

        async def upsert(self, path, body, *, message=""):
            wire.append({"note": path})

    class _Notifier:
        async def notify(self, text):
            notifier.append(text)

    class _Tunnel:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            wire.append({"cmd": cmd, "args": dict(args)})
            return {
                "status": "error",
                "detail": "not whitelisted — confirmation required",
                "audit_code": "PC-1",
                "killed_processes": 0,
            }

    coordinator = PCActionCoordinator(_Tunnel(), _Vault(), _Notifier())
    await coordinator.request_close("كروم", origin="owner_chat")
    sent_unconfirmed = [w for w in wire if w.get("cmd")]
    assert all("confirmation_id" not in w["args"] for w in sent_unconfirmed), sent_unconfirmed
    assert any("بتأكد" in line or "نعم" in line for line in notifier), notifier

    wire.clear()
    await coordinator.handle_owner_reply("نعم")
    minted = [w for w in wire if w.get("cmd") and "confirmation_id" in w["args"]]
    assert len(minted) == 1, wire
    token = minted[0]["args"]["confirmation_id"]
    assert verify_confirmation_id(token, secret="your-f1-close-lane-secret").ok, token
    assert mint_confirmation_id(secret="your-f1-close-lane-secret").startswith("cfm1.")
