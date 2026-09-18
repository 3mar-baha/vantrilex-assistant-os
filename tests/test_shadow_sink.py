"""Shadow sink (Tier-3): opt-in JSONL event stream for the live tracer console.

Seam: src.logsetup.configure_logging — public logging entrypoint.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from src.logsetup import configure_logging


def test_shadow_sink_emits_parseable_jsonl_per_record(tmp_path: Path, monkeypatch) -> None:
    """Owner can tail one JSON object per log record for the tracer console."""
    shadow = tmp_path / "shadow.jsonl"
    monkeypatch.setenv("SARA_SHADOW_JSONL", str(shadow))
    try:
        configure_logging("INFO")
        logger.bind(component="probe").info("shadow sink RED probe")
        logger.complete()
    finally:
        monkeypatch.delenv("SARA_SHADOW_JSONL", raising=False)
        configure_logging("INFO")
    lines = shadow.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    record = json.loads(lines[-1])
    assert record["record"]["message"] == "shadow sink RED probe"


def test_shadow_sink_absent_by_default(tmp_path: Path, monkeypatch) -> None:
    """Unset env = byte-identical current behavior: no sink file appears."""
    monkeypatch.delenv("SARA_SHADOW_JSONL", raising=False)
    sentinel = tmp_path / "should_not_exist.jsonl"
    configure_logging("INFO")
    logger.info("no sink expected")
    logger.complete()
    assert not sentinel.exists()


def test_shadow_sink_survives_unwritable_path(tmp_path: Path, monkeypatch) -> None:
    """A bad shadow path must never break logging itself."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    monkeypatch.setenv("SARA_SHADOW_JSONL", str(blocker / "missing.jsonl"))
    configure_logging("INFO")
    logger.info("logging still alive")
    logger.complete()
    monkeypatch.delenv("SARA_SHADOW_JSONL", raising=False)
    configure_logging("INFO")
