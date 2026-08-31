"""Deploy smoke — turns "is Sara alive?" into an exit code (sprint-4 4.4b).

Five checks — gateway, telegram, vault, google_token_cache, space_health — all run
even after one fails, each bounded by its own timeout. NO secret value ever reaches
a detail or log line: httpx errors embed full request URLs (the Telegram getMe URL
carries the bot token), so every failure is screened through the Settings-aware
masker before it lands; host + path class remain for debugging.

Usage: python scripts/deploy_smoke.py   (exit 0 iff all checks are green)
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from loguru import logger
from pydantic import ValidationError

from src.config import Settings
from src.google_auth import token_cache_path

MASK = "***"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _masker(settings: Settings) -> Callable[[str], str]:
    secrets = [
        settings.telegram_bot_token,
        settings.vault_github_token.get_secret_value(),
        settings.bridge_token.get_secret_value(),
    ]
    return lambda text: _mask(text, secrets)


def _mask(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, MASK)
    return text


async def _checked(
    name: str, settings: Settings, probe: Callable[[], Awaitable[tuple[bool, str]]]
) -> CheckResult:
    mask = _masker(settings)
    try:
        ok, detail = await probe()
        return CheckResult(name, ok, mask(detail))
    except Exception as error:  # noqa: BLE001 — smoke barrier: any failure becomes a red CheckResult, never a crash
        return CheckResult(name, False, mask(str(error)))


async def check_gateway(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> CheckResult:
    async def probe() -> tuple[bool, str]:
        http = client or httpx.AsyncClient(timeout=8.0)
        try:
            response = await http.get(
                f"{settings.omniroute_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.omniroute_api_key}"},
            )
            return response.status_code == 200, f"models endpoint HTTP {response.status_code}"
        finally:
            if client is None:
                await http.aclose()

    return await _checked("gateway", settings, probe)


async def check_telegram(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> CheckResult:
    async def probe() -> tuple[bool, str]:
        http = client or httpx.AsyncClient(timeout=8.0)
        try:
            response = await http.get(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe"
            )
            ok = response.status_code == 200 and response.json().get("ok") is True
            return ok, f"getMe HTTP {response.status_code}"
        finally:
            if client is None:
                await http.aclose()

    return await _checked("telegram", settings, probe)


async def check_vault(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> CheckResult:
    async def probe() -> tuple[bool, str]:
        http = client or httpx.AsyncClient(timeout=8.0)
        try:
            response = await http.get(
                f"https://api.github.com/repos/{settings.vault_github_repo}",
                headers={
                    "Authorization": f"Bearer {settings.vault_github_token.get_secret_value()}"
                },
            )
            return response.status_code == 200, f"vault repo HTTP {response.status_code}"
        finally:
            if client is None:
                await http.aclose()

    return await _checked("vault", settings, probe)


async def check_google_token_cache(settings: Settings) -> CheckResult:
    async def probe() -> tuple[bool, str]:
        path = token_cache_path(settings)
        if path.is_file() and path.stat().st_size > 0:
            return True, f"refresh-token cache present ({path.stat().st_size} bytes)"
        return False, "no refresh-token cache — run the OAuth bootstrap (RUNBOOK §6)"

    return await _checked("google_token_cache", settings, probe)


async def check_space_health(
    settings: Settings, *, client: httpx.AsyncClient | None = None
) -> CheckResult:
    async def probe() -> tuple[bool, str]:
        space = (settings.space_url or "").strip()
        if not space:
            return True, "SPACE_URL not set — local run, health probe skipped"
        http = client or httpx.AsyncClient(timeout=8.0)
        try:
            response = await http.get(f"{space.rstrip('/')}/health")
            return response.status_code == 200, f"space /health HTTP {response.status_code}"
        finally:
            if client is None:
                await http.aclose()

    return await _checked("space_health", settings, probe)


CHECKS = ("gateway", "telegram", "vault", "google_token_cache", "space_health")


async def run_all(
    settings: Settings,
    timeout_s: float = 10.0,
    *,
    clients: dict[str, httpx.AsyncClient] | None = None,
) -> list[CheckResult]:
    clients = clients or {}

    async def bounded(name: str, check: Awaitable[CheckResult]) -> CheckResult:
        try:
            async with asyncio.timeout(timeout_s):
                return await check
        except TimeoutError:
            return CheckResult(name, False, f"timed out after {timeout_s}s")

    coros = {
        "gateway": check_gateway(settings, client=clients.get("gateway")),
        "telegram": check_telegram(settings, client=clients.get("telegram")),
        "vault": check_vault(settings, client=clients.get("vault")),
        "google_token_cache": check_google_token_cache(settings),
        "space_health": check_space_health(settings, client=clients.get("space_health")),
    }
    return list(await asyncio.gather(*(bounded(name, coro) for name, coro in coros.items())))


def main(settings: Settings | None = None) -> int:
    try:
        settings = settings or Settings()
    except ValidationError as error:
        logger.critical("deploy smoke refused — invalid environment: {error}", error=error)
        return 2
    results = asyncio.run(run_all(settings))
    for result in results:
        (logger.info if result.ok else logger.error)(
            "smoke {name}: {detail}", name=result.name, detail=result.detail
        )
    if all(result.ok for result in results):
        logger.info("deploy smoke OK — Sara is alive")
        return 0
    logger.critical("deploy smoke FAILED — Sara is not fully alive")
    return 1


if __name__ == "__main__":
    sys.exit(main())
