import unittest
import os
import shutil
from io import StringIO
from contextlib import redirect_stdout
from taskman.project_manager import ProjectManager

class TestProjectManager(unittest.TestCase):
    TEST_PROJECT = "TestProject"
    PROJECT_A = "ProjectA"
    BASE_DATA_DIR = os.path.expanduser("~/sandbox/data/ai-sandbox")
    TEST_DATA_DIR = os.path.join(BASE_DATA_DIR, "test")
    TEST_PROJECTS_FILE = os.path.join(TEST_DATA_DIR, "projects.json")

    def setUp(self):
        # Clean and create test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        os.makedirs(self.TEST_DATA_DIR, exist_ok=True)
        # Patch ProjectManager to use test directories and files
        self._orig_projects_file = ProjectManager.PROJECTS_FILE
        ProjectManager.PROJECTS_FILE = self.TEST_PROJECTS_FILE
        self._orig_projects_dir = ProjectManager.PROJECTS_DIR
        ProjectManager.PROJECTS_DIR = self.TEST_DATA_DIR

    def tearDown(self):
        # Clean up test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        # Restore original ProjectManager settings
        ProjectManager.PROJECTS_FILE = self._orig_projects_file
        ProjectManager.PROJECTS_DIR = self._orig_projects_dir

    def test_save_and_load_project_name(self):
        ProjectManager.save_project_name(self.TEST_PROJECT)
        projects = ProjectManager.load_project_names()
        self.assertIn(self.TEST_PROJECT, projects)

    def test_edit_project_name(self):
        old_name = "OldProject"
        new_name = "NewProject"
        ProjectManager.save_project_name(old_name)
        old_task_file = ProjectManager.get_task_file_path(old_name)
        with open(old_task_file, "w") as f:
            f.write("[]")
        self.assertTrue(os.path.exists(old_task_file))
        result = ProjectManager.edit_project_name(old_name, new_name)
        self.assertTrue(result)
        projects = ProjectManager.load_project_names()
        self.assertNotIn(old_name, projects)
        self.assertIn(new_name, projects)
        new_task_file = ProjectManager.get_task_file_path(new_name)
        self.assertFalse(os.path.exists(old_task_file))
        self.assertTrue(os.path.exists(new_task_file))

    def test_edit_project_name_non_existent(self):
        with StringIO() as buf, redirect_stdout(buf):
            result = ProjectManager.edit_project_name("NonExistent", "NewName")
            output = buf.getvalue()
        self.assertFalse(result)
        self.assertIn("Error: Project 'NonExistent' not found.", output)

    def test_edit_project_name_to_existing(self):
        project1 = "Project1"
        project2 = "Project2"
        ProjectManager.save_project_name(project1)
        ProjectManager.save_project_name(project2)
        with StringIO() as buf, redirect_stdout(buf):
            result = ProjectManager.edit_project_name(project1, project2)
            output = buf.getvalue()
        self.assertFalse(result)
        self.assertIn(f"Error: Project name '{project2}' already exists.", output)
        projects = ProjectManager.load_project_names()
        self.assertIn(project1, projects)
        self.assertIn(project2, projects)

    def test_edit_project_name_with_markdown_file(self):
        old_name, new_name = "OldProjectMD", "NewProjectMD"
        ProjectManager.save_project_name(old_name)
        old_md_file = ProjectManager.get_markdown_file_path(old_name)
        with open(old_md_file, "w") as f: f.write("# Tasks")
        ProjectManager.edit_project_name(old_name, new_name)
        new_md_file = ProjectManager.get_markdown_file_path(new_name)
        self.assertFalse(os.path.exists(old_md_file))
        self.assertTrue(os.path.exists(new_md_file))

    def test_save_project_name_duplicate(self):
        ProjectManager.save_project_name(self.TEST_PROJECT)
        ProjectManager.save_project_name(self.TEST_PROJECT)
        projects = ProjectManager.load_project_names()
        self.assertEqual(projects.count(self.TEST_PROJECT), 1)
