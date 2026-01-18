"""
Tasker server for the taskman package.

This module provides a lightweight, dependency-free HTTP server and a minimal
frontend for managing projects. Static assets (HTML/CSS/JS) live in
`src/taskman/ui/` and are served directly by this module.

Currently supported routes:
  - GET  /health                                 -> basic health check (JSON)
  - GET  /                                       -> UI index (projects list with add + inline rename)
  - GET  /project.html?name=<name>               -> UI project view (tasks table)
  - GET  /api/projects                           -> list saved project names
  - GET  /api/project-tags                       -> map of all project tags
  - GET  /api/projects/<name>/tasks              -> list tasks JSON for a project
  - GET  /api/projects/<name>/tags               -> list tags for a project
  - GET  /api/highlights                         -> aggregate highlighted tasks across projects
  - GET  /api/assignees                          -> list unique assignees across all projects
  - GET  /api/tasks?assignee=...                 -> list tasks (optionally filtered by assignees) across projects
  - POST /api/projects/<name>/tasks/update       -> update a single task { index, fields }
  - POST /api/projects/<name>/tasks/create       -> create a new task { optional fields }
  - POST /api/projects/<name>/tasks/delete       -> delete a task { index }
  - POST /api/projects/<name>/tasks/highlight    -> toggle highlight { id, highlight }
  - POST /api/projects/<name>/tags/add           -> add one or more tags to a project
  - POST /api/projects/<name>/tags/remove        -> remove a tag from a project
  - POST /api/projects/open                      -> open/create a project { name }
  - POST /api/projects/edit-name                 -> rename project { old_name, new_name }
  - POST /api/projects/delete                    -> delete a project { name }
  - POST /api/exit                               -> graceful shutdown

  TODO APIs:
  - GET  /api/todo                               -> list todo items
  - GET  /api/todo/archive                       -> list archived todo items
  - POST /api/todo/add                           -> create a todo item
  - POST /api/todo/mark                          -> mark todo done/undone
  - POST /api/todo/edit                          -> edit a todo item

Usage:
  - Library: start_server(host, port) (call load_config() first)
  - CLI:     python -m taskman.server.tasker_server --config /path/config.json
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import importlib.resources as resources
import json
import logging
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from taskman.config import get_log_level, load_config

from . import asset_manifest
from . import route_handlers
from .project_api import ProjectAPI
from .task_api import TaskAPI
from .todo import TodoAPI

# Module-wide resources
# Keep a context open so importlib.resources can extract packaged assets if needed
_ui_stack = contextlib.ExitStack()
try:
    _ui_resources = resources.files("taskman") / "ui"
    UI_DIR = _ui_stack.enter_context(resources.as_file(_ui_resources))
except Exception:
    # Fallback for editable installs or unusual environments
    UI_DIR = (Path(__file__).resolve().parent.parent / "ui").resolve()
atexit.register(_ui_stack.close)

logger = logging.getLogger(__name__)

# API instances (module-level singletons)
_todo_api = TodoAPI()
_project_api = ProjectAPI()
_task_api = TaskAPI()

# Build asset manifest for cache-busting
try:
    _ASSET_MANIFEST, _HASHED_ASSET_MAP = asset_manifest.build_asset_manifest(UI_DIR)
except Exception:
    _ASSET_MANIFEST = {}
    _HASHED_ASSET_MAP = {}


class _UIRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for Taskman UI and API.

    - Serves static assets from ``UI_DIR`` (``/`` and other files).
    - Exposes a JSON health check at ``/health``.
    - Implements project/task API endpoints under ``/api/...`` (GET/POST), including
      cross-project highlight aggregation.
    - Validates paths to prevent traversal and dotfile access.
    - Overrides ``log_request`` to emit debug-level access logs via ``log_message``.
    - Uses the module logger for output instead of default stderr logging.
    """

    server_version = "taskman-server/0.1"

    def log_request(self, code="-", size="-") -> None:
        """Log an accepted request at debug level."""
        self.log_message(
            '"%s" %s %s', self.requestline, str(code), str(size), level="debug"
        )

    def _set_headers(
        self,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        self.end_headers()

    def _serve_file(self, file_path: Path, cache_control: str = "no-store") -> None:
        """Serve a static file from disk."""
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

        # Rewrite HTML to use hashed asset URLs
        if content_type.startswith("text/html"):
            text = data.decode("utf-8", errors="replace")
            text = asset_manifest.rewrite_html_assets(text, _ASSET_MANIFEST)
            data = text.encode("utf-8")
        if content_type.startswith("text/"):
            content_type = f"{content_type}; charset=utf-8"

        self._set_headers(200, content_type, cache_control)
        self.wfile.write(data)

    def _json(self, data: dict, status: int = 200) -> None:
        """Send a JSON response."""
        payload = json.dumps(data).encode("utf-8")
        self._set_headers(status, "application/json; charset=utf-8")
        self.wfile.write(payload)

    def _read_json(self) -> Optional[dict]:
        """Read and parse JSON from the request body."""
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
        """Handle GET requests."""
        parsed = urlparse(self.path)
        req_path = parsed.path

        # Health check endpoint
        if req_path in ("/health", "/_health"):
            payload, status = route_handlers.handle_health()
            return self._json(payload, status)

        # Simple API endpoints (no path parameters)
        if req_path == "/api/projects":
            payload, status = route_handlers.handle_list_projects(_project_api)
            return self._json(payload, status)

        if req_path == "/api/project-tags":
            payload, status = route_handlers.handle_project_tags(_project_api)
            return self._json(payload, status)

        if req_path == "/api/assignees":
            payload, status = route_handlers.handle_assignees(_project_api, _task_api)
            return self._json(payload, status)

        if req_path == "/api/tasks":
            payload, status = route_handlers.handle_tasks_list(
                _project_api, _task_api, parsed.query or ""
            )
            return self._json(payload, status)

        if req_path == "/api/highlights":
            payload, status = route_handlers.handle_highlights(_project_api, _task_api)
            return self._json(payload, status)

        # TODO API endpoints
        if req_path == "/api/todo":
            payload, status = route_handlers.handle_todo_list(_todo_api)
            return self._json(payload, status)

        if req_path == "/api/todo/archive":
            payload, status = route_handlers.handle_todo_archive(_todo_api)
            return self._json(payload, status)

        # Pattern-matched GET routes (with path parameters)
        for pattern, handler_key in route_handlers.GET_ROUTE_PATTERNS:
            match = pattern.match(req_path)
            if match:
                project_name = match.group(1)
                if handler_key == "project_tasks":
                    payload, status = route_handlers.handle_project_tasks(
                        _project_api, _task_api, project_name
                    )
                    return self._json(payload, status)
                elif handler_key == "project_tags":
                    payload, status = route_handlers.handle_get_project_tags(_project_api, project_name)
                    return self._json(payload, status)

        # Static file serving
        # Default document
        if req_path in ("", "/"):
            target = UI_DIR / "index.html"
            return self._serve_file(target)

        # Any other page
        clean = req_path.lstrip("/")

        # Prevent directory traversal - return 404 for consistency with unmatched routes
        if ".." in clean or clean.startswith(".") or clean.endswith("/"):
            self._set_headers(404)
            self.wfile.write(b"<h1>404 Not Found</h1>")
            return

        # Serve hashed assets with long-term caching headers
        if clean in _HASHED_ASSET_MAP:
            target = (UI_DIR / _HASHED_ASSET_MAP[clean]).resolve()
            return self._serve_file(target, cache_control=asset_manifest.ASSET_CACHE_CONTROL)

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
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Simple POST endpoints (no path parameters)
        if path == "/api/projects/open":
            body = self._read_json()
            payload, status = route_handlers.handle_open_project(_project_api, body)
            return self._json(payload, status)

        if path == "/api/projects/edit-name":
            body = self._read_json()
            payload, status = route_handlers.handle_edit_project_name(_project_api, body)
            return self._json(payload, status)

        if path == "/api/projects/delete":
            body = self._read_json()
            payload, status = route_handlers.handle_delete_project(_project_api, body)
            return self._json(payload, status)

        # TODO API endpoints
        if path == "/api/todo/add":
            body = self._read_json()
            payload, status = route_handlers.handle_todo_add(_todo_api, body)
            return self._json(payload, status)

        if path == "/api/todo/mark":
            body = self._read_json()
            payload, status = route_handlers.handle_todo_mark(_todo_api, body)
            return self._json(payload, status)

        if path == "/api/todo/edit":
            body = self._read_json()
            payload, status = route_handlers.handle_todo_edit(_todo_api, body)
            return self._json(payload, status)

        # Graceful shutdown endpoint
        if path == "/api/exit":
            self._json({"ok": True, "message": "Shutting down"})
            try:
                self.wfile.flush()
            except Exception:
                pass

            def _shutdown():
                # Small delay to ensure response is flushed
                try:
                    time.sleep(0.15)
                    self.server.shutdown()
                except Exception:
                    pass

            threading.Thread(target=_shutdown, daemon=True).start()
            return

        # Pattern-matched POST routes (with path parameters)
        for pattern, handler_key in route_handlers.POST_ROUTE_PATTERNS:
            match = pattern.match(path)
            if match:
                project_name = match.group(1)
                body = self._read_json()

                if handler_key == "task_update":
                    payload, status = route_handlers.handle_update_task(_task_api, project_name, body)
                    return self._json(payload, status)
                elif handler_key == "tags_add":
                    payload, status = route_handlers.handle_add_project_tags(
                        _project_api, project_name, body
                    )
                    return self._json(payload, status)
                elif handler_key == "tags_remove":
                    payload, status = route_handlers.handle_remove_project_tag(
                        _project_api, project_name, body
                    )
                    return self._json(payload, status)
                elif handler_key == "task_highlight":
                    payload, status = route_handlers.handle_highlight_task(
                        _task_api, project_name, body
                    )
                    return self._json(payload, status)
                elif handler_key == "task_create":
                    payload, status = route_handlers.handle_create_task(_task_api, project_name, body)
                    return self._json(payload, status)
                elif handler_key == "task_delete":
                    payload, status = route_handlers.handle_delete_task(_task_api, project_name, body)
                    return self._json(payload, status)

        # Unknown endpoint - consume the request body before responding
        self._read_json()
        self._json({"error": "Unknown endpoint"}, 404)

    def log_message(self, format: str, *args, level: str = "info") -> None:  # noqa: A003 (shadow builtins)
        """Log a message via the module logger."""
        message = format % args if args else str(format)
        prefix = f"[UI] {self.address_string()} - {self.requestline}"
        line = f"{prefix} - {message}" if message else prefix
        level_name = (level or "info").lower()
        if level_name == "warn":
            level_name = "warning"
        log_fn = getattr(logger, level_name, logger.info)
        log_fn(line)


def _configure_logging(level: Optional[int] = None) -> None:
    """Attach a basic console handler unless one is already configured."""
    if level is None:
        level = logging.INFO

    handler = next(
        (h for h in logger.handlers if getattr(h, "name", "") == "taskman-console"), None
    )
    if handler is None:
        handler = logging.StreamHandler()
        handler.name = "taskman-console"
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    handler.setLevel(level)
    logger.setLevel(level)


def start_server(host: str = "0.0.0.0", port: int = 8765) -> None:
    """
    Start the Taskman HTTP server.

    Parameters:
        host: Interface to bind. Defaults to loopback.
        port: TCP port to listen on. Defaults to 8765.
    """
    server_address: Tuple[str, int] = (host, port)
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(server_address, _UIRequestHandler)
    print(f"Taskman server listening on http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        httpd.server_close()


def main() -> None:
    """Console entry: start the server with defaults."""
    parser = argparse.ArgumentParser(description="Run the Taskman UI server.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON config containing DATA_STORE_PATH (and optional LOG_LEVEL)",
    )
    args = parser.parse_args()

    # default logging during startup
    _configure_logging()

    try:
        load_config(args.config)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load config: %s", exc)
        return

    _configure_logging(get_log_level())
    start_server()


if __name__ == "__main__":
    main()
