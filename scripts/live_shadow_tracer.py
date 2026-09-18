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
import socket
import sys
import time
import urllib.request
from collections.abc import Iterator
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
    "system": "dim",
}

# Ordered: first match wins. Blob = logger name + function + message, lowercased.
DOMAIN_RULES: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("audio", ("fish", "synth", "opus", "ffmpeg", "expressive_audio", "tts")),
    ("ingest", ("transcrib", "voice note", "inbound", "biometric", "telegram", "stt")),
    (
        "posture",
        ("posture", "turn counter", "turn_counter", "turns_since", "cadence", "situational"),
    ),
    ("router", ("verdict", "repair_verdict", "router", "dispatch", "decision_loop", "deduce")),
    ("memory", ("rag", "envelope", "digest", "ledger", "recall", "associative", "user_info")),
    ("generation", ("ttft", "token", "paidmodel", "cost", "$0", "gateway", "first-token")),
    (
        "tools",
        ("tool", "confirmation_id", "bridge", "screenshot", "screen_ocr", "pc_actions", "launch"),
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


def render_event(console: Console, record: dict) -> None:
    inner = record.get("record") or {} if isinstance(record, dict) else {}
    domain = classify_record(record if isinstance(record, dict) else {})
    color = DOMAIN_COLORS[domain]
    timestamp = str(inner.get("time", "--"))[:19]
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
    table = Table(title="SARA live vitals", show_header=True, header_style="bold")
    table.add_column("Signal")
    table.add_column("Value")
    table.add_row("CORE_HEALTH :8443", core_health())
    table.add_row("BRIDGE_SESSIONS", bridge_sessions())
    table.add_row("GATEWAY_MODELS", gateway_models())
    table.add_row("TURN_COUNTER", turn_count())
    return table


def snapshot_once(console: Console, log_path: Path, tail_depth: int) -> int:
    """Print one vitals table plus the last records, then exit (scriptable mode)."""
    console.print(vitals_table())
    if not log_path.exists():
        console.print(f"[yellow]No shadow log yet at {log_path} (core boots it).[/]")
        return 0
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-tail_depth:]:
        try:
            render_event(console, json.loads(line))
        except json.JSONDecodeError:
            continue
    return 0


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
    while not args.log.exists():
        console.print(f"[yellow]Waiting for shadow log at {args.log} … (start sara.bat)[/]")
        time.sleep(2)
    console.print(f"[green]Tailing {args.log} — Ctrl+C to stop.[/]")
    try:
        for record in follow_events(args.log):
            render_event(console, record)
    except KeyboardInterrupt:
        console.print("\n[dim]Tracer stopped.[/]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
