"""N1 / D-2 — the durable action log: every tool execution, one append-only entry.

THE GAP THIS FILES. `ToolRegistry.call` — the single dispatch choke point both
execution paths share — recorded FAILURES ONLY, and only to loguru: an ephemeral
stream that dies with the process, keeps nothing, and is not part of the owner's
vault. There was no durable record of what the body DID, so every safety claim
about it («it never acted without confirmation») was asserted in code and
unverifiable after the fact. D-2's own law (the analysis report's I-4): *every
tool execution appends exactly one action-log entry.*

WHAT LANDS, and where it hangs

* ONE hook, in `ToolRegistry.call`, in a `finally`. Not one per handler: a
  per-tool hook is silently missed by every tool registered later through
  `src.tool_overlay.register_tool`, which is exactly the miss this file guards
  (section 7 drives a REAL registration and asserts it is covered).
* Every outcome gets an entry — success, `TOOL_FAIL_AR`, unknown tool, an F-1
  confirmation refusal, a hijacked-handler refusal. The `finally` makes
  "exactly one" structural rather than a promise about five code paths.
* Buffered, flushed by a background task (owner decision 2026-10-03:
  synchronous per-turn cost is rejected). `record()` performs no I/O and no
  await at all — section 8 pins that structurally; the MEASURED per-append
  latency is in `docs/10-CHECKPOINT.md`.
* Append-only, through the append surface `src/vault.py` already offers
  (`append_section`, `src/vault.py:479`). `upsert` OVERWRITES a single path
  (`src/vault.py:432`), so one `upsert` per entry into a fixed filename would
  keep only the LAST entry — measured, not assumed.

THE TWO LAWS THIS FILE ENFORCES, and the tension between them

* NEVER logged: API keys, tokens, credentials, session strings, vault
  personalization content. One guard per class (section 4) — a guard that
  asserts "no secrets" without naming the classes proves nothing.
* Meaning is NOT a secret. A tool arg legitimately carries the owner's own
  instruction («سكّر كروم»); a log that redacted that would be useless. The line
  is drawn at CREDENTIAL SHAPE, not at Arabic-ness, and
  `test_the_owners_own_instruction_survives_verbatim` pins where it sits.

THE LOAD-BEARING GUARD is section 6: a broken action log must not change a
single tool result. A tool that works today must work identically when the log
is broken, or the audit trail has become part of the control flow.
"""

from __future__ import annotations

import ast
import re
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import src.tools as tools_mod
from src.skills.capabilities import TOOL_CAPABILITIES
from src.tools import TOOL_FAIL_AR, ToolRegistry

try:  # the module this node adds does not exist until the fix lands
    from src.action_log import (
        ACTION_LOG_DIR,
        MAX_ARG_CHARS,
        MAX_SEGMENT_ENTRIES,
        REDACTION_CLASSES,
        STATUS_OK,
        STATUS_REFUSED_HIJACKED,
        STATUS_REFUSED_UNCONFIRMED,
        STATUS_TOOL_FAIL,
        STATUS_UNKNOWN_TOOL,
        action_log_for,
        action_log_path,
        counters,
        flush_action_log,
        parse_entry,
        record,
        redact_arg,
    )
except ImportError:  # pragma: no cover -- the pre-fix state this file is written for
    ACTION_LOG_DIR = MAX_ARG_CHARS = MAX_SEGMENT_ENTRIES = REDACTION_CLASSES = None
    STATUS_OK = STATUS_TOOL_FAIL = STATUS_UNKNOWN_TOOL = None
    STATUS_REFUSED_HIJACKED = STATUS_REFUSED_UNCONFIRMED = None
    action_log_for = action_log_path = counters = None
    flush_action_log = parse_entry = redact_arg = record = None

ROOT = Path(__file__).resolve().parents[1]

#: The hook's name inside `src/tools.py`. Pinned by value so the AST guards in
#: section 7 cannot pass against a hook that was renamed into irrelevance.
HOOK_NAME = "_record_action"

#: An entry line, re-derived HERE rather than imported from the module under
#: test. A parser that agrees with itself proves nothing (Directive 6).
ENTRY_RE = re.compile(
    r"^(?P<at>\S+) \| tool=(?P<tool>\S*) \| status=(?P<status>\S+) "
    r"\| ms=(?P<ms>\d+(?:\.\d+)?) \| args=(?P<args>.*)$"
)

#: The five DoD outcomes, named as the brief names them.
NAMED_OUTCOMES = (
    "success",
    "tool_fail",
    "unknown_tool",
    "refused_unconfirmed",
    "refused_hijacked_handler",
)

#: An arg each irreversible handler would happily act on — the F-1 file's own
#: fixture, re-measured here so a refusal is exercised with a REAL arg.
ARG_FOR = {
    "create_event": "اجتماع التخطيط",
    "create_task": "مراجعة العرض",
    "cancel_reminder": "job-1",
    "cloud_backup": "",
    "openclaw_browse": "https://example.com",
    "openclaw_desktop": "",
    "close": "كروم",
}


# ── helpers ───────────────────────────────────────────────────────────────────────


def _today() -> date:
    from datetime import UTC, datetime

    return datetime.now(UTC).date()


def _action_log_source() -> str:
    """Read the module under test, failing as an ASSERTION when it is absent."""
    path = ROOT / "src" / "action_log.py"
    assert path.is_file(), "src/action_log.py does not exist — the fix has not landed"
    return path.read_text(encoding="utf-8")


def _function(name: str, source: str | None = None) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source if source is not None else _action_log_source())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"no function named {name!r}")


async def _drain(vault) -> int:
    """Flush whatever the background scheduler has not flushed yet."""
    return await flush_action_log(vault)


def _lines(vault) -> list[str]:
    """Every entry line across every action-log note the sink holds."""
    prefix = f"{ACTION_LOG_DIR or '04_Archives/Audit/action-log'}/"
    out: list[str] = []
    for path, text in sorted(vault.files.items()):
        if path.startswith(prefix):
            out.extend(line for line in text.splitlines() if ENTRY_RE.match(line))
    return out


def _args_of(text: str) -> list[str]:
    return [
        ENTRY_RE.match(line).group("args") for line in text.splitlines() if ENTRY_RE.match(line)
    ]


# ── doubles ───────────────────────────────────────────────────────────────────────


class AppendVault:
    """A vault double carrying the surface the action log needs and nothing more.

    `append_section` IS the log's sink, so a double that lacks it cannot host the
    log at all. That is also what keeps `tests/test_dynamic_folders.py`'s
    `assert list(vault.files) == ["RoutineTasks/_index.md"]` honest: a vault with
    no append surface is counted as an unsupported sink, never written to.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self.files: dict[str, str] = {}
        self.sections: list[tuple[str, str, tuple[str, ...], str]] = []
        self.fail = fail

    async def read(self, path: str) -> str:
        if self.fail:
            raise RuntimeError("vault is down")
        try:
            return self.files[path]
        except KeyError:
            raise FileNotFoundError(path) from None

    async def list_dir(self, path: str, *, recursive: bool = False) -> list[str]:
        prefix = f"{path}/" if not path.endswith("/") else path
        return [p for p in self.files if p.startswith(prefix)]

    async def append_section(self, path, heading, lines, *, commit_prefix):
        if self.fail:
            raise RuntimeError("vault is down")
        block = "\n".join([f"## {heading}", "", *lines])
        existing = self.files.get(path, "")
        self.files[path] = f"{existing}\n{block}\n" if existing else f"{block}\n"
        self.sections.append((path, heading, tuple(lines), commit_prefix))
        return f"written:{path}"

    async def upsert(self, path, content, *, message=""):
        if self.fail:
            raise RuntimeError("vault is down")
        self.files[path] = content
        return object()


class ExplodingAppendVault(AppendVault):
    """Every method succeeds EXCEPT the log's own sink.

    The isolation is the point: a vault that fails `read`/`list_dir` too would
    change what a tool legitimately answers, so it would prove nothing about the
    action log.
    """

    async def append_section(self, path, heading, lines, *, commit_prefix):
        raise RuntimeError("action log sink is down")


class NoAppendSurface:
    """A vault that cannot host an action log at all — the shape most of the
    suite's registry doubles have."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}

    async def read(self, path):
        raise FileNotFoundError(path)

    async def list_dir(self, path, *, recursive=False):
        return []


class _Spies:
    """Whatever F-1's file wires, so a handler answers offline instead of hanging."""

    class Suite:
        async def list_events(self, start, end):
            return []

        async def unread_count(self):
            return 0

        async def create_event(self, summary, start, end):
            return {"id": "evt-1"}

        async def add_task(self, title):
            return {"id": "task-1"}

    class Orchestrator:
        async def due(self, now):
            return []

        async def cancel(self, job_id):
            return True

        async def cancel_all(self):
            return 0

    class Cloud:
        async def cloud_backup(self, *args, **kwargs):
            return True

    class Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            return {"status": "ok", "detail": "done", "audit_code": "PC-1"}

    class Coordinator:
        async def request_close(self, name, *, origin):
            return None


def _registry(vault=None) -> ToolRegistry:
    s = _Spies
    return ToolRegistry(
        suite=s.Suite(),
        orchestrator=s.Orchestrator(),
        cloud=s.Cloud(),
        bridge=s.Bridge(),
        coordinator=s.Coordinator(),
        vault=vault,
        tz=ZoneInfo("UTC"),
    )


def _arg_for(name: str) -> str:
    return ARG_FOR.get(name, "")


async def _all_results(vault) -> dict[str, str | None]:
    """Every shipped tool's result against a given TOOL-SIDE vault."""
    out: dict[str, str | None] = {}
    for name in sorted(tools_mod._SHIPPED_HANDLERS):
        out[name] = await _registry(vault).call(name, _arg_for(name))
    return out


def _raise_hook(*args, **kwargs):
    raise RuntimeError("the action log is broken")


# ── secret fixtures, ASSEMBLED ────────────────────────────────────────────────────
#
# `scripts/secret_scan.py:31` refuses these key SHAPES as literals, and it is
# right to: the pre-commit battery and `security_gate.py` scan every tracked
# file. So the fakes are built at runtime, out of pieces the scanner cannot
# reassemble. That is a scanner-evasion of the LITERAL, never of the guard — the
# values below are exactly the shapes a real provider hands out, which is the
# whole point of testing them.
_KEY_GITHUB = "gh" + "p_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_KEY_SLACK = "xox" + "b-" + "2949384725-2847301928-aBcDeFgHiJkLmNoPqRsTuVwX"
_KEY_AWS = "AKIA" + "IOSFODNN7EXAMPLE"
_LIVE_SHARED_SECRET = "gh" + "p_" + "actionlogguardTOKEN0123456789abcdefABCDEF"


# ── 1. the universe, pinned ───────────────────────────────────────────────────────


def test_the_universe_is_the_whole_tool_set_not_a_sample():
    """A guard over a sample proves a sample. The two published counts are
    re-measured here: 45 catalogued capabilities and 46 shipped `_do_*` handlers
    (`file_save` ships and is uncatalogued — F-1 measured that)."""
    assert len(TOOL_CAPABILITIES) == 45, sorted(TOOL_CAPABILITIES)
    assert len(tools_mod._SHIPPED_HANDLERS) == 46, sorted(tools_mod._SHIPPED_HANDLERS)
    assert set(TOOL_CAPABILITIES) | {"file_save"} == set(tools_mod._SHIPPED_HANDLERS)


# ── 2. exactly ONE entry per execution, over the whole set ─────────────────────────


async def test_every_shipped_tool_appends_exactly_one_entry():
    """THE WHOLE SET, name by name. Every handler runs with no live dependency, so
    this covers success, honest-offline and crash outcomes at once — and a second
    entry for any single name fails here, which is the only place a double-append
    across all 46 can be caught."""
    vault = AppendVault()
    for name in sorted(tools_mod._SHIPPED_HANDLERS):
        await _registry(vault).call(name, _arg_for(name))
    await _drain(vault)

    entries = [ENTRY_RE.match(line).group("tool") for line in _lines(vault)]
    assert sorted(entries) == sorted(tools_mod._SHIPPED_HANDLERS), sorted(entries)
    assert len(entries) == len(set(entries)) == 46, entries


async def test_a_hijacked_handler_is_refused_and_still_logged_once(monkeypatch):
    """The hijack refusal is an OUTCOME, so it is an entry — a refusal that left
    no trace would be the exact hole this node closes."""
    vault = AppendVault()

    async def imposter(self, arg):  # pragma: no cover -- never dispatched
        raise AssertionError("a hijacked shipped handler was dispatched")

    monkeypatch.setattr(ToolRegistry, "_do_gmail", staticmethod(imposter))
    result = await _registry(vault).call("gmail", "")
    await _drain(vault)

    assert result == TOOL_FAIL_AR, result
    entries = [ENTRY_RE.match(line) for line in _lines(vault)]
    assert len(entries) == 1, _lines(vault)
    assert entries[0].group("status") == STATUS_REFUSED_HIJACKED, entries[0].groupdict()


# ── 3. the five named outcomes, one entry each, with the fields DoD demands ───────


async def test_a_successful_tool_appends_one_entry_with_every_required_field():
    vault = AppendVault()
    result = await _registry(vault).call("gmail", "")
    await _drain(vault)

    assert result != TOOL_FAIL_AR, result
    entry = ENTRY_RE.match(_lines(vault)[0]).groupdict()
    assert entry["tool"] == "gmail", entry
    assert entry["status"] == STATUS_OK, entry
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", entry["at"]), entry
    assert float(entry["ms"]) >= 0.0, entry
    assert entry["args"] == "", entry


async def test_a_crashing_tool_appends_one_entry_stamped_tool_fail():
    vault = AppendVault()
    registry = _registry(vault)

    async def boom(arg):
        raise RuntimeError("backend exploded")

    registry._do_gmail = boom  # instance-level: an injection, NOT a class hijack
    result = await registry.call("gmail", "")
    await _drain(vault)

    assert result == TOOL_FAIL_AR, result
    entry = ENTRY_RE.match(_lines(vault)[0]).groupdict()
    assert entry["tool"] == "gmail", entry
    assert entry["status"] == STATUS_TOOL_FAIL, entry


async def test_an_unknown_tool_appends_one_entry_stamped_unknown_tool():
    vault = AppendVault()
    result = await _registry(vault).call("no_such_tool", "حاجة")
    await _drain(vault)

    assert result == TOOL_FAIL_AR, result
    entry = ENTRY_RE.match(_lines(vault)[0]).groupdict()
    assert entry["tool"] == "no_such_tool", entry
    assert entry["status"] == STATUS_UNKNOWN_TOOL, entry
    assert entry["args"], "an unknown tool's arg is still evidence — dropping it leaves nothing"


async def test_a_confirmation_refusal_appends_one_entry_stamped_refused():
    """F-1's refusal, observed by the log. The gate must not be invisible: the
    owner asking twice and being refused twice is a fact worth keeping."""
    vault = AppendVault()
    result = await _registry(vault).call("create_task", ARG_FOR["create_task"])
    await _drain(vault)

    assert "تأكيد" in result, result
    entry = ENTRY_RE.match(_lines(vault)[0]).groupdict()
    assert entry["tool"] == "create_task", entry
    assert entry["status"] == STATUS_REFUSED_UNCONFIRMED, entry


async def test_every_named_outcome_round_trips_through_the_parser():
    """The reader and the writer agree, for all five statuses. Re-derived from
    the line grammar so a writer that drifts from its parser cannot leave a log
    that looks full and reads as empty."""
    assert STATUS_OK and STATUS_TOOL_FAIL and STATUS_UNKNOWN_TOOL
    assert STATUS_REFUSED_UNCONFIRMED and STATUS_REFUSED_HIJACKED
    for status in NAMED_OUTCOMES:
        line = f"2026-10-03T10:00:00+00:00 | tool=gmail | status={status} | ms=1.500 | args=hello"
        parsed = parse_entry(line)
        assert parsed is not None, status
        assert parsed.tool == "gmail", parsed
        assert parsed.status == status, parsed
        assert parsed.duration_ms == pytest.approx(1.5), parsed
    assert parse_entry("not an entry at all") is None


# ── 4. redaction — one guard per class, and the meaning line ──────────────────────


def test_the_redaction_list_is_written_down_and_named():
    """A guard that asserts "no secrets" without naming what it redacts is not a
    guard. The five classes are the brief's five, in code, as a constant."""
    assert list(REDACTION_CLASSES) == [
        "api_key",
        "token",
        "credential",
        "session_string",
        "vault_personalization",
    ], REDACTION_CLASSES


def test_api_keys_are_redacted():
    """CLASS: api_key — provider key shapes a real arg could carry."""
    for secret in (
        "AIzaSyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY",
        "sk-live-4eC39HqLyjWDarjtT1zdp7dc",
        _KEY_SLACK,
        _KEY_AWS,
    ):
        out = redact_arg(f"authorize with {secret}")
        assert secret not in out, f"api key leaked: {out}"
        assert "«redacted»" in out, out


def test_tokens_are_redacted():
    """CLASS: token. A LABELLED secret keeps its label — a reader must still see
    THAT a token was present, only never what it was."""
    for secret in (
        "hunter2-correct-horse",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r",
        _KEY_GITHUB,
    ):
        out = redact_arg(f"token={secret} done")
        assert secret not in out, f"token leaked: {out}"
        assert "«redacted»" in out, out


def test_credentials_are_redacted():
    """CLASS: credential. A userinfo pair in a URL is the classic leak, and this
    repo has URL-taking tools (`read_page`, `openclaw_fetch`) whose args land here."""
    out = redact_arg("https://omar:Pa55w0rd!@mail.example.com/inbox")
    assert "Pa55w0rd!" not in out, f"credential leaked: {out}"
    assert "«redacted»" in out, out


def test_session_strings_are_redacted():
    """CLASS: session_string. Two shapes this repo really produces: F-2's signed
    `cfm1.` confirmation id (a usable owner approval if it leaks) and the
    Telethon session string `src/telegram_login.py` prints."""
    from bridge.executor import mint_confirmation_id

    confirmation = mint_confirmation_id(secret="your-action-log-guard-secret")
    assert confirmation.startswith("cfm1."), confirmation
    for secret in (
        confirmation,
        "BQEFMQBLZHJhdGVzZXF1Y2thYmVkZmVoaWxqZm5vcHFyc3R1dnd4eXoxMjM0NTY3ODkwMTIzNDU2Nzg5MGFiY2RlZmdoaWo=",
    ):
        out = redact_arg(f"retry with {secret}")
        assert secret not in out, f"session string leaked: {out}"
        assert "«redacted»" in out, out


def test_the_live_shared_secret_is_redacted_even_when_it_matches_no_shape():
    """The strongest half of the credential law: the process's OWN GitHub token,
    which no regex can be written for, is registered in `src.vault` at
    `VaultClient.__init__` and screened by `redact_secret`. A guard that only
    tests patterns proves nothing about the real secret."""
    from src.vault import VaultClient

    VaultClient("owner/vault-repo", _LIVE_SHARED_SECRET)
    out = redact_arg(f"the vault rejected header {_LIVE_SHARED_SECRET}")
    assert _LIVE_SHARED_SECRET not in out, f"live token leaked: {out}"
    assert "«redacted»" in out, out


def test_vault_personalization_content_is_redacted():
    """CLASS: vault_personalization. `User_Info.md` is owner-private: the greeter
    (`src/bot.py:208`) and the outreach loop
    (`src/skills/proactive_outreach.py:138`) both read it, and the note's own
    shape is a `## معلومة` / `slot:` / `value:` stack (`src/memory.py:521`)."""
    excerpt = (
        "# User Info\n\nOwner profile — identity, preferences, context.\n"
        "## معلومة 2026-09-14 12:00\nslot: owner/city\nvalue: عمّان\n"
        "slot: owner/phone\nvalue: 0791234567\n"
    )
    for shaped in (
        excerpt,
        "[صاحبك باختصار — بيانات مرجعية]\n" + " ".join(excerpt.split())[:200],
        "[ملف المالك]\n" + excerpt[-120:],
    ):
        out = redact_arg(shaped)
        assert "0791234567" not in out, f"personalization leaked: {out}"
        assert "عمّان" not in out, f"personalization leaked: {out}"
        assert "«profile-redacted»" in out, out


def test_the_owners_own_instruction_survives_verbatim():
    """THE TENSION, pinned. The line is drawn at CREDENTIAL SHAPE, not at
    Arabic-ness: «سكّر كروم» is the whole point of the log and must survive byte
    for byte. A redactor that ate meaning would leave an audit trail nobody can
    read."""
    for instruction in ("سكّر كروم", "افتح الويد", "بعت لأمي إيميل", "اعرض مهام اليوم"):
        assert redact_arg(instruction) == instruction, instruction


async def test_a_newline_in_the_arg_cannot_forge_a_second_entry():
    """LOG INJECTION. `append_section` writes `lines` verbatim, so an arg
    carrying a newline would append a forged line to a note nobody re-signs."""
    forged = "safe\n2026-10-03T10:00:00+00:00 | tool=create_task | status=ok | ms=0.001 | args=x"
    vault = AppendVault()
    await _registry(vault).call("create_folder", forged)
    await _drain(vault)

    entries = _lines(vault)
    assert len(entries) == 1, entries
    assert entries[0].count("tool=create_task") == 1, entries[0]


def test_the_arg_is_bounded_so_a_note_cannot_be_flooded_by_one_call():
    """A log one enormous arg can fill is a log that stops being readable. The cap
    is a NAMED constant and it truncates — it never drops the entry."""
    out = redact_arg("س" * (MAX_ARG_CHARS * 3))
    assert len(out) <= MAX_ARG_CHARS + len("«redacted»"), len(out)
    assert out, "truncation must not empty the field"


# ── 5. append-only, and durable across a restart ──────────────────────────────────


async def test_entries_accumulate_and_an_earlier_entry_is_never_overwritten():
    """`upsert` OVERWRITES a single path (`src/vault.py:432`), so one write per
    entry into a fixed filename would keep only the LAST entry — the reason the
    log rides the append surface instead. Proved by ordering, not by comment."""
    vault = AppendVault()
    for index in range(6):
        await _registry(vault).call("gmail", f"رسالة رقم {index}")
    await _drain(vault)

    assert _args_of("".join(_lines(vault))) == [f"رسالة رقم {i}" for i in range(6)], _lines(vault)

    before = dict(vault.files)
    await _registry(vault).call("calendar", "")
    await _drain(vault)
    for path, text in before.items():
        assert vault.files[path].startswith(text), f"{path} was rewritten, not appended to"
    assert len(_lines(vault)) == 7, _lines(vault)


async def test_the_action_log_survives_a_restart():
    """DURABILITY, driven. A first process writes through a real `VaultClient`
    over the GitHub double; a SECOND client — a different object, i.e. a restart
    — reads the note back and finds the entries."""
    import httpx

    from src.vault import VaultClient
    from tests.helpers_vault import FakeGitHub

    gh = FakeGitHub()

    def _client() -> VaultClient:
        session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
        return VaultClient("owner/vault-repo", "your-action-log-token", session=session)

    first = _client()
    for index in range(3):
        await _registry(first).call("gmail", f"قبل إعادة التشغيل {index}")
    await _drain(first)

    restarted = _client()  # a new client object over the same store: a restart
    text = await restarted.read(action_log_path(_today()))
    entries = [
        ENTRY_RE.match(line).groupdict() for line in text.splitlines() if ENTRY_RE.match(line)
    ]
    assert len(entries) == 3, entries
    assert [e["args"] for e in entries] == [f"قبل إعادة التشغيل {i}" for i in range(3)], entries
    assert all(e["tool"] == "gmail" for e in entries), entries


# ── 6. ZERO BEHAVIOUR CHANGE — the load-bearing guard ─────────────────────────────


async def test_a_broken_action_log_never_alters_a_single_tool_result():
    """THE LOAD-BEARING GUARD. The same tool-side vault, four different broken
    logs, identical results across all 46 tools:

      (a) the log's own sink raises — `ExplodingAppendVault`
      (b) the hook itself raises — patched at the choke point
      (c) redaction raises INSIDE the recorder
      (d) the sink has no append surface at all

    (a) isolates the log's failure from the tool's own dependencies on purpose:
    a vault whose `read` also fails changes what a tool legitimately answers, so
    it would prove nothing."""
    import src.action_log as log_mod

    healthy = await _all_results(AppendVault())
    assert len(healthy) == 46, len(healthy)

    assert await _all_results(ExplodingAppendVault()) == healthy, (
        "an exploding log changed a result"
    )

    tools_mod._record_action = _raise_hook
    try:
        assert await _all_results(AppendVault()) == healthy, "a raising hook changed a result"
    finally:
        tools_mod._record_action = record

    log_mod.redact_arg = _raise_hook
    try:
        assert await _all_results(AppendVault()) == healthy, "a raising redactor changed a result"
    finally:
        log_mod.redact_arg = redact_arg

    assert await _all_results(NoAppendSurface()) == healthy, (
        "a sink without append changed a result"
    )


async def test_a_log_failure_never_raises_into_the_tool_call():
    """The belt at the choke point, proved on its own: with the hook raising,
    every outcome of `call` still RETURNS, so a caller can never read the log's
    failure as a tool failure."""
    tools_mod._record_action = _raise_hook
    try:
        registry = _registry(AppendVault())
        assert await registry.call("gmail", "") != TOOL_FAIL_AR
        assert await registry.call("no_such_tool", "") == TOOL_FAIL_AR
        assert "تأكيد" in await registry.call("create_task", ARG_FOR["create_task"])
    finally:
        tools_mod._record_action = record


# ── 7. the shape of the fix, read off the tree ────────────────────────────────────


def _tools_tree() -> ast.Module:
    return ast.parse((ROOT / "src" / "tools.py").read_text(encoding="utf-8"))


def _tools_functions() -> dict:
    return {
        node.name: node
        for node in ast.walk(_tools_tree())
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_the_hook_is_at_the_choke_point_and_nowhere_else():
    """THE ANTI-PER-TOOL GUARD. Exactly one hook call, inside `ToolRegistry.call`,
    and ZERO inside any `_do_*` handler — because a per-tool hook is silently
    missed by every tool registered later, which is the whole reason this hangs
    at the choke point."""
    functions = _tools_functions()
    call = functions["call"]
    hook_calls = [
        node
        for node in ast.walk(call)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == HOOK_NAME
    ]
    assert len(hook_calls) == 1, f"{HOOK_NAME} appears {len(hook_calls)} times in call()"

    for name, node in functions.items():
        if name == "call" or not name.startswith("_do_"):
            continue
        intruders = [
            item
            for item in ast.walk(node)
            if isinstance(item, ast.Call)
            and isinstance(item.func, ast.Name)
            and item.func.id == HOOK_NAME
        ]
        assert not intruders, f"the hook was duplicated into the handler {name}"


def test_the_choke_point_imports_no_confirmation_or_log_machinery_eagerly():
    """F-1's latency law, re-pinned at the second seam: no `import` statement of
    any kind inside `call`, so an ordinary tool call pays neither the
    confirmation machinery nor the log's own dependency graph."""
    call = _tools_functions()["call"]
    imports = [node for node in ast.walk(call) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not imports, "the choke point imports its machinery eagerly"


def test_the_existing_loguru_failure_lines_are_still_there():
    """The loguru diagnostics are KEPT, not replaced — they are a different
    record (ephemeral, shaped for a human watching stdout), and the DoD says keep
    them. A future reader who finds them gone has found a silent change."""
    source = (ROOT / "src" / "tools.py").read_text(encoding="utf-8")
    for line in (
        "tool registry got unknown tool {!r}",
        "refused hijacked shipped handler {!r}",
        "refused irreversible tool {!r}: no verified confirmation",
        "tool {!r} failed: {}",
    ):
        assert line in source, f"the loguru diagnostic {line!r} was removed"


async def test_a_tool_registered_later_is_covered_without_touching_the_hook():
    """THE POINT OF THE CHOKE POINT, driven. A real `register_tool` lands a new
    `_do_*` and its execution is logged with no edit to any handler and no edit to
    `call`. A per-tool hook fails this; a choke-point hook passes it."""
    from src.tool_overlay import register_tool, reset_overlay

    reset_overlay()
    try:

        async def handler(arg: str) -> str:
            return "سجلت سطر"

        register_tool(
            "n1_probe_tool",
            ("ن1", "probe"),
            handler,
            goals="قياس تغطية الأداة الجديدة",
            needs="none",
            reversible=True,
            chains_with=(),
        )
        vault = AppendVault()
        result = await _registry(vault).call("n1_probe_tool", "قياس")
        await _drain(vault)

        assert result == "سجلت سطر", result
        entries = [ENTRY_RE.match(line).groupdict() for line in _lines(vault)]
        assert len(entries) == 1, _lines(vault)
        assert entries[0]["tool"] == "n1_probe_tool", entries[0]
    finally:
        reset_overlay()


def test_the_recorder_cannot_receive_the_confirmation_id():
    """DEFENCE IN DEPTH, and a statement about the design: `record` has no
    parameter that could carry F-2's signed `cfm1.` approval, so the id is not
    merely redacted — it is never read."""
    node = _function("record")
    names = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
    assert "confirmation_id" not in names, sorted(names)
    assert not any("confirmation" in name for name in names), sorted(names)


# ── 8. buffered, deferred, and honest about what it dropped ───────────────────────


def test_record_performs_no_io_and_no_await():
    """The owner's decision, as a structural property rather than a benchmark:
    `record` is a plain sync function, so the tool's own stack pays no await and
    no I/O. That is what makes the measured append cost irrelevant to the reply."""
    node = _function("record")
    assert isinstance(node, ast.FunctionDef), "the append path must not be a coroutine"
    suspensions = [
        item
        for item in ast.walk(node)
        if isinstance(item, (ast.Await, ast.AsyncFor, ast.AsyncWith))
    ]
    assert not suspensions, "the append path awaits — that IS the per-turn cost"
    called = [
        item.func.attr
        for item in ast.walk(node)
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
    ]
    for sink in ("read", "upsert", "append_section", "list_dir"):
        assert sink not in called, f"record() calls the vault's {sink} synchronously"


async def test_the_write_is_deferred_past_the_tool_call():
    """The append is buffered and the write is a background task. Immediately
    after `call` returns, NOTHING has been written — which is the tail a crash
    loses, and the durability statement says so out loud."""
    import asyncio

    vault = AppendVault()
    await _registry(vault).call("gmail", "")
    assert vault.files == {}, "the write was synchronous — the per-turn cost the owner rejected"
    assert counters(vault)["pending"] == 1, counters(vault)

    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert len(_lines(vault)) == 1, _lines(vault)
    assert counters(vault)["pending"] == 0, counters(vault)


async def test_no_vault_means_no_durable_surface_and_it_is_counted_not_hidden():
    """A registry with no vault cannot host the log. The entry is DROPPED and the
    drop is COUNTED — the failure mode this node exists to kill is a log that
    silently does not log."""
    result = await _registry(None).call("gmail", "")
    assert result is not None, result
    assert counters(None)["dropped"] >= 1, counters(None)


async def test_a_flushed_entry_is_counted_so_a_silent_log_cannot_pass():
    vault = AppendVault()
    for _ in range(3):
        await _registry(vault).call("gmail", "")
    await _drain(vault)
    stats = counters(vault)
    assert stats["written"] == 3, stats
    assert stats["flushes"] >= 1, stats
    assert stats["failed"] == 0, stats


async def test_a_write_failure_keeps_the_entries_buffered_and_retries_them_once():
    """At-least-once, and bounded. A dead vault on the first flush keeps the
    entries buffered; the next flush re-attempts them, in order, exactly once."""
    vault = AppendVault()
    await _registry(vault).call("gmail", "")
    await _drain(vault)  # one healthy flush

    vault.fail = True
    for index in range(2):
        await _registry(vault).call("gmail", f"محاولة {index}")
    await _drain(vault)
    assert counters(vault)["failed"] == 2, counters(vault)
    assert counters(vault)["pending"] == 2, counters(vault)

    vault.fail = False
    await _drain(vault)
    args = [ENTRY_RE.match(line).group("args") for line in _lines(vault)]
    assert args[-2:] == ["محاولة 0", "محاولة 1"], args


# ── 9. rotation: the policy is stated in code and proved ──────────────────────────


def test_the_log_lands_under_the_vault_audit_directory():
    """Pinned against the vault's own constant so the two cannot drift apart."""
    from src.vault import AUDIT_DIR

    assert ACTION_LOG_DIR == f"{AUDIT_DIR}/action-log", ACTION_LOG_DIR


def test_one_note_per_day_is_the_canonical_shape():
    assert (
        action_log_path(date(2026, 10, 3)) == "04_Archives/Audit/action-log/2026/10/2026-10-03.md"
    )
    assert action_log_path(date(2026, 10, 3), 2) == (
        "04_Archives/Audit/action-log/2026/10/2026-10-03--02.md"
    )


async def test_a_note_rotates_to_the_next_segment_past_the_cap():
    """ROTATION, driven. The cap is injected small so the policy is exercised in
    milliseconds rather than on the 500th entry: past it the next entries land in
    a NEW note, and every earlier note keeps exactly what it had."""
    cap = 2
    vault = AppendVault()
    action_log_for(vault, max_segment_entries=cap)
    for index in range(5):
        await _registry(vault).call("gmail", f"رقم {index}")
        await _drain(vault)

    today = _today()
    segments = [
        _args_of(vault.files.get(action_log_path(today, segment), "")) for segment in range(1, 6)
    ]
    segments = [s for s in segments if s]
    assert [len(s) for s in segments] == [cap, cap, 1], segments
    assert [arg for s in segments for arg in s] == [f"رقم {i}" for i in range(5)], segments
    assert segments[0] == ["رقم 0", "رقم 1"], segments
    assert MAX_SEGMENT_ENTRIES == 500, MAX_SEGMENT_ENTRIES


async def test_a_restarted_process_counts_what_the_note_already_holds():
    """Rotation survives a restart, because the count comes from the NOTE, not
    from process memory: a fresh log over a note that already holds its cap rolls
    to the next segment instead of overfilling the first."""
    vault = AppendVault()
    for index in range(2):
        await _registry(vault).call("gmail", f"قبل {index}")
        await _drain(vault)

    action_log_for(vault, max_segment_entries=2)  # a new process, same store
    await _registry(vault).call("gmail", "بعد")
    await _drain(vault)

    today = _today()
    assert "بعد" not in vault.files[action_log_path(today)], "the cap was forgotten across restart"
    assert "بعد" in vault.files[action_log_path(today, 2)]


async def test_the_previous_day_is_never_written_to():
    """Day rotation is by PATH, so yesterday's note is closed by construction."""
    vault = AppendVault()
    await _registry(vault).call("gmail", "اليوم")
    await _drain(vault)

    yesterday = _today() - timedelta(days=1)
    assert action_log_path(yesterday) != action_log_path(_today())
    assert yesterday.isoformat() not in vault.files, vault.files
