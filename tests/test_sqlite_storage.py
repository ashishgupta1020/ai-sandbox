import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.migrate_add_highlight_column import migrate_highlight_columns
from taskman.server.project_manager import ProjectManager
from taskman.server.sqlite_storage import SQLiteTaskStore, _project_table_name


class TestSQLiteStorage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="taskman-sqlite-tests-"))
        self.orig_dir = ProjectManager.PROJECTS_DIR
        ProjectManager.PROJECTS_DIR = str(self.tmpdir)
        self.db_path = self.tmpdir / "custom.db"

    def tearDown(self):
        ProjectManager.PROJECTS_DIR = self.orig_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_project_table_name_invalid_inputs(self):
        with self.assertRaises(ValueError):
            # Empty names are rejected before reaching sqlite
            _project_table_name("")

        self.assertEqual(_project_table_name("Alpha/Beta"), "tasks_alpha_beta")

    def test_open_idempotent(self):
        store = SQLiteTaskStore(db_path=self.db_path)
        store.open()
        first_conn = store._conn
        store.open()  # second call should no-op
        self.assertIs(store._conn, first_conn)
        store.close()

    def test_ensure_table_without_open(self):
        store = SQLiteTaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store._ensure_table("alpha")

    def test_fetch_all_without_open(self):
        store = SQLiteTaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.fetch_all("alpha")

    def test_upsert_task_errors(self):
        store = SQLiteTaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.upsert_task("alpha", {"task_id": 1})

        store.open()
        with self.assertRaises(ValueError):
            # Required fields missing from payload triggers validation guard
            store.upsert_task("alpha", {"task_id": 1})
        store.close()

    def test_bulk_replace_errors(self):
        store = SQLiteTaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.bulk_replace("alpha", [])

        store.open()
        with self.assertRaises(ValueError):
            # bulk_replace enforces each task providing task_id for integrity
            store.bulk_replace("alpha", [{"summary": "S"}])
        store.close()

    def test_bulk_replace_rollback_on_failure(self):
        store = SQLiteTaskStore(db_path=self.db_path)
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

    def test_migration_script_adds_highlight_column(self):
        store = SQLiteTaskStore(db_path=self.db_path)
        store.open()
        table = _project_table_name("alpha")
        store._conn.execute(
            f"""
            CREATE TABLE {table} (
                task_id   INTEGER PRIMARY KEY,
                summary   TEXT NOT NULL,
                assignee  TEXT,
                remarks   TEXT,
                status    TEXT NOT NULL,
                priority  TEXT NOT NULL
            )
            """
        )
        store._conn.execute(
            f"INSERT INTO {table} (task_id, summary, assignee, remarks, status, priority) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "S", "A", "R", "Not Started", "Low"),
        )
        store.close()

        altered, unchanged = migrate_highlight_columns(self.db_path)
        self.assertEqual(altered, 1)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        row = conn.execute(f"SELECT highlight FROM {table} WHERE task_id = 1").fetchone()
        conn.close()
        self.assertIn("highlight", columns)
        self.assertEqual(row["highlight"], 0)
        self.assertEqual(unchanged, 0)

    def test_delete_task_without_open(self):
        store = SQLiteTaskStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.delete_task("alpha", 1)
