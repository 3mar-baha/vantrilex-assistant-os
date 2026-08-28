"""One-function loguru setup: exactly one stderr sink at the requested level."""

import sys

from loguru import logger


def configure_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format="{time:YYYY-MM-DDTHH:mm:ssZZ} | {level: <8} | {name}:{function}:{line} | {message}",
    )
