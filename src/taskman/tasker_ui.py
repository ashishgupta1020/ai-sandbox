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
import json
import threading
import time
from typing import Tuple, Optional

from .project_manager import ProjectManager
from .project import Project


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

    def _json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self._set_headers(status, "application/json; charset=utf-8")
        self.wfile.write(payload)

    def _read_json(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def do_GET(self) -> None:  # noqa: N802 (match http.server signature)
        if self.path in ("/health", "/_health"):
            payload = b"{\n  \"status\": \"ok\"\n}\n"
            self._set_headers(200, "application/json; charset=utf-8")
            self.wfile.write(payload)
            return

        # API endpoints (read-only)
        if self.path == "/api/projects":
            projects = ProjectManager.load_project_names()
            current = getattr(self.server, "current_project_name", None)
            return self._json({"projects": projects, "currentProject": current})
        if self.path == "/api/state":
            current = getattr(self.server, "current_project_name", None)
            return self._json({"currentProject": current})

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

    def do_POST(self) -> None:  # noqa: N802
        # API endpoints (mutations)
        parsed = urlparse(self.path)
        if parsed.path == "/api/projects/open":
            body = self._read_json()
            if body is None or "name" not in body or not str(body["name"]).strip():
                return self._json({"error": "Missing 'name'"}, 400)
            name = str(body["name"]).strip()
            try:
                # Persist and load
                ProjectManager.save_project_name(name)
                # Initialize project (creates files/dirs as needed)
                _ = Project(name)
                # Remember current project on server
                setattr(self.server, "current_project_name", name)
                return self._json({"ok": True, "currentProject": name})
            except Exception as e:
                return self._json({"error": str(e)}, 500)

        if parsed.path == "/api/projects/edit-name":
            body = self._read_json()
            if body is None:
                return self._json({"error": "Invalid JSON"}, 400)
            old = str(body.get("old_name", "")).strip()
            new = str(body.get("new_name", "")).strip()
            if not old or not new:
                return self._json({"error": "'old_name' and 'new_name' required"}, 400)
            ok = ProjectManager.edit_project_name(old, new)
            if not ok:
                # edit_project_name already prints; respond with generic failure
                return self._json({"ok": False}, 400)
            # update current project if it matched
            cur = getattr(self.server, "current_project_name", None)
            if cur == old:
                setattr(self.server, "current_project_name", new)
            return self._json({"ok": True, "currentProject": getattr(self.server, "current_project_name", None)})

        if parsed.path == "/api/exit":
            # Respond then shutdown the server gracefully
            self._json({"ok": True, "message": "Shutting down"})
            try:
                self.wfile.flush()
            except Exception:
                pass
            def _shutdown():
                # small delay to ensure response is flushed
                try:
                    time.sleep(0.15)
                    self.server.shutdown()
                except Exception:
                    pass
            threading.Thread(target=_shutdown, daemon=True).start()
            return

        # Unknown mutation
        self._json({"error": "Unknown endpoint"}, 404)

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
    # Track current project name across requests (in-memory)
    httpd.current_project_name = None  # type: ignore[attr-defined]
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
