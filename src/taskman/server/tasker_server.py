"""
Tasker server for the taskman package.

This module provides a lightweight, dependency-free HTTP server and a minimal
frontend for managing projects. Static assets (HTML/CSS/JS) live in
`src/taskman/ui/` and are served directly by this module.

Currently supported routes:
  - GET  /health                                 -> basic health check (JSON)
  - GET  /                                       -> UI index (projects list with add + inline rename)
  - GET  /project.html?name=<name>               -> UI project view (tasks table)
  - GET  /api/projects                           -> list saved project names + current
  - GET  /api/state                              -> current project name
  - GET  /api/projects/<name>/tasks              -> list tasks JSON for a project
  - POST /api/projects/<name>/tasks/update       -> update a single task { index, fields }
  - POST /api/projects/<name>/tasks/create       -> create a new task { optional fields }
  - POST /api/projects/<name>/tasks/delete       -> delete a task { index }
  - POST /api/projects/open                      -> open/create a project { name }
  - POST /api/projects/edit-name                 -> rename project { old_name, new_name }
  - POST /api/exit                               -> graceful shutdown

Usage:
  - Library: start_server(host, port)
  - CLI:     python -m taskman.server.tasker_server
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse

from .project import Project
from .project_manager import ProjectManager

# Module-wide resources
UI_DIR = (Path(__file__).resolve().parent.parent / "ui").resolve()
logger = logging.getLogger(__name__)


class _UIRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for Taskman UI and API.

    - Serves static assets from ``UI_DIR`` (``/`` and other files).
    - Exposes a JSON health check at ``/health``.
    - Implements project/task API endpoints under ``/api/...`` (GET/POST).
    - Validates paths to prevent traversal and dotfile access.
    - Overrides ``log_request`` to emit debug-level access logs via ``log_message``.
    - Uses the module logger for output instead of default stderr logging.
    """

    server_version = "taskman-server/0.1"

    def log_request(self, code='-', size='-') -> None:  # noqa: D401, N802
        """Log an accepted request at debug level."""
        self.log_message('"%s" %s %s', self.requestline, str(code), str(size), level="debug")

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
            cur_obj = getattr(self.server, "current_project", None)
            current = cur_obj.name if isinstance(cur_obj, Project) else None
            return self._json({"projects": projects, "currentProject": current})
        if req_path == "/api/highlights":
            highlights = []
            try:
                projects = ProjectManager.load_project_names()
                for name in projects:
                    proj = Project(name)
                    for t in proj.iter_tasks():
                        if getattr(t, "highlight", False):
                            highlights.append(
                                {
                                    "project": name,
                                    "summary": t.summary,
                                    "assignee": getattr(t, "assignee", "") or "",
                                    "status": getattr(t, "status", None).value if hasattr(t, "status") else "",
                                    "priority": getattr(t, "priority", None).value if hasattr(t, "priority") else "",
                                }
                            )
            except Exception as e:
                return self._json({"error": f"Failed to fetch highlights: {e}"}, 500)
            return self._json({"highlights": highlights})
        if req_path == "/api/state":
            cur_obj = getattr(self.server, "current_project", None)
            current = cur_obj.name if isinstance(cur_obj, Project) else None
            return self._json({"currentProject": current})

        # Project tasks for a given project name
        m_tasks = re.match(r"^/api/projects/([^/]+)/tasks$", req_path)
        if m_tasks:
            name = unquote(m_tasks.group(1))
            # Basic validation; prevent traversal or dotfiles
            if not name or ".." in name or name.startswith("."):
                return self._json({"error": "Invalid project name"}, 400)
            tasks = []
            proj: Optional[Project] = None
            try:
                cur_obj = getattr(self.server, "current_project", None)
                if isinstance(cur_obj, Project) and cur_obj.name.lower() == name.lower():
                    proj = cur_obj
                else:
                    proj = Project(name)
                tasks = [t.to_dict() for t in proj.iter_tasks()]
            except Exception as e:
                # Be forgiving: if file contains unexpected JSON (non-list), return empty list
                self.log_message("Failed loading tasks for project '%s': %r", name, e, level="warning")
                tasks = []
            return self._json({"project": name, "tasks": tasks})

        # Default document
        if req_path in ("", "/"):
            target = UI_DIR / "index.html"
            return self._serve_file(target)

        # Any other page
        clean = req_path.lstrip("/")
        # Prevent directory traversal
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
        path = parsed.path
        if path == "/api/projects/open":
            body = self._read_json()
            if body is None or "name" not in body or not str(body["name"]).strip():
                return self._json({"error": "Missing 'name'"}, 400)
            name = str(body["name"]).strip()
            try:
                # Persist and load
                canonical = ProjectManager.save_project_name(name)
                # Initialize project (creates files/dirs as needed)
                proj = Project(canonical)
                # Remember current project object on server
                setattr(self.server, "current_project", proj)
                return self._json({"ok": True, "currentProject": proj.name})
            except Exception as e:
                return self._json({"error": str(e)}, 500)

        if path == "/api/projects/edit-name":
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
            cur_obj = getattr(self.server, "current_project", None)
            if isinstance(cur_obj, Project) and cur_obj.name.lower() == old.lower():
                # Replace with a fresh Project bound to new name
                setattr(self.server, "current_project", Project(new))
            cur_obj = getattr(self.server, "current_project", None)
            cur_name = cur_obj.name if isinstance(cur_obj, Project) else None
            return self._json({"ok": True, "currentProject": cur_name})

        # Update a single task in a project: POST /api/projects/<name>/tasks/update
        m_update = re.match(r"^/api/projects/(.+)/tasks/update$", path)
        if m_update:
            name = unquote(m_update.group(1))
            if not name or ".." in name or name.startswith(".") or "/" in name:
                # Drain any body to keep connection healthy
                _ = self._read_json()
                return self._json({"error": "Invalid project name"}, 400)
            body = self._read_json()
            if body is None:
                return self._json({"error": "Invalid JSON"}, 400)
            if not isinstance(body, dict):
                return self._json({"error": "Invalid payload"}, 400)
            # Delegate validation and update to Project model
            cur_obj = getattr(self.server, "current_project", None)
            proj = cur_obj if (isinstance(cur_obj, Project) and cur_obj.name.lower() == name.lower()) else Project(name)
            resp, status = proj.update_task_from_payload(body)
            return self._json(resp, status)

        # Highlight or un-highlight a task: POST /api/projects/<name>/tasks/highlight
        m_highlight = re.match(r"^/api/projects/(.+)/tasks/highlight$", path)
        if m_highlight:
            name = unquote(m_highlight.group(1))
            if not name or ".." in name or name.startswith(".") or "/" in name:
                _ = self._read_json()
                return self._json({"error": "Invalid project name"}, 400)
            body = self._read_json()
            if body is None or not isinstance(body, dict):
                return self._json({"error": "Invalid payload"}, 400)
            highlight_val = body.get("highlight")
            if not isinstance(highlight_val, bool):
                return self._json({"error": "Invalid highlight"}, 400)
            try:
                cur_obj = getattr(self.server, "current_project", None)
                proj = cur_obj if (isinstance(cur_obj, Project) and cur_obj.name.lower() == name.lower()) else Project(name)
                resp, status = proj.update_task_from_payload(
                    {"id": body.get("id"), "fields": {"highlight": highlight_val}}
                )
                return self._json(resp, status)
            except Exception as e:
                return self._json({"error": f"Failed to update highlight: {e}"}, 500)

        # Create a new task in a project: POST /api/projects/<name>/tasks/create
        m_create = re.match(r"^/api/projects/(.+)/tasks/create$", path)
        if m_create:
            name = unquote(m_create.group(1))
            if not name or ".." in name or name.startswith(".") or "/" in name:
                _ = self._read_json()  # drain
                return self._json({"error": "Invalid project name"}, 400)
            body = self._read_json()
            if body is None:
                # treat invalid JSON as empty object
                body = {}
            try:
                cur_obj = getattr(self.server, "current_project", None)
                proj = cur_obj if (isinstance(cur_obj, Project) and cur_obj.name.lower() == name.lower()) else Project(name)
                resp, status = proj.create_task_from_payload(body)
                return self._json(resp, status)
            except Exception as e:
                return self._json({"error": f"Failed to create task: {e}"}, 500)

        # Delete a task in a project: POST /api/projects/<name>/tasks/delete
        m_delete = re.match(r"^/api/projects/(.+)/tasks/delete$", path)
        if m_delete:
            name = unquote(m_delete.group(1))
            if not name or ".." in name or name.startswith(".") or "/" in name:
                _ = self._read_json()  # drain
                return self._json({"error": "Invalid project name"}, 400)
            body = self._read_json()
            try:
                cur_obj = getattr(self.server, "current_project", None)
                proj = cur_obj if (isinstance(cur_obj, Project) and cur_obj.name.lower() == name.lower()) else Project(name)
                resp, status = proj.delete_task_from_payload(body)
                return self._json(resp, status)
            except Exception as e:
                return self._json({"error": f"Failed to delete task: {e}"}, 500)

        if path == "/api/exit":
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
        line = f"[UI] {self.address_string()} - {self.requestline}"
        if message:
            line += f" - {message}"
        lvl = (level or "info").lower()
        if lvl == "warn":
            lvl = "warning"
        getattr(logger, lvl, logger.info)(line)


def start_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """
    Start the Taskman HTTP server.

    Parameters:
        host: Interface to bind. Defaults to loopback.
        port: TCP port to listen on. Defaults to 8765.
    """
    server_address: Tuple[str, int] = (host, port)
    httpd = ThreadingHTTPServer(server_address, _UIRequestHandler)
    # Track current project object across requests (in-memory)
    httpd.current_project = None  # type: ignore[attr-defined]
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
    # Configure a simple console handler if none are present so info logs show up
    if not logger.handlers:
        handler = logging.StreamHandler()
        # Let the logger's level control emission; don't filter here
        handler.setLevel(logging.NOTSET)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    start_server()


if __name__ == "__main__":
    main()
