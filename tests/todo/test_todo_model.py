import unittest

from taskman.server.todo.todo import Todo, TodoPriority


class TestTodoModel(unittest.TestCase):
    def test_to_dict_from_dict(self):
        todo = Todo(
            id=5,
            title="Demo",
            note="Notes",
            due_date="2024-06-01",
            people=["Alex"],
            priority=TodoPriority.HIGH,
            done=True,
        )
        data = todo.to_dict()
        self.assertEqual(data["id"], 5)
        self.assertEqual(data["priority"], "high")

        roundtrip = Todo.from_dict(data)
        self.assertEqual(roundtrip.title, todo.title)
        self.assertEqual(roundtrip.priority, TodoPriority.HIGH)
        self.assertTrue(roundtrip.done)

    def test_priority_fallback(self):
        todo = Todo.from_dict({"title": "X", "priority": "unknown"})
        self.assertEqual(todo.priority, TodoPriority.MEDIUM)


if __name__ == "__main__":
    unittest.main()
