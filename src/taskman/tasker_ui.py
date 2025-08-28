"""
Tasker UI server scaffold for the taskman package.

This module provides a minimal, dependency-free HTTP server as a placeholder
for a future web UI. Static assets (HTML/CSS/JS) live in `src/taskman/ui/` and
are served directly by this module. This separation keeps Python code and UI
assets modular.

Usage:
    - Library: call start_ui(host, port)
    - CLI:     python -m taskman.tasker_ui
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import mimetypes
import os
from typing import Tuple


UI_DIR = (Path(__file__).parent / "ui").resolve()


class _UIRequestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler serving static UI and a health endpoint."""

    server_version = "taskman-tasker-ui/0.1"

    def _set_headers(self, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _serve_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self._set_headers(404)
            self.wfile.write(b"<h1>404 Not Found</h1><p>File not found.</p>")
            return

        # Guess content type
        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type is None:
            content_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as fp:
                data = fp.read()
        except OSError:
            self._set_headers(500)
            self.wfile.write(b"<h1>500 Internal Server Error</h1>")
            return

        self._set_headers(200, f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 (match http.server signature)
        if self.path in ("/health", "/_health"):
            payload = b"{\n  \"status\": \"ok\"\n}\n"
            self._set_headers(200, "application/json; charset=utf-8")
            self.wfile.write(payload)
            return

        # Static file serving
        parsed = urlparse(self.path)
        req_path = parsed.path

        # Default document
        if req_path in ("", "/"):
            target = UI_DIR / "index.html"
            return self._serve_file(target)

        # Prevent directory traversal
        clean = req_path.lstrip("/")
        if ".." in clean or clean.startswith(".") or clean.endswith("/"):
            self._set_headers(400)
            self.wfile.write(b"<h1>400 Bad Request</h1>")
            return

        target = (UI_DIR / clean).resolve()
        # Ensure the resolved path is within UI_DIR
        ui_root = UI_DIR
        try:
            target.relative_to(ui_root)
        except Exception:
            self._set_headers(403)
            self.wfile.write(b"<h1>403 Forbidden</h1>")
            return

        self._serve_file(target)

    # Suppress default noisy logging to stderr; keep it minimal
    def log_message(self, format: str, *args) -> None:  # noqa: A003 (shadow builtins)
        # Print a concise one-liner to stdout
        print(f"[UI] {self.address_string()} - {self.requestline}")


def start_ui(host: str = "127.0.0.1", port: int = 8765) -> None:
    """
    Start the placeholder UI HTTP server.

    Parameters:
        host: Interface to bind. Defaults to loopback.
        port: TCP port to listen on. Defaults to 8765.
    """
    server_address: Tuple[str, int] = (host, port)
    httpd = ThreadingHTTPServer(server_address, _UIRequestHandler)
    print(f"Taskman UI server (placeholder) listening on http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down UI server...")
    finally:
        httpd.server_close()


def main() -> None:
    """Console entry: start the UI with defaults."""
    start_ui()


if __name__ == "__main__":
    main()
