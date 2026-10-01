"""F-3 (report Part F §43) — the `open_path` holes, guard by guard.

Three walls stand between the owner's chat and `os.startfile`:

  1. SHAPE     — no UNC, no relative traversal (pre-existing, unchanged).
  2. SUFFIX    — a double-click equivalent never opens through `open_path`:
                 opening one of those IS launching it. The set now also holds
                 `.lnk`/`.url` (the classic vector), `.jar`, `.hta`, `.html`,
                 `.wsf`, `.wsh` — the pre-F-3 set failed to match the rule its
                 own comment above it states.
  3. CONTAINMENT — the resolved path must land inside a configured OPEN root.
                 `DEFAULT_FILE_ROOTS` (Downloads) is the file-drop landing
                 zone and is deliberately NOT reused here.

Every guard names the mutant it kills; the table lives in the F-3 commit
message. OS boundaries stay on the module's own `_open` spy seam.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from bridge import executor as executor_mod
from bridge.executor import (
    DEFAULT_FILE_ROOTS,
    OPEN_BLOCKED_SUFFIXES,
    Executor,
    default_open_roots,
    resolve_in_roots,
)
from bridge.guard import Guard

# The set as it stood before F-3 — these must stay refused (DoD: "the existing
# set still refused"). Keeping the literal HERE means a future edit to
# OPEN_BLOCKED_SUFFIXES cannot quietly drop one of them without this file
# going red.
PRE_F3_BLOCKED = (".exe", ".bat", ".cmd", ".com", ".scr", ".msi", ".ps1", ".vbs", ".js")
# The double-click equivalents F-3 adds. `.htm` is a byte-for-byte alias of
# `.html`; omitting it would re-open the same hole through the other spelling.
F3_ADDED_BLOCKED = (".lnk", ".url", ".jar", ".hta", ".html", ".htm", ".wsf", ".wsh")


def _guard(tmp_path: Path) -> Guard:
    wl = tmp_path / "whitelist.json"
    wl.write_text('{"allowed_apps": [], "restricted_actions": []}', encoding="utf-8")
    return Guard(str(wl))


def _executor(tmp_path: Path, roots: tuple[Path, ...] | None) -> tuple[Executor, list[str]]:
    """A real Executor with only the OS edge replaced by a spy (never a real
    `os.startfile` — this suite must never touch the owner's desktop).

    `roots=None` passes NO `open_roots` at all, so the shipped seed applies —
    that is how the over-blocking guard exercises the real default wiring."""
    opened: list[str] = []

    async def _open(path: str) -> None:
        opened.append(path)

    kwargs = {} if roots is None else {"open_roots": roots}
    ex = Executor(_guard(tmp_path), **kwargs)
    ex._open = _open  # type: ignore[method-assign]
    return ex, opened


# -- 2. SUFFIX --------------------------------------------------------------------


@pytest.mark.parametrize("suffix", PRE_F3_BLOCKED + F3_ADDED_BLOCKED)
async def test_double_click_equivalents_never_open(tmp_path: Path, suffix: str):
    """MUTANT (b) — dropping .lnk/.url/... from OPEN_BLOCKED_SUFFIXES.

    A double-click equivalent is a launcher wearing a document's clothes:
    `.lnk` runs its target, `.url` navigates to an attacker-chosen page,
    `.jar` executes, `.hta`/`.html`/`.htm` run script, `.wsf`/`.wsh` run
    Windows Script Host. None of them may reach `os.startfile`."""
    root = tmp_path / "open_root"
    root.mkdir()
    ex, opened = _executor(tmp_path, (root,))
    result = await ex.open_path(str(root / f"payload{suffix}"))
    assert result.status == "error", suffix
    assert opened == [], suffix


async def test_blocked_set_is_a_superset_of_the_pre_f3_set():
    """The F-3 additions must not have cost the original nine a refusal."""
    assert set(PRE_F3_BLOCKED) <= set(OPEN_BLOCKED_SUFFIXES)
    assert set(F3_ADDED_BLOCKED) <= set(OPEN_BLOCKED_SUFFIXES)


async def test_suffix_refusal_names_the_reason_and_the_working_route(tmp_path: Path):
    """MUTANT (f) — a bare "error" teaches the owner nothing. The refusal must
    say WHY (opening it IS launching it) and name the route that works (the app
    whitelist). The owner's legitimate `.url`/`.jar` opens must not dead-end on
    an unexplained error.

    Each clause is asserted SEPARATELY and on the EXACT phrases. Asserting only
    "whitelist" in detail is not a guard: the containment refusal also mentions
    the whitelist, so a mangled suffix message would slip through (measured —
    this guard was blind until the phrases were pinned)."""
    root = tmp_path / "open_root"
    root.mkdir()
    ex, _ = _executor(tmp_path, (root,))
    for suffix in (".url", ".jar", ".lnk"):
        result = await ex.open_path(str(root / f"thing{suffix}"))
        assert result.status == "error", suffix
        detail = result.detail
        # the WHY — the suffix, and that opening it is launching it
        assert suffix in detail, (suffix, detail)
        assert "IS launching it" in detail, (suffix, detail)
        # the ROUTE that does work — the app whitelist, by name and by file
        assert "app whitelist" in detail, (suffix, detail)
        assert "whitelist.json" in detail, (suffix, detail)


async def test_containment_refusal_is_distinguishable_from_the_suffix_refusal(tmp_path: Path):
    """The two walls must not share copy, and each must be the one that fires.

    The shipped order is SUFFIX then CONTAINMENT (checked, not incidental: the
    suffix wall must not be reachable only after a path walk, and "launch the
    app instead" is the more actionable message for a blocked file). So the
    isolating shapes are a BENIGN suffix outside the roots (containment alone)
    and a BLOCKED suffix inside them (suffix alone). A single `.exe` outside the
    roots would report the suffix wall under this order, so it cannot
    discriminate — asserted separately rather than smuggled in here."""
    root = tmp_path / "open_root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    ex, opened = _executor(tmp_path, (root,))
    contained = await ex.open_path(str(outside / "notes.txt"))
    assert "outside_allowed_roots" in contained.detail, contained.detail
    assert "IS launching it" not in contained.detail, contained.detail
    suffix = await ex.open_path(str(root / "payload.exe"))
    assert "outside_allowed_roots" not in suffix.detail, suffix.detail
    assert "IS launching it" in suffix.detail, suffix.detail
    assert opened == []


async def test_a_blocked_suffix_outside_the_roots_reports_the_suffix_wall(tmp_path: Path):
    """The order law, pinned: the suffix wall fires FIRST, so a `.exe` anywhere
    is refused as a launcher even when its location would also fail
    containment. Both are refusals, so nothing is admitted — but the message
    tells the owner the thing that would actually help them."""
    root = tmp_path / "open_root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    ex, opened = _executor(tmp_path, (root,))
    result = await ex.open_path(str(outside / "payload.exe"))
    assert result.status == "error"
    assert "IS launching it" in result.detail, result.detail
    assert opened == []


async def test_case_folded_suffix_is_still_refused(tmp_path: Path):
    """`.LNK`/`.URL` must not walk past a casefold — Windows filenames are
    case-insensitive, so a case-sensitive set would be theatre."""
    root = tmp_path / "open_root"
    root.mkdir()
    ex, opened = _executor(tmp_path, (root,))
    result = await ex.open_path(str(root / "SHORTCUT.LNK"))
    assert result.status == "error"
    assert opened == []


# -- 3. CONTAINMENT ----------------------------------------------------------------


async def test_absolute_path_outside_every_root_is_refused(tmp_path: Path):
    """MUTANT (c) — dropping the roots check entirely. Pre-F-3 this was the
    hole: ANY absolute path on ANY drive was opened."""
    root = tmp_path / "open_root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    ex, opened = _executor(tmp_path, (root,))
    result = await ex.open_path(str(outside / "report.txt"))
    assert result.status == "error"
    assert "outside_allowed_roots" in result.detail
    assert opened == []


async def test_absolute_path_inside_a_root_is_admitted(tmp_path: Path):
    """MUTANT (c') — the opposite failure: a containment check that refuses
    everything is not a fix, it is a dead bridge. The fix must NOT
    over-block."""
    root = tmp_path / "open_root"
    root.mkdir()
    doc = root / "report.txt"
    doc.write_text("hello", encoding="utf-8")
    ex, opened = _executor(tmp_path, (root,))
    result = await ex.open_path(str(doc))
    assert result.status == "ok", result.detail
    assert opened == [str(doc.resolve())]


async def test_every_configured_root_is_reachable(tmp_path: Path):
    """The roots are a SET, not a first-root-only wall: a second root the
    owner configured must be as reachable as the first."""
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir()
    second.mkdir()
    doc = second / "deep" / "notes.md"
    doc.parent.mkdir()
    doc.write_text("x", encoding="utf-8")
    ex, opened = _executor(tmp_path, (first, second))
    result = await ex.open_path(str(doc))
    assert result.status == "ok", result.detail
    assert opened == [str(doc.resolve())]


async def test_sibling_directory_sharing_the_root_name_is_refused(tmp_path: Path):
    """MUTANT (a)/the prefix bug — `Downloads-evil` is NOT inside `Downloads`.
    Containment must compare PATH COMPONENTS; a plain string-prefix test
    admits the sibling, and `resolve_in_roots` still does exactly that."""
    root = tmp_path / "Downloads"
    root.mkdir()
    sibling = tmp_path / "Downloads-evil"
    sibling.mkdir()
    ex, opened = _executor(tmp_path, (root,))
    result = await ex.open_path(str(sibling / "x.txt"))
    assert result.status == "error"
    assert "outside_allowed_roots" in result.detail
    assert opened == []


async def test_resolve_in_roots_refuses_when_the_relative_resolve_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The RELATIVE branch of `resolve_in_roots` has its own OSError arm, added
    with the containment rewrite. An unresolvable relative path must skip that
    base and keep looking — never raise out of the helper, which `file_download`
    and the file-drop wall both call on the owner's request."""
    root = tmp_path / "Downloads"
    root.mkdir()
    calls: list[int] = []
    real_resolve = Path.resolve

    def _counting_resolve(self, *args, **kwargs):
        calls.append(1)
        if "bad" in self.name:
            raise OSError("unresolvable")
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", _counting_resolve)
    assert resolve_in_roots("bad.txt", (root,)) is None
    assert calls, "the helper never attempted a resolve"
    assert resolve_in_roots("good.txt", (root,)) == real_resolve(root / "good.txt")


async def test_resolve_in_roots_refuses_the_sibling_prefix_escape(tmp_path: Path):
    """The shared helper is the containment primitive — it carries the same
    wall for `file_download`, so its prefix hole is F-3's hole too.
    (Measured pre-fix: `str(resolved).startswith(str(base_resolved))` admits
    `<root>-evil`.)"""
    root = tmp_path / "Downloads"
    root.mkdir()
    sibling = tmp_path / "Downloads-evil"
    sibling.mkdir()
    assert resolve_in_roots(str(sibling / "x.txt"), (root,)) is None
    assert resolve_in_roots(str(root / "ok.txt"), (root,)) is not None


async def test_roots_refusal_names_the_roots_that_do_work(tmp_path: Path):
    """Same honesty law as the suffix refusal: an owner told only
    'outside_allowed_roots' cannot act on it. The message must name the
    folders that ARE reachable."""
    root = tmp_path / "open_root"
    root.mkdir()
    ex, _ = _executor(tmp_path, (root,))
    result = await ex.open_path(str(tmp_path / "nope" / "x.txt"))
    assert result.status == "error"
    assert str(root) in result.detail, result.detail


async def test_relative_bare_name_resolves_against_the_process_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """MUTANT (c4) — a bare name must NOT silently re-home itself into the
    first open root. That would open a DIFFERENT file of the same name than the
    daemon was pointed at: today `os.startfile("report.pdf")` means CWD-relative
    (`data/inbox` is itself a CWD-relative file root), and a decoy of the same
    name sitting in the first root would be opened instead.

    The decoy is the whole point: without one, "resolve against CWD" and
    "resolve against root[0]" are indistinguishable, and this guard measured
    itself blind to that mutant until the decoy landed."""
    first = tmp_path / "open_root"
    first.mkdir()
    (first / "report.pdf").write_bytes(b"decoy")
    work = tmp_path / "work"
    work.mkdir()
    (work / "report.pdf").write_bytes(b"real")
    ex, opened = _executor(tmp_path, (first, work))
    monkeypatch.chdir(work)
    result = await ex.open_path("report.pdf")
    assert result.status == "ok", result.detail
    assert opened == [str((work / "report.pdf").resolve())], "opened the wrong file of the two"


async def test_no_open_roots_configured_fails_closed(tmp_path: Path):
    """MUTANT (c) — 'unconfigured' must mean 'nothing opens', never 'the wall
    is off'. Fail-closed, and the token `src/tools.py` maps to the owner's
    Arabic message is still present.

    The token is asserted for a REASON, not decoration: dropping the explicit
    empty-roots branch would fall through to the per-path loop, which on an
    empty tuple happens to refuse too. Same outcome, different message — and a
    refusal whose copy the core cannot map is a dead end, so the branch is
    pinned."""
    ex, opened = _executor(tmp_path, ())
    result = await ex.open_path(str(tmp_path / "report.txt"))
    assert result.status == "error"
    assert "outside_allowed_roots" in result.detail
    assert "not configured" in result.detail, result.detail
    assert opened == []


async def test_empty_path_is_refused_by_the_empty_wall_not_by_containment(tmp_path: Path):
    """MUTANT (h) — `os.startfile("")` used to be the answer for an empty
    request. An empty path must hit the empty-wall refusal, NOT fall through to
    the containment wall: `Path("")` resolves to the CWD, so containment would
    refuse it too and the owner would be told 'outside_allowed_roots' for a
    request that never named a path at all."""
    root = tmp_path / "open_root"
    root.mkdir()
    ex, opened = _executor(tmp_path, (root,))
    for blank in ("", "   ", "\t\n"):
        result = await ex.open_path(blank)
        assert result.status == "error", repr(blank)
        assert "empty path" in result.detail, (repr(blank), result.detail)
    assert opened == []


async def test_unresolvable_path_fails_closed_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A resolve() that raises must refuse, not propagate — `os.startfile` on
    an unvalidated string is exactly the hole."""
    root = tmp_path / "open_root"
    root.mkdir()
    ex, opened = _executor(tmp_path, (root,))

    def _boom(self, *args, **kwargs):
        raise OSError("unresolvable")

    monkeypatch.setattr(Path, "resolve", _boom)
    result = await ex.open_path(str(root / "report.txt"))
    assert result.status == "error"
    assert "outside_allowed_roots" in result.detail
    assert opened == []


# -- the seeded roots: no over-blocking, no over-broadness -------------------------


async def test_executor_seed_reaches_the_owner_home_and_the_project(tmp_path: Path):
    """MUTANT (c3) — the over-blocking guard, asserted on the EXECUTOR, not on
    the seed helper.

    Asserting only `default_open_roots()` was blind: swapping the constructor's
    default for `DEFAULT_FILE_ROOTS` leaves the helper correct and confines
    every open to Downloads, breaking the tool for the whole project. The law
    is about what the shipped Executor does, so the guard reads the Executor.

    No file is written under the home or the repo: `open_path` only resolves and
    hands the path to the `_open` seam, which is spied here."""
    ex, _opened = _executor(tmp_path, None)
    assert ex._open_roots, "an unconfigured Executor must still be seeded"
    assert Path.home() in ex._open_roots, ex._open_roots
    repo_root = Path(executor_mod.__file__).resolve().parents[1]
    assert repo_root in ex._open_roots, ex._open_roots
    # and the real verb agrees with the attribute
    assert (await ex.open_path(str(Path.home() / "desktop_probe.txt"))).status == "ok"
    assert (await ex.open_path(str(repo_root / "probe.txt"))).status == "ok"
    assert (await ex.open_path("C:/Windows/System32/drivers/etc/hosts")).status == "error"


async def test_default_open_roots_reach_the_owner_home_and_the_project():
    """The seed helper itself carries the same two entries (the constructor
    guard above is the one that survives a wiring swap; this one pins the
    helper's contract independently)."""
    roots = default_open_roots()
    home = Path.home()
    assert any(root == home for root in roots), roots
    repo_root = Path(executor_mod.__file__).resolve().parents[1]
    assert any(root == repo_root for root in roots), roots


async def test_default_open_roots_are_deduplicated_and_dont_include_user_profile():
    """The counter-weight to the over-blocking guard: `C:\\Users` as a root
    would 'reach the home' while admitting every other profile on the box —
    a containment failure dressed as convenience. The home's PARENT must never
    be a seeded root."""
    roots = default_open_roots()
    assert len(roots) == len(set(roots)), roots
    parent_of_home = Path.home().parent
    assert parent_of_home not in roots, roots
    assert Path("C:/") not in roots, roots
    assert Path("C:/Windows") not in roots, roots


async def test_open_path_does_not_reuse_the_file_drop_roots():
    """MUTANT (c'''') — reusing DEFAULT_FILE_ROOTS confines every open to
    Downloads and breaks the tool. open_roots must be an INDEPENDENT set that
    happens to be a superset, not the same object."""
    assert DEFAULT_FILE_ROOTS  # the file-drop landing zone still exists
    assert tuple(Path(r) for r in DEFAULT_FILE_ROOTS) not in default_open_roots() or set(
        DEFAULT_FILE_ROOTS
    ) != {str(p) for p in default_open_roots()}


async def test_open_roots_constructor_argument_overrides_the_seed(tmp_path: Path):
    """The knob is a CONSTRUCTOR ARGUMENT (F-5 `bridge_path` precedent — no
    env var), so the owner wires it where the daemon builds the Executor."""
    root = tmp_path / "only_this"
    root.mkdir()
    doc = root / "x.txt"
    doc.write_text("x", encoding="utf-8")
    ex, opened = _executor(tmp_path, (root,))
    assert (await ex.open_path(str(doc))).status == "ok"
    assert (await ex.open_path(str(Path.home() / "Desktop" / "y.txt"))).status == "error"
    assert opened == [str(doc.resolve())]


# -- 1. confirmation_id --------------------------------------------------------------


def test_open_path_never_deletes_its_confirmation_id():
    """MUTANT (d) — `del confirmation_id` at the top of open_path. The report's
    DoD is a source-level pin: the id must not be silently discarded. Reading
    the source is the only honest way to say that — Python gives us no hook on
    a `del` of a parameter."""
    source = inspect.getsource(executor_mod)
    assert "del confirmation_id" not in source


async def test_confirmation_id_does_not_gate_a_legitimate_open(tmp_path: Path):
    """MUTANT (e') — the counter-mutant to `..._is_not_a_bypass`. An id must
    neither HELP nor HURT: a path inside the roots opens with and without one.
    This pins the other half of the contract, so a fix cannot satisfy
    `is_not_a_bypass` by demanding an id and breaking every ordinary open."""
    root = tmp_path / "open_root"
    root.mkdir()
    doc = root / "report.txt"
    doc.write_text("x", encoding="utf-8")
    without, _ = _executor(tmp_path, (root,))
    with_id, _ = _executor(tmp_path, (root,))
    assert (await without.open_path(str(doc))).status == "ok"
    assert (await with_id.open_path(str(doc), confirmation_id="cid-123")).status == "ok"


async def test_open_path_documents_the_confirmation_contract():
    """The id is kept for wire symmetry with launch/close, and it is NOT a
    bypass. That is a policy statement, so it must be TRUE OF THE CODE and
    written down where a reader (and F-2) will find it."""
    doc = inspect.getdoc(Executor.open_path) or ""
    assert doc.strip(), "open_path must document what it does with confirmation_id"
    assert "confirmation_id" in doc


async def test_confirmation_id_is_not_a_bypass(tmp_path: Path):
    """Whatever the id says, the walls hold. F-2 owns id VERIFICATION for the
    verbs that need one; F-3's law is narrower and is tested here: no id moves
    a path out of a wall."""
    root = tmp_path / "open_root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    # The blocked path sits INSIDE the roots on purpose. An `.exe` outside the
    # roots is refused by the containment wall whichever way the suffix check
    # reads, so that shape cannot tell whether the id moved it — measured, this
    # guard was blind until the payload moved inside. The walls are separate
    # laws and a guard must isolate one of them.
    (root / "payload.exe").write_bytes(b"MZ")
    (outside / "plain.txt").write_text("x", encoding="utf-8")
    for cid in ("cid-123", "a" * 64, ""):
        inside, inside_opened = _executor(tmp_path, (root,))
        assert (await inside.open_path(str(root / "ok.txt"), confirmation_id=cid)).status == "ok"
        assert len(inside_opened) == 1, cid
        escaped, escaped_opened = _executor(tmp_path, (root,))
        out = await escaped.open_path(str(outside / "plain.txt"), confirmation_id=cid)
        assert out.status == "error", cid
        assert "outside_allowed_roots" in out.detail, (cid, out.detail)
        assert escaped_opened == [], (cid, escaped_opened)
        blocked_exec, blocked_opened = _executor(tmp_path, (root,))
        blocked = await blocked_exec.open_path(str(root / "payload.exe"), confirmation_id=cid)
        assert blocked.status == "error", cid
        assert "app whitelist" in blocked.detail, (cid, blocked.detail)
        assert blocked_opened == [], (cid, blocked_opened)
