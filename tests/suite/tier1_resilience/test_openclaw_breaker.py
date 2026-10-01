"""Tier 1 — OpenClaw Phase-2 Reversibility Circuit Breaker contracts. Hermetic.

The breaker is deterministic: the SAME op classifies the SAME way on every
run, on both sides of the tunnel. The reversibility CLAIM riding the wire
is ignored — the verdict is recomputed from (kind, target, value, verify).
"""

import pytest

from bridge.executor import mint_confirmation_id
from bridge.openclaw.breaker import ActionForbiddenError, SafetyCircuitBreaker
from bridge.openclaw.protocol import Op, OpKind

# F-2: the shared signing secret this suite verifies confirmation ids against.
CONFIRM_KEY = "your-breaker-shared-confirmation-key"


def _op(kind: OpKind, **kw) -> Op:
    return Op(op=kind, **kw)


# -- READ / NAVIGATE: auto -----------------------------------------------------


@pytest.mark.parametrize(
    "kind,kw",
    [
        (OpKind.SCREENSHOT, {}),
        (OpKind.INSPECT_TREE, {}),
        (OpKind.EXTRACT, {}),
        (OpKind.NAVIGATE, {"value": "https://example.com"}),
        (OpKind.FOCUS, {"target": "notepad"}),
        (OpKind.SCROLL, {"value": "down"}),
    ],
)
def test_read_navigate_ops_are_reversible(kind, kw):
    assert SafetyCircuitBreaker.classify(_op(kind, **kw)) == "reversible"


def test_safe_hotkeys_are_reversible():
    for keys in ("Ctrl+L", "Ctrl+T", "Ctrl+Tab", "F6", "Alt+Tab", "Escape", "Tab"):
        assert SafetyCircuitBreaker.classify(_op(OpKind.HOTKEY, value=keys)) == "reversible"


def test_plain_typing_is_reversible():
    assert SafetyCircuitBreaker.classify(_op(OpKind.TYPE_TEXT, value="notepad")) == "reversible"


def test_plain_click_is_reversible():
    assert (
        SafetyCircuitBreaker.classify(_op(OpKind.CLICK, target="e12", verify="focused"))
        == "reversible"
    )


# -- COMMIT: compulsory confirmation -------------------------------------------


@pytest.mark.parametrize("keys", ["Alt+F4", "Ctrl+S", "Enter", "Ctrl+Enter"])
def test_committing_hotkeys_are_irreversible(keys):
    assert SafetyCircuitBreaker.classify(_op(OpKind.HOTKEY, value=keys)) == "irreversible"


@pytest.mark.parametrize("value", ["line one\nline two", "submit{ENTER}", "ok{Enter}"])
def test_typing_with_submit_is_irreversible(value):
    assert SafetyCircuitBreaker.classify(_op(OpKind.TYPE_TEXT, value=value)) == "irreversible"


@pytest.mark.parametrize("verify", ["submit", "save", "delete", "close", "send", "commit"])
def test_click_with_commit_verify_is_irreversible(verify):
    assert (
        SafetyCircuitBreaker.classify(_op(OpKind.CLICK, target="e9", verify=verify))
        == "irreversible"
    )


def test_wire_claim_never_downgrades_the_verdict():
    """A «reversible» claim on a committing op is ignored — loudly unsafe
    otherwise."""
    op = Op(op=OpKind.HOTKEY, value="Alt+F4", reversibility="reversible")
    assert SafetyCircuitBreaker.classify(op) == "irreversible"


# -- FORBIDDEN: hard rejection ---------------------------------------------------


@pytest.mark.parametrize(
    "kind,kw",
    [
        (OpKind.TYPE_TEXT, {"value": "powershell -c Remove-Item C:\\*"}),
        (OpKind.TYPE_TEXT, {"value": "reg add HKLM\\Software\\X /v a /t REG_SZ /d 1"}),
        (OpKind.HOTKEY, {"value": "powershell"}),
        (OpKind.CLICK, {"target": "HKEY_CURRENT_USER\\Run"}),
        (OpKind.EXTRACT, {"value": "api_key=sk-live-123"}),
        (OpKind.TYPE_TEXT, {"value": "login with password: hunter2"}),
    ],
)
def test_forbidden_shapes_raise(kind, kw):
    with pytest.raises(ActionForbiddenError):
        SafetyCircuitBreaker.classify(_op(kind, **kw))


# -- authorize: fail-closed ------------------------------------------------------


def test_authorize_reversible_needs_nothing():
    assert SafetyCircuitBreaker.authorize(_op(OpKind.SCREENSHOT), None) is True


@pytest.mark.parametrize("cid", [None, "", "   "])
def test_authorize_irreversible_without_id_refuses(cid):
    assert SafetyCircuitBreaker.authorize(_op(OpKind.HOTKEY, value="Alt+F4"), cid) is False


def test_authorize_irreversible_with_id_passes():
    """F-2 CORRECTED this guard. The pre-F-2 body asserted that the bare string
    `"abc123"` authorized an Alt+F4 — it pinned the forgery as law, and its name
    ("with_id_passes") disagreed with the contract it was meant to state. A
    confirmation id is now a signed, expiring, single-use token, so the law is
    "with a VERIFIED id passes" and the forgery has its own guard below."""
    token = mint_confirmation_id(secret=CONFIRM_KEY)
    assert (
        SafetyCircuitBreaker.authorize(
            _op(OpKind.HOTKEY, value="Alt+F4"), token, confirm_key=CONFIRM_KEY
        )
        is True
    )


@pytest.mark.parametrize("forged", ["abc123", "cid-123", "1234567890ab", "cfm1.1.2.3"])
def test_authorize_irreversible_with_forged_id_refuses(forged):
    """The other half of the correction: a non-empty id that nobody signed is
    refused, exactly like an absent one."""
    assert (
        SafetyCircuitBreaker.authorize(
            _op(OpKind.HOTKEY, value="Alt+F4"), forged, confirm_key=CONFIRM_KEY
        )
        is False
    )


def test_authorize_forbidden_raises_even_with_id():
    with pytest.raises(ActionForbiddenError):
        SafetyCircuitBreaker.authorize(
            _op(OpKind.TYPE_TEXT, value="powershell -c whoami"), "abc123"
        )
