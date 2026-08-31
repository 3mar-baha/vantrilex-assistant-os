"""LAN HTTP surface (sprint-3 3.4): a tiny stdlib http.server bound to loopback/LAN —
NEVER 0.0.0.0. Serves /health now; the token-gated telemetry route arrives with 3.5."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args) -> None:  # keep the daemon log clean
        pass


class LanServer:
    def __init__(self, port: int, *, host: str = "127.0.0.1"):
        self._port = port
        self._host = host
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    async def start(self) -> tuple[str, int]:
        self._httpd = ThreadingHTTPServer((self._host, self._port), _Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._httpd.server_address[:2]
        return host, port

    async def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._thread.join(timeout=5)
            self._httpd = None
