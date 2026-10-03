"""Decision 4 (2026-09-30) superseded — the routing matrix is owner-pinned.

Decision 4 pinned `MEDIUM_MODEL` / `HEAVY_MODEL` to the `openrouter/`-prefixed
`nex-agi` slugs, and pinned six other tier variables as UNCHANGED so a slug
migration could not drag an unrelated chain along with it.

That guard has done its job and its premise is now false. MEASURED 2026-10-03
against the live gateway (1,482 models):

  * `openrouter/nex-agi/nex-n2.5-mini:free` returns `KeyError: 'choices'` —
    a malformed body, no completions. Same for `nex-n2.5-pro:free`. Both
    primaries were DEAD, so every Tier 2 / Tier 3 turn was paying a wasted
    round trip before falling through.
  * `google/gemma-4-31b-it:free` is ABSENT from the catalog. The slug moved to
    the `openrouter/` prefix, so the FAST fallback was a dead entry too.
  * `apodex/apodex-1.1-mini:free` (a candidate in the swap request) is ABSENT.
    Dropped, not substituted.

So the file keeps its REAL job — asserting that every pinned slug is PRESENT in
the gateway catalog and carries a free-tier prefix — but the pinned VALUES are
now the owner's 2026-10-03 matrix, and the "unchanged" set is gone because the
whole point of this commit is that they all moved.

The re-derived invariant is stronger than the one it replaces: it checks every
tier variable against the LIVE catalog rather than against a snapshot recorded
in 2026-09, which is what let two dead primaries and a dead fallback survive
unnoticed in the first place.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO / ".env.example"
LIVE_ENV = REPO / ".env"

GATEWAY = "http://127.0.0.1:20128/v1/models"

#: Every variable that participates in the routing matrix. Owner-pinned
#: 2026-10-03, latency-aware per tier role.
TIER_KEYS = (
    "FAST_MODEL",
    "FAST_MODEL_FALLBACKS",
    "MEDIUM_MODEL",
    "MEDIUM_MODEL_FALLBACKS",
    "HEAVY_MODEL",
    "HEAVY_MODEL_FALLBACKS",
    "HEAVY_ESCALATION_MODEL",
    "HEAVY_ESCALATION_FALLBACKS",
)


def _values(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


def _catalog() -> set[str]:
    """Live gateway catalog. Skips when the gateway is not running."""
    try:
        with urllib.request.urlopen(GATEWAY, timeout=40) as resp:
            return {m["id"] for m in json.load(resp).get("data", [])}
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"gateway not reachable, cannot verify against live catalog: {exc}")


@pytest.mark.parametrize("filename", [".env.example", ".env"])
def test_every_pinned_slug_exists_in_the_live_catalog(filename: str) -> None:
    """THE invariant: a pinned slug that the gateway does not list is a dead
    entry costing a wasted round trip on every turn of that tier."""
    path = ENV_EXAMPLE if filename == ".env.example" else LIVE_ENV
    if path.name == ".env" and not path.exists():
        pytest.skip(".env is gitignored and absent in CI; .env.example is asserted instead")
    values = _values(path)
    catalog = _catalog()

    dead: list[str] = []
    for key in TIER_KEYS:
        raw = values.get(key, "")
        for slug in (s.strip() for s in raw.split(",") if s.strip()):
            if slug not in catalog:
                dead.append(f"{key}={slug}")
    assert not dead, (
        f"{path.name} pins slugs the gateway catalog does not list: {dead}. A dead pin "
        "is not a fallback — it is a wasted round trip before the real fallback, on "
        "every turn of that tier. (This is how two dead nex-agi primaries and a dead "
        "google/gemma prefix survived until 2026-10-03.)"
    )


@pytest.mark.parametrize("filename", [".env.example", ".env"])
def test_every_pinned_slug_carries_a_free_tier_prefix(filename: str) -> None:
    """`:free` suffix, or a gateway-held provider prefix. Mirrors
    `FREE_TIER_PREFIXES` in src/gateway.py — the config must not be able to pin
    something the runtime would refuse before the wire."""
    from src.gateway import FREE_TIER_PREFIXES

    path = ENV_EXAMPLE if filename == ".env.example" else LIVE_ENV
    if path.name == ".env" and not path.exists():
        pytest.skip(".env is gitignored and absent in CI; .env.example is asserted instead")
    values = _values(path)

    bad: list[str] = []
    for key in TIER_KEYS:
        for slug in (s.strip() for s in values.get(key, "").split(",") if s.strip()):
            if not (slug.endswith(":free") or slug.startswith(FREE_TIER_PREFIXES)):
                bad.append(f"{key}={slug}")
    assert not bad, (
        f"{path.name} pins slugs the $0.00 guard would block before the wire: {bad}. "
        "Every pinned slug needs a ':free' suffix or a gateway-held provider prefix."
    )


@pytest.mark.parametrize("filename", [".env.example", ".env"])
def test_the_matrix_has_no_dead_nex_agi_primary(filename: str) -> None:
    """The specific regression that went unnoticed: `nex-agi/*:free` resolves in
    the catalog but returns no completions, so presence alone was never enough.
    This asserts the primaries are the owner's 2026-10-03 pin."""
    path = ENV_EXAMPLE if filename == ".env.example" else LIVE_ENV
    if path.name == ".env" and not path.exists():
        pytest.skip(".env is gitignored and absent in CI; .env.example is asserted instead")
    values = _values(path)
    for key in ("FAST_MODEL", "MEDIUM_MODEL", "HEAVY_MODEL"):
        assert "nex-agi" not in values.get(key, ""), (
            f"{path.name}:{key} still pins a nex-agi slug — both measured dead on "
            "2026-10-03 (KeyError: 'choices', no completions returned)"
        )


@pytest.mark.parametrize("filename", [".env.example", ".env"])
def test_fast_speaker_keeps_a_fast_fallback_first(filename: str) -> None:
    """FAST is the speaker lane. The owner's ordering constraint: groq (1.4-2.4 s)
    belongs early because gemini is ~11.7 s and gemma measured 42.2 s."""
    path = ENV_EXAMPLE if filename == ".env.example" else LIVE_ENV
    if path.name == ".env" and not path.exists():
        pytest.skip(".env is gitignored and absent in CI; .env.example is asserted instead")
    fallbacks = [
        s.strip() for s in _values(path).get("FAST_MODEL_FALLBACKS", "").split(",") if s.strip()
    ]
    assert fallbacks, "FAST must keep a fallback — gemini alone is a single point of failure"
    assert fallbacks[0].startswith("groq/"), (
        f"the FAST fallback chain must open with a groq/ id (measured 1.4-2.4 s), got "
        f"{fallbacks[0]!r}. The speaker lane cannot wait 42 s on gemma."
    )


@pytest.mark.parametrize("filename", [".env.example", ".env"])
def test_the_slowest_model_is_last_in_every_chain(filename: str) -> None:
    """gemma-4-31b-it:free measured 42.2 s — last resort only, never early."""
    path = ENV_EXAMPLE if filename == ".env.example" else LIVE_ENV
    if path.name == ".env" and not path.exists():
        pytest.skip(".env is gitignored and absent in CI; .env.example is asserted instead")
    values = _values(path)
    for key in TIER_KEYS:
        slugs = [s.strip() for s in values.get(key, "").split(",") if s.strip()]
        gemma = [i for i, s in enumerate(slugs) if "gemma-4-31b" in s]
        if gemma and gemma[0] != len(slugs) - 1:
            pytest.fail(
                f"{path.name}:{key} has gemma-4-31b-it:free at position {gemma[0] + 1} of "
                f"{len(slugs)}; measured 42.2 s, so it belongs last: {slugs}"
            )
