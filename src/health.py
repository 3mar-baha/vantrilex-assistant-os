"""Ops health probe: gateway reachability, token presence, ffmpeg availability.

Degraded components never crash the process — health reports, ops decide.
"""

import shutil

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
    report["overall"] = (
        "ok"
        if report["gateway"] in ("ok", "unchecked")
        and report["telegram_token"] == "set"
        and report["ffmpeg"] == "found"
        else "degraded"
    )
    return report


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
