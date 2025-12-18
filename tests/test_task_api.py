import shutil
import tempfile
import unittest
from pathlib import Path

from taskman.config import get_data_store_dir, set_data_store_dir
from taskman.server.task_api import TaskAPI
from taskman.server.task import TaskPriority, TaskStatus


class _DummyStore:
    def __init__(self, **kwargs):
        self.fetch_all_response = kwargs.get("fetch_all_response", [])
        self.fetch_task_response = kwargs.get("fetch_task_response")
        self.next_id = kwargs.get("next_id", 0)
        self.upsert_raises = kwargs.get("upsert_raises", False)
        self.delete_raises = kwargs.get("delete_raises", False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def fetch_all(self, project_name: str):
        if isinstance(self.fetch_all_response, Exception):
            raise self.fetch_all_response
        return list(self.fetch_all_response)

    def fetch_task(self, project_name: str, task_id: int):
        if isinstance(self.fetch_task_response, Exception):
            raise self.fetch_task_response
        return self.fetch_task_response

    def next_task_id(self, project_name: str) -> int:
        return self.next_id

    def upsert_task(self, project_name: str, row: dict):
        if self.upsert_raises:
            raise RuntimeError("upsert boom")
        self.last_upsert = row

    def delete_task(self, project_name: str, task_id: int):
        if self.delete_raises:
            raise RuntimeError("delete boom")


class TestTaskAPI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="taskman-task-api-"))
        self.orig_data_dir = get_data_store_dir()
        set_data_store_dir(self.tmpdir)

    def tearDown(self):
        set_data_store_dir(self.orig_data_dir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_tasks_logs_and_returns_empty_on_error(self):
        store = _DummyStore(fetch_all_response=RuntimeError("db down"))
        api = TaskAPI(store_factory=lambda: store)
        logs = []
        payload, status = api.list_tasks("Alpha", log_warning=lambda msg: logs.append(msg))
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("tasks"), [])
        self.assertTrue(logs)

    def test_update_task_validation_errors(self):
        api = TaskAPI()
        self.assertEqual(api.update_task("..", {} )[1], 400)
        self.assertEqual(api.update_task("Alpha", "bad")[1], 400)
        self.assertEqual(api.update_task("Alpha", {"id": "x", "fields": {}})[1], 400)
        self.assertEqual(api.update_task("Alpha", {"id": 1, "fields": {}})[1], 400)
        self.assertEqual(api.update_task("Alpha", {"id": 1, "fields": {"oops": 1}})[1], 400)

    def test_update_task_invalid_status_and_priority(self):
        store = _DummyStore(fetch_task_response={"task_id": 1, "summary": "S", "assignee": "", "remarks": "", "status": "Not Started", "priority": "Low", "highlight": False})
        api = TaskAPI(store_factory=lambda: store)
        resp_status_invalid, status_code = api.update_task("Alpha", {"id": 1, "fields": {"status": "???"}})
        self.assertEqual(status_code, 400)
        resp_priority_invalid, status_code2 = api.update_task("Alpha", {"id": 1, "fields": {"priority": "???"}})
        self.assertEqual(status_code2, 400)

    def test_update_task_persist_error(self):
        store = _DummyStore(fetch_task_response={"task_id": 1, "summary": "S", "assignee": "", "remarks": "", "status": "Not Started", "priority": "Low", "highlight": False}, upsert_raises=True)
        api = TaskAPI(store_factory=lambda: store)
        resp, status = api.update_task("Alpha", {"id": 1, "fields": {"summary": "X"}})
        self.assertEqual(status, 500)
        self.assertIn("Failed to save", resp.get("error", ""))

    def test_create_task_validation_and_defaults(self):
        api = TaskAPI()
        self.assertEqual(api.create_task("..", {})[1], 400)
        self.assertEqual(api.create_task("Alpha", "bad")[1], 400)

        store = _DummyStore(next_id=7)
        api2 = TaskAPI(store_factory=lambda: store)
        resp, status = api2.create_task("Alpha", {"summary": "S", "status": "???", "priority": "???"})
        self.assertEqual(status, 200)
        self.assertEqual(resp.get("id"), 7)
        self.assertEqual(resp.get("task", {}).get("status"), TaskStatus.NOT_STARTED.value)
        self.assertEqual(resp.get("task", {}).get("priority"), TaskPriority.MEDIUM.value)

    def test_create_task_persist_error(self):
        store = _DummyStore(next_id=1, upsert_raises=True)
        api = TaskAPI(store_factory=lambda: store)
        resp, status = api.create_task("Alpha", {"summary": "S"})
        self.assertEqual(status, 500)
        self.assertIn("Failed to save", resp.get("error", ""))

    def test_delete_task_validation_and_not_found(self):
        api = TaskAPI()
        self.assertEqual(api.delete_task("..", {})[1], 400)
        self.assertEqual(api.delete_task("Alpha", "bad")[1], 400)
        self.assertEqual(api.delete_task("Alpha", {"id": "x"})[1], 400)

        store = _DummyStore(fetch_task_response=None)
        api2 = TaskAPI(store_factory=lambda: store)
        resp, status = api2.delete_task("Alpha", {"id": 1})
        self.assertEqual(status, 400)
        self.assertIn("Task not found", resp.get("error", ""))

    def test_delete_task_persist_error_and_fallback_dict(self):
        store = _DummyStore(fetch_task_response={"task_id": 1, "summary": "S", "assignee": "A", "remarks": "R", "status": "Not Started", "priority": "Low", "highlight": False}, delete_raises=True)
        api = TaskAPI(store_factory=lambda: store)
        resp, status = api.delete_task("Alpha", {"id": 1})
        self.assertEqual(status, 500)
        self.assertIn("Failed to save", resp.get("error", ""))

        bad_store = _DummyStore(fetch_task_response={"task_id": 2, "summary": "S", "assignee": "A", "remarks": "R", "status": "???", "priority": "???", "highlight": 1})
        api_bad = TaskAPI(store_factory=lambda: bad_store)
        resp2, status2 = api_bad.delete_task("Alpha", {"id": 2})
        self.assertEqual(status2, 200)
        self.assertEqual(resp2.get("task", {}).get("id"), 2)
        self.assertTrue(resp2.get("task", {}).get("highlight"))


if __name__ == "__main__":
    unittest.main()
