import json
import unittest
import os
import shutil
from io import StringIO
from contextlib import redirect_stdout
import socket
import threading
import time
import http.client
from contextlib import closing
from pathlib import Path

from taskman.config import get_data_store_dir, set_data_store_dir
from taskman.server.project_api import ProjectAPI
from taskman.server.tasker_server import start_server


class _ServerThread:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.thread = threading.Thread(target=start_server, kwargs={"host": host, "port": port})
        self.thread.daemon = True

    def start(self):
        self.thread.start()
        deadline = time.time() + 3.0
        healthy = False
        while time.time() < deadline:
            try:
                with closing(http.client.HTTPConnection(self.host, self.port, timeout=0.25)) as conn:
                    conn.request("GET", "/health")
                    resp = conn.getresponse()
                    _ = resp.read()
                    if resp.status == 200:
                        healthy = True
                        break
            except Exception:
                time.sleep(0.05)
        if not healthy:
            raise AssertionError("UI server did not start in time for CLI tests")

    def stop(self):
        try:
            with closing(http.client.HTTPConnection(self.host, self.port, timeout=1)) as conn:
                conn.request("POST", "/api/exit", body=b"{}", headers={"Content-Type": "application/json"})
                _ = conn.getresponse()
        except Exception:
            pass
        self.thread.join(timeout=2)

class TestTaskManager(unittest.TestCase):
    TEST_PROJECT = "TestProject"
    CLI_PROJECT = "CliProject"
    PROJECT_A = "ProjectA"
    PROJECT_B = "ProjectB"
    PROJECT_C = "ProjectC"
    BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "tmp_data", "cli")
    TEST_DATA_DIR = os.path.join(BASE_DATA_DIR, "test")

    def setUp(self):
        # Clean and create test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        os.makedirs(self.TEST_DATA_DIR, exist_ok=True)
        # Patch data store path and config file for tests
        self._orig_data_dir = get_data_store_dir()
        self.config_path = Path(self.TEST_DATA_DIR) / "config.json"
        self.config_path.write_text(json.dumps({"DATA_STORE_PATH": str(Path(self.TEST_DATA_DIR).resolve())}))
        set_data_store_dir(Path(self.TEST_DATA_DIR))
        # Ensure any previous server on default port is stopped
        try:
            with closing(http.client.HTTPConnection("127.0.0.1", 8765, timeout=0.5)) as conn:
                conn.request("POST", "/api/exit", body=b"{}", headers={"Content-Type": "application/json"})
                _ = conn.getresponse()
                time.sleep(0.1)
        except Exception:
            pass
        # Start UI server (API) on default host:port used by CLI
        self._server = _ServerThread("127.0.0.1", 8765)
        self._server.start()

    def tearDown(self):
        # Clean up test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        # Restore original data store path
        set_data_store_dir(self._orig_data_dir)
        # Stop server
        if hasattr(self, "_server"):
            self._server.stop()

    def test_main_cli_exit(self):
        from unittest.mock import patch
        # Simulate user input to exit from main menu
        import builtins
        user_inputs = ["4"]  # Choose 'Exit' immediately
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_invalid_choice(self):
        from unittest.mock import patch
        # Simulate invalid choice then exit
        import builtins
        user_inputs = ["99", "4"]  # Invalid, then exit
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Invalid choice. Please try again.", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_menu_list_projects_empty(self):
        # With no projects, listing should say none
        import builtins
        user_inputs = ["1", "4"]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("No projects found.", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_menu_list_projects_with_entries(self):
        # Create a project via API and list it
        from taskman.client.api_client import TaskmanApiClient
        api = TaskmanApiClient()
        api.open_project(self.PROJECT_A)
        import builtins
        user_inputs = ["1", "4"]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Projects:", output)
            self.assertIn(self.PROJECT_A, output)
        finally:
            builtins.input = original_input

    def test_main_cli_open_project_and_exit(self):
        from unittest.mock import patch
        # Simulate opening a project and then exiting from project menu
        import builtins
        user_inputs = ["2", self.CLI_PROJECT, "9"]  # Open project, then exit
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn(f"Opened project: '{self.CLI_PROJECT}'", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_open_existing_project_from_list(self):
        from taskman.client.api_client import TaskmanApiClient
        api = TaskmanApiClient()
        api.open_project(self.PROJECT_A)
        api.open_project(self.PROJECT_B)
        import builtins
        user_inputs = ["2", "1", "9"]  # Open existing project via menu, then exit
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Select a project to open:", output)
            self.assertIn(f"Opened project: '{self.PROJECT_A}'", output)
        finally:
            builtins.input = original_input

    def test_main_cli_add_list_edit_switch_exit(self):
        from unittest.mock import patch
        # Simulate full CLI flow: open, add, list, edit, switch, exit
        import builtins
        user_inputs = [
            "2", self.PROJECT_A,  # Open project
            "1", "Task1", "User1", "Remark1", "", "1", "1",  # Add task
            "2",  # List tasks
            "4", "1", "Task1 edited", "User1 edited", "First line of remarks", "Second line with **markdown**", "", "2", "2",  # Edit task
            "2",  # List tasks after editing
            "7",  # List all projects
            "8", self.PROJECT_B,  # Switch project
            "9"   # Exit from project menu
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn(f"Opened project: '{self.PROJECT_A}'", output)
            self.assertIn(f"Task added successfully to project: '{self.PROJECT_A}'", output)
            self.assertIn(f"Tasks in project '{self.PROJECT_A}':", output)
            self.assertIn("Editing Task:", output)
            self.assertIn("Task updated successfully.", output)
            self.assertIn("Projects:", output)
            self.assertIn(f"Switched to project: '{self.PROJECT_B}'", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
            self.assertIn("First line of remarks", output)
            self.assertIn("Second line with **markdown**", output)
        finally:
            builtins.input = original_input

    def test_project_menu_sort_invalid_choice(self):
        # Open, add, then choose invalid sort option
        import builtins
        user_inputs = [
            "2", self.PROJECT_A,
            "1", "S", "A", "R", "", "2", "2",
            "3", "99", "1",  # invalid sort option, then pick Status
            "9"
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Invalid choice. Please try again.", output)
        finally:
            builtins.input = original_input

    def test_project_menu_edit_invalid_id_numeric(self):
        # Open, add 1 task, then try editing index 2
        import builtins
        user_inputs = [
            "2", self.PROJECT_A,
            "1", "S", "A", "R", "", "2", "2",
            "4", "2",  # invalid index (out of range)
            "9"
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Invalid task index.", output)
        finally:
            builtins.input = original_input

    def test_project_menu_rename_failure(self):
        # Create two projects, try renaming current to the other -> fail
        from taskman.client.api_client import TaskmanApiClient
        api = TaskmanApiClient()
        api.open_project(self.PROJECT_A)
        api.open_project(self.PROJECT_B)
        import builtins
        user_inputs = [
            "2", "1",  # open menu, select ProjectA from list
            "6", self.PROJECT_B,  # rename to existing B -> error
            "9"
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Error: Failed to rename project.", output)
        finally:
            builtins.input = original_input

    def test_project_menu_invalid_choice(self):
        # In project menu, choose invalid option then exit
        import builtins
        user_inputs = [
            "2", self.PROJECT_A,
            "99",  # invalid choice in project menu
            "9"
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Invalid choice. Please try again.", output)
        finally:
            builtins.input = original_input

    def test_main_menu_rename_no_projects(self):
        # Select rename from main menu when no projects exist
        import builtins
        user_inputs = ["3", "4"]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("No projects found.", output)
        finally:
            builtins.input = original_input

    def test_main_cli_edit_task_value_error(self):
        from unittest.mock import patch
        # Simulate ValueError when editing task index
        import builtins
        user_inputs = [
            "2", self.PROJECT_C,  # Open project
            "1", "Task2", "User2", "Remark2", "", "1", "1",  # Add task
            "4", "invalid", "9"  # Edit task with invalid index, then exit
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn("Invalid input. Please enter a valid task index.", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_export_tasks_to_markdown(self):
        from unittest.mock import patch
        # Simulate CLI: open project, add task, export to Markdown, exit
        import builtins
        user_inputs = [
            "2", self.CLI_PROJECT,  # Open project
            "1", "CLI Summary", "CLI Assignee", "CLI Remarks", "", "2", "2",    # Add task
            "5",    # Export to Markdown
            "9"     # Exit
        ]
        base = get_data_store_dir()
        base.mkdir(parents=True, exist_ok=True)
        expected_md_path = base / f"{self.CLI_PROJECT.lower()}_tasks_export.md"
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn(f"Tasks exported to Markdown file: '{expected_md_path}'", output)
            # Check that the file was created and contains expected Markdown
            self.assertTrue(os.path.exists(expected_md_path))
            with open(expected_md_path, "r") as f:
                md = f.read()
            self.assertIn("| Index | Summary | Assignee | Status | Priority | Remarks |", md)
            self.assertIn("CLI Summary", md)
            self.assertIn("CLI Assignee", md)
            self.assertIn("In Progress", md)
            self.assertIn("Medium", md)
            self.assertIn("CLI Remarks", md)
        finally:
            builtins.input = original_input
            if os.path.exists(expected_md_path):
                os.remove(expected_md_path)

    def test_main_cli_list_tasks_with_custom_sort(self):
        from unittest.mock import patch
        # Simulate CLI: open project, add tasks, list with custom sort by status, then by priority, then exit
        import builtins
        user_inputs = [
            "2", self.CLI_PROJECT,  # Open project
            "1", "Summary0", "Assignee0", "Remarks0", "", "2", "3",  # Add task 0 (In Progress, High)
            "1", "Summary1", "Assignee1", "Remarks1", "", "2", "1",  # Add task 1 (In Progress, Low)
            "1", "Summary2", "Assignee2", "Remarks2", "", "1", "2",  # Add task 2 (Not Started, Medium)
            "3", "1",  # List tasks with custom sort by Status
            "3", "2",  # List tasks with custom sort by Priority
            "9"   # Exit
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            # Check that all tasks are present
            self.assertIn("Summary0", output)
            self.assertIn("Summary1", output)
            self.assertIn("Summary2", output)
            # Check that sorting by Status puts 'Not Started' before 'In Progress'
            status_table = output.split("Sort by:")[1].split("Project Menu:")[0]
            not_started_index = status_table.find("Not Started")
            in_progress_index = status_table.find("In Progress")
            self.assertTrue(not_started_index < in_progress_index)
            # Check that sorting by Priority puts 'Low' before 'Medium' and 'High'
            priority_table = output.split("Sort by:")[2].split("Project Menu:")[0]
            low_index = priority_table.find("Low")
            medium_index = priority_table.find("Medium")
            high_index = priority_table.find("High")
            self.assertTrue(low_index < medium_index < high_index)
            # Ensure that some reordering has occurred (i.e., the first task is not always first)
            self.assertNotEqual(priority_table.find("Summary0"), 0)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

    def test_main_cli_edit_project_name_from_main_menu(self):
        from unittest.mock import patch
        import builtins
        # First, create a project "manually"
        ProjectAPI().open_project(self.PROJECT_A)
        # Simulate editing a project name from the main menu, then exiting
        user_inputs = [
            "3",  # Edit project name
            self.PROJECT_A,  # old name
            self.PROJECT_B,  # new name
            "4"  # Exit
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn(f"Project '{self.PROJECT_A}' has been renamed to '{self.PROJECT_B}'.", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
            names = ProjectAPI().list_project_names()
            self.assertIn(self.PROJECT_B, names)
            self.assertNotIn(self.PROJECT_A, names)
        finally:
            builtins.input = original_input

    def test_main_cli_edit_project_name_from_project_menu(self):
        from unittest.mock import patch
        import builtins
        # Simulate editing current project name from the project menu
        user_inputs = [
            "2", self.PROJECT_A,  # Open project A
            "6",  # Edit current project name
            self.PROJECT_B,  # new name
            "2",  # List tasks in new project
            "9"  # exit
        ]
        def mock_input(prompt=None):
            return user_inputs.pop(0)
        original_input = builtins.input
        builtins.input = mock_input
        from taskman.cli import task_manager
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(["--config", str(self.config_path)])
                output = buf.getvalue()
            self.assertIn(f"Opened project: '{self.PROJECT_A}'", output)
            self.assertIn(f"Project '{self.PROJECT_A}' has been renamed to '{self.PROJECT_B}'.", output)
            self.assertIn(f"Project renamed. Current project is now '{self.PROJECT_B}'.", output)
            self.assertIn(f"Current Project: {self.PROJECT_B}", output)
            self.assertIn(f"Listing tasks in project: '{self.PROJECT_B}'", output)
            self.assertIn("Exiting Task Manager. Goodbye!", output)
        finally:
            builtins.input = original_input

if __name__ == "__main__":
    unittest.main()
