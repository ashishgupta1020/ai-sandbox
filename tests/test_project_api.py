import shutil
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from taskman.config import get_data_store_dir, set_data_store_dir
from taskman.server.project_api import ProjectAPI


class TestProjectAPI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="taskman-project-api-"))
        self.orig_data_dir = get_data_store_dir()
        set_data_store_dir(self.tmpdir)
        self.api = ProjectAPI()

    def tearDown(self):
        set_data_store_dir(self.orig_data_dir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_open_and_list_projects(self):
        resp, status, canonical = self.api.open_project("Alpha")
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(canonical, "Alpha")

        names = self.api.list_project_names()
        self.assertEqual(names, ["Alpha"])

        payload, status = self.api.list_projects(current_project=None)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("projects"), ["Alpha"])
        self.assertIsNone(payload.get("currentProject"))

    def test_open_project_missing_name(self):
        resp, status, canonical = self.api.open_project("")
        self.assertEqual(status, 400)
        self.assertIsNone(canonical)
        self.assertIn("Missing", resp.get("error", ""))

    def test_edit_project_name_success_and_markdown_rename(self):
        self.api.open_project("OldProjectMD")
        cur = SimpleNamespace(name="OldProjectMD")
        old_md = self.api._markdown_file_path("OldProjectMD")
        old_md.write_text("# Tasks")

        resp, status, new_current = self.api.edit_project_name("OldProjectMD", "NewProjectMD", cur)
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(new_current, "NewProjectMD")

        self.assertFalse(old_md.exists())
        self.assertTrue(self.api._markdown_file_path("NewProjectMD").exists())
        names = self.api.list_project_names()
        self.assertIn("NewProjectMD", names)
        self.assertNotIn("OldProjectMD", names)

    def test_edit_project_name_conflict(self):
        self.api.open_project("Alpha")
        self.api.open_project("Beta")
        resp, status, _ = self.api.edit_project_name("Alpha", "Beta", None)
        self.assertEqual(status, 400)
        self.assertFalse(resp.get("ok"))
        names = set(self.api.list_project_names())
        self.assertIn("Alpha", names)
        self.assertIn("Beta", names)

    def test_add_remove_and_list_tags(self):
        self.api.open_project("Tagged")
        resp, status = self.api.add_project_tags("Tagged", ["one", "two"])
        self.assertEqual(status, 200)
        self.assertEqual(resp.get("tags"), ["one", "two"])

        resp_rm, status_rm = self.api.remove_project_tag("Tagged", "one")
        self.assertEqual(status_rm, 200)
        self.assertEqual(resp_rm.get("tags"), ["two"])

        resp_get, status_get = self.api.get_project_tags("Tagged")
        self.assertEqual(status_get, 200)
        self.assertEqual(resp_get.get("tags"), ["two"])

        # list_project_tags should include untagged projects with empty list
        self.api.open_project("Untagged")
        all_tags, status_all = self.api.list_project_tags()
        self.assertEqual(status_all, 200)
        tags_map = all_tags.get("tagsByProject") or {}
        self.assertEqual(tags_map.get("Tagged"), ["two"])
        self.assertEqual(tags_map.get("Untagged"), [])


if __name__ == "__main__":
    unittest.main()
