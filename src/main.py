"""Core entrypoint: ``--health`` ops probe; $PORT Space entry (ADR-15) + bot polling."""

import asyncio
import json
import os
import sys

from loguru import logger
from pydantic import ValidationError

from src.config import Settings
from src.health import healthcheck
from src.logsetup import configure_logging


async def start_public_port(settings: Settings, port: int, *, host: str = "0.0.0.0"):
    """HF Space contract (sprint-4 4.4b): ONE public port serves GET /health for the
    keep-alive ping + Space probes, and the authenticated bridge WSS for everything
    else. Returns (bridge, bound_port)."""
    from websockets.datastructures import Headers
    from websockets.http11 import Response

    from src.bridge_server import BridgeServer

    async def health_responder(connection, request):
        if request.path.split("?")[0] == "/health":
            return Response(200, "OK", Headers(), b'{"status":"ok"}\n')
        return None

    bridge = BridgeServer(settings.bridge_token.get_secret_value())
    bound = await bridge.start(host, port, process_request=health_responder)
    logger.info("space entry: public port {p} serves /health + bridge WSS", p=bound)
    return bridge, bound


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

    bridge = None
    try:
        if os.environ.get("PORT"):
            bridge, _bound = await start_public_port(settings, int(os.environ["PORT"]))
        await run_bot(settings, bridge=bridge)
    finally:
        if bridge is not None:
            await bridge.close()
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
