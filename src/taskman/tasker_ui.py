"""
Tasker UI server for the taskman package.

This module provides a lightweight, dependency-free HTTP server and a minimal
frontend for managing projects. Static assets (HTML/CSS/JS) live in
`src/taskman/ui/` and are served directly by this module.

Currently supported routes:
  - GET  /health                         -> basic health check (JSON)
  - GET  /                               -> UI index (projects list with add + inline rename)
  - GET  /project.html?name=<name>       -> UI project view (tasks table)
  - GET  /api/projects                   -> list saved project names + current
  - GET  /api/state                      -> current project name
  - GET  /api/projects/<name>/tasks      -> tasks JSON for a project
  - POST /api/projects/open              -> open/create a project { name }
  - POST /api/projects/edit-name         -> rename project { old_name, new_name }
  - POST /api/exit                       -> graceful shutdown

Usage:
  - Library: start_ui(host, port)
  - CLI:     python -m taskman.tasker_ui
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
import mimetypes
import os
import json
import threading
import time
from typing import Tuple, Optional
import logging

from .project_manager import ProjectManager
from .project import Project


UI_DIR = (Path(__file__).parent / "ui").resolve()
logger = logging.getLogger("taskman.tasker_ui")
# Configure a simple console handler if none are present so info logs show up
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


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

        # Guess content type and stream bytes
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
        parsed = urlparse(self.path)
        req_path = parsed.path
        if req_path in ("/health", "/_health"):
            payload = b"{\n  \"status\": \"ok\"\n}\n"
            self._set_headers(200, "application/json; charset=utf-8")
            self.wfile.write(payload)
            return

        # API endpoints (read-only)
        if req_path == "/api/projects":
            projects = ProjectManager.load_project_names()
            current = getattr(self.server, "current_project_name", None)
            return self._json({"projects": projects, "currentProject": current})
        if req_path == "/api/state":
            current = getattr(self.server, "current_project_name", None)
            return self._json({"currentProject": current})

        # Project tasks for a given project name
        if req_path.startswith("/api/projects/") and req_path.endswith("/tasks"):
            parts = req_path.split("/")
            # ['', 'api', 'projects', '<name>', 'tasks']
            if len(parts) >= 5 and parts[1] == "api" and parts[2] == "projects" and parts[-1] == "tasks":
                name = unquote(parts[3])
                # Basic validation; prevent traversal or dotfiles
                if not name or ".." in name or name.startswith("."):
                    return self._json({"error": "Invalid project name"}, 400)
                task_file = ProjectManager.get_task_file_path(name)
                tasks = []
                if os.path.exists(task_file):
                    try:
                        with open(task_file, "r", encoding="utf-8") as f:
                            tasks = json.load(f)
                            if not isinstance(tasks, list):
                                self.log_message(
                                    "Tasks JSON for project '%s' is not a list: %r", name, type(tasks), level="warning"
                                )
                                tasks = []
                    except Exception as e:
                        # Use request handler's logger to capture details concisely
                        self.log_message(
                            "Failed reading tasks for project '%s' from %s: %r", name, task_file, e, level="exception"
                        )
                        tasks = []
                return self._json({"project": name, "tasks": tasks})

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
    def log_message(self, format: str, *args, level: str = "info") -> None:  # noqa: A003 (shadow builtins)
        # Consistent one-liner format via logger; keeps signature compatible with BaseHTTPRequestHandler
        try:
            message = (format % args) if args else str(format)
        except Exception:
            message = str(format)
        suffix = f" - {message}" if message else ""
        line = f"[UI] {self.address_string()} - {self.requestline}{suffix}"
        lvl = (level or "info").lower()
        if lvl == "warning" or lvl == "warn":
            logger.warning(line)
        elif lvl == "error":
            logger.error(line)
        elif lvl == "exception":
            logger.exception(line)
        elif lvl == "debug":
            logger.debug(line)
        else:
            logger.info(line)


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
