"""LAN HTTP surface (sprint-3 3.4/3.5): a tiny stdlib http.server bound to loopback/LAN —
NEVER 0.0.0.0. Serves /health always; /telemetry/live-state arrives only when both a
shared token and a live_state provider are wired (Bearer-gated, 401 otherwise)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    lan_token: str | None = None
    provider = None  # Callable[[], LiveState] | None

    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/telemetry/live-state" and self.provider is not None:
            auth = self.headers.get("Authorization", "")
            if self.lan_token is None or auth != f"Bearer {self.lan_token}":
                body = json.dumps({"error": "unauthorized"}).encode("utf-8")
                self.send_response(401)
                self.send_header("WWW-Authenticate", "Bearer")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            body = self.provider().model_dump_json().encode("utf-8")
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
    def __init__(
        self,
        port: int,
        *,
        host: str = "127.0.0.1",
        token: str | None = None,
        provider=None,
    ):
        self._port = port
        self._host = host
        self._handler = type(
            "_LanHandler",
            (_Handler,),
            {"lan_token": token, "provider": staticmethod(provider)},
        )
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    async def start(self) -> tuple[str, int]:
        self._httpd = ThreadingHTTPServer((self._host, self._port), self._handler)
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
