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
from taskman.tasker_ui import _UIRequestHandler
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


class TestTasksPageAPI(unittest.TestCase):
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

    # ----- Tests for /api/projects/<name>/tasks -----
    def test_tasks_endpoint_empty(self):
        # No task file created yet
        resp, body = self._get("/api/projects/Alpha/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["project"], "Alpha")
        self.assertEqual(data["tasks"], [])

    def test_tasks_endpoint_with_tasks(self):
        # Create a valid tasks list
        path = ProjectManager.get_task_file_path("Alpha")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tasks = [
            {"summary": "S1", "assignee": "A1", "remarks": "R1", "status": "Not Started", "priority": "Low"},
            {"summary": "S2", "assignee": "A2", "remarks": "R2", "status": "Completed", "priority": "High"},
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f)
        resp, body = self._get("/api/projects/Alpha/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(len(data["tasks"]), 2)
        self.assertEqual(data["tasks"][0]["summary"], "S1")

    def test_tasks_endpoint_non_list_json(self):
        # Write a dict instead of list
        path = ProjectManager.get_task_file_path("Bravo")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"oops": True}, f)
        resp, body = self._get("/api/projects/Bravo/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tasks"], [])

    def test_tasks_endpoint_malformed_json(self):
        path = ProjectManager.get_task_file_path("Charlie")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not valid json}")
        resp, body = self._get("/api/projects/Charlie/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tasks"], [])

    def test_tasks_endpoint_invalid_names(self):
        # Traversal-like
        resp, _ = self._get("/api/projects/../etc/tasks")
        self.assertEqual(resp.status, 400)
        # Leading dot
        resp, _ = self._get("/api/projects/.hidden/tasks")
        self.assertEqual(resp.status, 400)

    def test_tasks_endpoint_url_decoding(self):
        name = "Alpha Beta"
        path = ProjectManager.get_task_file_path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
        resp, body = self._get("/api/projects/Alpha%20Beta/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["project"], name)

