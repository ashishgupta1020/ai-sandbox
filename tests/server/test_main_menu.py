import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import http.client
from contextlib import closing

from http.server import ThreadingHTTPServer
from taskman.tasker_server import _UIRequestHandler, UI_DIR
from taskman.project_manager import ProjectManager


class _ServerThread:
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.server = ThreadingHTTPServer((host, port), _UIRequestHandler)
        self.server.current_project_name = None  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1})
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


class TestMainMenuAPI(unittest.TestCase):
    def setUp(self):
        # Patch ProjectManager storage to temp dir
        self.tmpdir = tempfile.mkdtemp(prefix="taskman-ui-test-")
        self.orig_dir = ProjectManager.PROJECTS_DIR
        self.orig_file = ProjectManager.PROJECTS_FILE
        ProjectManager.PROJECTS_DIR = self.tmpdir
        ProjectManager.PROJECTS_FILE = os.path.join(self.tmpdir, "projects.json")

        self.srv = _ServerThread()
        self.srv.start()
        (self.host, self.port) = self.srv.address

    def tearDown(self):
        self.srv.stop()
        ProjectManager.PROJECTS_DIR = self.orig_dir
        ProjectManager.PROJECTS_FILE = self.orig_file
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _get(self, path: str):
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("GET", path)
            resp = conn.getresponse()
            body = resp.read()
            return resp, body

    def _post(self, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Content-Length": str(len(data))}
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("POST", path, body=data, headers=headers)
            resp = conn.getresponse()
            body = resp.read()
            return resp, body

    def test_state_endpoint_initially_none(self):
        resp, body = self._get("/api/state")
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertIsNone(obj.get("currentProject"))

    def test_list_projects_initially_empty(self):
        resp, body = self._get("/api/projects")
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertEqual(obj["projects"], [])
        self.assertIsNone(obj["currentProject"])

    def test_open_project_and_edit_name(self):
        # Open a project
        resp, body = self._post("/api/projects/open", {"name": "Alpha"})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["currentProject"], "Alpha")

        # Verify listing shows it
        resp, body = self._get("/api/projects")
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertEqual(obj["projects"], ["Alpha"])
        self.assertEqual(obj["currentProject"], "Alpha")

        # Edit name
        resp, body = self._post("/api/projects/edit-name", {"old_name": "Alpha", "new_name": "Beta"})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj["ok"])
        self.assertEqual(obj["currentProject"], "Beta")

        # List reflects rename
        resp, body = self._get("/api/projects")
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertEqual(obj["projects"], ["Beta"])

    def test_open_missing_name_variants(self):
        # Empty body (length 0) -> {} -> missing name
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("POST", "/api/projects/open", body=b"", headers={"Content-Type": "application/json", "Content-Length": "0"})
            resp = conn.getresponse()
            _ = resp.read()
            self.assertEqual(resp.status, 400)
        # Invalid Content-Length (non-integer) -> ValueError -> None
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.putrequest("POST", "/api/projects/open")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", "notanint")
            conn.endheaders()
            resp = conn.getresponse()
            _ = resp.read()
            self.assertEqual(resp.status, 400)

    def test_edit_name_missing_params_and_failure(self):
        # Missing params
        resp, body = self._post("/api/projects/edit-name", {"old_name": "", "new_name": ""})
        self.assertEqual(resp.status, 400)
        # Failure path when old_name does not exist
        resp, body = self._post("/api/projects/edit-name", {"old_name": "NoSuch", "new_name": "X"})
        self.assertEqual(resp.status, 400)
        obj = json.loads(body)
        self.assertFalse(obj.get("ok", True))

    def test_edit_name_same_name_is_ok(self):
        # Open a project then rename to the same name; should succeed (no-op)
        resp, body = self._post("/api/projects/open", {"name": "Alpha"})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj["ok"]) 
        self.assertEqual(obj["currentProject"], "Alpha")
        # Rename to same
        resp, body = self._post("/api/projects/edit-name", {"old_name": "Alpha", "new_name": "Alpha"})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj["ok"]) 
        self.assertEqual(obj["currentProject"], "Alpha")
        # List remains unchanged
        resp, body = self._get("/api/projects")
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertEqual(obj["projects"], ["Alpha"])

    def test_unknown_mutation_endpoint(self):
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("POST", "/api/does-not-exist", body=b"{}", headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            # Avoid reading body to reduce race with server lifecycles
            self.assertEqual(resp.status, 404)

    def test_forbidden_outside_root_via_symlink(self):
        # Create a symlink inside UI_DIR pointing outside; request should be 403
        import os, tempfile
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

    def test_unknown_extension_served_as_octet_stream(self):
        # Create a file with an unknown extension; should be served as application/octet-stream
        import os
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

    # (moved) tests for /api/projects/<name>/tasks are in tests/server/test_tasks_page.py

    def test_exit_endpoint(self):
        # Make a separate server just for exit test to avoid tearing down main instance mid-run
        srv2 = _ServerThread()
        srv2.start()
        host, port = srv2.address
        with closing(http.client.HTTPConnection(host, port, timeout=2)) as conn:
            conn.request("POST", "/api/exit", body=b"{}", headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
        # Allow time for shutdown
        time.sleep(0.2)
        srv2.stop()


if __name__ == "__main__":
    unittest.main()
