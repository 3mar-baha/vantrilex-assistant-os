"""Core entrypoint: ``--health`` ops probe; $PORT Space entry (ADR-15) + bot polling.

``/health`` is TRUTHFUL, per lane (N3 / F-8). It answers HTTP 200 with a
machine-readable body carrying a state per lane — `healthy` / `misconfigured` /
`unreachable`, never a vague `ok` — and it never BLOCKS this event loop waiting
for four network calls, because the authenticated WSS tunnel shares the loop with
it. It reads the probe cache, and schedules a background sweep when that cache is
cold or past its TTL; a cold cache answers every lane `unreachable` rather than
claiming health it has not measured. The status-code decision is
`src.health.HTTP_STATUS_BY_STATE` and the reason it is 200 for every state is in
that module's docstring; the operator's non-zero alarm is `--health`'s exit code.
"""

import asyncio
import os
import sys

from loguru import logger
from pydantic import ValidationError

from src.config import Settings
from src.health import (
    HTTP_STATUS_BY_STATE,
    encode_body,
    exit_code_for,
    healthcheck,
    schedule_refresh,
    snapshot,
)
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
            # Serve the last completed sweep, and kick off the next one if it is
            # cold or stale. Fire-and-forget on purpose: awaiting the sweep here
            # would hold this connection (and every other task on the loop,
            # including the tunnel) for up to ~23s of probe timeouts.
            schedule_refresh(settings)
            body = snapshot()
            return Response(
                HTTP_STATUS_BY_STATE[body["overall"]],
                "OK",
                Headers(),
                encode_body(body),
            )
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
        # Always a FRESH sweep here: this is an operator asking, not a poll, and
        # the endpoint's cache is deliberately not in this path.
        report = await healthcheck(settings)
        print(encode_body(report).decode("utf-8"), end="")
        return exit_code_for(report)

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
