import os
import shutil
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from taskman.config import get_data_store_dir, set_data_store_dir
from taskman.server.project import Project
from taskman.server.task_store import ProjectTaskSession
from taskman.server.task import Task, TaskPriority, TaskStatus

class TestProject(unittest.TestCase):
    TEST_PROJECT = "TestProject"
    BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "tmp_data")
    TEST_DATA_DIR = os.path.join(BASE_DATA_DIR, "project")

    def setUp(self):
        # Clean and create test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        os.makedirs(self.TEST_DATA_DIR, exist_ok=True)
        # Patch data store path for tests
        self.db_path = Path(self.TEST_DATA_DIR) / "taskman.db"
        self._orig_data_dir = get_data_store_dir()
        set_data_store_dir(Path(self.TEST_DATA_DIR))

    def tearDown(self):
        # Clean up test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        set_data_store_dir(self._orig_data_dir)


    def test_edit_task(self):
        project = Project(self.TEST_PROJECT)
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
        project = Project(self.TEST_PROJECT)
        # Add a task so index 2 is invalid
        tid = project.add_task(Task("Summary", "Assignee", "Remarks", "Not Started", "Low"))
        dummy_task = project._tasks_by_id[tid]
        with StringIO() as buf, redirect_stdout(buf):
            project.edit_task(999, dummy_task)
            output = buf.getvalue()
        self.assertIn("Invalid task id.", output)

    def test_load_tasks_from_empty_database(self):
        # No prior database should result in an empty project view
        project = Project(self.TEST_PROJECT)
        self.assertEqual(project._tasks_by_id, {})
        self.assertTrue(self.db_path.exists())

    # --- Tests for API helper methods and exports ---
    def test_update_task_from_payload_success(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        first = project._tasks_by_id[tid]
        resp, status = project.update_task_from_payload({
            "id": first.id,
            "fields": {"summary": "New", "status": "Completed", "priority": "High", "highlight": True}
        })
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        after = project._tasks_by_id[tid]
        self.assertEqual(resp.get("id"), after.id)
        self.assertEqual(after.summary, "New")
        self.assertEqual(after.status, TaskStatus.COMPLETED)
        self.assertEqual(after.priority, TaskPriority.HIGH)
        self.assertTrue(after.highlight)

        # Verify persisted to disk (use original task id)
        project2 = Project(self.TEST_PROJECT)
        self.assertEqual(project2._tasks_by_id[tid].summary, "New")
        self.assertTrue(project2._tasks_by_id[tid].highlight)

    def test_update_task_from_payload_invalid_id_type(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({"id": "zero", "fields": {"summary": "X"}})
        self.assertEqual(status, 400)
        self.assertIn("id", resp.get("error", ""))

    def test_update_task_from_payload_not_dict(self):
        project = Project(self.TEST_PROJECT)
        resp, status = project.update_task_from_payload("not dict")  # type: ignore[arg-type]
        self.assertEqual(status, 400)
        self.assertIn("Invalid payload", resp.get("error", ""))

    def test_update_task_from_payload_empty_fields(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({"id": tid, "fields": {}})
        self.assertEqual(status, 400)
        self.assertIn("non-empty", resp.get("error", ""))

    def test_update_task_from_payload_out_of_range(self):
        project = Project(self.TEST_PROJECT)
        resp, status = project.update_task_from_payload({"id": 1, "fields": {"summary": "X"}})
        self.assertEqual(status, 400)

    def test_update_task_from_payload_unknown_field(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload({"id": 0, "fields": {"foo": "bar"}})
        self.assertEqual(status, 400)

    def test_update_task_from_payload_invalid_enums(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        # Invalid status
        resp, status = project.update_task_from_payload({"id": 0, "fields": {"status": "Started"}})
        self.assertEqual(status, 400)
        # Invalid priority
        resp2, status2 = project.update_task_from_payload({"id": 0, "fields": {"priority": "Urgent"}})
        self.assertEqual(status2, 400)

    def test_update_task_from_payload_updates_optional_fields(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.update_task_from_payload(
            {"id": tid, "fields": {"assignee": None, "remarks": "Updated"}}
        )
        self.assertEqual(status, 200)
        task = project._tasks_by_id[tid]
        self.assertEqual(task.assignee, "")
        self.assertEqual(task.remarks, "Updated")

    def test_update_task_from_payload_persist_failure(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        with mock.patch.object(project, "_persist_task", side_effect=RuntimeError("boom")):
            resp, status = project.update_task_from_payload({"id": tid, "fields": {"summary": "New"}})
        self.assertEqual(status, 500)
        self.assertIn("Failed to save", resp.get("error", ""))

    def test_create_task_from_payload_defaults(self):
        project = Project(self.TEST_PROJECT)
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
        self.assertFalse(t.highlight)

    def test_create_task_from_payload_overrides_and_persist(self):
        project = Project(self.TEST_PROJECT)
        payload = {"summary": "S", "assignee": "A", "remarks": "R", "status": "Completed", "priority": "High", "highlight": True}
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
        self.assertTrue(t.highlight)
        # Persist check
        project2 = Project(self.TEST_PROJECT)
        self.assertEqual(len(project2._tasks_by_id), 1)
        self.assertEqual(project2._tasks_by_id[first.id].summary, "S")
        self.assertTrue(project2._tasks_by_id[first.id].highlight)

    def test_create_task_from_payload_invalid_payload_type(self):
        project = Project(self.TEST_PROJECT)
        resp, status = project.create_task_from_payload("not a dict")  # type: ignore[arg-type]
        self.assertEqual(status, 400)

    def test_create_task_from_payload_none_defaults(self):
        project = Project(self.TEST_PROJECT)
        resp, status = project.create_task_from_payload(None)
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        created = project._tasks_by_id[resp["id"]]
        self.assertEqual(created.status, TaskStatus.NOT_STARTED)
        self.assertEqual(created.priority, TaskPriority.MEDIUM)

    def test_create_task_from_payload_invalid_enums(self):
        project = Project(self.TEST_PROJECT)
        resp, status = project.create_task_from_payload({"status": "???", "priority": "!!!"})
        self.assertEqual(status, 200)
        created = project._tasks_by_id[resp["id"]]
        self.assertEqual(created.status, TaskStatus.NOT_STARTED)
        self.assertEqual(created.priority, TaskPriority.MEDIUM)

    def test_create_task_from_payload_persist_failure(self):
        project = Project(self.TEST_PROJECT)
        with mock.patch.object(project, "add_task", side_effect=RuntimeError("boom")):
            resp, status = project.create_task_from_payload({})
        self.assertEqual(status, 500)
        self.assertIn("Failed to save", resp.get("error", ""))

    def test_delete_task_from_payload_success(self):
        project = Project(self.TEST_PROJECT)
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
        project2 = Project(self.TEST_PROJECT)
        self.assertEqual(len(project2._tasks_by_id), 1)
        self.assertEqual(list(project2._tasks_by_id.values())[0].summary, "S2")

    def test_delete_task_from_payload_invalid_id_type(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        resp, status = project.delete_task_from_payload({"id": "zero"})  # type: ignore[arg-type]
        self.assertEqual(status, 400)

    def test_delete_task_from_payload_out_of_range(self):
        project = Project(self.TEST_PROJECT)
        resp, status = project.delete_task_from_payload({"id": 0})
        self.assertEqual(status, 400)

    def test_delete_task_from_payload_none_payload(self):
        project = Project(self.TEST_PROJECT)
        resp, status = project.delete_task_from_payload(None)
        self.assertEqual(status, 400)

    def test_delete_task_from_payload_removed_none(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        project._tasks_by_id[tid] = None  # type: ignore[assignment]
        resp, status = project.delete_task_from_payload({"id": tid})
        self.assertEqual(status, 400)
        self.assertIn("Task not found", resp.get("error", ""))

    def test_delete_task_from_payload_delete_failure(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        with mock.patch.object(project, "_delete_task", side_effect=RuntimeError("boom")):
            resp, status = project.delete_task_from_payload({"id": tid})
        self.assertEqual(status, 500)
        self.assertIn("Failed to save", resp.get("error", ""))


    # --- Tests for persistence behavior ---
    def test_save_and_load_tasks_roundtrip(self):
        project = Project(self.TEST_PROJECT)
        # Add two tasks and persist
        project.add_task(Task("S1", "A1", "R1", "Not Started", "Low"))
        project.add_task(Task("S2", "A2", "R2", "Completed", "High"))

        # Load in a new Project instance and verify contents
        project2 = Project(self.TEST_PROJECT)
        vals = list(project2.iter_tasks())
        self.assertEqual(len(vals), 2)
        self.assertEqual([t.id for t in vals], [0, 1])
        self.assertEqual(vals[0].summary, "S1")
        self.assertEqual(vals[1].summary, "S2")
        self.assertEqual(project2.last_id, 1)

    def test_load_recomputes_last_id_and_persists(self):
        # Seed the database with non-sequential IDs and ensure last_id reflects max id
        Project(self.TEST_PROJECT)  # ensure table exists
        with ProjectTaskSession(self.TEST_PROJECT, db_path=self.db_path) as store:
            store.bulk_replace(
                self.TEST_PROJECT,
                [
                    {
                        "task_id": 5,
                        "summary": "A",
                        "assignee": "a",
                        "remarks": "",
                        "status": "Not Started",
                        "priority": "Low",
                    },
                    {
                        "task_id": 7,
                        "summary": "B",
                        "assignee": "b",
                        "remarks": "",
                        "status": "In Progress",
                        "priority": "Medium",
                    },
                ],
            )

        project = Project(self.TEST_PROJECT)
        self.assertEqual(project.last_id, 7)
        self.assertEqual(sorted(project._tasks_by_id.keys()), [5, 7])

    def test_edit_task_persists_to_database(self):
        project = Project(self.TEST_PROJECT)
        tid = project.add_task(Task("S", "A", "R", "Not Started", "Low"))
        updated = Task("S-edit", "A", "R", "Not Started", "Low")
        with StringIO() as buf, redirect_stdout(buf):
            project.edit_task(tid, updated)
        project_reloaded = Project(self.TEST_PROJECT)
        self.assertEqual(project_reloaded._tasks_by_id[tid].summary, "S-edit")


if __name__ == "__main__":
    unittest.main()
