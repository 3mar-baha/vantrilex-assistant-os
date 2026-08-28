"""Sprint-1 §1.1 AC4: loguru setup — one sink, configured level, idempotent."""

from loguru import logger

from src.logsetup import configure_logging


def test_single_sink_at_configured_level_and_idempotent(capsys):
    """Two configure calls leave exactly one sink (probe printed once) at DEBUG;
    reconfiguring to INFO suppresses debug output."""
    configure_logging("DEBUG")
    configure_logging("DEBUG")  # second call must not duplicate sinks
    logger.debug("probe-debug-marker")
    assert capsys.readouterr().err.count("probe-debug-marker") == 1

    configure_logging("INFO")
    logger.debug("probe-suppressed-marker")
    assert "probe-suppressed-marker" not in capsys.readouterr().err
