"""Tier 1 — routing-matrix contracts: pins, fallbacks, escalation boundaries.

Hermetic: the dynamic 3-tier matrix is verified without network.

RE-PINNED 2026-10-03 (owner). This file's constants described the matrix of
2026-09-30, and two of them were measured DEAD against the live gateway the same
day the new matrix was pinned:

  * `openrouter/nex-agi/nex-n2.5-{mini,pro}:free` → `KeyError: 'choices'` — the
    gateway returns a body with no completions. Both MEDIUM and HEAVY primaries
    were paying a wasted round trip on every turn.
  * `google/gemma-4-31b-it:free` → absent from the 1,482-model catalog. The slug
    moved under the `openrouter/` prefix.

The law this file exists to protect did not change: the three tier primaries are
distinct, each chain leads with its primary, fallbacks parse in order, and HEAVY
escalates past a concurrency threshold. Only the VALUES moved. Whether a value is
LIVE is now checked against the gateway catalog, in
`tests/test_env_model_slugs.py` — presence in a 2026-09 snapshot was exactly what
let two dead primaries survive unnoticed.
"""

from src.gateway import (
    ConcurrencyTracker,
    Tier,
    select_heavy_chain,
)

FAST = "gemini/gemini-3.8-flash"
FAST_FB = "groq/openai/gpt-oss-120b"
MEDIUM = "gemini/gemini-3.8-flash"
HEAVY = "gemini/gemini-3.8-flash"
ESCALATED = "openrouter/poolside/laguna-s-2.1:free"
FB = "groq/openai/gpt-oss-120b"


def test_settings_pins_match_matrix(make_settings):
    s = make_settings()
    assert (s.fast_model, s.medium_model, s.heavy_model) == (FAST, MEDIUM, HEAVY)
    # Owner 2026-10-03: each tier carries its primary plus a latency-ordered
    # free-tier fallback SET, so the chains are multi-entry. What this guard owns
    # is the ORDERING LAW — primary leads, then the documented fallbacks — while
    # liveness of each slug against the gateway catalog is `test_env_model_slugs.py`'s
    # job. Asserting exact whole-chain equality here would just re-freeze a snapshot.
    assert s.fast_chain[0] == FAST and s.fast_chain[1] == FAST_FB
    assert s.medium_chain[0] == MEDIUM and s.medium_chain[1] == FB
    assert s.heavy_chain[0] == HEAVY
    assert s.heavy_escalated_chain[0] == ESCALATED
    assert FB in s.heavy_escalated_chain, (
        f"the escalated chain must retain a groq/ last resort, got {s.heavy_escalated_chain}"
    )
    for chain in (s.fast_chain, s.medium_chain, s.heavy_chain):
        assert len(chain) >= 2, f"a single-entry chain is a single point of failure: {chain}"
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
