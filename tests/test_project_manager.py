import unittest
import os
import shutil
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
from taskman.server import sqlite_storage
from taskman.server.project_manager import ProjectManager

class TestProjectManager(unittest.TestCase):
    TEST_PROJECT = "TestProject"
    PROJECT_A = "ProjectA"
    BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "tmp_data", "project_manager")
    TEST_DATA_DIR = os.path.join(BASE_DATA_DIR, "test")

    def setUp(self):
        # Clean and create test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        os.makedirs(self.TEST_DATA_DIR, exist_ok=True)
        # Patch ProjectManager to use test directories and files
        self._orig_projects_dir = ProjectManager.PROJECTS_DIR
        ProjectManager.PROJECTS_DIR = self.TEST_DATA_DIR
        self._orig_default_dir = sqlite_storage._DEFAULT_DB_DIR
        sqlite_storage._DEFAULT_DB_DIR = Path(self.TEST_DATA_DIR)

    def tearDown(self):
        # Clean up test data directory
        if os.path.exists(self.TEST_DATA_DIR):
            shutil.rmtree(self.TEST_DATA_DIR)
        # Restore original ProjectManager settings
        ProjectManager.PROJECTS_DIR = self._orig_projects_dir
        sqlite_storage._DEFAULT_DB_DIR = self._orig_default_dir

    def test_save_and_load_project_name(self):
        saved = ProjectManager.save_project_name(self.TEST_PROJECT)
        self.assertEqual(saved, self.TEST_PROJECT)
        projects = ProjectManager.load_project_names()
        self.assertIn(self.TEST_PROJECT, projects)

    def test_edit_project_name(self):
        old_name = "OldProject"
        new_name = "NewProject"
        ProjectManager.save_project_name(old_name)
        result = ProjectManager.edit_project_name(old_name, new_name)
        self.assertTrue(result)
        projects = ProjectManager.load_project_names()
        self.assertNotIn(old_name, projects)
        self.assertIn(new_name, projects)

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

    def test_edit_project_name_same_name_ok(self):
        name = "SameNameProject"
        ProjectManager.save_project_name(name)
        # Renaming to the same name should be a no-op but succeed
        with StringIO() as buf, redirect_stdout(buf):
            result = ProjectManager.edit_project_name(name, name)
            output = buf.getvalue()
        self.assertTrue(result)
        projects = ProjectManager.load_project_names()
        self.assertEqual(projects.count(name), 1)

    def test_save_project_name_duplicate(self):
        first = ProjectManager.save_project_name(self.TEST_PROJECT)
        second = ProjectManager.save_project_name(self.TEST_PROJECT)
        projects = ProjectManager.load_project_names()
        self.assertEqual(projects.count(self.TEST_PROJECT), 1)
        self.assertEqual(first, self.TEST_PROJECT)
        self.assertEqual(second, self.TEST_PROJECT)

    def test_save_project_name_case_returns_canonical(self):
        canonical = ProjectManager.save_project_name("Alpha")
        self.assertEqual(canonical, "Alpha")
        again = ProjectManager.save_project_name("alpha")
        self.assertEqual(again, "Alpha")
        projects = ProjectManager.load_project_names()
        self.assertEqual(projects, ["Alpha"])
