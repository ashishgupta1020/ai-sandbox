#!/usr/bin/env python3
"""
Comprehensive unit tests for task_manager.py
"""

import unittest
import json
import os
import tempfile
import shutil
from datetime import datetime
from unittest.mock import patch, MagicMock

from task_manager import TaskManager
from models import Task, Priority, Status
from markdown_utils import render_markdown


class TestPriority(unittest.TestCase):
    """Test Priority enum"""
    
    def test_priority_values(self):
        """Test that all priority values are correct"""
        self.assertEqual(Priority.LOW.value, "Low")
        self.assertEqual(Priority.MEDIUM.value, "Medium")
        self.assertEqual(Priority.HIGH.value, "High")
        self.assertEqual(Priority.CRITICAL.value, "Critical")
    
    def test_priority_creation(self):
        """Test creating priorities from strings"""
        self.assertEqual(Priority("Low"), Priority.LOW)
        self.assertEqual(Priority("Medium"), Priority.MEDIUM)
        self.assertEqual(Priority("High"), Priority.HIGH)
        self.assertEqual(Priority("Critical"), Priority.CRITICAL)
    
    def test_invalid_priority(self):
        """Test that invalid priority raises ValueError"""
        with self.assertRaises(ValueError):
            Priority("Invalid")


class TestStatus(unittest.TestCase):
    """Test Status enum"""
    
    def test_status_values(self):
        """Test that all status values are correct"""
        self.assertEqual(Status.TODO.value, "To Do")
        self.assertEqual(Status.IN_PROGRESS.value, "In Progress")
        self.assertEqual(Status.REVIEW.value, "Review")
        self.assertEqual(Status.DONE.value, "Done")
        self.assertEqual(Status.BLOCKED.value, "Blocked")
        self.assertEqual(Status.CANCELLED.value, "Cancelled")
    
    def test_status_creation(self):
        """Test creating statuses from strings"""
        self.assertEqual(Status("To Do"), Status.TODO)
        self.assertEqual(Status("In Progress"), Status.IN_PROGRESS)
        self.assertEqual(Status("Review"), Status.REVIEW)
        self.assertEqual(Status("Done"), Status.DONE)
        self.assertEqual(Status("Blocked"), Status.BLOCKED)
        self.assertEqual(Status("Cancelled"), Status.CANCELLED)
    
    def test_invalid_status(self):
        """Test that invalid status raises ValueError"""
        with self.assertRaises(ValueError):
            Status("Invalid")


class TestTask(unittest.TestCase):
    """Test Task dataclass"""
    
    def test_task_creation(self):
        """Test creating a task with all fields"""
        task = Task(
            id="1",
            summary="Test task",
            assignee="Test User",
            remarks="Test remarks",
            priority=Priority.HIGH,
            tags=["test", "unit"],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            status=Status.TODO
        )
        
        self.assertEqual(task.id, "1")
        self.assertEqual(task.summary, "Test task")
        self.assertEqual(task.assignee, "Test User")
        self.assertEqual(task.remarks, "Test remarks")
        self.assertEqual(task.priority, Priority.HIGH)
        self.assertEqual(task.tags, ["test", "unit"])
        self.assertEqual(task.status, Status.TODO)
    
    def test_task_default_status(self):
        """Test that task gets default status if not provided"""
        task = Task(
            id="1",
            summary="Test task",
            assignee="Test User",
            remarks="Test remarks",
            priority=Priority.HIGH,
            tags=[],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )
        
        self.assertEqual(task.status, Status.TODO)


class TestRenderMarkdown(unittest.TestCase):
    """Test markdown rendering functionality"""
    
    def test_empty_text(self):
        """Test rendering empty text"""
        result = render_markdown("")
        self.assertEqual(result, "")
    
    def test_plain_text(self):
        """Test rendering plain text without markdown"""
        text = "This is plain text"
        result = render_markdown(text)
        self.assertEqual(result, text)
    
    def test_bold_text(self):
        """Test rendering bold text"""
        text = "This is **bold** text"
        result = render_markdown(text)
        self.assertIn("**bold**", result)
    
    def test_italic_text(self):
        """Test rendering italic text"""
        text = "This is *italic* text"
        result = render_markdown(text)
        self.assertIn("*italic*", result)
    
    def test_code_text(self):
        """Test rendering inline code"""
        text = "Use `console.log()` for debugging"
        result = render_markdown(text)
        self.assertIn("`console.log()`", result)
    
    def test_lists(self):
        """Test rendering lists"""
        text = "- Item 1\n- Item 2\n- Item 3"
        result = render_markdown(text)
        self.assertIn("• Item 1", result)
        self.assertIn("• Item 2", result)
        self.assertIn("• Item 3", result)
    
    def test_headers(self):
        """Test rendering headers"""
        text = "# Header 1\n## Header 2"
        result = render_markdown(text)
        self.assertIn("Header 1", result)
        self.assertIn("Header 2", result)
    
    @patch('markdown_utils.MARKDOWN_AVAILABLE', False)
    def test_markdown_not_available(self):
        """Test behavior when markdown library is not available"""
        text = "**bold** text"
        result = render_markdown(text)
        self.assertEqual(result, text)  # Should return original text


class TestTaskManager(unittest.TestCase):
    """Test TaskManager class"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_tasks.json")
        self.task_manager = TaskManager(self.test_file)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def test_init_empty_file(self):
        """Test initializing with empty file"""
        self.assertEqual(self.task_manager.projects, {})
    
    def test_init_existing_file(self):
        """Test initializing with existing data"""
        data = {
            "Test Project": {
                "1": {
                    "id": "1",
                    "summary": "Test task",
                    "assignee": "Test User",
                    "remarks": "Test remarks",
                    "priority": "High",
                    "tags": ["test"],
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "status": "To Do"
                }
            }
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(data, f)
        
        task_manager = TaskManager(self.test_file)
        self.assertIn("Test Project", task_manager.projects)
        self.assertIn("1", task_manager.projects["Test Project"])
    
    def test_create_project(self):
        """Test creating a new project"""
        result = self.task_manager.create_project("Test Project")
        self.assertTrue(result)
        self.assertIn("Test Project", self.task_manager.projects)
        self.assertEqual(len(self.task_manager.projects["Test Project"]), 0)
    
    def test_create_duplicate_project(self):
        """Test creating a duplicate project"""
        self.task_manager.create_project("Test Project")
        result = self.task_manager.create_project("Test Project")
        self.assertFalse(result)
    
    def test_list_projects_empty(self):
        """Test listing projects when none exist"""
        with patch('builtins.print') as mock_print:
            self.task_manager.list_projects()
            mock_print.assert_called_with("No projects found.")
    
    def test_list_projects_with_data(self):
        """Test listing projects with data"""
        self.task_manager.create_project("Project 1")
        self.task_manager.create_project("Project 2")
        
        with patch('builtins.print') as mock_print:
            self.task_manager.list_projects()
            # Should call print multiple times for header and projects
            self.assertGreater(mock_print.call_count, 1)
    
    def test_generate_task_id_first_task(self):
        """Test generating first task ID"""
        self.task_manager.create_project("Test Project")
        task_id = self.task_manager._generate_task_id("Test Project")
        self.assertEqual(task_id, "1")
    
    def test_generate_task_id_subsequent_tasks(self):
        """Test generating subsequent task IDs"""
        self.task_manager.create_project("Test Project")
        
        # Create some tasks
        self.task_manager.projects["Test Project"]["1"] = MagicMock()
        self.task_manager.projects["Test Project"]["2"] = MagicMock()
        
        task_id = self.task_manager._generate_task_id("Test Project")
        self.assertEqual(task_id, "3")
        
    def test_create_task(self):
        """Test creating a task"""
        self.task_manager.create_project("Test Project")
        
        result = self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.HIGH,
            ["test"]
        )
        
        self.assertTrue(result)
        self.assertIn("1", self.task_manager.projects["Test Project"])
        
        task = self.task_manager.projects["Test Project"]["1"]
        self.assertEqual(task.summary, "Test task")
        self.assertEqual(task.assignee, "Test User")
        self.assertEqual(task.priority, Priority.HIGH)
    
    def test_create_task_invalid_project(self):
        """Test creating task in non-existent project"""
        result = self.task_manager.create_task(
            "Non-existent Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.HIGH,
            ["test"]
        )
        
        self.assertFalse(result)
    
    def test_create_task_invalid_priority(self):
        """Test creating task with invalid priority"""
        self.task_manager.create_project("Test Project")
        result = self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            "Invalid Priority",  # Invalid priority
            ["test"]
        )
        self.assertFalse(result)

    def test_create_task_invalid_status(self):
        """Test creating task with invalid status"""
        self.task_manager.create_project("Test Project")
        result = self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.HIGH,
            ["test"],
            "Invalid Status"  # Invalid status
        )
        self.assertFalse(result)
    
    def test_list_tasks_empty_project(self):
        """Test listing tasks in empty project"""
        self.task_manager.create_project("Test Project")
        
        with patch('builtins.print') as mock_print:
            self.task_manager.list_tasks("Test Project")
            mock_print.assert_called_with("No tasks found in project 'Test Project'.")
    
    def test_list_tasks_with_data(self):
        """Test listing tasks with data"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Task 1",
            "User 1",
            "Remarks 1",
            Priority.HIGH,
            ["tag1"]
        )
        self.task_manager.create_task(
            "Test Project",
            "Task 2",
            "User 2",
            "Remarks 2",
            Priority.MEDIUM,
            ["tag2"]
        )
        
        with patch('builtins.print') as mock_print:
            self.task_manager.list_tasks("Test Project")
            # Should print header and tasks
            self.assertGreater(mock_print.call_count, 2)
    
    def test_list_tasks_with_filters(self):
        """Test listing tasks with filters"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Task 1",
            "John Doe",
            "Remarks 1",
            Priority.HIGH,
            ["auth"]
        )
        self.task_manager.create_task(
            "Test Project",
            "Task 2",
            "Jane Smith",
            "Remarks 2",
            Priority.MEDIUM,
            ["ui"]
        )
        
        # Filter by assignee
        with patch('builtins.print') as mock_print:
            self.task_manager.list_tasks("Test Project", {"assignee": "John"})
            # Should only show John's task
            self.assertGreater(mock_print.call_count, 1)
        
        # Filter by priority
        with patch('builtins.print') as mock_print:
            self.task_manager.list_tasks("Test Project", {"priority": Priority.HIGH})
            # Should only show high priority tasks
            self.assertGreater(mock_print.call_count, 1)
        
        # Filter by tags
        with patch('builtins.print') as mock_print:
            self.task_manager.list_tasks("Test Project", {"tags": ["auth"]})
            # Should only show tasks with auth tag
            self.assertGreater(mock_print.call_count, 1)
        
        # Filter by status
        with patch('builtins.print') as mock_print:
            self.task_manager.list_tasks("Test Project", {"status": Status.TODO})
            # Should only show tasks with TODO status
            self.assertGreater(mock_print.call_count, 1)
    
    def test_view_task(self):
        """Test viewing a specific task"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.HIGH,
            ["test"]
        )
        
        with patch('builtins.print') as mock_print:
            self.task_manager.view_task("Test Project", "1")
            # Should print task details
            self.assertGreater(mock_print.call_count, 5)
    
    def test_view_task_invalid_project(self):
        """Test viewing task in non-existent project"""
        with patch('builtins.print') as mock_print:
            self.task_manager.view_task("Non-existent Project", "1")
            mock_print.assert_called_with("Project 'Non-existent Project' does not exist.")
    
    def test_view_task_invalid_task(self):
        """Test viewing non-existent task"""
        self.task_manager.create_project("Test Project")
        
        with patch('builtins.print') as mock_print:
            self.task_manager.view_task("Test Project", "999")
            mock_print.assert_called_with("Task '999' does not exist in project 'Test Project'.")
    
    def test_update_task(self):
        """Test updating a task"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Original task",
            "Original User",
            "Original remarks",
            Priority.LOW,
            ["original"]
        )
        
        result = self.task_manager.update_task(
            "Test Project",
            "1",
            summary="Updated task",
            assignee="Updated User",
            priority=Priority.HIGH
        )
        
        self.assertTrue(result)
        
        task = self.task_manager.projects["Test Project"]["1"]
        self.assertEqual(task.summary, "Updated task")
        self.assertEqual(task.assignee, "Updated User")
        self.assertEqual(task.priority, Priority.HIGH)
    
    def test_update_task_invalid_priority(self):
        """Test updating task with invalid priority"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.LOW,
            ["test"]
        )
        
        result = self.task_manager.update_task(
            "Test Project",
            "1",
            priority="Invalid Priority"
        )
        
        self.assertFalse(result)
    
    def test_update_task_invalid_status(self):
        """Test updating task with invalid status"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.LOW,
            ["test"]
        )
        
        result = self.task_manager.update_task(
            "Test Project",
            "1",
            status="Invalid Status"
        )
        
        self.assertFalse(result)
    
    def test_delete_task(self):
        """Test deleting a task"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.HIGH,
            ["test"]
        )
        
        result = self.task_manager.delete_task("Test Project", "1")
        self.assertTrue(result)
        self.assertNotIn("1", self.task_manager.projects["Test Project"])
    
    def test_delete_project(self):
        """Test deleting a project"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.HIGH,
            ["test"]
        )
        
        result = self.task_manager.delete_project("Test Project")
        self.assertTrue(result)
        self.assertNotIn("Test Project", self.task_manager.projects)
    
    def test_save_and_load_data(self):
        """Test saving and loading data"""
        self.task_manager.create_project("Test Project")
        self.task_manager.create_task(
            "Test Project",
            "Test task",
            "Test User",
            "Test remarks",
            Priority.HIGH,
            ["test"]
        )
        
        # Save data
        self.task_manager._save_data()
        
        # Create new task manager and load data
        new_task_manager = TaskManager(self.test_file)
        
        self.assertIn("Test Project", new_task_manager.projects)
        self.assertIn("1", new_task_manager.projects["Test Project"])
        
        task = new_task_manager.projects["Test Project"]["1"]
        self.assertEqual(task.summary, "Test task")
        self.assertEqual(task.assignee, "Test User")
        self.assertEqual(task.priority, Priority.HIGH)
    
    def test_load_corrupted_data(self):
        """Test loading corrupted JSON data"""
        with open(self.test_file, 'w') as f:
            f.write("invalid json content")
        
        task_manager = TaskManager(self.test_file)
        self.assertEqual(task_manager.projects, {})
    
    def test_save_data_error_handling(self):
        """Test error handling during data save"""
        # Create a read-only directory to cause save error
        read_only_dir = tempfile.mkdtemp()
        os.chmod(read_only_dir, 0o444)  # Read-only
        
        test_file = os.path.join(read_only_dir, "test.json")
        task_manager = TaskManager(test_file)
        
        task_manager.create_project("Test Project")
        
        # This should not raise an exception
        task_manager._save_data()
        
        # Clean up
        os.chmod(read_only_dir, 0o755)
        shutil.rmtree(read_only_dir)


class TestInteractiveFunctions(unittest.TestCase):
    """Test interactive functions"""
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_interactive_create_task_success(self, mock_print, mock_input):
        """Test successful interactive task creation"""
        mock_input.side_effect = [
            "Test task",  # summary
            "Test User",  # assignee
            "",  # remarks (empty)
            "3",  # priority (High)
            "",  # tags (empty)
            "1"  # status (To Do)
        ]
        
        task_manager = TaskManager("test.json")
        task_manager.create_project("Test Project")
        
        from task_manager import interactive_create_task
        result = interactive_create_task(task_manager, "Test Project")
        
        self.assertTrue(result)
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_interactive_create_task_missing_summary(self, mock_print, mock_input):
        """Test interactive task creation with missing summary"""
        mock_input.return_value = ""
        
        task_manager = TaskManager("test.json")
        task_manager.create_project("Test Project")
        
        from task_manager import interactive_create_task
        result = interactive_create_task(task_manager, "Test Project")
        
        self.assertFalse(result)
    
    @patch('builtins.input')
    @patch('builtins.print')
    def test_interactive_create_task_missing_assignee(self, mock_print, mock_input):
        """Test interactive task creation with missing assignee"""
        mock_input.side_effect = [
            "Test task",  # summary
            ""  # assignee (empty)
        ]
        
        task_manager = TaskManager("test.json")
        task_manager.create_project("Test Project")
        
        from task_manager import interactive_create_task
        result = interactive_create_task(task_manager, "Test Project")
        
        self.assertFalse(result)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestPriority,
        TestStatus,
        TestTask,
        TestRenderMarkdown,
        TestTaskManager,
        TestInteractiveFunctions
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
    
    # Exit with appropriate code
    exit(len(result.failures) + len(result.errors))
