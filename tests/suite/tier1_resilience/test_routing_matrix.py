"""Tier 1 — routing-matrix contracts: pins, fallbacks, escalation boundaries.

Hermetic: the dynamic 3-tier matrix (FAST gemma / MEDIUM nex-mini / HEAVY
nex-pro base + nemotron MoE escalation) is verified without network.
"""

from src.gateway import (
    ConcurrencyTracker,
    Tier,
    select_heavy_chain,
)

FAST = "google/gemma-4-31b-it:free"
MEDIUM = "nex-agi/nex-n2.5-mini:free"
HEAVY = "nex-agi/nex-n2.5-pro:free"
ESCALATED = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
FB = "groq/openai/gpt-oss-120b"


def test_settings_pins_match_matrix(make_settings):
    s = make_settings()
    assert (s.fast_model, s.medium_model, s.heavy_model) == (FAST, MEDIUM, HEAVY)
    assert s.fast_chain == [FAST, FB]
    assert s.medium_chain == [MEDIUM, FB]
    assert s.heavy_chain == [HEAVY, FB]
    assert s.heavy_escalated_chain == [ESCALATED, FB]
    assert s.heavy_concurrency_threshold == 3


def test_heavy_selector_boundaries(make_settings):
    s = make_settings()
    assert s.heavy_chain_for(1)[0] == HEAVY
    assert s.heavy_chain_for(3)[0] == HEAVY  # at threshold: base holds
    assert s.heavy_chain_for(4)[0] == ESCALATED  # beyond: MoE escalates
    assert s.heavy_chain_for(1, is_dag_swarm=True)[0] == ESCALATED


def test_select_heavy_chain_pure():
    assert select_heavy_chain([HEAVY], [ESCALATED], 2)[0] == HEAVY
    assert select_heavy_chain([HEAVY], [ESCALATED], 9)[0] == ESCALATED
    assert select_heavy_chain([HEAVY], [ESCALATED], 1, is_dag_swarm=True)[0] == ESCALATED
    assert select_heavy_chain([HEAVY], [], 9) == [HEAVY]  # no escalation configured: base serves


def test_tracker_counts_and_escalates():
    t = ConcurrencyTracker(threshold=3)
    assert t.active == 0 and not t.should_escalate()
    t.acquire(3)
    assert not t.should_escalate()  # at threshold: no escalation
    t.acquire()
    assert t.should_escalate()  # 4 active: escalate
    t.release(2)
    assert t.active == 2 and not t.should_escalate()
    t.release(99)
    assert t.active == 0  # floor at zero, never negative


def test_client_heavy_for_selects_escalation_chain():
    from src.gateway import OmniRouteClient

    client = OmniRouteClient(
        "http://gw.test/v1",
        "k",
        chains={Tier.FAST: [FAST], Tier.MEDIUM: [MEDIUM], Tier.HEAVY: [HEAVY, FB]},
        escalated_heavy_chain=[ESCALATED, FB],
        concurrency_threshold=3,
    )
    assert client.heavy_chain_for(2)[0] == HEAVY
    assert client.heavy_chain_for(5)[0] == ESCALATED
    assert client.tracker.threshold == 3
