"""Decision 4 — `MEDIUM_MODEL` / `HEAVY_MODEL` carry the `openrouter/` prefix.

MEASURED DEFECT (Directive 3). `.env.example:35` and `:42` and the live `.env`
all carry the BARE slug:
    MEDIUM_MODEL=nex-agi/nex-n2.5-mini:free
    HEAVY_MODEL=nex-agi/nex-n2.5-pro:free
`.env.example:38-40` records the history: "2026-09-13: nex-agi has no live
provider credentials (HTTP 404) — the chain falls back". The live gateway's
`/models` now lists both slugs under the `openrouter/` provider, so the bare
slug 404s and the primary slot is a dead entry that costs a wasted round trip
on every Tier 2 / Tier 3 turn before the fallback engages.

SCOPE, stated so the guard cannot be over-read: this change touches TWO
variables. The fallback chains, Tier 1 and the escalation model are untouched,
and a guard says so — a slug migration is exactly the moment an unrelated chain
gets "tidied" along with it.

CI SAFETY (the reason the live-`.env` guard skips rather than fails): `.env` is
gitignored and absent in CI. A test that fails there because a secret file is
missing is a test that gets muted, and a muted test is worse than no test. So:
`.env.example` (tracked) is asserted unconditionally; `.env` is asserted only
when the file is present and `pytest.skip` names the reason otherwise.

Parser note: a 6-line dotenv reader, not `python-dotenv` — the constraints are
stdlib + pytest only, and the whole contract is `KEY=VALUE` on its own line.
Comments (`# ...`) and blank lines are skipped, so the prose in `.env.example`
that mentions `nex-agi` in a sentence is not a value and is not asserted on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO / ".env.example"
LIVE_ENV = REPO / ".env"

# The two variables this decision moves. Bytes from the live gateway /models.
PREFIXED_SLUGS = {
    "MEDIUM_MODEL": "openrouter/nex-agi/nex-n2.5-mini:free",
    "HEAVY_MODEL": "openrouter/nex-agi/nex-n2.5-pro:free",
}

# Everything in the 3-tier block that must NOT move. Read from .env.example:27-47
# at HEAD; a guard that says "two variables" has to be able to say the rest held.
UNCHANGED_TIER_PINS = {
    "FAST_MODEL": "groq/openai/gpt-oss-120b",
    "FAST_MODEL_FALLBACKS": "google/gemma-4-31b-it:free",
    "MEDIUM_MODEL_FALLBACKS": "groq/openai/gpt-oss-120b",
    "HEAVY_MODEL_FALLBACKS": (
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free,groq/openai/gpt-oss-120b"
    ),
    "HEAVY_ESCALATION_MODEL": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    "HEAVY_ESCALATION_FALLBACKS": "groq/openai/gpt-oss-120b",
    "HEAVY_CONCURRENCY_THRESHOLD": "3",
}

# A tier's PRIMARY is its first chain element. Every primary the gateway resolves
# by slug is checked, not just the two being changed.
PRIMARY_MODEL_KEYS = (
    "FAST_MODEL",
    "MEDIUM_MODEL",
    "HEAVY_MODEL",
    "HEAVY_ESCALATION_MODEL",
)

ENV_FILES = (".env.example", ".env")


def _values(path: Path) -> dict[str, str]:
    """`KEY=VALUE` pairs only — comments and blanks are not values."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip().removeprefix("export ").strip()] = value.strip()
    return values


def _require(filename: str) -> dict[str, str]:
    """Read an env file, skipping (never failing) when it is legitimately absent.

    `.env` is gitignored: absent in CI and in every fresh clone. Skipping is the
    honest outcome, and the reason is named in the skip message.
    """
    path = REPO / filename
    if not path.exists():
        pytest.skip(f"{filename} is absent (gitignored secret file, never in CI)")
    return _values(path)


# --- the tracked template: unconditional ---------------------------------------


@pytest.mark.parametrize(("key", "expected"), sorted(PREFIXED_SLUGS.items()))
def test_env_example_pins_the_provider_prefixed_slugs(key: str, expected: str) -> None:
    """RED: `.env.example` still carries the bare `nex-agi/` slug.

    The bare slug 404s against the live gateway; the gateway lists both models
    under `openrouter/`. `.env.example` is the canonical routing-matrix pin
    (`tests/test_dispatcher.py::test_env_pins_match_adr16` reads it), so it is
    the file that has to be right.
    """
    assert _values(ENV_EXAMPLE).get(key) == expected, (
        f".env.example must set {key}={expected} (the live gateway lists it under "
        f"openrouter/; the bare nex-agi/ slug 404s)"
    )


# --- the live file: skip when absent, assert when present ----------------------


@pytest.mark.parametrize(("key", "expected"), sorted(PREFIXED_SLUGS.items()))
def test_live_env_carries_the_same_prefixed_slugs(key: str, expected: str) -> None:
    """RED locally (`.env` still bare), SKIPPED in CI (`.env` is gitignored).

    The template and the owner's live file must not diverge: a fixed template
    with a stale `.env` keeps Terminal 1 and Telegram on the 404ing slug and
    every local run looks fine.
    """
    assert _require(LIVE_ENV.name).get(key) == expected, (
        f"the live .env must set {key}={expected}; a bare nex-agi/ slug 404s and "
        "the tier silently degrades to its fallback"
    )


# --- scope: the rest of the 3-tier block held still ---------------------------


@pytest.mark.parametrize(
    ("filename", "key", "expected"),
    [
        (filename, key, value)
        for filename in ENV_FILES
        for key, value in sorted(UNCHANGED_TIER_PINS.items())
    ],
    ids=[f"{filename}:{key}" for filename in ENV_FILES for key in sorted(UNCHANGED_TIER_PINS)],
)
def test_untouched_tier_pins_and_fallback_chains_did_not_move(
    filename: str, key: str, expected: str
) -> None:
    """This decision is scoped to two variables; the guard proves the rest held.

    Tier 1 (`FAST_MODEL` + its gemma fallback), both tier-2/3 fallback lists and
    the escalation model are unchanged. A slug migration is exactly when an
    adjacent chain gets tidied along with it, and an unnoticed move here is a
    routing regression with no test naming it.
    """
    assert _require(filename).get(key) == expected, (
        f"{filename}: {key} must stay {expected!r} — decision 4 moves {sorted(PREFIXED_SLUGS)} only"
    )


@pytest.mark.parametrize(
    ("filename", "key"),
    [(filename, key) for filename in ENV_FILES for key in PRIMARY_MODEL_KEYS],
    ids=[f"{filename}:{key}" for filename in ENV_FILES for key in PRIMARY_MODEL_KEYS],
)
def test_no_tier_primary_is_a_bare_nex_agi_slug(filename: str, key: str) -> None:
    """RED on `MEDIUM_MODEL` and `HEAVY_MODEL`: the bare slug is still primary.

    The general rule behind the decision — every tier primary must name its
    provider — asserted over all four primaries so the next bare slug is caught
    by this guard instead of by a 404 in a log file. The primary is the FIRST
    chain element; a value may be a comma-separated fallback list.
    """
    primary = _require(filename).get(key, "").split(",")[0].strip()
    assert not primary.startswith("nex-agi/"), (
        f"{filename}: {key} resolves {primary!r}, a bare nex-agi/ slug. The live "
        "gateway's /models lists these under openrouter/; bare slugs 404."
    )
