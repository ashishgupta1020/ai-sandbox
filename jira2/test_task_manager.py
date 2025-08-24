import unittest
import os
import json
from io import StringIO
from contextlib import redirect_stdout
from jira2.task_manager import ProjectManager, Project, Task

class TestTaskManager(unittest.TestCase):
    TEST_PROJECT = "TestProject"
    CLI_PROJECT = "CliProject"
    PROJECT_A = "ProjectA"
    PROJECT_B = "ProjectB"
    PROJECT_C = "ProjectC"
    TEST_PROJECTS = [TEST_PROJECT, CLI_PROJECT, PROJECT_A, PROJECT_B, PROJECT_C]
    TEST_PROJECTS_FILE = ProjectManager.PROJECTS_FILE

    def setUp(self):
        # Clean up any test files before each test
        for project in self.TEST_PROJECTS:
            task_file = f"{project}_tasks.json"
            if os.path.exists(task_file):
                os.remove(task_file)
        if os.path.exists(self.TEST_PROJECTS_FILE):
            os.remove(self.TEST_PROJECTS_FILE)

    def tearDown(self):
        # Clean up any test files after each test
        for project in self.TEST_PROJECTS:
            task_file = f"{project}_tasks.json"
            if os.path.exists(task_file):
                os.remove(task_file)
        if os.path.exists(self.TEST_PROJECTS_FILE):
            os.remove(self.TEST_PROJECTS_FILE)

    def test_save_and_load_project_name(self):
        ProjectManager.save_project_name(self.TEST_PROJECT)
        projects = ProjectManager.load_project_names()
        self.assertIn(self.TEST_PROJECT, projects)

    def test_list_projects(self):
        # Add multiple projects
        ProjectManager.save_project_name(self.TEST_PROJECT)
        ProjectManager.save_project_name(self.PROJECT_A)
        expected_projects = [self.TEST_PROJECT, self.PROJECT_A]
        # Capture output
        with StringIO() as buf, redirect_stdout(buf):
            ProjectManager.list_projects()
            output = buf.getvalue()
        # Assert all project names are in output
        for project in expected_projects:
            self.assertIn(project, output)

    def test_list_projects_empty(self):
        # Ensure output is correct when no projects exist
        with StringIO() as buf, redirect_stdout(buf):
            ProjectManager.list_projects()
            output = buf.getvalue()
        self.assertIn("No projects found.", output)

    def test_add_and_list_task(self):
        project = Project(self.TEST_PROJECT)
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
        project = Project(self.TEST_PROJECT)
        # Ensure output is correct when no tasks exist
        with StringIO() as buf, redirect_stdout(buf):
            project.list_tasks()
            output = buf.getvalue()
        self.assertIn("No tasks found in this project.", output)

    def test_edit_task(self):
        project = Project(self.TEST_PROJECT)
        task = Task("Summary", "Assignee", "Remarks", "Not Started", "Low")
        project.add_task(task)
        # Prepare simulated user input for editing the task
        user_inputs = [
            "New Summary",      # new summary
            "New Assignee",    # new assignee
            "New Remarks",     # new remarks
            "3",               # new status (Completed)
            "2"                # new priority (Medium)
        ]
        def mock_input(prompt):
            return user_inputs.pop(0)
        # Patch input function using builtins module for Python 3 compatibility
        import builtins
        original_input = builtins.input
        builtins.input = mock_input
        try:
            project.edit_task(1)
        finally:
            builtins.input = original_input
        # Check that the task was updated as expected
        updated_task = project.tasks[0]
        self.assertEqual(updated_task.summary, "New Summary")
        self.assertEqual(updated_task.assignee, "New Assignee")
        self.assertEqual(updated_task.remarks, "New Remarks")
        self.assertEqual(updated_task.status, "Completed")
        self.assertEqual(updated_task.priority, "Medium")

    def test_edit_task_invalid_index(self):
        project = Project(self.TEST_PROJECT)
        # Add a task so index 2 is invalid
        project.add_task(Task("Summary", "Assignee", "Remarks", "Not Started", "Low"))
        with StringIO() as buf, redirect_stdout(buf):
            project.edit_task(2)
            output = buf.getvalue()
        self.assertIn("Invalid task index.", output)

    def test_task_serialization(self):
        task = Task("Summary", "Assignee", "Remarks", "Not Started", "Low")
        data = task.to_dict()
        new_task = Task.from_dict(data)
        self.assertEqual(task.summary, new_task.summary)
        self.assertEqual(task.assignee, new_task.assignee)
        self.assertEqual(task.remarks, new_task.remarks)
        self.assertEqual(task.status, new_task.status)
        self.assertEqual(task.priority, new_task.priority)

    def test_load_tasks_from_file_invalid_json(self):
        # Write invalid JSON to the task file
        task_file = f"{self.TEST_PROJECT}_tasks.json"
        with open(task_file, "w") as f:
            f.write("invalid json")
        project = Project(self.TEST_PROJECT)
        self.assertEqual(project.tasks, [])

    def test_save_project_name_duplicate(self):
        ProjectManager.save_project_name(self.TEST_PROJECT)
        ProjectManager.save_project_name(self.TEST_PROJECT)
        projects = ProjectManager.load_project_names()
        self.assertEqual(projects.count(self.TEST_PROJECT), 1)

    def test_main_cli_exit(self):
        # Simulate user input to exit from main menu
        import builtins
        user_inputs = ["3"]  # Choose 'Exit' immediately
        def mock_input(prompt):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from jira2 import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli()
                output = buf.getvalue()
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_invalid_choice(self):
        # Simulate invalid choice then exit
        import builtins
        user_inputs = ["99", "3"]  # Invalid, then exit
        def mock_input(prompt):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from jira2 import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli()
                output = buf.getvalue()
            self.assertIn("Invalid choice. Please try again.", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_open_project_and_exit(self):
        # Simulate opening a project and then exiting from project menu
        import builtins
        user_inputs = ["2", self.CLI_PROJECT, "6"]  # Open project, then exit
        def mock_input(prompt):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from jira2 import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli()
                output = buf.getvalue()
            self.assertIn(f"Opened project: '{self.CLI_PROJECT}'", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_add_list_edit_switch_exit(self):
        # Simulate full CLI flow: open, add, list, edit, switch, exit
        import builtins
        user_inputs = [
            "2", self.PROJECT_A,  # Open project
            "1", "Task1", "User1", "Remark1", "1", "1",  # Add task
            "2",  # List tasks
            "3", "1", "Task1 edited", "User1 edited", "Remark1 edited", "2", "2",  # Edit task
            "4",  # List all projects
            "5", self.PROJECT_B,  # Switch project
            "6"   # Exit
        ]
        def mock_input(prompt):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from jira2 import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli()
                output = buf.getvalue()
            self.assertIn(f"Opened project: '{self.PROJECT_A}'", output)
            self.assertIn(f"Task added successfully to project: '{self.PROJECT_A}'", output)
            self.assertIn(f"Tasks in project '{self.PROJECT_A}':", output)
            self.assertIn("Editing Task 1:", output)
            self.assertIn("Task updated successfully.", output)
            self.assertIn("Projects:", output)
            self.assertIn(f"Switched to project: '{self.PROJECT_B}'", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_edit_task_value_error(self):
        # Simulate ValueError when editing task index
        import builtins
        user_inputs = [
            "2", self.PROJECT_C,  # Open project
            "1", "Task2", "User2", "Remark2", "1", "1",  # Add task
            "3", "invalid", "6"  # Edit task with invalid index, then exit
        ]
        def mock_input(prompt):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from jira2 import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli()
                output = buf.getvalue()
            self.assertIn("Invalid input. Please enter a valid task index.", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

if __name__ == "__main__":
    unittest.main()
