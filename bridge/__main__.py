"""Bridge daemon entrypoint (sprint-3 3.4): `py -3.12 -m bridge` on the owner's PC.
Runs the outbound tunnel client and the loopback LAN surface; Ctrl+C stops cleanly."""

from __future__ import annotations

import asyncio

from loguru import logger

from bridge.daemon import BridgeDaemon
from bridge.executor import Executor
from bridge.guard import Guard
from bridge.server import LanServer
from src.config import get_settings


async def main() -> int:
    settings = get_settings()
    stop = asyncio.Event()

    lan = LanServer(settings.bridge_lan_port)
    _, lan_port = await lan.start()
    logger.info("LAN surface on http://127.0.0.1:{port}/health", port=lan_port)

    daemon = BridgeDaemon(
        settings.bridge_server_url,
        settings.bridge_token.get_secret_value(),
        Executor(Guard("config/whitelist.json")),
    )
    runner = asyncio.create_task(daemon.run(stop))
    logger.info("bridge daemon dialing out; Ctrl+C to stop")
    try:
        await runner
    finally:
        stop.set()
        await lan.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("bridge daemon stopped")
