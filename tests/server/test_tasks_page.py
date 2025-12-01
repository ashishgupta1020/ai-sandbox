import http.client
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path

from http.server import ThreadingHTTPServer
from taskman.server import tasker_server
from taskman.server.project_manager import ProjectManager
from taskman.server.sqlite_storage import ProjectTaskSession
from taskman.server.tasker_server import _UIRequestHandler


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
        self.orig_project_cls = tasker_server.Project
        ProjectManager.PROJECTS_DIR = self.tmpdir
        ProjectManager.PROJECTS_FILE = os.path.join(self.tmpdir, "projects.json")
        self.db_path = Path(self.tmpdir) / "taskman.db"

        self.srv = _ServerThread()
        self.srv.start()
        (self.host, self.port) = self.srv.address

    def tearDown(self):
        self.srv.stop()
        tasker_server.Project = self.orig_project_cls
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

    def _seed_tasks(self, project: str, tasks: list[dict]):
        with ProjectTaskSession(project, db_path=self.db_path) as store:
            store.bulk_replace(project, tasks)
        # Also ensure the project is recorded for load_project_names()
        ProjectManager.save_project_name(project)

    def _restart_with_project_stub(self, project_cls):
        """Restart the server using a patched Project class."""
        self.srv.stop()
        tasker_server.Project = project_cls
        self.srv = _ServerThread()
        self.srv.start()
        (self.host, self.port) = self.srv.address

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
        self._seed_tasks(
            "Alpha",
            [
                {"task_id": 0, "summary": "S1", "assignee": "A1", "remarks": "R1", "status": "Not Started", "priority": "Low"},
                {"task_id": 1, "summary": "S2", "assignee": "A2", "remarks": "R2", "status": "Completed", "priority": "High"},
            ],
        )
        resp, body = self._get("/api/projects/Alpha/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(len(data["tasks"]), 2)
        self.assertEqual(data["tasks"][0]["summary"], "S1")

    def test_tasks_endpoint_non_list_json(self):
        # Corrupt the tasks schema to simulate unreadable storage
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS tasks_bravo (payload TEXT)")
            conn.execute("INSERT INTO tasks_bravo (payload) VALUES ('oops')")
        resp, body = self._get("/api/projects/Bravo/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tasks"], [])

    def test_tasks_endpoint_malformed_json(self):
        # Seed a row with invalid enum values so loading fails gracefully
        self._seed_tasks(
            "Charlie",
            [
                {"task_id": 0, "summary": "Bad", "assignee": "A", "remarks": "", "status": "???", "priority": "Low"},
            ],
        )
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
        self._seed_tasks(name, [])
        resp, body = self._get("/api/projects/Alpha%20Beta/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["project"], name)

    def test_update_task_summary(self):
        name = "Delta"
        self._seed_tasks(
            name,
            [
                {"task_id": 0, "summary": "Old", "assignee": "A", "remarks": "R", "status": "Not Started", "priority": "Low"},
            ],
        )
        resp, body = self._post(f"/api/projects/{name}/tasks/update", {"id": 0, "fields": {"summary": "New"}})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj.get("ok"))
        self.assertEqual(obj.get("id"), 0)
        self.assertEqual(obj["task"]["summary"], "New")
        # Verify persisted
        resp2, body2 = self._get(f"/api/projects/{name}/tasks")
        self.assertEqual(resp2.status, 200)
        data = json.loads(body2)
        self.assertEqual(data["tasks"][0]["summary"], "New")

    def test_update_task_highlight(self):
        name = "Echo"
        self._seed_tasks(
            name,
            [
                {"task_id": 0, "summary": "Old", "assignee": "A", "remarks": "R", "status": "Not Started", "priority": "Low", "highlight": False},
            ],
        )
        resp, body = self._post(f"/api/projects/{name}/tasks/highlight", {"id": 0, "highlight": True})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj.get("ok"))
        self.assertTrue(obj["task"]["highlight"])
        # Verify persisted
        resp2, body2 = self._get(f"/api/projects/{name}/tasks")
        self.assertEqual(resp2.status, 200)
        data = json.loads(body2)
        self.assertTrue(data["tasks"][0]["highlight"])

    def test_update_task_highlight_exception_returns_500(self):
        class ExplodingProject(self.orig_project_cls):
            def __init__(self, name: str):
                self.name = name

            def update_task_from_payload(self, payload):
                raise RuntimeError("boom highlight")

        self._restart_with_project_stub(ExplodingProject)
        resp, body = self._post("/api/projects/demo/tasks/highlight", {"id": 1, "highlight": True})
        self.assertEqual(resp.status, 500)
        data = json.loads(body)
        self.assertIn("Failed to update highlight", data.get("error", ""))

    def test_highlights_endpoint(self):
        alpha = "Alpha"
        bravo = "Bravo"
        self._seed_tasks(
            alpha,
            [
                {"task_id": 0, "summary": "S1", "assignee": "A1", "remarks": "", "status": "Not Started", "priority": "Low", "highlight": True},
                {"task_id": 1, "summary": "S2", "assignee": "A2", "remarks": "", "status": "Completed", "priority": "High", "highlight": False},
            ],
        )
        self._seed_tasks(
            bravo,
            [
                {"task_id": 0, "summary": "B1", "assignee": "B1", "remarks": "", "status": "In Progress", "priority": "Medium", "highlight": True},
            ],
        )
        resp, body = self._get("/api/highlights")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        highlights = data.get("highlights") or []
        self.assertEqual(len(highlights), 2)
        projects = {h["project"] for h in highlights}
        self.assertEqual(projects, {alpha, bravo})
        summary_set = {h["summary"] for h in highlights}
        self.assertIn("S1", summary_set)
        self.assertIn("B1", summary_set)
        # Verify fields are present
        for h in highlights:
            self.assertIn("assignee", h)
            self.assertIn("status", h)
            self.assertIn("priority", h)

    def test_update_task_invalid_name(self):
        resp, _ = self._post("/api/projects/../etc/tasks/update", {"id": 0, "fields": {"summary": "X"}})
        self.assertEqual(resp.status, 400)

    # ----- Tests for /api/projects/<name>/tasks/create -----
    def test_create_task_defaults(self):
        name = "Hotel"
        # Create with empty payload; expect defaults and persistence
        resp, body = self._post(f"/api/projects/{name}/tasks/create", {})
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("ok"))
        # Backend now returns task id instead of index
        self.assertIn("id", data)
        self.assertEqual(data["id"], 0)
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

    def test_create_task_exception_returns_500(self):
        class ExplodingProject(self.orig_project_cls):
            def __init__(self, name: str):
                self.name = name

            def create_task_from_payload(self, payload):
                raise RuntimeError("boom create")

        self._restart_with_project_stub(ExplodingProject)
        resp, body = self._post("/api/projects/demo/tasks/create", {"summary": "X"})
        self.assertEqual(resp.status, 500)
        data = json.loads(body)
        self.assertIn("Failed to create task", data.get("error", ""))

    # ----- Tests for /api/projects/<name>/tasks/delete -----
    def test_delete_task_success(self):
        name = "Kilo"
        # Seed tasks in the SQLite backend
        self._seed_tasks(
            name,
            [
                {"task_id": 0, "summary": "S1", "assignee": "A1", "remarks": "R1", "status": "Not Started", "priority": "Low"},
                {"task_id": 1, "summary": "S2", "assignee": "A2", "remarks": "R2", "status": "Completed", "priority": "High"},
            ],
        )
        resp, body = self._post(f"/api/projects/{name}/tasks/delete", {"id": 0})
        self.assertEqual(resp.status, 200)
        obj = json.loads(body)
        self.assertTrue(obj.get("ok"))
        self.assertEqual(obj.get("id"), 0)
        # Verify one left and it's S2
        resp2, body2 = self._get(f"/api/projects/{name}/tasks")
        self.assertEqual(resp2.status, 200)
        listing = json.loads(body2)
        self.assertEqual(len(listing["tasks"]), 1)
        self.assertEqual(listing["tasks"][0]["summary"], "S2")

    def test_delete_task_invalid_name(self):
        resp, _ = self._post("/api/projects/.hidden/tasks/delete", {"id": 0})
        self.assertEqual(resp.status, 400)
        resp2, _ = self._post("/api/projects/../etc/tasks/delete", {"id": 0})
        self.assertEqual(resp2.status, 400)

    def test_delete_task_exception_returns_500(self):
        class ExplodingProject(self.orig_project_cls):
            def __init__(self, name: str):
                self.name = name

            def delete_task_from_payload(self, payload):
                raise RuntimeError("boom delete")

        self._restart_with_project_stub(ExplodingProject)
        resp, body = self._post("/api/projects/demo/tasks/delete", {"id": 1})
        self.assertEqual(resp.status, 500)
        data = json.loads(body)
        self.assertIn("Failed to delete task", data.get("error", ""))
