"""Live Shadow Tracer Console — real-time tail of Sara's cognition stream.

Reads the opt-in JSONL sink (`SARA_SHADOW_JSONL`, default
`vault/State/SARA_SHADOW_COGNITION_LOG.jsonl`) without locking it, classifies
each record into one of seven cognitive domains (unknown fields render as
`--`, never fabricated), and streams rich-colored events with live vitals.

Usage:
    python scripts/live_shadow_tracer.py [--once] [--lines N] [--log PATH]
    .\\sara.bat -Trace
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
import urllib.request
from collections import deque
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Final

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:  # pragma: no cover -- import-time guard, exercised only without rich installed
    sys.exit("live_shadow_tracer needs the 'rich' package (.venv has it).")

try:
    import psutil  # optional: bridge session count only, vitals degrade to '--'
except (
    ImportError
):  # pragma: no cover -- import-time guard, exercised only without psutil installed
    psutil = None  # type: ignore[assignment]

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_LOG: Final[Path] = ROOT / "vault" / "State" / "SARA_SHADOW_COGNITION_LOG.jsonl"
TURN_COUNTER: Final[Path] = ROOT / "vault" / "State" / "turn_counter.txt"
CORE_PORT: Final[int] = 8443
GATEWAY_MODELS_URL: Final[str] = "http://localhost:20128/v1/models"

DOMAIN_COLORS: Final[dict[str, str]] = {
    "ingest": "cyan",
    "posture": "magenta",
    "router": "yellow",
    "memory": "green",
    "generation": "blue",
    "tools": "red",
    "audio": "bright_cyan",
    "invariants": "bright_magenta",
    "system": "dim",
}

# The tracer's own tool-call marker — the keyword the `tools` group already keys on.
# Emitted by the `{!r}` tool logs: src/tools.py:145 (`tool 'gmail' failed: …`),
# src/dispatcher.py:1040 (`dispatcher tool 'gmail' failed -> plain tier2: …`) and
# src/decision_loop.py:435. Decision 8's per-tool counters read the same stream the
# classifier already consumes, so no new instrumentation is needed in `src/`.
#
# MEASURED LIMIT, stated here because the HUD must not overclaim: as of this writing
# only the tool lane's FAILURE path logs that marker. A successful call logs nothing,
# and the dispatcher's verdict lines use a different shape (`tool='gmail'`). In the
# owner's live log, 1 of 229 records carried it. So these counters count recorded
# tool-lane events, NOT total tool traffic, and the row reads as a floor. Making them
# exact needs a success-path log in src/tools.py — out of this file's write-set.
TOOL_MARKER: Final[re.Pattern[str]] = re.compile(r"tool '([^']+)'")

# How many rendered records the HUD's per-tool counters can see. Bounded so a live
# tail cannot grow this without limit; the oldest record falls off the window.
RECORD_WINDOW: Final[int] = 500
RECENT_RECORDS: Final[deque[dict]] = deque(maxlen=RECORD_WINDOW)

# Ordered: first match wins. Blob = logger name + function + message, lowercased.
# NOTE: bare `router` is deliberately absent — model slugs like `openrouter/…`
# contain it. Router signals use multi-word/dispatcher-anchored keywords.
#
# `invariants` is FIRST, and that ordering is load-bearing rather than cosmetic. A
# real invariant report names the invariants themselves, and those words collide with
# two other groups: "Zero Edge-TTS" contains `tts` (the `audio` group) and "$0.00 cost"
# contains `cost`/`$0` (the `generation` group). Under first-match-wins, any position
# after those groups files every invariant line under the wrong domain and the HUD
# silently loses the marker.
DOMAIN_RULES: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("invariants", ("invariant", "sacred floor")),
    ("audio", ("fish", "synth", "opus", "ffmpeg", "expressive_audio", "tts")),
    ("ingest", ("transcrib", "voice note", "inbound", "biometric", "telegram", "stt")),
    (
        "posture",
        ("posture", "turn counter", "turn_counter", "turns_since", "cadence", "situational"),
    ),
    (
        "memory",
        (
            "rag",
            "envelope",
            "digest",
            "ledger",
            "recall",
            "associative",
            "user_info",
            "affect",
            "extraction",
        ),
    ),
    (
        "tools",
        ("tool '", "confirmation_id", "bridge", "screenshot", "screen_ocr", "pc_actions", "launch"),
    ),
    (
        "router",
        (
            "dispatcher",
            "decision_loop",
            "deduce",
            "repair_verdict",
            "router-miss",
            "router verdict",
            "router failed",
            "verdict",
        ),
    ),
    (
        "generation",
        (
            "ttft",
            "token",
            "paidmodel",
            "cost",
            "$0",
            "gateway",
            "first-token",
            "exhausted",
            "all models",
        ),
    ),
)


def classify_record(record: dict) -> str:
    """Map one serialized loguru record to its cognition domain (never raises)."""
    try:
        inner = record.get("record") or {}
        blob = " ".join(str(inner.get(key, "")) for key in ("name", "function", "message")).lower()
    except (AttributeError, TypeError):
        return "system"
    if not blob.strip():
        return "system"
    for domain, keywords in DOMAIN_RULES:
        if any(keyword in blob for keyword in keywords):
            return domain
    return "system"


def _reopen_tail(path: Path, stat: object, handle: object | None) -> tuple[object, object]:
    """Open a fresh read handle after rotation or truncation."""
    if handle is not None:
        handle.close()
    return path.open(encoding="utf-8", errors="replace"), stat.st_ino


def follow_events(path: Path, poll_s: float = 0.25) -> Iterator[dict]:
    """Yield parsed records across appends and log rotation (reopen on shrink)."""
    handle = None
    position = 0
    known_inode = None
    try:
        while True:
            try:
                stat = path.stat()
            except OSError:
                time.sleep(poll_s or 0.01)
                continue
            if handle is None or stat.st_ino != known_inode or stat.st_size < position:
                handle, known_inode = _reopen_tail(path, stat, handle)
                position = 0
            handle.seek(position)
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
            position = handle.tell()
            time.sleep(poll_s or 0.01)
    finally:
        if handle is not None:
            handle.close()


def core_health() -> str:
    """Raw TCP Upgrade handshake against :8443 (mirrors sara.ps1, no HTTP lib)."""
    started = time.perf_counter()
    try:
        with socket.create_connection(("127.0.0.1", CORE_PORT), timeout=3) as sock:
            sock.sendall(
                b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                b"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            head = sock.recv(64)
        if b"101" in head:
            return f"True {((time.perf_counter() - started) * 1000):.0f}ms"
    except OSError:
        pass
    return "--"


def bridge_sessions() -> str:
    """ESTABLISHED loopback sessions on the core port (tuple-anchored dial)."""
    if psutil is None:
        return "--"
    try:
        count = sum(
            1
            for conn in psutil.net_connections(kind="tcp")
            if conn.status == "ESTABLISHED"
            and conn.laddr
            and conn.raddr
            and conn.laddr.port == CORE_PORT
            and conn.raddr.ip in ("127.0.0.1", "::1")
        )
        return str(count)
    except (OSError, RuntimeError):
        return "--"


def gateway_models() -> str:
    try:
        with urllib.request.urlopen(GATEWAY_MODELS_URL, timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return str(len(payload.get("data", [])))
    except (OSError, ValueError, KeyError):
        return "--"


def turn_count() -> str:
    try:
        return TURN_COUNTER.read_text(encoding="utf-8").strip() or "--"
    except (OSError, ValueError):
        return "--"


def tool_call_counters(records: Iterable[dict]) -> dict[str, int]:
    """Per-tool call counts read off the record stream the classifier already reads.

    Keys on the tracer's own `tool '<name>'` marker, so a record that merely lands in
    the `tools` domain without naming a tool — `confirmation_id pending`, say —
    contributes nothing, and a gateway record never does either.

    Returns `{}` for no tool records: never `None`, so the HUD can print the row
    without a `TypeError`. Never raises — a malformed record is skipped, not fatal.
    """
    counters: dict[str, int] = {}
    for record in records:
        inner = record.get("record") if isinstance(record, dict) else None
        if not isinstance(inner, dict):
            continue
        found = TOOL_MARKER.search(str(inner.get("message", "")))
        if found is None:
            continue
        name = found.group(1).strip()
        if name:
            counters[name] = counters.get(name, 0) + 1
    return counters


def _event_timestamp(inner: dict) -> str:
    """Serialized loguru `time` is a dict (`repr`/`timestamp`) — unwrap it."""
    raw_time = inner.get("time", "--")
    if isinstance(raw_time, dict):
        raw_time = raw_time.get("repr", "--")
    return str(raw_time)[:19]


def render_event(console: Console, record: dict) -> None:
    inner = record.get("record") or {} if isinstance(record, dict) else {}
    if isinstance(record, dict):
        # Feed the HUD's per-tool counters (Decision 8). Every record the tracer
        # displays passes through here — live tail and `--once` alike — so this is
        # the one place the counter has to hook to see real traffic.
        RECENT_RECORDS.append(record)
    domain = classify_record(record if isinstance(record, dict) else {})
    color = DOMAIN_COLORS[domain]
    timestamp = _event_timestamp(inner)
    level = str(
        inner.get("level", {}).get("name", "INFO")
        if isinstance(inner.get("level"), dict)
        else inner.get("level", "INFO")
    )
    message = str(inner.get("message", "--"))
    origin = f"{inner.get('name', '?')}:{inner.get('function', '?')}"
    console.print(
        f"[dim]{timestamp}[/] [{color}]{domain:>10}[/] [{level:<7}] {message} [dim]({origin})[/]"
    )


def vitals_table() -> Table:
    """The HUD's signal table.

    The per-tool counters read `RECENT_RECORDS`, the window `render_event` fills, so
    in the live console they count what has actually streamed past on this run.
    """
    table = Table(title="SARA live vitals", show_header=True, header_style="bold")
    table.add_column("Signal")
    table.add_column("Value")
    table.add_row("CORE_HEALTH :8443", core_health())
    table.add_row("BRIDGE_SESSIONS", bridge_sessions())
    table.add_row("GATEWAY_MODELS", gateway_models())
    table.add_row("TURN_COUNTER", turn_count())
    counters = tool_call_counters(RECENT_RECORDS)
    if counters:
        for tool, count in sorted(counters.items()):
            table.add_row(f"TOOL_CALLS {tool}", str(count))
    else:
        table.add_row("TOOL_CALLS", "--")
    return table


def snapshot_once(console: Console, log_path: Path, tail_depth: int) -> int:
    """Print one vitals table plus the last records, then exit (scriptable mode)."""
    if not log_path.exists():
        console.print(vitals_table())
        console.print(f"[yellow]No shadow log yet at {log_path} (core boots it).[/]")
        return 0
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail_depth:]
    # Parse the tail BEFORE the vitals print, so the per-tool counters above are real
    # numbers in `--once` mode instead of a row of dashes.
    records: list[dict] = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    console.print(vitals_table())
    for record in records:
        render_event(console, record)
    return 0


def wait_for_log(
    console: Console, log_path: Path, poll_s: float = 2.0, timeout_s: float | None = None
) -> None:
    """Block until the shadow log appears; the notice prints exactly once."""
    console.print(f"[yellow]Waiting for shadow log at {log_path} … (start sara.bat)[/]")
    started = time.monotonic()
    while not log_path.exists():
        if timeout_s is not None and time.monotonic() - started >= timeout_s:
            raise TimeoutError(log_path)
        time.sleep(poll_s or 0.01)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sara live shadow tracer console")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--once", action="store_true", help="snapshot vitals + tail, then exit")
    parser.add_argument("--lines", type=int, default=15, help="tail depth for --once")
    args = parser.parse_args(argv)
    console = Console()
    if args.once:
        return snapshot_once(console, args.log, args.lines)
    console.print(Panel(vitals_table(), title="SHADOW TRACER — live", border_style="green"))
    wait_for_log(console, args.log)
    console.print(f"[green]Tailing {args.log} — Ctrl+C to stop.[/]")
    try:
        for record in follow_events(args.log):
            render_event(console, record)
    except KeyboardInterrupt:
        console.print("\n[dim]Tracer stopped.[/]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
