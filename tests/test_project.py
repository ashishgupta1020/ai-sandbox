import unittest
import os
import shutil
from io import StringIO
from contextlib import redirect_stdout
from taskman.project_manager import ProjectManager
from taskman.project import Project
from taskman.task import Task, TaskStatus, TaskPriority

class TestProject(unittest.TestCase):
    TEST_PROJECT = "TestProject"
    BASE_DATA_DIR = os.path.expanduser("~/sandbox/data/ai-sandbox")
    TEST_DATA_DIR = os.path.join(BASE_DATA_DIR, "test")

    def setUp(self):
        # Clean and create test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        os.makedirs(self.TEST_DATA_DIR, exist_ok=True)
        # Patch ProjectManager to use test directories
        self._orig_projects_dir = ProjectManager.PROJECTS_DIR
        ProjectManager.PROJECTS_DIR = self.TEST_DATA_DIR
        self.task_file = ProjectManager.get_task_file_path(self.TEST_PROJECT)

    def tearDown(self):
        # Clean up test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        # Restore original projects dir
        ProjectManager.PROJECTS_DIR = self._orig_projects_dir

    def test_add_and_list_task(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        task1 = Task("Summary1", "Assignee1", "Remarks1", "Not Started", "Low")
        task2 = Task("Summary2", "Assignee2", "Remarks2", "Completed", "High")
        project.add_task(task1)
        project.add_task(task2)
        self.assertEqual(len(project.tasks), 2)
        # Capture output
        with StringIO() as buf, redirect_stdout(buf):
            project.list_tasks()
            output = buf.getvalue()
        # Assert all task summaries and assignees are in output
        self.assertIn("Summary1", output)
        self.assertIn("Summary2", output)
        self.assertIn("Assignee1", output)
        self.assertIn("Assignee2", output)

    def test_list_tasks_empty(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        # Ensure output is correct when no tasks exist
        with StringIO() as buf, redirect_stdout(buf):
            project.list_tasks()
            output = buf.getvalue()
        self.assertIn("No tasks found in this project.", output)

    def test_edit_task(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        task = Task("Summary", "Assignee", "Remarks", "Not Started", "Low")
        project.add_task(task)
        # Prepare simulated user input for editing the task
        user_inputs = [
            "New Summary",      # new summary
            "New Assignee",    # new assignee
            "New Remarks",     # new remarks
            "",  # End of multi-line remarks
            "3",               # new status (Completed)
            "2"                # new priority (Medium)
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        # Patch input function using builtins module for Python 3 compatibility
        import builtins
        original_input = builtins.input
        builtins.input = mock_input
        try:
            from taskman.cli.interaction import Interaction
            old_task = project.tasks[0]
            new_task = Interaction.edit_task_details(old_task)
            project.edit_task(1, new_task)
        finally:
            builtins.input = original_input
        # Check that the task was updated as expected
        updated_task = project.tasks[0]
        self.assertEqual(updated_task.summary, "New Summary")
        self.assertEqual(updated_task.assignee, "New Assignee")
        self.assertEqual(updated_task.remarks, "New Remarks")
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)
        self.assertEqual(updated_task.priority, TaskPriority.MEDIUM)

    def test_edit_task_invalid_index(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        # Add a task so index 2 is invalid
        project.add_task(Task("Summary", "Assignee", "Remarks", "Not Started", "Low"))
        dummy_task = project.tasks[0]
        with StringIO() as buf, redirect_stdout(buf):
            project.edit_task(2, dummy_task)
            output = buf.getvalue()
        self.assertIn("Invalid task index.", output)

    def test_load_tasks_from_file_invalid_json(self):
        # Write invalid JSON to the test task file
        with open(self.task_file, "w") as f:
            f.write("invalid json")
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(project.tasks, [])

    # --- New unit tests for API helper methods and exports ---
    def test_update_task_from_payload_success(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({
            "index": 0,
            "fields": {"summary": "New", "status": "Completed", "priority": "High"}
        })
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(project.tasks[0].summary, "New")
        self.assertEqual(project.tasks[0].status, TaskStatus.COMPLETED)
        self.assertEqual(project.tasks[0].priority, TaskPriority.HIGH)

        # Verify persisted to disk
        project2 = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(project2.tasks[0].summary, "New")

    def test_update_task_from_payload_invalid_index_type(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({"index": "zero", "fields": {"summary": "X"}})
        self.assertEqual(status, 400)
        self.assertIn("index", resp.get("error", ""))

    def test_update_task_from_payload_out_of_range(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.update_task_from_payload({"index": 1, "fields": {"summary": "X"}})
        self.assertEqual(status, 400)

    def test_update_task_from_payload_unknown_field(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({"index": 0, "fields": {"foo": "bar"}})
        self.assertEqual(status, 400)

    def test_update_task_from_payload_invalid_enums(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        # Invalid status
        resp, status = project.update_task_from_payload({"index": 0, "fields": {"status": "Started"}})
        self.assertEqual(status, 400)
        # Invalid priority
        resp2, status2 = project.update_task_from_payload({"index": 0, "fields": {"priority": "Urgent"}})
        self.assertEqual(status2, 400)

    def test_create_task_from_payload_defaults(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.create_task_from_payload({})
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(len(project.tasks), 1)
        t = project.tasks[0]
        self.assertEqual(t.summary, "")
        self.assertEqual(t.assignee, "")
        self.assertEqual(t.remarks, "")
        self.assertEqual(t.status, TaskStatus.NOT_STARTED)
        self.assertEqual(t.priority, TaskPriority.MEDIUM)

    def test_create_task_from_payload_overrides_and_persist(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        payload = {"summary": "S", "assignee": "A", "remarks": "R", "status": "Completed", "priority": "High"}
        resp, status = project.create_task_from_payload(payload)
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(len(project.tasks), 1)
        t = project.tasks[0]
        self.assertEqual(t.summary, "S")
        self.assertEqual(t.assignee, "A")
        self.assertEqual(t.remarks, "R")
        self.assertEqual(t.status, TaskStatus.COMPLETED)
        self.assertEqual(t.priority, TaskPriority.HIGH)
        # Persist check
        project2 = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(len(project2.tasks), 1)
        self.assertEqual(project2.tasks[0].summary, "S")

    def test_create_task_from_payload_invalid_payload_type(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.create_task_from_payload("not a dict")  # type: ignore[arg-type]
        self.assertEqual(status, 400)

    def test_delete_task_from_payload_success(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S1", "A1", "R1", "Not Started", "Low"))
        project.add_task(Task("S2", "A2", "R2", "Completed", "High"))
        resp, status = project.delete_task_from_payload({"index": 0})
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(len(project.tasks), 1)
        self.assertEqual(project.tasks[0].summary, "S2")
        # Persist check
        project2 = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(len(project2.tasks), 1)
        self.assertEqual(project2.tasks[0].summary, "S2")

    def test_delete_task_from_payload_invalid_index_type(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.delete_task_from_payload({"index": "zero"})  # type: ignore[arg-type]
        self.assertEqual(status, 400)

    def test_delete_task_from_payload_out_of_range(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.delete_task_from_payload({"index": 0})
        self.assertEqual(status, 400)

    

    def test_export_tasks_to_markdown_file(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S1", "A1", "R1", "Not Started", "Low"))
        project.export_tasks_to_markdown_file()
        md_path = ProjectManager.get_markdown_file_path(self.TEST_PROJECT)
        self.assertTrue(os.path.exists(md_path))
        with open(md_path, "r") as f:
            content = f.read()
        self.assertIn("S1", content)

if __name__ == "__main__":
    unittest.main()
