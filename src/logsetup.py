"""One-function loguru setup: stderr sink + opt-in shadow JSONL sink.

`SARA_SHADOW_JSONL` (default-ON from sara.ps1) adds a serialized file sink the
live tracer console tails. Unset = exactly the historical single-sink behavior.
"""

import os
import sys

from loguru import logger

SHADOW_ENV_VAR = "SARA_SHADOW_JSONL"


def configure_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format="{time:YYYY-MM-DDTHH:mm:ssZZ} | {level: <8} | {name}:{function}:{line} | {message}",
    )
    shadow_path = os.environ.get(SHADOW_ENV_VAR)
    if shadow_path:
        try:
            logger.add(
                shadow_path,
                serialize=True,
                level=level.upper(),
                rotation="5 MB",
                retention=2,
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("shadow sink disabled ({}): {}", shadow_path, exc)
