import shutil
import tempfile
import unittest
import time
from pathlib import Path

from taskman.server.todo.todo_api import TodoAPI
from taskman.server.todo.todo_store import TodoStore


class TestTodoAPI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="taskman-todo-api-")
        self.db_path = Path(self.tmpdir) / "todo.db"
        self.api = TodoAPI(store_factory=lambda: TodoStore(db_path=self.db_path))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_requires_title(self):
        resp, status = self.api.add_todo({})
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_add_invalid_payload_type(self):
        resp, status = self.api.add_todo(["not a dict"])  # type: ignore[arg-type]
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_add_roundtrip(self):
        payload = {
            "title": "Ship feature",
            "note": "Sync with docs",
            "due_date": "2024-12-01",
            "priority": "urgent",
            "people": "Alex, Casey",
            "done": True,
        }
        resp, status = self.api.add_todo(payload)
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        item = resp.get("item", {})
        self.assertEqual(item.get("title"), payload["title"])
        self.assertEqual(item.get("due_date"), "2024-12-01")
        self.assertTrue(item.get("done"))
        self.assertEqual(item.get("people"), ["Alex", "Casey"])
        self.assertEqual(item.get("priority"), "urgent")

        resp2, status2 = self.api.list_todos()
        self.assertEqual(status2, 200)
        items = resp2.get("items") or []
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("title"), payload["title"])

    def test_add_ignores_non_iso_due(self):
        resp, status = self.api.add_todo({"title": "Bad date", "due_date": "03/02"})
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(resp.get("item", {}).get("due_date"), "")

        resp2, status2 = self.api.list_todos()
        self.assertEqual(status2, 200)
        items = resp2.get("items") or []
        self.assertEqual(items[0].get("due_date"), "")

    def test_mark_done(self):
        # Seed
        resp, status = self.api.add_todo({"title": "Toggle me"})
        self.assertEqual(status, 200)
        todo_id = resp["item"]["id"]
        # Mark as done
        resp2, status2 = self.api.mark_done({"id": todo_id, "done": True})
        self.assertEqual(status2, 200)
        self.assertTrue(resp2.get("ok"))
        self.assertTrue(resp2.get("done"))
        # Verify persisted state
        resp3, status3 = self.api.list_todos()
        self.assertEqual(status3, 200)
        items = resp3.get("items") or []
        self.assertTrue(items[0].get("done"))

    def test_list_archived_filters_old_done(self):
        resp, status = self.api.add_todo({"title": "Recent", "done": True})
        self.assertEqual(status, 200)
        resp2, status2 = self.api.add_todo({"title": "Old", "done": True})
        self.assertEqual(status2, 200)
        old_id = resp2["item"]["id"]

        old_ts = int(time.time()) - (40 * 24 * 60 * 60)
        with TodoStore(db_path=self.db_path) as store:
            store._ensure_table()
            store._conn.execute(
                "UPDATE todos SET done_at = :done_at, created_at = :created_at WHERE id = :id",
                {"done_at": old_ts, "created_at": old_ts, "id": old_id},
            )

        active_resp, active_status = self.api.list_todos()
        self.assertEqual(active_status, 200)
        active_titles = [item.get("title") for item in active_resp.get("items") or []]
        self.assertEqual(active_titles, ["Recent"])

        archived_resp, archived_status = self.api.list_archived_todos()
        self.assertEqual(archived_status, 200)
        archived_titles = [item.get("title") for item in archived_resp.get("items") or []]
        self.assertEqual(archived_titles, ["Old"])

    def test_mark_done_requires_id(self):
        resp, status = self.api.mark_done({"done": True})
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_mark_done_invalid_id(self):
        resp, status = self.api.mark_done({"id": "not-int"})
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_mark_done_invalid_payload_type(self):
        resp, status = self.api.mark_done("bad")  # type: ignore[arg-type]
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_mark_done_not_found(self):
        resp, status = self.api.mark_done({"id": 999, "done": True})
        self.assertEqual(status, 404)
        self.assertIn("error", resp)

    def test_edit_todo_success(self):
        # Seed item
        resp, status = self.api.add_todo({"title": "Original", "note": "first"})
        self.assertEqual(status, 200)
        todo_id = resp["item"]["id"]

        payload = {"id": todo_id, "title": "Updated", "note": "changed", "priority": "high", "due_date": "2024-12-31"}
        resp2, status2 = self.api.edit_todo(payload)
        self.assertEqual(status2, 200)
        self.assertTrue(resp2.get("ok"))
        self.assertEqual(resp2["item"]["title"], "Updated")
        self.assertEqual(resp2["item"]["priority"], "high")

        resp3, status3 = self.api.list_todos()
        self.assertEqual(status3, 200)
        items = resp3.get("items") or []
        self.assertEqual(items[0]["title"], "Updated")
        self.assertEqual(items[0]["note"], "changed")

    def test_edit_requires_id(self):
        resp, status = self.api.edit_todo({"title": "No id"})
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_edit_requires_title(self):
        resp, status = self.api.add_todo({"title": "Seed"})
        self.assertEqual(status, 200)
        todo_id = resp["item"]["id"]
        resp2, status2 = self.api.edit_todo({"id": todo_id, "title": ""})
        self.assertEqual(status2, 400)
        self.assertIn("error", resp2)

    def test_edit_invalid_id(self):
        resp, status = self.api.edit_todo({"id": "bad", "title": "X"})
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_edit_invalid_payload_type(self):
        resp, status = self.api.edit_todo(["bad"])  # type: ignore[arg-type]
        self.assertEqual(status, 400)
        self.assertIn("error", resp)

    def test_edit_not_found(self):
        resp, status = self.api.edit_todo({"id": 999, "title": "Missing"})
        self.assertEqual(status, 404)
        self.assertIn("error", resp)

    def test_add_normalizes_whitespace_and_people_type(self):
        resp, status = self.api.add_todo({"title": "Spaces", "due_date": "   ", "people": 123})
        self.assertEqual(status, 200)
        item = resp["item"]
        self.assertEqual(item["due_date"], "")
        self.assertEqual(item["people"], [])

    def test_store_errors_surface_as_500(self):
        class BoomStore:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def add_item(self, todo):
                raise RuntimeError("add fail")

            def list_items(self):
                raise RuntimeError("list fail")

            def set_done(self, todo_id, done):
                raise RuntimeError("done fail")

            def update_item(self, todo_id, todo):
                raise RuntimeError("edit fail")

        api = TodoAPI(store_factory=lambda: BoomStore())
        resp, status = api.add_todo({"title": "X"})
        self.assertEqual(status, 500)
        self.assertIn("Failed to add todo", resp.get("error", ""))

        resp2, status2 = api.list_todos()
        self.assertEqual(status2, 500)
        self.assertIn("Failed to fetch todos", resp2.get("error", ""))

        resp3, status3 = api.mark_done({"id": 1, "done": True})
        self.assertEqual(status3, 500)
        self.assertIn("Failed to update todo", resp3.get("error", ""))

        resp4, status4 = api.edit_todo({"id": 1, "title": "X"})
        self.assertEqual(status4, 500)
        self.assertIn("Failed to update todo", resp4.get("error", ""))


if __name__ == "__main__":
    unittest.main()
