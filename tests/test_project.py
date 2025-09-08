import unittest
import json
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


    def test_edit_task(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        task = Task("Summary", "Assignee", "Remarks", "Not Started", "Low")
        tid = project.add_task(task)
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
            first = project._tasks_by_id[tid]
            new_task = Interaction.edit_task_details(first)
            project.edit_task(tid, new_task)  # type: ignore[arg-type]
        finally:
            builtins.input = original_input
        # Check that the task was updated as expected
        updated_task = project._tasks_by_id[tid]
        self.assertEqual(updated_task.summary, "New Summary")
        self.assertEqual(updated_task.assignee, "New Assignee")
        self.assertEqual(updated_task.remarks, "New Remarks")
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)
        self.assertEqual(updated_task.priority, TaskPriority.MEDIUM)

    def test_edit_task_invalid_id(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        # Add a task so index 2 is invalid
        tid = project.add_task(Task("Summary", "Assignee", "Remarks", "Not Started", "Low"))
        dummy_task = project._tasks_by_id[tid]
        with StringIO() as buf, redirect_stdout(buf):
            project.edit_task(999, dummy_task)
            output = buf.getvalue()
        self.assertIn("Invalid task id.", output)

    def test_load_tasks_from_file_invalid_json(self):
        # Write invalid JSON to the test task file
        with open(self.task_file, "w") as f:
            f.write("invalid json")
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(project._tasks_by_id, {})

    # --- Tests for API helper methods and exports ---
    def test_update_task_from_payload_success(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        first = project._tasks_by_id[tid]
        resp, status = project.update_task_from_payload({
            "id": first.id,
            "fields": {"summary": "New", "status": "Completed", "priority": "High"}
        })
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        after = project._tasks_by_id[tid]
        self.assertEqual(resp.get("id"), after.id)
        self.assertEqual(after.summary, "New")
        self.assertEqual(after.status, TaskStatus.COMPLETED)
        self.assertEqual(after.priority, TaskPriority.HIGH)

        # Verify persisted to disk (use original task id)
        project2 = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(project2._tasks_by_id[tid].summary, "New")

    def test_update_task_from_payload_invalid_id_type(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({"id": "zero", "fields": {"summary": "X"}})
        self.assertEqual(status, 400)
        self.assertIn("id", resp.get("error", ""))

    def test_update_task_from_payload_out_of_range(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.update_task_from_payload({"id": 1, "fields": {"summary": "X"}})
        self.assertEqual(status, 400)

    def test_update_task_from_payload_unknown_field(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({"id": 0, "fields": {"foo": "bar"}})
        self.assertEqual(status, 400)

    def test_update_task_from_payload_invalid_enums(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        # Invalid status
        resp, status = project.update_task_from_payload({"id": 0, "fields": {"status": "Started"}})
        self.assertEqual(status, 400)
        # Invalid priority
        resp2, status2 = project.update_task_from_payload({"id": 0, "fields": {"priority": "Urgent"}})
        self.assertEqual(status2, 400)

    def test_create_task_from_payload_defaults(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.create_task_from_payload({})
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertIn("id", resp)
        first = list(project._tasks_by_id.values())[0]
        self.assertEqual(resp.get("id"), first.id)
        self.assertEqual(len(project._tasks_by_id), 1)
        t = project._tasks_by_id[first.id]
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
        self.assertIn("id", resp)
        first = list(project._tasks_by_id.values())[0]
        self.assertEqual(resp.get("id"), first.id)
        self.assertEqual(len(project._tasks_by_id), 1)
        t = project._tasks_by_id[first.id]
        self.assertEqual(t.summary, "S")
        self.assertEqual(t.assignee, "A")
        self.assertEqual(t.remarks, "R")
        self.assertEqual(t.status, TaskStatus.COMPLETED)
        self.assertEqual(t.priority, TaskPriority.HIGH)
        # Persist check
        project2 = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(len(project2._tasks_by_id), 1)
        self.assertEqual(project2._tasks_by_id[first.id].summary, "S")

    def test_create_task_from_payload_invalid_payload_type(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.create_task_from_payload("not a dict")  # type: ignore[arg-type]
        self.assertEqual(status, 400)

    def test_delete_task_from_payload_success(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        project.add_task(Task("S1", "A1", "R1", "Not Started", "Low"))
        project.add_task(Task("S2", "A2", "R2", "Completed", "High"))
        resp, status = project.delete_task_from_payload({"id": 0})
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(resp.get("id"), 0)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(len(project._tasks_by_id), 1)
        self.assertEqual(list(project._tasks_by_id.values())[0].summary, "S2")
        # Persist check
        project2 = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(len(project2._tasks_by_id), 1)
        self.assertEqual(list(project2._tasks_by_id.values())[0].summary, "S2")

    def test_delete_task_from_payload_invalid_id_type(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.delete_task_from_payload({"id": "zero"})  # type: ignore[arg-type]
        self.assertEqual(status, 400)

    def test_delete_task_from_payload_out_of_range(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        resp, status = project.delete_task_from_payload({"id": 0})
        self.assertEqual(status, 400)


    # --- Tests for file load/save behavior ---
    def test_save_and_load_tasks_roundtrip(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        # Add two tasks and persist
        project.add_task(Task("S1", "A1", "R1", "Not Started", "Low"))
        project.add_task(Task("S2", "A2", "R2", "Completed", "High"))

        # Read raw file and verify structured format with ids
        with open(self.task_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)
        self.assertIn("last_id", data)
        self.assertIn("tasks", data)
        self.assertEqual(len(data["tasks"]), 2)
        ids = [t.get("id") for t in data["tasks"]]
        self.assertEqual(ids, [0, 1])
        self.assertEqual(data["last_id"], 1)

        # Load in a new Project instance and verify contents
        project2 = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        self.assertEqual(len(project2._tasks_by_id), 2)
        vals = list(project2._tasks_by_id.values())
        self.assertEqual(vals[0].id, 0)
        self.assertEqual(vals[1].id, 1)
        self.assertEqual(vals[0].summary, "S1")
        self.assertEqual(vals[1].summary, "S2")

    def test_load_recomputes_last_id_and_persists(self):
        # Seed file with inconsistent last_id vs max task id
        initial = {
            "last_id": 0,
            "tasks": [
                {"id": 5, "summary": "A", "assignee": "a", "remarks": "", "status": "Not Started", "priority": "Low"},
                {"id": 7, "summary": "B", "assignee": "b", "remarks": "", "status": "In Progress", "priority": "Medium"},
            ],
        }
        with open(self.task_file, "w", encoding="utf-8") as f:
            json.dump(initial, f)

        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        # last_id should be recomputed to 7
        self.assertEqual(project.last_id, 7)
        # File should be updated to persist corrected last_id
        with open(self.task_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("last_id"), 7)
        # Tasks loaded with same ids
        self.assertEqual([t.id for t in project._tasks_by_id.values()], [5, 7])

    def test_save_tasks_to_file_overwrites_content(self):
        project = Project(self.TEST_PROJECT, open(self.task_file, "a+"))
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        # Edit in-memory and save
        t = project._tasks_by_id[tid]
        t.summary = "S-edit"
        project.save_tasks_to_file()
        # Verify file reflects changes
        with open(self.task_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["tasks"][0]["summary"], "S-edit")


if __name__ == "__main__":
    unittest.main()
