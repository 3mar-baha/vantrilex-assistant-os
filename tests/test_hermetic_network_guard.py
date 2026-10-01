"""The suite's hermeticity guard: $0.00 and CI-offline are ENFORCED, not promised.

Measured motivation: `tests/test_production_wiring.py::test_run_bot_boots_all_
components_and_shuts_down` was the one test in the tree that reached
`api.github.com` for real, and its 31 live 401s are what turned a 1.1s boot
into a 30s timeout. Nothing stopped that from recurring — the guard below now
does, by refusing every external connect/resolve at the socket layer.

The contract, all four parts asserted here:
  1. an external resolve is refused;
  2. an external connect is refused (the resolve-only guard would miss a
     caller that already holds a resolved address);
  3. loopback still works — the guard is a lane rule, not a blanket ban, and
     bridge/probe tests bind and dial 127.0.0.1;
  4. the two live lanes are exempt BY MARKER, which is the only sanctioned way
     to reach real infrastructure.
"""

from __future__ import annotations

import socket

import pytest

from conftest import SuiteNetworkBlocked

_EXTERNAL_HOST = "api.github.com"


def test_external_resolve_is_refused() -> None:
    with pytest.raises(SuiteNetworkBlocked, match="resolve"):
        socket.getaddrinfo(_EXTERNAL_HOST, 443)


def test_external_connect_is_refused() -> None:
    """A guard on `getaddrinfo` alone would not catch a caller that already
    holds a resolved address (a pooled/kept-alive socket, a literal IP), so the
    connect path must be refused independently.

    Dials `203.0.113.1` (TEST-NET-3, reserved and unroutable) rather than a
    resolved name: this exercises `connect` without `create_connection`'s
    internal resolve, which is the whole point of the separate assertion. Were
    the guard removed, this would attempt a real — and doomed — connection.
    """
    sock = socket.socket()
    try:
        with pytest.raises(SuiteNetworkBlocked, match="connect"):
            sock.connect(("203.0.113.1", 443))
    finally:
        sock.close()


def test_loopback_still_resolves_and_connects() -> None:
    """The guard must not be a blanket ban: the bridge binds 127.0.0.1 and the
    live probe dials it, so loopback has to keep working."""
    assert socket.getaddrinfo("127.0.0.1", 80)
    server = socket.socket()
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        host, port = server.getsockname()
        with socket.create_connection((host, port), timeout=2.0):
            pass
    finally:
        server.close()


@pytest.mark.live_probe
@pytest.mark.live_harness
def test_live_lanes_are_exempt_by_marker() -> None:
    """A live lane really is unblocked — this test carries both markers, so if
    the exemption broke, THIS would fail with `SuiteNetworkBlocked` instead of
    the ordinary tests passing for the wrong reason. It resolves a real host
    and accepts either outcome (answer or DNS failure): the assertion is that
    no guard refused it."""
    try:
        socket.getaddrinfo(_EXTERNAL_HOST, 443)
    except SuiteNetworkBlocked:  # pragma: no cover -- only reachable if the exemption breaks
        pytest.fail("live lane was network-blocked; the marker exemption is broken")
