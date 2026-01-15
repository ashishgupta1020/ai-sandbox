"""
Tests for tasker_server.py - HTTP server infrastructure.

This file tests:
- Server lifecycle (start_server, graceful shutdown)
- Static file serving (HTML, CSS, JS, hashed assets)
- Security (path traversal, symlinks, forbidden paths)
- Request handling edge cases (unknown endpoints, invalid JSON)
- API endpoint wiring (verifies each endpoint calls its handler and returns JSON)

For route handler unit tests, see test_route_handlers.py.
"""

import hashlib
import http.client
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path

from http.server import ThreadingHTTPServer

from taskman.config import get_data_store_dir, set_data_store_dir
from taskman.server.asset_manifest import ASSET_CACHE_CONTROL
from taskman.server.tasker_server import UI_DIR, _UIRequestHandler, start_server


class _ServerThread:
    """Run ThreadingHTTPServer in a background thread for tests."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.server = ThreadingHTTPServer((host, port), _UIRequestHandler)
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.1}
        )
        self.thread.daemon = True

    @property
    def address(self):
        return self.server.server_address

    def start(self):
        self.thread.start()
        time.sleep(0.05)

    def stop(self):
        try:
            self.server.shutdown()
        finally:
            self.server.server_close()
            self.thread.join(timeout=2)


def _pick_free_port(host: str = "127.0.0.1") -> int:
    """Find an available port for testing."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind((host, 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class TestServerLifecycle(unittest.TestCase):
    """Tests for server startup and shutdown."""

    def test_start_server_and_graceful_exit(self):
        """Server starts, responds to health check, and shuts down gracefully."""
        host = "127.0.0.1"
        port = _pick_free_port(host)

        t = threading.Thread(target=start_server, kwargs={"host": host, "port": port})
        t.daemon = True
        t.start()

        # Wait for the server to come up
        deadline = time.time() + 3.0
        connected = False
        while time.time() < deadline:
            try:
                with closing(http.client.HTTPConnection(host, port, timeout=0.25)) as conn:
                    conn.request("GET", "/health")
                    resp = conn.getresponse()
                    resp.read()
                    if resp.status == 200:
                        connected = True
                        break
            except Exception:
                time.sleep(0.05)
        self.assertTrue(connected, "Server did not start in time")

        # Ask it to exit gracefully
        with closing(http.client.HTTPConnection(host, port, timeout=1)) as conn:
            conn.request(
                "POST",
                "/api/exit",
                body=b"{}",
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)

        # Server thread should exit shortly
        t.join(timeout=2)
        self.assertFalse(t.is_alive(), "Server thread did not stop")

    def test_exit_endpoint_via_handler(self):
        """Exit endpoint returns 200 and triggers shutdown."""
        srv = _ServerThread()
        srv.start()
        host, port = srv.address

        with closing(http.client.HTTPConnection(host, port, timeout=2)) as conn:
            conn.request(
                "POST",
                "/api/exit",
                body=b"{}",
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)

        time.sleep(0.2)
        srv.stop()


class TestStaticFileServing(unittest.TestCase):
    """Tests for static file serving."""

    def setUp(self):
        self.srv = _ServerThread()
        self.srv.start()
        self.host, self.port = self.srv.address

    def tearDown(self):
        self.srv.stop()

    def _get(self, path: str):
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("GET", path)
            resp = conn.getresponse()
            body = resp.read()
            return resp, body

    def test_health_endpoint(self):
        """Health check returns JSON with ok status."""
        resp, body = self._get("/health")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "application/json; charset=utf-8")
        self.assertIn(b'"status"', body)
        self.assertIn(b'"ok"', body)

    def test_root_serves_index_html(self):
        """Root path serves index.html."""
        resp, body = self._get("/")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.getheader("Content-Type", "").startswith("text/html"))
        self.assertTrue(len(body) > 0)

    def test_static_css_served(self):
        """CSS files are served with correct content type."""
        resp, body = self._get("/styles/base.css")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.getheader("Content-Type", "").startswith("text/css"))
        self.assertTrue(len(body) > 0)

    def test_html_rewrites_hashed_assets(self):
        """HTML files have asset URLs rewritten to hashed versions."""
        resp, body = self._get("/")
        self.assertEqual(resp.status, 200)
        html = body.decode("utf-8", errors="ignore")

        # Compute expected hashed name
        src = (UI_DIR / "styles/base.css").read_bytes()
        digest = hashlib.sha256(src).hexdigest()[:8]
        hashed = f"styles/base.{digest}.css"

        self.assertIn(f"/{hashed}", html)

        # Hashed asset should be served with long cache headers
        resp, body = self._get(f"/{hashed}")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.getheader("Content-Type", "").startswith("text/css"))
        self.assertEqual(resp.getheader("Cache-Control"), ASSET_CACHE_CONTROL)
        self.assertTrue(len(body) > 0)

    def test_404_for_missing_file(self):
        """Missing files return 404."""
        resp, body = self._get("/no-such-file.txt")
        self.assertEqual(resp.status, 404)

    def test_unknown_extension_served_as_octet_stream(self):
        """Files with unknown extensions are served as application/octet-stream."""
        fname = UI_DIR / "__blob.unknownext__"
        try:
            with open(fname, "wb") as f:
                f.write(b"\x00\x01\x02\x03test")
            resp, body = self._get(f"/{fname.name}")
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.getheader("Content-Type"), "application/octet-stream")
            self.assertGreater(len(body), 0)
        finally:
            if os.path.exists(fname):
                os.remove(fname)


class TestSecurityAndEdgeCases(unittest.TestCase):
    """Tests for security measures and edge cases."""

    def setUp(self):
        self.srv = _ServerThread()
        self.srv.start()
        self.host, self.port = self.srv.address

    def tearDown(self):
        self.srv.stop()

    def _get(self, path: str):
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("GET", path)
            resp = conn.getresponse()
            body = resp.read()
            return resp, body

    def test_blocks_path_traversal(self):
        """Path traversal attempts return 404."""
        resp, body = self._get("/../../etc/passwd")
        self.assertEqual(resp.status, 404)

    def test_blocks_dotfiles(self):
        """Dotfile paths return 404."""
        resp, body = self._get("/.hidden")
        self.assertEqual(resp.status, 404)

    def test_forbidden_outside_root_via_symlink(self):
        """Symlinks pointing outside UI_DIR return 403."""
        outside_fd, outside_path = tempfile.mkstemp()
        os.close(outside_fd)
        link_name = UI_DIR / "__test_symlink_outside__"
        try:
            try:
                os.symlink(outside_path, link_name)
            except (OSError, NotImplementedError):
                self.skipTest("symlink not supported")
            resp, body = self._get(f"/{link_name.name}")
            self.assertEqual(resp.status, 403)
        finally:
            try:
                if os.path.islink(link_name):
                    os.unlink(link_name)
            finally:
                if os.path.exists(outside_path):
                    os.remove(outside_path)

    def test_unknown_post_endpoint_returns_404(self):
        """Unknown POST endpoints return 404."""
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request(
                "POST",
                "/api/does-not-exist",
                body=b"{}",
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            # Avoid reading body to reduce race with server lifecycles
            self.assertEqual(resp.status, 404)

    def test_invalid_content_length_returns_400(self):
        """Invalid Content-Length header returns 400."""
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.putrequest("POST", "/api/projects/open")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", "notanint")
            conn.endheaders()
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 400)

    def test_invalid_json_returns_400(self):
        """Invalid JSON body returns 400."""
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request(
                "POST",
                "/api/projects/delete",
                body=b"not json",
                headers={"Content-Type": "application/json", "Content-Length": "8"},
            )
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 400)


# API endpoint -> handler name mapping
# Format: (method, path, handler_name, sample_body_for_post)
API_ENDPOINT_HANDLERS = [
    # Simple GET endpoints
    ("GET", "/api/projects", "handle_list_projects", None),
    ("GET", "/api/project-tags", "handle_project_tags", None),
    ("GET", "/api/assignees", "handle_assignees", None),
    ("GET", "/api/tasks", "handle_tasks_list", None),
    ("GET", "/api/highlights", "handle_highlights", None),
    ("GET", "/api/todo", "handle_todo_list", None),
    ("GET", "/api/todo/archive", "handle_todo_archive", None),
    # Pattern-matched GET endpoints
    ("GET", "/api/projects/TestProject/tasks", "handle_project_tasks", None),
    ("GET", "/api/projects/TestProject/tags", "handle_get_project_tags", None),
    # Simple POST endpoints
    ("POST", "/api/projects/open", "handle_open_project", {"name": "Test"}),
    ("POST", "/api/projects/edit-name", "handle_edit_project_name", {"old_name": "A", "new_name": "B"}),
    ("POST", "/api/projects/delete", "handle_delete_project", {"name": "Test"}),
    ("POST", "/api/todo/add", "handle_todo_add", {"title": "Test"}),
    ("POST", "/api/todo/mark", "handle_todo_mark", {"id": 1, "done": True}),
    ("POST", "/api/todo/edit", "handle_todo_edit", {"id": 1, "title": "New"}),
    # Pattern-matched POST endpoints
    ("POST", "/api/projects/Test/tasks/update", "handle_update_task", {"id": 0, "fields": {}}),
    ("POST", "/api/projects/Test/tags/add", "handle_add_project_tags", {"tags": ["a"]}),
    ("POST", "/api/projects/Test/tags/remove", "handle_remove_project_tag", {"tag": "a"}),
    ("POST", "/api/projects/Test/tasks/highlight", "handle_highlight_task", {"id": 0, "highlight": True}),
    ("POST", "/api/projects/Test/tasks/create", "handle_create_task", {}),
    ("POST", "/api/projects/Test/tasks/delete", "handle_delete_task", {"id": 0}),
]


class TestAPIEndpointRouting(unittest.TestCase):
    """Verify API endpoints call the correct route handlers."""

    def setUp(self):
        self.srv = _ServerThread()
        self.srv.start()
        self.host, self.port = self.srv.address

    def tearDown(self):
        self.srv.stop()

    def test_all_endpoints_call_correct_handlers(self):
        """Each API endpoint calls its corresponding route handler."""
        from unittest.mock import patch
        from taskman.server import route_handlers

        for method, path, handler_name, body in API_ENDPOINT_HANDLERS:
            with self.subTest(endpoint=f"{method} {path}"):
                marker = {"_handler": handler_name}
                with patch.object(route_handlers, handler_name, return_value=(marker, 200)) as mock:
                    with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
                        if method == "GET":
                            conn.request("GET", path)
                        else:
                            data = json.dumps(body).encode("utf-8")
                            headers = {"Content-Type": "application/json", "Content-Length": str(len(data))}
                            conn.request("POST", path, body=data, headers=headers)
                        resp = conn.getresponse()
                        resp_body = json.loads(resp.read())

                    self.assertEqual(resp.status, 200, f"Expected 200 for {method} {path}")
                    self.assertEqual(resp_body["_handler"], handler_name)
                    mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
