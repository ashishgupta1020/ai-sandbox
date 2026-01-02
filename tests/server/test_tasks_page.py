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
from taskman.server.project_api import ProjectAPI
from taskman.server.task_store import TaskStore
from taskman.server.tasker_server import _UIRequestHandler
from taskman.config import get_data_store_dir, set_data_store_dir


class _ServerThread:
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.server = ThreadingHTTPServer((host, port), _UIRequestHandler)
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
        # Patch storage to temp dir
        self.tmpdir = tempfile.mkdtemp(prefix="taskman-ui-test-")
        self.orig_data_dir = get_data_store_dir()
        set_data_store_dir(Path(self.tmpdir))
        self.db_path = Path(self.tmpdir) / "taskman.db"

        self.srv = _ServerThread()
        self.srv.start()
        (self.host, self.port) = self.srv.address

    def tearDown(self):
        self.srv.stop()
        set_data_store_dir(self.orig_data_dir)
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
        with TaskStore(db_path=self.db_path) as store:
            store.bulk_replace(project, tasks)
        # Also ensure the project is recorded for listing
        ProjectAPI().open_project(project)

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
            conn.execute("CREATE TABLE IF NOT EXISTS tasks (payload TEXT)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, name TEXT, name_lower TEXT)"
            )
            conn.execute(
                "INSERT INTO projects (name, name_lower) VALUES (?, ?)",
                ("Bravo", "bravo"),
            )
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

    def test_project_tags_roundtrip(self):
        name = "Taggy"
        resp, body = self._get(f"/api/projects/{name}/tags")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tags"], [])

        resp, body = self._post(f"/api/projects/{name}/tags/add", {"tags": ["alpha"]})
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tags"], ["alpha"])

        resp, body = self._post(f"/api/projects/{name}/tags/add", {"tags": ["beta", "gamma"]})
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tags"], ["alpha", "beta", "gamma"])

        resp, body = self._post(f"/api/projects/{name}/tags/remove", {"tag": "beta"})
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tags"], ["alpha", "gamma"])

        resp, body = self._get(f"/api/projects/{name}/tags")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data["tags"], ["alpha", "gamma"])

    def test_project_tags_bulk_endpoint(self):
        self._post("/api/projects/Alpha/tags/add", {"tags": ["one", "two"]})
        self._post("/api/projects/Beta/tags/add", {"tags": ["z"]})
        # Project without tags still appears with an empty list
        ProjectAPI().open_project("Gamma")

        resp, body = self._get("/api/project-tags")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        tags_by_project = data.get("tagsByProject") or {}
        self.assertEqual(tags_by_project.get("Alpha"), ["one", "two"])
        self.assertEqual(tags_by_project.get("Beta"), ["z"])
        self.assertIn("Gamma", tags_by_project)
        self.assertEqual(tags_by_project.get("Gamma"), [])

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
        original = tasker_server._task_api.update_task
        try:
            tasker_server._task_api.update_task = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom highlight"))
            resp, body = self._post("/api/projects/demo/tasks/highlight", {"id": 1, "highlight": True})
            self.assertEqual(resp.status, 500)
            data = json.loads(body)
            self.assertIn("Failed to update highlight", data.get("error", ""))
        finally:
            tasker_server._task_api.update_task = original

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
            self.assertIn("id", h)
            self.assertIn("assignee", h)
            self.assertIn("status", h)
            self.assertIn("priority", h)

    def test_update_task_invalid_name(self):
        resp, _ = self._post("/api/projects/../etc/tasks/update", {"id": 0, "fields": {"summary": "X"}})
        self.assertEqual(resp.status, 400)

    def test_assignees_endpoint(self):
        self._seed_tasks(
            "Alpha",
            [
                {"task_id": 0, "summary": "S1", "assignee": "Alice", "remarks": "", "status": "Not Started", "priority": "Low"},
                {"task_id": 1, "summary": "S2", "assignee": "alice", "remarks": "", "status": "Completed", "priority": "High"},
                {"task_id": 2, "summary": "S3", "assignee": "", "remarks": "", "status": "Completed", "priority": "High"},
            ],
        )
        self._seed_tasks(
            "Beta",
            [
                {"task_id": 0, "summary": "B1", "assignee": "Bob", "remarks": "", "status": "In Progress", "priority": "Medium"},
            ],
        )

        resp, body = self._get("/api/assignees")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual(data.get("assignees"), ["Alice", "Bob"])

    def test_tasks_endpoint_cross_project_and_filter(self):
        self._seed_tasks(
            "Alpha",
            [
                {"task_id": 0, "summary": "S1", "assignee": "Alice", "remarks": "", "status": "Not Started", "priority": "Low"},
                {"task_id": 1, "summary": "S2", "assignee": "Bob", "remarks": "", "status": "Completed", "priority": "High"},
            ],
        )
        self._seed_tasks(
            "Beta",
            [
                {"task_id": 0, "summary": "B1", "assignee": "Alice", "remarks": "", "status": "In Progress", "priority": "Medium"},
            ],
        )

        resp, body = self._get("/api/tasks")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        tasks = data.get("tasks") or []
        self.assertEqual(len(tasks), 3)
        projects_seen = {t["project"] for t in tasks}
        self.assertEqual(projects_seen, {"Alpha", "Beta"})
        for t in tasks:
            self.assertIn("id", t)

        resp_filt, body_filt = self._get("/api/tasks?assignee=alice")
        self.assertEqual(resp_filt.status, 200)
        data_filt = json.loads(body_filt)
        filt_tasks = data_filt.get("tasks") or []
        self.assertEqual(len(filt_tasks), 2)
        for t in filt_tasks:
            self.assertEqual(t["assignee"], "Alice")
            self.assertIn("id", t)

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
        original = tasker_server._task_api.create_task
        try:
            tasker_server._task_api.create_task = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom create"))
            resp, body = self._post("/api/projects/demo/tasks/create", {"summary": "X"})
            self.assertEqual(resp.status, 500)
            data = json.loads(body)
            self.assertIn("Failed to create task", data.get("error", ""))
        finally:
            tasker_server._task_api.create_task = original

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
        original = tasker_server._task_api.delete_task
        try:
            tasker_server._task_api.delete_task = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom delete"))
            resp, body = self._post("/api/projects/demo/tasks/delete", {"id": 1})
            self.assertEqual(resp.status, 500)
            data = json.loads(body)
            self.assertIn("Failed to delete task", data.get("error", ""))
        finally:
            tasker_server._task_api.delete_task = original
