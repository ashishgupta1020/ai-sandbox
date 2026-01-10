import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from taskman.server.task_store import TaskStore


class TestSQLiteStorage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="taskman-sqlite-tests-"))
        self.db_path = self.tmpdir / "custom.db"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_open_idempotent(self):
        store = TaskStore(db_path=self.db_path)
        store.open()
        first_conn = store._conn
        store.open()  # second call should no-op
        self.assertIs(store._conn, first_conn)
        store.close()

    def test_ensure_schema_without_open(self):
        store = TaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store._ensure_schema()

    def test_fetch_all_without_open(self):
        store = TaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.fetch_all("alpha")

    def test_upsert_task_errors(self):
        store = TaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.upsert_task("alpha", {"task_id": 1})

        store.open()
        with self.assertRaises(ValueError):
            # Required fields missing from payload triggers validation guard
            store.upsert_task("alpha", {"task_id": 1})
        store.close()

    def test_bulk_replace_errors(self):
        store = TaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.bulk_replace("alpha", [])

        store.open()
        with self.assertRaises(ValueError):
            # bulk_replace enforces each task providing task_id for integrity
            store.bulk_replace("alpha", [{"summary": "S"}])
        store.close()

    def test_bulk_replace_rollback_on_failure(self):
        store = TaskStore(db_path=self.db_path)
        store.open()
        with self.assertRaises(sqlite3.IntegrityError):
            store.bulk_replace(
                "alpha",
                [
                    {"task_id": 1, "summary": "", "assignee": "", "remarks": "", "status": "", "priority": ""},
                    {"task_id": 1, "summary": "", "assignee": "", "remarks": "", "status": "", "priority": ""},
                ],
            )
        store.close()

    def test_delete_task_without_open(self):
        store = TaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.delete_task("alpha", 1)

    def test_delete_project_without_open(self):
        store = TaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.delete_project("alpha")

    def test_delete_project_empty_name(self):
        store = TaskStore(db_path=self.db_path)
        store.open()
        try:
            with self.assertRaises(ValueError):
                store.delete_project("")
            with self.assertRaises(ValueError):
                store.delete_project("   ")
        finally:
            store.close()

    def test_delete_project_not_found(self):
        store = TaskStore(db_path=self.db_path)
        store.open()
        try:
            result = store.delete_project("nonexistent")
            self.assertFalse(result)
        finally:
            store.close()

    def test_delete_project_with_tasks_and_tags(self):
        store = TaskStore(db_path=self.db_path)
        store.open()
        try:
            # Create project with tasks and tags
            store.upsert_task(
                "ToDelete",
                {
                    "task_id": 1,
                    "summary": "Task 1",
                    "assignee": "Alice",
                    "remarks": "",
                    "status": "Not Started",
                    "priority": "High",
                },
            )
            store.upsert_task(
                "ToDelete",
                {
                    "task_id": 2,
                    "summary": "Task 2",
                    "assignee": "Bob",
                    "remarks": "",
                    "status": "In Progress",
                    "priority": "Low",
                },
            )
            store.add_tags("ToDelete", ["tag1", "tag2"])

            # Verify project exists with tasks and tags
            self.assertIn("ToDelete", store.list_projects())
            self.assertEqual(len(store.fetch_all("ToDelete")), 2)
            self.assertEqual(store.get_tags_for_project("ToDelete"), ["tag1", "tag2"])

            # Delete the project
            result = store.delete_project("ToDelete")
            self.assertTrue(result)

            # Verify project and all data is gone
            self.assertNotIn("ToDelete", store.list_projects())
            self.assertEqual(store.fetch_all("ToDelete"), [])
            self.assertEqual(store.get_tags_for_project("ToDelete"), [])
        finally:
            store.close()

    def test_delete_project_case_insensitive(self):
        store = TaskStore(db_path=self.db_path)
        store.open()
        try:
            store.upsert_project_name("MyProject")
            self.assertIn("MyProject", store.list_projects())

            # Delete with different case
            result = store.delete_project("myproject")
            self.assertTrue(result)
            self.assertNotIn("MyProject", store.list_projects())
        finally:
            store.close()

    def test_get_tags_for_all_projects(self):
        store = TaskStore(db_path=self.db_path)
        store.open()
        try:
            store.add_tags("Alpha", ["one", "two"])
            store.add_tags("beta", ["three"])
            store.upsert_project_name("Gamma")
            tags = store.get_tags_for_all_projects()
        finally:
            store.close()
        self.assertEqual(tags.get("Alpha"), ["one", "two"])
        self.assertEqual(tags.get("beta"), ["three"])
        self.assertIn("Gamma", tags)
        self.assertEqual(tags.get("Gamma"), [])

    def test_fetch_task_and_next_id(self):
        store = TaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.fetch_task("alpha", 1)

        store.open()
        try:
            # Empty table returns zero as next id
            self.assertEqual(store.next_task_id("alpha"), 0)

            store.upsert_task(
                "alpha",
                {
                    "task_id": 1,
                    "summary": "S1",
                    "assignee": "A",
                    "remarks": "",
                    "status": "Not Started",
                    "priority": "Low",
                    "highlight": True,
                },
            )
            row = store.fetch_task("alpha", 1)
            self.assertIsNotNone(row)
            assert row is not None  # for type checkers
            self.assertEqual(row["task_id"], 1)
            self.assertTrue(isinstance(row.get("highlight"), bool))
            self.assertIsNone(store.fetch_task("alpha", 999))

            # Next id should be max + 1
            store.upsert_task(
                "alpha",
                {
                    "task_id": 5,
                    "summary": "S5",
                    "assignee": "",
                    "remarks": "",
                    "status": "Completed",
                    "priority": "High",
                    "highlight": False,
                },
            )
            self.assertEqual(store.next_task_id("alpha"), 6)
        finally:
            store.close()
