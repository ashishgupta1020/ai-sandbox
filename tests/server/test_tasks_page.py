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
from taskman.tasker_server import _UIRequestHandler
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

    def _post(self, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Content-Length": str(len(data))}
        with closing(http.client.HTTPConnection(self.host, self.port, timeout=2)) as conn:
            conn.request("POST", path, body=data, headers=headers)
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

    def test_update_task_summary(self):
        name = "Delta"
        path = ProjectManager.get_task_file_path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tasks = [{"summary": "Old", "assignee": "A", "remarks": "R", "status": "Not Started", "priority": "Low"}]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f)
        resp, body = self._post(f"/api/projects/{name}/tasks/update", {"index": 0, "fields": {"summary": "New"}})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj.get("ok"))
        self.assertEqual(obj["task"]["summary"], "New")
        # Verify persisted
        resp2, body2 = self._get(f"/api/projects/{name}/tasks")
        self.assertEqual(resp2.status, 200)
        data = json.loads(body2)
        self.assertEqual(data["tasks"][0]["summary"], "New")

    def test_update_task_invalid_name(self):
        resp, _ = self._post("/api/projects/../etc/tasks/update", {"index": 0, "fields": {"summary": "X"}})
        self.assertEqual(resp.status, 400)

    # ----- Tests for /api/projects/<name>/tasks/create -----
    def test_create_task_defaults(self):
        name = "Hotel"
        # Create with empty payload; expect defaults and persistence
        resp, body = self._post(f"/api/projects/{name}/tasks/create", {})
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("ok"))
        self.assertEqual(data["index"], 0)
        # Verify via GET
        resp2, body2 = self._get(f"/api/projects/{name}/tasks")
        self.assertEqual(resp2.status, 200)
        listing = json.loads(body2)
        self.assertEqual(len(listing["tasks"]), 1)
        t = listing["tasks"][0]
        self.assertEqual(t["summary"], "")
        self.assertEqual(t["assignee"], "")
        self.assertEqual(t["remarks"], "")
        self.assertEqual(t["status"], "Not Started")
        self.assertEqual(t["priority"], "Medium")


    def test_create_task_invalid_name(self):
        resp, _ = self._post("/api/projects/.hidden/tasks/create", {})
        self.assertEqual(resp.status, 400)
        resp2, _ = self._post("/api/projects/../etc/tasks/create", {})
        self.assertEqual(resp2.status, 400)

    # ----- Tests for /api/projects/<name>/tasks/delete -----
    def test_delete_task_success(self):
        name = "Kilo"
        # Seed task file
        path = ProjectManager.get_task_file_path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tasks = [
            {"summary": "S1", "assignee": "A1", "remarks": "R1", "status": "Not Started", "priority": "Low"},
            {"summary": "S2", "assignee": "A2", "remarks": "R2", "status": "Completed", "priority": "High"},
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f)
        resp, body = self._post(f"/api/projects/{name}/tasks/delete", {"index": 0})
        self.assertEqual(resp.status, 200)
        # Verify one left and it's S2
        resp2, body2 = self._get(f"/api/projects/{name}/tasks")
        self.assertEqual(resp2.status, 200)
        listing = json.loads(body2)
        self.assertEqual(len(listing["tasks"]), 1)
        self.assertEqual(listing["tasks"][0]["summary"], "S2")

    def test_delete_task_invalid_name(self):
        resp, _ = self._post("/api/projects/.hidden/tasks/delete", {"index": 0})
        self.assertEqual(resp.status, 400)
        resp2, _ = self._post("/api/projects/../etc/tasks/delete", {"index": 0})
        self.assertEqual(resp2.status, 400)
