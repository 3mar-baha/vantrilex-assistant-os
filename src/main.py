"""Core entrypoint: ``--health`` ops probe today; bot polling runner lands in 1.4."""

import asyncio
import json
import sys

from loguru import logger
from pydantic import ValidationError

from src.config import Settings
from src.health import healthcheck
from src.logsetup import configure_logging


async def run(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        settings = Settings()
    except ValidationError as error:
        logger.error("startup blocked — invalid environment: {}", error)
        return 2
    configure_logging(settings.log_level)

    if "--health" in argv:
        report = await healthcheck(settings)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["overall"] == "ok" else 1

    # Bind the gateway host only — never the API key or bot token.
    gateway_host = settings.omniroute_base_url.split("//")[-1].split("/")[0]
    logger.bind(owner_id=settings.authorized_user_id, gateway=gateway_host).info("core starting")

    from src.bot import run_bot  # lazy: bot shell lands with sprint-1 task 1.4

    await run_bot(settings)
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
