import unittest
from taskman.server.task import Task

class TestTask(unittest.TestCase):
    def test_task_serialization(self):
        task = Task("Summary", "Assignee", "Remarks", "Not Started", "Low", True)
        data = task.to_dict()
        new_task = Task.from_dict(data)
        self.assertEqual(task.summary, new_task.summary)
        self.assertEqual(task.assignee, new_task.assignee)
        self.assertEqual(task.remarks, new_task.remarks)
        self.assertEqual(task.status, new_task.status)
        self.assertEqual(task.priority, new_task.priority)
        self.assertTrue(task.highlight)
        self.assertTrue(new_task.highlight)

if __name__ == "__main__":
    unittest.main()
