import shutil
import tempfile
import unittest
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
        resp, status = self.api.open_project("Alpha")
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(resp.get("currentProject"), "Alpha")

        names = self.api.list_project_names()
        self.assertEqual(names, ["Alpha"])

        payload, status = self.api.list_projects()
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("projects"), ["Alpha"])
        self.assertNotIn("currentProject", payload)

    def test_open_project_missing_name(self):
        resp, status = self.api.open_project("")
        self.assertEqual(status, 400)
        self.assertIn("Missing", resp.get("error", ""))

    def test_edit_project_name_success_and_markdown_rename(self):
        self.api.open_project("OldProjectMD")
        old_md = self.api._markdown_file_path("OldProjectMD")
        old_md.write_text("# Tasks")

        resp, status = self.api.edit_project_name("OldProjectMD", "NewProjectMD")
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(resp.get("currentProject"), "NewProjectMD")

        self.assertFalse(old_md.exists())
        self.assertTrue(self.api._markdown_file_path("NewProjectMD").exists())
        names = self.api.list_project_names()
        self.assertIn("NewProjectMD", names)
        self.assertNotIn("OldProjectMD", names)

    def test_edit_project_name_conflict(self):
        self.api.open_project("Alpha")
        self.api.open_project("Beta")
        resp, status = self.api.edit_project_name("Alpha", "Beta")
        self.assertEqual(status, 400)
        self.assertFalse(resp.get("ok"))
        names = set(self.api.list_project_names())
        self.assertIn("Alpha", names)
        self.assertIn("Beta", names)

    def test_list_project_names_case_insensitive(self):
        self.api.open_project("Alpha")
        self.api.open_project("Bravo")
        lowered = self.api.list_project_names(case_insensitive=True)
        self.assertEqual(lowered, ["alpha", "bravo"])

    def test_list_project_tags_error_handling(self):
        class BoomStore:
            def __enter__(self):
                raise RuntimeError("boom tags")

            def __exit__(self, exc_type, exc, tb):
                return False

        api = ProjectAPI(store_factory=lambda: BoomStore())
        resp, status = api.list_project_tags()
        self.assertEqual(status, 500)
        self.assertIn("Failed to fetch project tags", resp.get("error", ""))

    def test_project_tags_invalid_inputs(self):
        resp, status = self.api.get_project_tags("..")
        self.assertEqual(status, 400)
        resp2, status2 = self.api.add_project_tags("", [])
        self.assertEqual(status2, 400)
        resp3, status3 = self.api.add_project_tags("Alpha", [])
        self.assertEqual(status3, 400)
        resp4, status4 = self.api.remove_project_tag("..", "x")
        self.assertEqual(status4, 400)
        resp5, status5 = self.api.remove_project_tag("Alpha", "")
        self.assertEqual(status5, 400)

    def test_open_project_error_bubble(self):
        class BoomStore:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def upsert_project_name(self, name):
                raise RuntimeError("db down")

        api = ProjectAPI(store_factory=lambda: BoomStore())
        resp, status = api.open_project("Alpha")
        self.assertEqual(status, 500)
        self.assertIn("db down", resp.get("error", ""))

    def test_edit_project_name_rename_markdown_failure_nonfatal(self):
        self.api.open_project("OldName")
        old_md = self.api._markdown_file_path("OldName")
        old_md.write_text("content")
        with unittest.mock.patch.object(Path, "rename", side_effect=OSError("nope")):
            resp, status = self.api.edit_project_name("OldName", "NewName")
        self.assertEqual(status, 200)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(resp.get("currentProject"), "NewName")

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
