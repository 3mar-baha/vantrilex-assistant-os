"""N5 — the 429/403 DISCRIMINATOR: a rate limit is retried, a REFUSED credential is
not, and the decision happens in exactly one pure function.

THE DEFECT THIS PINS. GitHub answers HTTP 403 for BOTH an exhausted rate limit AND
an under-scoped PAT. The shipped reader treated a 403 as «a rate limit iff it
carries ``Retry-After``» and therefore did three wrong things:

  1. a bad-scope 403 that happens to carry ``Retry-After`` WAS RETRIED — waiting on
     a refusal, which cannot become a success, burning a request and hiding the real
     operator action («rotate the PAT»);
  2. a primary rate-limit 403 with NO ``Retry-After`` was NOT retried — it fell
     straight to ``raise_for_status()`` while ``X-RateLimit-Remaining: 0`` and
     ``x-ratelimit-reset`` sat in the same response, fully sufficient to decide;
  3. there was no ``x-ratelimit-reset`` fallback at all and the cap was a flat 30 s,
     so a limit whose reset was 40 s out was abandoned rather than waited out.

LAW 1 — ONE decision site, and it is PURE. ``src.vault.classify_rate_limit`` maps
``(headers, status)`` to a ``RateVerdict``. No client, no I/O, no sleeping. The
purity is the whole point: it is what lets ``src/health.py`` — which opens its OWN
``httpx.AsyncClient`` and never touches ``VaultClient``, so it has no shared call
site to reuse — consume the same law instead of reimplementing it. The one-site
guard is a whole-module AST scan of the header literals, so a second
implementation anywhere in ``src/`` is caught structurally.

LAW 2 — ``Retry-After`` is DEMOTED to a secondary signal, and the mechanism is why.
It is the header that caused failure 1 above: GitHub attaches it to secondary rate
limits AND an under-scoped PAT can receive one, so its presence does NOT
establish «rate limited». Only ``X-RateLimit-Remaining: 0`` — present AND zero —
does. A 403 with neither is REFUSED and is NEVER retried.

LAW 3 — the retry stays SINGLE-SHOT. One extra request per call, bounded, asserted
here by request COUNT. An unbounded loop against a free API is how the ``$0.00``
invariant gets spent.

LAW 4 — ``misconfigured`` and ``unreachable`` stay DISTINGUISHABLE end to end. The
probe consumes the predicate, so a rate-limited 403 reports ``unreachable``
(nobody could determine the state) and a refused PAT still reports
``misconfigured`` (present and REFUSED). N3's docstrings reserved this as open work;
N5 landed it, so those reservations are now false claims and are pinned gone.

NO TEST REACHES THE NETWORK. Every GitHub call is driven through
``httpx.MockTransport`` and the predicate is handed plain dicts. ``tests/conftest.py``
raises ``SuiteNetworkBlocked`` on any non-loopback socket regardless.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import inspect
import time
from pathlib import Path

import httpx
import pytest

from src import health as health_mod
from src import vault as vault_mod

SRC = Path(__file__).resolve().parents[1] / "src"
VAULT_PY = SRC / "vault.py"
HEALTH_PY = SRC / "health.py"

TOKEN = "your-github-test-pat-abcdef0123456789"
API = "https://api.github.com"

#: The three headers the discriminator READS, lowercased because HTTP header names
#: are case-insensitive and the law is about a MECHANISM, not a spelling.
RATE_LIMIT_HEADERS = frozenset({"retry-after", "x-ratelimit-remaining", "x-ratelimit-reset"})

#: Nothing a PURE function may touch. It reads header values and the clock, and
#: that is the whole of its world: no socket, no file, no client, no clock-wait.
_FORBIDDEN_IN_A_PURE_FUNCTION = frozenset(
    {
        "httpx",
        "socket",
        "ssl",
        "open",
        "urlopen",
        "urlretrieve",
        "requests",
        "aiohttp",
        "subprocess",
        "pathlib",
        "os",
        "shutil",
        "tempfile",
        "sleep",
        "get",
        "post",
        "request",
        "send",
        "headers",
        "client",
        "session",
        "transport",
    }
)


# ── doubles ────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace ``asyncio.sleep`` with a recorder and return the list it fills.

    Backoff is part of the shipped behaviour, so a guard that let the real clock
    run would either take a minute or lie about the cap. Recording keeps the
    assertions exact AND keeps the suite fast.
    """
    recorded: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    return recorded


def _boom_on_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """A sleep that FAILS the test. For guards proving nothing slept."""

    async def _boom(seconds: float) -> None:
        raise AssertionError(f"the predicate slept {seconds}s — it must be pure")

    monkeypatch.setattr(asyncio, "sleep", _boom)


def _note(text: str = "سطر") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "name": "x.md",
            "path": "notes/x.md",
            "encoding": "base64",
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        },
    )


def _reset_header(seconds_from_now: float) -> str:
    """GitHub's reset header: an ABSOLUTE unix epoch second, not a duration."""
    return str(int(time.time() + seconds_from_now))


def _exhausted(reset_in: float = 40.0, **extra: str) -> dict[str, str]:
    headers = {
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Limit": "5000",
        "x-ratelimit-reset": _reset_header(reset_in),
    }
    headers.update(extra)
    return headers


class _Script:
    """Queued responses over a real ``httpx`` transport, counting every request.

    A real ``httpx.Response`` matters: its ``.headers`` is a case-insensitive
    ``Headers`` object, so the guards exercise the header access the shipped code
    actually performs rather than a dict stand-in's ``.get``.
    """

    def __init__(self, *responses: httpx.Response) -> None:
        self.queued = list(responses)
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self.queued.pop(0) if self.queued else _note()

        return httpx.MockTransport(handler)

    def client(self) -> vault_mod.VaultClient:
        session = httpx.AsyncClient(base_url=API, transport=self.transport())
        return vault_mod.VaultClient("owner/vault-repo", TOKEN, session=session)

    @property
    def count(self) -> int:
        return len(self.requests)


def _client(*responses: httpx.Response) -> tuple[vault_mod.VaultClient, _Script]:
    script = _Script(*responses)
    return script.client(), script


class _GitHub:
    """Answers the GitHub lane with one fixed status/headers pair; counts calls.

    Every other host answers 200 so a stray lane cannot be mistaken for the vault.
    """

    def __init__(self, status: int, headers: dict[str, str]) -> None:
        self.status = status
        self.headers = dict(headers)
        self.calls: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(request)
            if request.url.host != "api.github.com":
                return httpx.Response(200, json={"ok": True, "items": []})
            return httpx.Response(self.status, json={"message": "x"}, headers=self.headers)

        return httpx.MockTransport(handler)


# ── AST helpers: the source of truth for «where is the decision made» ───────────────


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """The named function, found by NAME. Raises if it is gone.

    A guard whose subject disappeared must FAIL, not pass vacuously (Directive 2).
    """
    for node in ast.walk(_tree(path)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{path.name}: `{name}` is gone — this guard has nothing left to check")


def _code_strings(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Every string literal in ``func`` EXCEPT its own docstring.

    Excluding the docstring is what lets prose NAME the headers it describes
    without that reading as a second implementation of the decision.
    """
    doc_node = None
    if func.body and isinstance(func.body[0], ast.Expr):
        head = func.body[0].value
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            doc_node = head
    return {
        node.value
        for node in ast.walk(func)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node is not doc_node
    }


def _rate_limit_sites() -> list[tuple[str, str]]:
    """``(module, function)`` for every function in the two modules that READS a
    rate-limit header. The one-decision-site law is the identity of this list, not
    a grep over prose."""
    found: list[tuple[str, str]] = []
    for path in (VAULT_PY, HEALTH_PY):
        for node in ast.walk(_tree(path)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if {s.lower() for s in _code_strings(node)} & RATE_LIMIT_HEADERS:
                found.append((path.name, node.name))
    return found


# ── the DELETED logic, kept only so the OLD→NEW table is machine-checked ───────────


def _deleted_shipped_logic(headers: dict[str, str], status: int) -> str:
    """``src.vault.VaultClient._get_with_rate_limit`` exactly as it shipped before N5.

    THIS IS THE OLD CODE, NOT A SECOND DECISION SITE. It exists so the OLD→NEW
    acceptance table below is checked against a runnable statement of the old law
    rather than against my memory of it. Nothing in ``src/`` imports it — the
    one-site guard scans ``src/`` only, and that is the point.
    """
    if status not in (429, 403):
        return "surface"  # not 429/403 — returned untouched, no header consulted
    retry_after = headers.get("Retry-After")
    if retry_after is None:
        return "surface"  # failure 2: a primary 403 with no Retry-After gave up here
    try:
        min(float(retry_after), 30.0)  # failure 3: the flat, non-negotiable 30 s cap
    except ValueError:
        return "surface"
    return "retry"


# ── LAW 1: the predicate is pure and has ONE signature ──────────────────────────────


def test_the_predicate_takes_headers_and_a_status_and_nothing_else() -> None:
    """The contract a second module relies on: no client, no session, no settings.

    Read from the signature rather than from prose, so a new required parameter
    cannot be slipped in behind a docstring that still says «headers and a status».
    """
    params = list(inspect.signature(vault_mod.classify_rate_limit).parameters.values())
    assert [p.name for p in params] == ["headers", "status"], (
        "classify_rate_limit must accept exactly (headers, status) — a second module calls it "
        "with headers alone, and any further parameter breaks that contract"
    )
    assert all(
        p.default is inspect.Parameter.empty and p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        for p in params
    ), "neither parameter may be optional or keyword-only: the caller passes both, in order"


def test_the_predicate_needs_no_client_and_never_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE PURITY GUARD, behaviourally.

    Called with a plain ``dict`` and an ``int`` — no client exists anywhere in the
    call — while ``asyncio.sleep`` is rigged to fail. If purity were a claim rather
    than a fact, this is where it would show. Both verdicts are exercised, so
    purity is not a property of only the rate-limit branch.
    """
    _boom_on_sleep(monkeypatch)
    assert vault_mod.classify_rate_limit({"x-ratelimit-remaining": "0"}, 403).should_retry is True
    assert vault_mod.classify_rate_limit({}, 403).should_retry is False
    assert vault_mod.classify_rate_limit({}, 429).should_retry is True
    assert vault_mod.classify_rate_limit({}, 200).should_retry is False


def test_the_predicate_cannot_block_or_reach_out_of_the_process() -> None:
    """Purity, structurally: no ``await``, no yield, and no I/O root name.

    «Pure» would be unfalsifiable if it were only prose. This reads the body: the
    predicate must reference no networking, filesystem or subprocess name at all,
    which is what makes «a second module can call it without a client» a fact.
    """
    func = _function(VAULT_PY, "classify_rate_limit")
    referenced: set[str] = set()
    blocking: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Await):
            blocking.append("awaits")
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            blocking.append("yields")
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        if isinstance(node, ast.Attribute):
            referenced.add(node.attr)
    assert not blocking, f"classify_rate_limit {blocking} — it must be a pure mapping"
    leaked = referenced & _FORBIDDEN_IN_A_PURE_FUNCTION
    assert not leaked, f"classify_rate_limit references {sorted(leaked)} — it is not pure"


# ── LAW 2: the discriminator, case by case ─────────────────────────────────────────


def test_a_429_is_always_retried_whatever_else_it_carries() -> None:
    """429 IS the limit. GitHub sends it for no other reason, so nothing demotes
    it — not a missing header, not a malformed one."""
    for label, headers in {
        "bare": {},
        "malformed hint": {"Retry-After": "soon"},
        "exhausted quota": {"X-RateLimit-Remaining": "0"},
        "malformed reset": {"x-ratelimit-reset": "whenever"},
    }.items():
        verdict = vault_mod.classify_rate_limit(dict(headers), 429)
        assert verdict.kind is vault_mod.RateLimitKind.TOO_MANY, f"429 {label} kind"
        assert verdict.should_retry is True, f"429 {label} must retry"
        assert verdict.backoff_s >= 0.0, f"429 {label} must carry a usable wait"


def test_an_exhausted_quota_is_a_primary_limit_with_and_without_retry_after() -> None:
    """Failure 2, pinned from both sides.

    ``X-RateLimit-Remaining: 0`` — present AND zero — is the ONLY header that
    proves a rate limit. With ``Retry-After`` alongside it the verdict is the same,
    which is the property the old code lacked: it only ever looked at the second
    header.
    """
    for label, headers in {
        "without a hint": _exhausted(40.0),
        "with a hint": _exhausted(40.0, **{"Retry-After": "12"}),
    }.items():
        verdict = vault_mod.classify_rate_limit(dict(headers), 403)
        assert verdict.kind is vault_mod.RateLimitKind.PRIMARY, label
        assert verdict.should_retry is True, f"primary rate-limit 403 {label} must retry"
        assert verdict.backoff_s == pytest.approx(40.0, abs=2.0), (
            f"{label}: the backoff must come from the reset header, not from the hint"
        )


def test_a_retry_after_without_an_exhausted_quota_is_only_a_secondary_signal() -> None:
    """The demotion, stated. Still retryable — GitHub does use this for secondary
    limits — but the KIND records that the evidence is weaker than «quota: 0»."""
    verdict = vault_mod.classify_rate_limit({"Retry-After": "30"}, 403)
    assert verdict.kind is vault_mod.RateLimitKind.SECONDARY
    assert verdict.should_retry is True
    assert verdict.backoff_s == pytest.approx(30.0)


def test_the_headline_law_a_bad_scope_403_never_retries() -> None:
    """THE LIVE BUG. A 403 carrying ``Retry-After`` but no exhausted-rate-limit
    header is an under-scoped PAT, and the old code retried it.

    This is the single guard the node exists for, so it is asserted from both
    directions: the verdict refuses, AND ``backoff_s`` is zero — a verdict that
    said «do not retry» while still handing the caller a sixty-second wait would
    be a contradiction the caller could not resolve.
    """
    verdict = vault_mod.classify_rate_limit({"Retry-After": "5"}, 403)
    assert verdict.kind is vault_mod.RateLimitKind.REFUSED
    assert verdict.should_retry is False, (
        "a 403 with a retry hint and no exhausted quota is a REFUSED credential — retrying it "
        "hides the operator's real action (rotate the PAT)"
    )
    assert verdict.backoff_s == 0.0, "a verdict that will not retry must carry no backoff"


def test_a_bare_403_with_no_headers_at_all_is_refused() -> None:
    verdict = vault_mod.classify_rate_limit({}, 403)
    assert verdict.kind is vault_mod.RateLimitKind.REFUSED
    assert verdict.should_retry is False
    assert verdict.backoff_s == 0.0


@pytest.mark.parametrize("status", [200, 201, 301, 404, 409, 422, 500, 502])
def test_no_other_status_is_ever_a_rate_limit(status: int) -> None:
    """Row 5 of the discriminator.

    Note the exhausted-quota header rides along on a 200 too — GitHub sends it on
    every response — and it must NOT turn a success into a retryable rate limit.
    The rate-limit rows are gated on the two statuses where a retry can still
    succeed; retrying a 200 would burn a request and sleep for nothing.
    """
    verdict = vault_mod.classify_rate_limit(_exhausted(5.0), status)
    assert verdict.kind is vault_mod.RateLimitKind.CLEAR
    assert verdict.should_retry is False
    assert verdict.backoff_s == 0.0


def test_a_non_zero_remaining_quota_is_not_a_limit() -> None:
    """«Present AND zero». 4999 remaining is a working quota, not an exhausted one
    — and a 403 alongside it is a refusal."""
    verdict = vault_mod.classify_rate_limit({"X-RateLimit-Remaining": "4999"}, 403)
    assert verdict.kind is vault_mod.RateLimitKind.REFUSED
    assert verdict.should_retry is False


def test_a_reset_in_the_past_never_produces_a_negative_sleep() -> None:
    """A reset that has already passed means «retry now», not «retry in -30 s»."""
    verdict = vault_mod.classify_rate_limit(
        {"X-RateLimit-Remaining": "0", "x-ratelimit-reset": str(int(time.time()) - 30)}, 403
    )
    assert verdict.should_retry is True
    assert verdict.backoff_s == 0.0


def test_the_predicate_reads_headers_case_insensitively() -> None:
    """HTTP header names are case-insensitive, so a dict spelled any way must
    classify identically. httpx lower-cases its own headers; a plain dict does not,
    and this predicate is documented to take a plain mapping."""
    canonical = _exhausted(15.0, **{"Retry-After": "9"})
    shouted = {key.upper(): value for key, value in canonical.items()}
    lower = vault_mod.classify_rate_limit(canonical, 403)
    upper = vault_mod.classify_rate_limit(shouted, 403)
    assert lower.kind is upper.kind is vault_mod.RateLimitKind.PRIMARY
    assert lower.should_retry is upper.should_retry is True
    assert lower.backoff_s == pytest.approx(upper.backoff_s, abs=2.0)

    for header in ("Retry-After", "retry-after", "RETRY-AFTER"):
        verdict = vault_mod.classify_rate_limit({header: "9"}, 403)
        assert verdict.kind is vault_mod.RateLimitKind.SECONDARY, header
        assert verdict.backoff_s == pytest.approx(9.0), header


# ── the cap and the fallback: asserted, never assumed ──────────────────────────────


def test_the_backoff_cap_is_stated_and_the_backoff_is_clamped_to_it() -> None:
    """The cap is a NAMED constant with a stated reason, and a reset far beyond it
    is clamped rather than slept.

    GitHub's primary window is an hour, so the reset header can legitimately point
    far out. Honouring it literally would pin a read handler for most of an hour;
    the cap bounds that, and the bound is what the client actually sleeps.
    """
    cap = vault_mod.RATE_LIMIT_BACKOFF_CAP_S
    assert cap == 60.0, f"the backoff cap is {cap}, not the stated 60.0"
    verdict = vault_mod.classify_rate_limit(_exhausted(3600.0), 403)
    assert verdict.backoff_s == cap, "an hour-out reset must be clamped to the cap, not slept"


def test_the_cap_is_never_exceeded_by_any_hint_a_server_can_send() -> None:
    """A hostile or confused server must not be able to buy an unbounded sleep.
    Every hint is checked: a huge one, a negative one, a non-numeric one, and a
    reset far in the future."""
    hints = [
        {"Retry-After": "99999"},
        {"Retry-After": "-5"},
        {"Retry-After": "later"},
        _exhausted(100000.0),
        _exhausted(-100000.0),
        _exhausted(100000.0, **{"Retry-After": "99999"}),
    ]
    for hint in hints:
        for status in (403, 429):
            verdict = vault_mod.classify_rate_limit(dict(hint), status)
            assert 0.0 <= verdict.backoff_s <= vault_mod.RATE_LIMIT_BACKOFF_CAP_S, (
                f"{hint} on HTTP {status} produced {verdict.backoff_s}s, outside "
                f"[0, {vault_mod.RATE_LIMIT_BACKOFF_CAP_S}]"
            )


def test_the_backoff_falls_back_to_a_short_default_when_the_server_says_nothing() -> None:
    """A 429 with no usable timing hint still retries — but briefly, because the
    server said «slow down» without saying for how long, and this is one retry."""
    verdict = vault_mod.classify_rate_limit({}, 429)
    assert verdict.should_retry is True
    assert verdict.backoff_s == vault_mod.RATE_LIMIT_FALLBACK_BACKOFF_S
    assert 0.0 < verdict.backoff_s <= 5.0, (
        "the no-hint fallback must be short: it runs inside a chat turn, not a batch job"
    )


def test_a_malformed_hint_does_not_parse_crash_and_does_not_sleep_the_garbage() -> None:
    verdict = vault_mod.classify_rate_limit(
        {"X-RateLimit-Remaining": "0", "x-ratelimit-reset": "in a minute"}, 403
    )
    assert verdict.should_retry is True
    assert verdict.backoff_s == vault_mod.RATE_LIMIT_FALLBACK_BACKOFF_S


# ── the client: the retry actually happens, exactly once ────────────────────────────


async def test_a_rate_limited_read_is_retried_and_succeeds() -> None:
    client, script = _client(
        httpx.Response(403, json={"message": "rate limited"}, headers=_exhausted(40.0)),
        _note("بعد إعادة المحاولة"),
    )
    assert await client.read("notes/x.md") == "بعد إعادة المحاولة"
    assert script.count == 2, "one retry means exactly two requests"


async def test_a_rate_limited_read_with_no_retry_hint_is_retried() -> None:
    """Failure 2 at the seam the operator actually hits: the old code surfaced this
    response even though the response itself said the quota was exhausted."""
    client, script = _client(
        httpx.Response(403, json={"message": "rate limited"}, headers=_exhausted(40.0)),
        _note("نجحت"),
    )
    assert await client.read("notes/x.md") == "نجحت"
    assert script.count == 2


async def test_a_429_read_is_retried_and_succeeds() -> None:
    client, script = _client(
        httpx.Response(429, json={"message": "too many"}, headers={"Retry-After": "0"}),
        _note("نجحت"),
    )
    assert await client.read("notes/x.md") == "نجحت"
    assert script.count == 2


async def test_a_bad_scope_403_reaches_the_network_exactly_once() -> None:
    """Failure 1 at the seam, including the case the brief names: a retry hint
    present, no exhausted quota. ONE request — not two."""
    client, script = _client(
        httpx.Response(
            403,
            json={"message": "Resource not accessible by personal access token"},
            headers={"Retry-After": "1"},
        ),
        _note("must never be reached"),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.read("notes/x.md")
    assert script.count == 1, (
        "a REFUSED credential was retried — the read waited on a refusal that cannot become a "
        "success and hid the operator's real action"
    )


async def test_a_bare_bad_scope_403_reaches_the_network_exactly_once() -> None:
    client, script = _client(
        httpx.Response(403, json={"message": "Bad credentials"}), _note("must never be reached")
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.read("notes/x.md")
    assert script.count == 1


async def test_a_refused_list_reaches_the_network_exactly_once() -> None:
    """The same law on the directory path, which has its own ``raise_for_status`` —
    so the bound is a property of the DECISION, not of one caller."""
    client, script = _client(
        httpx.Response(403, json={"message": "Bad credentials"}, headers={"Retry-After": "2"}),
        httpx.Response(200, json=[]),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.list_dir("notes")
    assert script.count == 1


async def test_the_client_sleeps_the_verdict_backoff_not_a_flat_thirty(
    sleeps: list[float],
) -> None:
    """Failure 3. The old cap was a hard 30.0 s, so a limit whose reset was 40 s out
    was abandoned. The wait is now the verdict's, clamped by a named cap."""
    client, _script = _client(
        httpx.Response(403, json={"message": "rate limited"}, headers=_exhausted(40.0)), _note()
    )
    assert await client.read("notes/x.md")
    assert len(sleeps) == 1, f"expected exactly one wait, got {sleeps}"
    assert sleeps[0] == pytest.approx(40.0, abs=2.0), (
        f"the client slept {sleeps[0]}s — it must wait out the reset the response announced, not "
        "a hardcoded 30 s that abandons a limit 40 s out"
    )


async def test_a_rate_limit_is_retried_once_and_only_once(sleeps: list[float]) -> None:
    """LAW 3, by request COUNT rather than by prose.

    A limit that survives the retry must SURFACE, not loop. Two requests, never
    three, and exactly one sleep: an unbounded loop against a free API is how the
    ``$0.00`` invariant gets spent.
    """
    client, script = _client(*[_limited_403() for _ in range(3)])
    with pytest.raises(httpx.HTTPStatusError):
        await client.read("notes/x.md")
    assert script.count == 2, (
        f"a persistent rate limit made {script.count} requests; the bound is 2"
    )
    assert len(sleeps) == 1, f"the bound is ONE retry, so ONE wait; got {sleeps}"


def _limited_403() -> httpx.Response:
    return httpx.Response(403, json={"message": "rate limited"}, headers=_exhausted(5.0))


async def test_a_persistent_rate_limit_still_fails_loudly() -> None:
    """The half of the old law that was already right and must stay right."""
    client, _script = _client(
        httpx.Response(429, json={"message": "too many"}, headers={"Retry-After": "0"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.read("notes/x.md")


async def test_the_single_shot_latch_is_released_for_the_next_call() -> None:
    """The bound is per CALL, not per client lifetime: a later rate-limited read
    still gets its one retry, or a transient blip would degrade a whole session."""
    client, script = _client(_limited_403(), _note("one"), _limited_403(), _note("two"))
    assert await client.read("notes/x.md") == "one"
    assert await client.read("notes/x.md") == "two"
    assert script.count == 4, "two calls, one retry each — the latch must not stay closed"


# ── LAW 1 again: exactly ONE decision site ─────────────────────────────────────────


def test_the_rate_limit_headers_are_read_in_exactly_one_function() -> None:
    """THE ONE-SITE GUARD, structural.

    Every rate-limit header literal in ``src/vault.py`` and ``src/health.py`` must
    live inside ``classify_rate_limit`` and nowhere else. A second copy anywhere —
    a «quick check» in the probe, a «temporary» branch in a client — is a second
    decision that can drift, and this is the guard that says so.

    Mutation-tested: duplicating the decision inline in ``_probe_vault`` puts the
    literals there and turns this red.
    """
    assert _rate_limit_sites() == [("vault.py", "classify_rate_limit")], (
        "the rate-limit headers must be read in ONE function — classify_rate_limit — and nowhere "
        f"else. Found: {_rate_limit_sites()}"
    )


async def test_the_client_delegates_to_the_predicate_instead_of_re_deciding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behaviourally: the call site is LIVE.

    A predicate nobody calls would pass every source guard above while changing
    nothing at runtime, so the reader's contract is proved by steering the verdict
    the client actually receives: force «do not retry» and the request count must
    drop to one.
    """
    seen: list[tuple[dict[str, str], int]] = []
    real = vault_mod.classify_rate_limit

    def _spy(headers, status):
        seen.append((dict(headers), status))
        verdict = real(headers, status)
        return vault_mod.RateVerdict(
            kind=verdict.kind, should_retry=False, backoff_s=0.0, reason="steered"
        )

    monkeypatch.setattr(vault_mod, "classify_rate_limit", _spy)
    sent = _exhausted(40.0, **{"Retry-After": "9"})
    client, script = _client(
        httpx.Response(403, json={"message": "rate limited"}, headers=sent),
        _note("must never be reached"),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.read("notes/x.md")
    assert seen, "the client did not consult the predicate at all"
    assert seen[0][1] == 403, "the predicate must be handed the status"
    assert {key.lower() for key in sent} <= {key.lower() for key in seen[0][0]}, (
        "the client must hand the predicate the RESPONSE HEADERS unfiltered — a client that "
        "pre-picks the headers it thinks matter IS the second decision site"
    )
    assert script.count == 1, "a no-retry verdict must produce exactly one request"


def test_the_client_body_carries_no_header_lookup_or_status_branch_of_its_own() -> None:
    """The inline status/header logic is GONE, not merely bypassed. Dead code that
    reads the same headers is a second place to be wrong."""
    func = _function(VAULT_PY, "_get_with_rate_limit")
    leaked = {s for s in _code_strings(func) if s.lower() in RATE_LIMIT_HEADERS}
    assert not leaked, f"_get_with_rate_limit still names {sorted(leaked)} — it must delegate"
    branches_on_limit_status = any(
        isinstance(node, ast.Compare)
        and any(
            isinstance(cmp, ast.Constant) and cmp.value in (429, 403) for cmp in node.comparators
        )
        for node in ast.walk(func)
    )
    assert not branches_on_limit_status, (
        "_get_with_rate_limit still branches on 429/403 itself — the predicate owns that"
    )


# ── LAW 4: the probe consumes the same predicate ───────────────────────────────────


async def test_the_probe_reports_a_rate_limited_403_as_unreachable(make_settings) -> None:
    """The probe must reach the SAME conclusion the reader does, and it can only do
    that by consuming the predicate — it opens its own client and never touches
    ``VaultClient``, so there is no shared call site to reuse.

    ``unreachable`` is the truthful answer: nobody could determine the credential's
    state, which is NOT the same claim as «the credential was refused».
    """
    github = _GitHub(403, _exhausted(40.0))
    lane = await health_mod._probe_vault(
        make_settings(VAULT_GITHUB_TOKEN=TOKEN), transport=github.transport()
    )
    assert lane.state == health_mod.STATE_UNREACHABLE, (
        "a rate-limited 403 must not read misconfigured — the credential was never refused, only "
        f"throttled. Got {lane.state}: {lane.reason}"
    )
    assert len(github.calls) == 1, (
        "the probe must NOT retry or sleep — it answers /health on a 5 s budget and reports what "
        "it learned"
    )


async def test_the_probe_reports_a_rate_limited_429_as_unreachable(make_settings) -> None:
    github = _GitHub(429, {"Retry-After": "30"})
    lane = await health_mod._probe_vault(
        make_settings(VAULT_GITHUB_TOKEN=TOKEN), transport=github.transport()
    )
    assert lane.state == health_mod.STATE_UNREACHABLE, lane.reason


async def test_the_probe_still_reports_a_refused_pat_as_misconfigured(make_settings) -> None:
    """The half of N3's law N5 must not blur: present and REFUSED stays
    ``misconfigured``, and a retry hint on a 403 does not change that."""
    for label, headers in {"bare": {}, "carrying a retry hint": {"Retry-After": "7"}}.items():
        github = _GitHub(403, dict(headers))
        lane = await health_mod._probe_vault(
            make_settings(VAULT_GITHUB_TOKEN=TOKEN), transport=github.transport()
        )
        assert lane.state == health_mod.STATE_MISCONFIGURED, (
            f"a 403 {label} is a REFUSED credential and must stay misconfigured. "
            f"Got {lane.state}: {lane.reason}"
        )


async def test_a_401_stays_misconfigured_and_a_transport_error_stays_unreachable(
    make_settings,
) -> None:
    github = _GitHub(401, {})
    assert (
        await health_mod._probe_vault(
            make_settings(VAULT_GITHUB_TOKEN=TOKEN), transport=github.transport()
        )
    ).state == health_mod.STATE_MISCONFIGURED

    def _dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    assert (
        await health_mod._probe_vault(
            make_settings(VAULT_GITHUB_TOKEN=TOKEN), transport=httpx.MockTransport(_dead)
        )
    ).state == health_mod.STATE_UNREACHABLE


async def test_the_probe_calls_the_predicate_rather_than_reimplementing_it(
    monkeypatch: pytest.MonkeyPatch, make_settings
) -> None:
    """Proves the IMPORT behaviourally.

    If the probe re-derived «rate limited vs refused» from headers itself, this spy
    would never be called and the probe would keep its own copy of the law.
    Steering the spy to REFUSE and watching the lane flip to ``misconfigured``
    proves the probe's answer comes from the predicate, not from its own reading.
    """
    seen: list[int] = []
    real = health_mod.classify_rate_limit

    def _spy(headers, status):
        seen.append(status)
        return real(headers, status)

    monkeypatch.setattr(health_mod, "classify_rate_limit", _spy)
    lane = await health_mod._probe_vault(
        make_settings(VAULT_GITHUB_TOKEN=TOKEN),
        transport=_GitHub(403, _exhausted(40.0)).transport(),
    )
    assert seen == [403], f"the probe did not consult the predicate (saw {seen})"
    assert lane.state == health_mod.STATE_UNREACHABLE

    monkeypatch.setattr(
        health_mod,
        "classify_rate_limit",
        lambda headers, status: vault_mod.RateVerdict(
            kind=vault_mod.RateLimitKind.REFUSED,
            should_retry=False,
            backoff_s=0.0,
            reason="steered",
        ),
    )
    steered = await health_mod._probe_vault(
        make_settings(VAULT_GITHUB_TOKEN=TOKEN),
        transport=_GitHub(403, _exhausted(40.0)).transport(),
    )
    assert steered.state == health_mod.STATE_MISCONFIGURED, (
        "steering the predicate did not move the lane — the probe is not reading it"
    )


def test_the_probe_body_carries_no_header_lookup_of_its_own() -> None:
    body = _code_strings(_function(HEALTH_PY, "_probe_vault"))
    leaked = {s for s in body if s.lower() in RATE_LIMIT_HEADERS}
    assert not leaked, f"_probe_vault still names {sorted(leaked)} — it must consume the predicate"


async def test_the_two_states_stay_distinguishable_end_to_end(make_settings, monkeypatch) -> None:
    """LAW 4 at the level an operator reads: the whole report, not one lane.

    ``misconfigured`` means «your credential was refused — go rotate it»;
    ``unreachable`` means «nobody could tell». Collapsing them would send an
    operator to rotate a perfectly good PAT because GitHub was busy.
    """

    async def _healthy(settings, *, transport=None):
        return health_mod.Lane(health_mod.STATE_HEALTHY)

    monkeypatch.setattr(health_mod, "_probe_gateway", _healthy)
    monkeypatch.setattr(health_mod, "_probe_telegram", _healthy)
    monkeypatch.setattr(health_mod, "_probe_ffmpeg", _healthy)

    settings = make_settings(
        VAULT_GITHUB_TOKEN=TOKEN,
        VAULT_LOCAL_PATH="./_nonexistent_test_vault",
        GOOGLE_OAUTH_CLIENT_JSON="./_nonexistent_google_client.json",
    )
    throttled = await health_mod.healthcheck(
        settings, transport=_GitHub(403, _exhausted(40.0)).transport()
    )
    refused = await health_mod.healthcheck(settings, transport=_GitHub(403, {}).transport())
    assert throttled["lanes"]["vault"]["state"] == health_mod.STATE_UNREACHABLE
    assert refused["lanes"]["vault"]["state"] == health_mod.STATE_MISCONFIGURED
    assert throttled["lanes"]["vault"]["reason"] != refused["lanes"]["vault"]["reason"], (
        "the reason must say which of the two happened, not repeat the HTTP status"
    )


# ── the docstrings: N3's reservation is now a false claim ──────────────────────────


def _docstring_of(path: Path, name: str) -> str:
    doc = ast.get_docstring(_function(path, name))
    assert doc, f"{path.name}::{name} has no docstring to check"
    return doc


def _health_docstrings() -> list[tuple[str, str]]:
    return [
        ("health.py module docstring", ast.get_docstring(_tree(HEALTH_PY)) or ""),
        ("_probe_vault", _docstring_of(HEALTH_PY, "_probe_vault")),
    ]


_STALE_RESERVATIONS = ("not solved here", "n5's open work")


def test_the_n3_open_work_reservation_is_gone_from_both_docstrings() -> None:
    """N3 wrote «THE 403 AMBIGUITY IS NOT SOLVED HERE — it is N5's open work» into
    ``_probe_vault`` AND the module docstring. N5 landed it, so both sentences are
    now false: a docstring claiming open work directly above shipped code teaches
    the next maintainer to distrust the probe.

    Both copies are checked, because N3 wrote both and a fix that edits one leaves
    the other lying.
    """
    for label, doc in _health_docstrings():
        lowered = doc.lower()
        for stale in _STALE_RESERVATIONS:
            assert stale not in lowered, (
                f"the {label} still says '{stale}'. N5 resolved the 403 ambiguity — the docstring "
                "is now claiming open work on top of the code that closes it."
            )


def test_the_replacement_text_states_the_law_the_code_actually_ships() -> None:
    """The replacement must be TRUE, and «true» is checked against the code rather
    than against intent: both docstrings have to name the discriminator the shipped
    predicate implements, so a reader cannot mistake it for the old conflated rule.
    """
    for label, doc in _health_docstrings():
        lowered = doc.lower()
        assert "classify_rate_limit" in lowered, (
            f"the {label} must name classify_rate_limit as the source of the verdict — the probe "
            "consumes that predicate, and a docstring that does not say so invites a "
            "reimplementation"
        )
        assert "x-ratelimit-remaining" in lowered, (
            f"the {label} must state WHICH header decides a rate limit (X-RateLimit-Remaining: 0), "
            "or a reader cannot tell whether this is the new law or the old conflated one"
        )
        assert "retry-after" in lowered, (
            f"the {label} must say the retry hint is DEMOTED — it is the header that made the old "
            "code retry a refused credential, and that mechanism is the whole node"
        )


def test_the_reader_docstring_states_the_single_shot_bound_and_the_predicate() -> None:
    """The behaviour lives here, so the bound is documented here.

    The old text claimed a limit «is honored ONCE», which was true only of the
    narrow case the old code detected. The claim has to be restated over what the
    shipped code now does, or it is a stale claim about different behaviour.
    """
    doc = _docstring_of(VAULT_PY, "_get_with_rate_limit")
    lowered = doc.lower()
    assert "classify_rate_limit" in lowered, (
        "the reader's docstring must name the predicate — it delegates, and a docstring still "
        "describing its own header handling is describing code that no longer exists"
    )
    assert "once" in lowered, "the single-shot bound must be stated where the retry lives"
    assert "x-ratelimit-remaining" in lowered, (
        "the docstring must state the discriminator that now drives the retry"
    )
    module_doc = (ast.get_docstring(_tree(VAULT_PY)) or "").lower()
    assert "retry-after" not in module_doc, (
        "the module docstring's «a 429/403 on a READ is retried at most once, honoring "
        "`Retry-After`» is the OLD law: that header alone no longer decides anything"
    )
    assert "rate limit" in module_doc and "403" in module_doc, (
        "the module docstring must still describe the rate-limit path at all"
    )


# ── the acceptance artefact: OLD → NEW, machine-checked ────────────────────────────


def test_the_old_to_new_acceptance_table() -> None:
    """Every status/header combination, what the deleted code did, what ships now.

    The «old» column is checked against ``_deleted_shipped_logic`` — the shipped-
    then-deleted body, run — rather than against prose, so this table cannot drift
    into flattering the new behaviour.
    """
    table: list[tuple[str, dict[str, str], int, str, str, bool]] = [
        # label, headers, status, old behaviour, new kind, new retry
        ("200 ok", {}, 200, "surface", "CLEAR", False),
        ("404 missing", {}, 404, "surface", "CLEAR", False),
        ("500 server error", {}, 500, "surface", "CLEAR", False),
        ("429 with a hint", {"Retry-After": "5"}, 429, "retry", "TOO_MANY", True),
        ("429 bare", {}, 429, "surface", "TOO_MANY", True),
        ("429 with a malformed hint", {"Retry-After": "soon"}, 429, "surface", "TOO_MANY", True),
        (
            "403 bad scope carrying a hint  <- THE BUG",
            {"Retry-After": "5"},
            403,
            "retry",
            "REFUSED",
            False,
        ),
        ("403 bad scope bare", {}, 403, "surface", "REFUSED", False),
        (
            "403 primary limit, no hint  <- failure 2",
            _exhausted(40.0),
            403,
            "surface",
            "PRIMARY",
            True,
        ),
        (
            "403 primary limit with a hint",
            _exhausted(40.0, **{"Retry-After": "5"}),
            403,
            "retry",
            "PRIMARY",
            True,
        ),
        (
            "403 secondary limit (hint only)",
            {"Retry-After": "5"},
            403,
            "retry",
            "SECONDARY",
            True,
        ),
        (
            "403 quota header present and non-zero",
            {"X-RateLimit-Remaining": "17"},
            403,
            "surface",
            "REFUSED",
            False,
        ),
        ("200 carrying an exhausted quota header", _exhausted(5.0), 200, "surface", "CLEAR", False),
    ]
    for label, headers, status, old, kind, retry in table:
        assert _deleted_shipped_logic(dict(headers), status) == old, (
            f"{label}: the recorded OLD behaviour does not match the deleted code — the table "
            "documents the wrong past"
        )
        verdict = vault_mod.classify_rate_limit(dict(headers), status)
        assert verdict.kind is vault_mod.RateLimitKind[kind], (
            f"{label}: expected kind {kind}, got {verdict.kind.value} ({verdict.reason})"
        )
        assert verdict.should_retry is retry, f"{label}: expected retry={retry}"
        assert (verdict.backoff_s > 0.0) is retry, (
            f"{label}: backoff_s={verdict.backoff_s} but retry={retry} — a non-retrying verdict must "
            "carry no wait, and a retrying one must carry one"
        )


async def test_the_backoff_the_old_code_clamped_at_thirty_now_waits_the_reset() -> None:
    """Failure 3, stated as the delta rather than as a table row: the old code
    slept ``min(retry_after, 30)``, so a reset 40 s out was never waited out."""
    headers = _exhausted(40.0)
    assert _deleted_shipped_logic(dict(headers), 403) == "surface", (
        "precondition: the old code gave up on this response"
    )
    client, script = _client(
        httpx.Response(403, json={"message": "rate limited"}, headers=headers), _note()
    )
    assert await client.read("notes/x.md")
    assert script.count == 2
    assert sleeps and sleeps[0] > 30.0, (
        f"the client slept {sleeps} — the 30 s flat cap is exactly what abandoned this limit"
    )
