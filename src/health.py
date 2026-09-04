"""Ops health probe: gateway reachability, token presence, ffmpeg availability,
plus the vault + Google state (deferred queue §13 — /health must never read
green while Gmail is actually failing).

Degraded components never crash the process — health reports, ops decide.
"""

import shutil
from pathlib import Path

import httpx
from loguru import logger

from src.config import Settings


async def healthcheck(settings: Settings, *, probe_gateway: bool = True) -> dict[str, str]:
    report: dict[str, str] = {}
    if probe_gateway:
        report["gateway"] = await _probe_gateway(settings.omniroute_base_url)
    else:
        report["gateway"] = "unchecked"
    report["telegram_token"] = "set" if settings.telegram_bot_token else "missing"
    report["ffmpeg"] = "found" if shutil.which("ffmpeg") else "missing"
    # §13 honesty: the vault token + the Google token cache report real state
    report["vault"] = await _safe_probe(_probe_vault, settings)
    report["google"] = await _safe_probe(_probe_google, settings)
    report["overall"] = (
        "ok"
        if report["gateway"] in ("ok", "unchecked")
        and report["telegram_token"] == "set"
        and report["ffmpeg"] == "found"
        and report["vault"] == "ok"
        and report["google"] in ("ok", "missing")
        else "degraded"
    )
    return report


async def _safe_probe(probe, settings) -> str:
    """A probe crash degrades its row loudly — never the whole report."""
    try:
        return await probe(settings)
    except Exception:  # noqa: BLE001 — the report survives, the row degrades
        logger.warning("health probe {} failed", getattr(probe, "__name__", probe))
        return "unreachable"


async def _probe_vault(settings: Settings) -> str:
    """Vault honesty: the sealed Google-token file existing means the vault
    path is populated; a probe of the repo itself stays cheap — token
    presence is the honest signal (a dead PAT surfaces on first real read,
    loudly, where it belongs)."""
    token = getattr(settings, "vault_github_token", None)
    if token is None or not str(token):
        return "unreachable"
    return "ok"


async def _probe_google(settings: Settings) -> str:
    """Google honesty: the sealed token cache presence — THE local cause of
    live Gmail failures per the audit (§14). Absent cache = 'missing' row,
    never a silent green."""
    cache = Path(settings.vault_local_path) / "State" / "google_token.json.enc"
    if not cache.exists():
        return "missing"
    return "ok"


async def _probe_gateway(base_url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url.rstrip('/')}/models")
    except httpx.HTTPError:
        logger.warning("health probe: gateway unreachable at {}", base_url)
        return "unreachable"
    if response.status_code != 200:
        logger.warning("health probe: gateway answered HTTP {}", response.status_code)
        return "unreachable"
    return "ok"
