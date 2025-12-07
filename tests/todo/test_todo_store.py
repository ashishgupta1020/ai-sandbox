import shutil
import tempfile
import unittest
from pathlib import Path

from taskman.server.todo.todo import Todo, TodoPriority
from taskman.server.todo.todo_store import TodoStore


class TestTodoStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="taskman-todo-store-")
        self.db_path = Path(self.tmpdir) / "todo.db"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_and_list_ordering(self):
        with TodoStore(db_path=self.db_path) as store:
            store.add_item(Todo(title="First", due_date="2024-01-05", priority=TodoPriority.HIGH, done=False))
            store.add_item(Todo(title="Second", due_date="2024-01-01", priority=TodoPriority.LOW, done=True))
        with TodoStore(db_path=self.db_path) as store:
            items = store.list_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "First")
        self.assertFalse(items[0].done)
        self.assertEqual(items[1].title, "Second")
        self.assertTrue(items[1].done)

    def test_people_and_priority_persist(self):
        people = ["Alex", "Blake"]
        with TodoStore(db_path=self.db_path) as store:
            store.add_item(Todo(title="People", people=people, priority=TodoPriority.URGENT))
        with TodoStore(db_path=self.db_path) as store:
            items = store.list_items()
        self.assertEqual(items[0].people, people)
        self.assertEqual(items[0].priority, TodoPriority.URGENT)

    def test_set_done_updates_state(self):
        with TodoStore(db_path=self.db_path) as store:
            todo = store.add_item(Todo(title="To toggle"))
            updated = store.set_done(todo.id, True)
            self.assertTrue(updated)
        with TodoStore(db_path=self.db_path) as store:
            items = store.list_items()
        self.assertTrue(items[0].done)

    def test_update_item_changes_fields(self):
        with TodoStore(db_path=self.db_path) as store:
            todo = store.add_item(Todo(title="Old", note="n1", priority=TodoPriority.LOW, due_date="2024-01-01", people=["A"]))
            updated = store.update_item(todo.id, Todo(title="New", note="n2", priority=TodoPriority.HIGH, due_date="2024-02-02", people=["B", "C"]))
            self.assertTrue(updated)
        with TodoStore(db_path=self.db_path) as store:
            items = store.list_items()
        self.assertEqual(items[0].title, "New")
        self.assertEqual(items[0].note, "n2")
        self.assertEqual(items[0].priority, TodoPriority.HIGH)
        self.assertEqual(items[0].due_date, "2024-02-02")
        self.assertEqual(items[0].people, ["B", "C"])

    def test_requires_open_connection(self):
        store = TodoStore(db_path=self.db_path)
        with self.assertRaises(RuntimeError):
            store.add_item(Todo(title="No open"))
        with self.assertRaises(RuntimeError):
            store.list_items()
        with self.assertRaises(RuntimeError):
            store.set_done(1, True)
        with self.assertRaises(RuntimeError):
            store.update_item(1, Todo(title="X"))

    def test_malformed_people_json_defaults_empty(self):
        with TodoStore(db_path=self.db_path) as store:
            store._ensure_table()
            # Insert malformed people JSON directly
            store._conn.execute(
                "INSERT INTO todos (title, note, due_date, people, priority, done) VALUES (:title, '', '', 'not-json', 'low', 0)",
                {"title": "Bad people"},
            )
            items = store.list_items()
        self.assertEqual(items[0].people, [])


if __name__ == "__main__":
    unittest.main()
