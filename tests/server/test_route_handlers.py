"""Tests for route_handlers module.

These tests verify the handler functions in isolation, without needing
a full HTTP server. Each handler takes API instances and returns
(payload, status) tuples.
"""

import unittest
from unittest.mock import MagicMock, patch

from taskman.server.route_handlers import (
    GET_ROUTE_PATTERNS,
    POST_ROUTE_PATTERNS,
    aggregate_tasks,
    handle_add_project_tags,
    handle_assignees,
    handle_create_task,
    handle_delete_project,
    handle_delete_task,
    handle_edit_project_name,
    handle_get_project_tags,
    handle_health,
    handle_highlight_task,
    handle_highlights,
    handle_list_projects,
    handle_open_project,
    handle_project_tags,
    handle_project_tasks,
    handle_remove_project_tag,
    handle_tasks_list,
    handle_todo_add,
    handle_todo_archive,
    handle_todo_edit,
    handle_todo_list,
    handle_todo_mark,
    handle_update_task,
    is_valid_project_name,
)


class TestIsValidProjectName(unittest.TestCase):
    def test_valid_names(self):
        """Valid project names return True."""
        self.assertTrue(is_valid_project_name("Alpha"))
        self.assertTrue(is_valid_project_name("my-project"))
        self.assertTrue(is_valid_project_name("project_123"))
        self.assertTrue(is_valid_project_name("Project With Spaces"))

    def test_invalid_empty(self):
        """Empty or None names return False."""
        self.assertFalse(is_valid_project_name(""))
        self.assertFalse(is_valid_project_name(None))

    def test_invalid_traversal(self):
        """Path traversal sequences return False."""
        self.assertFalse(is_valid_project_name(".."))
        self.assertFalse(is_valid_project_name("../etc"))
        self.assertFalse(is_valid_project_name("foo/../bar"))

    def test_invalid_dotfile(self):
        """Dotfiles return False."""
        self.assertFalse(is_valid_project_name(".hidden"))
        self.assertFalse(is_valid_project_name(".git"))

    def test_invalid_slashes(self):
        """Names with slashes return False."""
        self.assertFalse(is_valid_project_name("foo/bar"))
        self.assertFalse(is_valid_project_name("path/to/project"))


class TestAggregateTasks(unittest.TestCase):
    def setUp(self):
        self.project_api = MagicMock()
        self.task_api = MagicMock()

    def test_empty_projects(self):
        """No projects returns empty list."""
        self.project_api.list_project_names.return_value = []
        result = aggregate_tasks(self.project_api, self.task_api)
        self.assertEqual(result, [])

    def test_aggregates_all_tasks(self):
        """Tasks from all projects are aggregated."""
        self.project_api.list_project_names.return_value = ["A", "B"]
        self.task_api.list_tasks.side_effect = [
            ({"tasks": [{"id": 1}, {"id": 2}]}, 200),
            ({"tasks": [{"id": 3}]}, 200),
        ]
        result = aggregate_tasks(self.project_api, self.task_api)
        self.assertEqual(len(result), 3)

    def test_filter_function(self):
        """Filter function excludes tasks."""
        self.project_api.list_project_names.return_value = ["A"]
        self.task_api.list_tasks.return_value = (
            {"tasks": [{"id": 1, "keep": True}, {"id": 2, "keep": False}]}, 200
        )
        result = aggregate_tasks(
            self.project_api, self.task_api,
            filter_fn=lambda t: t.get("keep")
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)

    def test_transform_function(self):
        """Transform function modifies tasks."""
        self.project_api.list_project_names.return_value = ["ProjectX"]
        self.task_api.list_tasks.return_value = ({"tasks": [{"id": 1}]}, 200)
        result = aggregate_tasks(
            self.project_api, self.task_api,
            transform_fn=lambda proj, task: {"project": proj, "task_id": task["id"]}
        )
        self.assertEqual(result, [{"project": "ProjectX", "task_id": 1}])

    def test_skips_failed_projects(self):
        """Projects with non-200 status are skipped."""
        self.project_api.list_project_names.return_value = ["A", "B"]
        self.task_api.list_tasks.side_effect = [
            ({"error": "not found"}, 404),
            ({"tasks": [{"id": 1}]}, 200),
        ]
        result = aggregate_tasks(self.project_api, self.task_api)
        self.assertEqual(len(result), 1)


class TestHandleHealth(unittest.TestCase):
    def test_returns_ok(self):
        """Health endpoint returns ok status."""
        payload, status = handle_health()
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")


class TestHandleListProjects(unittest.TestCase):
    def test_delegates_to_api(self):
        """Delegates to project API list_projects."""
        project_api = MagicMock()
        project_api.list_projects.return_value = ({"projects": ["A", "B"]}, 200)
        payload, status = handle_list_projects(project_api)
        self.assertEqual(status, 200)
        self.assertEqual(payload["projects"], ["A", "B"])
        project_api.list_projects.assert_called_once()


class TestHandleProjectTags(unittest.TestCase):
    def test_delegates_to_api(self):
        """Delegates to project API list_project_tags."""
        project_api = MagicMock()
        project_api.list_project_tags.return_value = ({"tagsByProject": {"A": ["x"]}}, 200)
        payload, status = handle_project_tags(project_api)
        self.assertEqual(status, 200)
        project_api.list_project_tags.assert_called_once()


class TestHandleAssignees(unittest.TestCase):
    def setUp(self):
        self.project_api = MagicMock()
        self.task_api = MagicMock()

    def test_deduplicates_case_insensitive(self):
        """Assignees are deduplicated case-insensitively."""
        self.project_api.list_project_names.return_value = ["A"]
        self.task_api.list_tasks.return_value = (
            {"tasks": [
                {"assignee": "Alice"},
                {"assignee": "ALICE"},
                {"assignee": "Bob"},
            ]}, 200
        )
        payload, status = handle_assignees(self.project_api, self.task_api)
        self.assertEqual(status, 200)
        # First occurrence is preserved
        self.assertEqual(len(payload["assignees"]), 2)
        self.assertIn("Alice", payload["assignees"])
        self.assertIn("Bob", payload["assignees"])

    def test_excludes_empty_assignees(self):
        """Empty assignees are excluded."""
        self.project_api.list_project_names.return_value = ["A"]
        self.task_api.list_tasks.return_value = (
            {"tasks": [{"assignee": "Alice"}, {"assignee": ""}, {"assignee": None}]}, 200
        )
        payload, status = handle_assignees(self.project_api, self.task_api)
        self.assertEqual(status, 200)
        self.assertEqual(payload["assignees"], ["Alice"])

    def test_sorted_case_insensitive(self):
        """Assignees are sorted case-insensitively."""
        self.project_api.list_project_names.return_value = ["A"]
        self.task_api.list_tasks.return_value = (
            {"tasks": [{"assignee": "zoe"}, {"assignee": "Alice"}, {"assignee": "bob"}]}, 200
        )
        payload, status = handle_assignees(self.project_api, self.task_api)
        self.assertEqual(status, 200)
        self.assertEqual(payload["assignees"], ["Alice", "bob", "zoe"])


class TestHandleTasksList(unittest.TestCase):
    def setUp(self):
        self.project_api = MagicMock()
        self.task_api = MagicMock()
        self.project_api.list_project_names.return_value = ["A"]
        self.task_api.list_tasks.return_value = (
            {"tasks": [
                {"id": 1, "summary": "S1", "assignee": "Alice", "status": "Done", "priority": "High"},
                {"id": 2, "summary": "S2", "assignee": "Bob", "status": "New", "priority": "Low"},
            ]}, 200
        )

    def test_returns_all_tasks_no_filter(self):
        """Returns all tasks when no filter is provided."""
        payload, status = handle_tasks_list(self.project_api, self.task_api, "")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["tasks"]), 2)

    def test_filters_by_assignee(self):
        """Filters tasks by assignee query param."""
        payload, status = handle_tasks_list(self.project_api, self.task_api, "assignee=alice")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["tasks"]), 1)
        self.assertEqual(payload["tasks"][0]["assignee"], "Alice")

    def test_includes_project_in_response(self):
        """Each task includes project name."""
        payload, status = handle_tasks_list(self.project_api, self.task_api, "")
        self.assertEqual(status, 200)
        for task in payload["tasks"]:
            self.assertEqual(task["project"], "A")

    def test_cross_project_aggregation(self):
        """Tasks from multiple projects are aggregated."""
        self.project_api.list_project_names.return_value = ["Alpha", "Beta"]
        self.task_api.list_tasks.side_effect = [
            ({"tasks": [
                {"id": 0, "summary": "S1", "assignee": "Alice", "status": "Not Started", "priority": "Low"},
                {"id": 1, "summary": "S2", "assignee": "Bob", "status": "Completed", "priority": "High"},
            ]}, 200),
            ({"tasks": [
                {"id": 0, "summary": "B1", "assignee": "Alice", "status": "In Progress", "priority": "Medium"},
            ]}, 200),
        ]
        payload, status = handle_tasks_list(self.project_api, self.task_api, "")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["tasks"]), 3)
        projects_seen = {t["project"] for t in payload["tasks"]}
        self.assertEqual(projects_seen, {"Alpha", "Beta"})
        for t in payload["tasks"]:
            self.assertIn("id", t)


class TestHandleHighlights(unittest.TestCase):
    def test_filters_highlighted_tasks(self):
        """Only returns tasks with highlight=True."""
        project_api = MagicMock()
        task_api = MagicMock()
        project_api.list_project_names.return_value = ["A"]
        task_api.list_tasks.return_value = (
            {"tasks": [
                {"id": 1, "summary": "S1", "highlight": True, "assignee": "", "status": "", "priority": ""},
                {"id": 2, "summary": "S2", "highlight": False, "assignee": "", "status": "", "priority": ""},
            ]}, 200
        )
        payload, status = handle_highlights(project_api, task_api)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["highlights"]), 1)
        self.assertEqual(payload["highlights"][0]["summary"], "S1")

    def test_includes_required_fields(self):
        """Highlighted tasks include all required fields."""
        project_api = MagicMock()
        task_api = MagicMock()
        project_api.list_project_names.return_value = ["Alpha", "Beta"]
        task_api.list_tasks.side_effect = [
            ({"tasks": [
                {"id": 0, "summary": "S1", "highlight": True, "assignee": "A1", "status": "Not Started", "priority": "Low"},
            ]}, 200),
            ({"tasks": [
                {"id": 0, "summary": "B1", "highlight": True, "assignee": "B1", "status": "In Progress", "priority": "Medium"},
            ]}, 200),
        ]
        payload, status = handle_highlights(project_api, task_api)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["highlights"]), 2)
        # Verify all required fields are present
        for h in payload["highlights"]:
            self.assertIn("id", h)
            self.assertIn("summary", h)
            self.assertIn("assignee", h)
            self.assertIn("status", h)
            self.assertIn("priority", h)
            self.assertIn("project", h)
        # Verify projects are correctly set
        projects = {h["project"] for h in payload["highlights"]}
        self.assertEqual(projects, {"Alpha", "Beta"})


class TestHandleTodoEndpoints(unittest.TestCase):
    def setUp(self):
        self.todo_api = MagicMock()

    def test_todo_list(self):
        """handle_todo_list delegates to API."""
        self.todo_api.list_todos.return_value = ({"items": []}, 200)
        payload, status = handle_todo_list(self.todo_api)
        self.assertEqual(status, 200)
        self.todo_api.list_todos.assert_called_once()

    def test_todo_archive(self):
        """handle_todo_archive delegates to API."""
        self.todo_api.list_archived_todos.return_value = ({"items": []}, 200)
        payload, status = handle_todo_archive(self.todo_api)
        self.assertEqual(status, 200)
        self.todo_api.list_archived_todos.assert_called_once()

    def test_todo_add(self):
        """handle_todo_add delegates to API."""
        self.todo_api.add_todo.return_value = ({"item": {"id": 1}}, 200)
        payload, status = handle_todo_add(self.todo_api, {"title": "Test"})
        self.assertEqual(status, 200)
        self.todo_api.add_todo.assert_called_once_with({"title": "Test"})

    def test_todo_add_none_body(self):
        """handle_todo_add with None body uses empty dict."""
        self.todo_api.add_todo.return_value = ({"item": {}}, 200)
        handle_todo_add(self.todo_api, None)
        self.todo_api.add_todo.assert_called_once_with({})

    def test_todo_mark(self):
        """handle_todo_mark delegates to API."""
        self.todo_api.mark_done.return_value = ({"done": True}, 200)
        payload, status = handle_todo_mark(self.todo_api, {"id": 1, "done": True})
        self.assertEqual(status, 200)
        self.todo_api.mark_done.assert_called_once()

    def test_todo_edit(self):
        """handle_todo_edit delegates to API."""
        self.todo_api.edit_todo.return_value = ({"item": {"id": 1}}, 200)
        payload, status = handle_todo_edit(self.todo_api, {"id": 1, "title": "New"})
        self.assertEqual(status, 200)
        self.todo_api.edit_todo.assert_called_once()


class TestHandleProjectTasks(unittest.TestCase):
    def test_decodes_url_and_delegates(self):
        """URL decodes project name and delegates to task API."""
        project_api = MagicMock()
        task_api = MagicMock()
        task_api.list_tasks.return_value = ({"project": "Alpha Beta", "tasks": []}, 200)
        payload, status = handle_project_tasks(project_api, task_api, "Alpha%20Beta")
        self.assertEqual(status, 200)
        task_api.list_tasks.assert_called_once()
        # Check the decoded name was passed
        call_args = task_api.list_tasks.call_args
        self.assertEqual(call_args[0][0], "Alpha Beta")

    def test_invalid_project_name_returns_400(self):
        """Invalid project name returns 400."""
        project_api = MagicMock()
        task_api = MagicMock()
        payload, status = handle_project_tasks(project_api, task_api, ".hidden")
        self.assertEqual(status, 400)
        self.assertIn("Invalid project name", payload["error"])
        task_api.list_tasks.assert_not_called()


class TestHandleGetProjectTags(unittest.TestCase):
    def test_decodes_url_and_delegates(self):
        """URL decodes project name and delegates to project API."""
        project_api = MagicMock()
        project_api.get_project_tags.return_value = ({"tags": ["a", "b"]}, 200)
        payload, status = handle_get_project_tags(project_api, "My%20Project")
        self.assertEqual(status, 200)
        project_api.get_project_tags.assert_called_once_with("My Project")

    def test_invalid_project_name_returns_400(self):
        """Invalid project name returns 400."""
        project_api = MagicMock()
        payload, status = handle_get_project_tags(project_api, ".hidden")
        self.assertEqual(status, 400)
        self.assertIn("Invalid project name", payload["error"])
        project_api.get_project_tags.assert_not_called()


class TestHandleOpenProject(unittest.TestCase):
    def test_delegates_to_api(self):
        """Delegates to project API open_project."""
        project_api = MagicMock()
        project_api.open_project.return_value = ({"ok": True, "currentProject": "Test"}, 200)
        payload, status = handle_open_project(project_api, {"name": "Test"})
        self.assertEqual(status, 200)
        project_api.open_project.assert_called_once_with("Test")

    def test_none_body(self):
        """None body passes None name to API."""
        project_api = MagicMock()
        project_api.open_project.return_value = ({"error": "Missing name"}, 400)
        handle_open_project(project_api, None)
        project_api.open_project.assert_called_once_with(None)


class TestHandleEditProjectName(unittest.TestCase):
    def test_delegates_to_api(self):
        """Delegates to project API edit_project_name."""
        project_api = MagicMock()
        project_api.edit_project_name.return_value = ({"ok": True}, 200)
        payload, status = handle_edit_project_name(project_api, {"old_name": "A", "new_name": "B"})
        self.assertEqual(status, 200)
        project_api.edit_project_name.assert_called_once_with("A", "B")

    def test_none_body_returns_400(self):
        """None body returns 400 error."""
        project_api = MagicMock()
        payload, status = handle_edit_project_name(project_api, None)
        self.assertEqual(status, 400)
        self.assertIn("error", payload)


class TestHandleDeleteProject(unittest.TestCase):
    def test_delegates_to_api(self):
        """Delegates to project API delete_project."""
        project_api = MagicMock()
        project_api.delete_project.return_value = ({"ok": True, "deleted": "Test"}, 200)
        payload, status = handle_delete_project(project_api, {"name": "Test"})
        self.assertEqual(status, 200)
        project_api.delete_project.assert_called_once_with("Test")

    def test_none_body_returns_400(self):
        """None body returns 400 error."""
        project_api = MagicMock()
        payload, status = handle_delete_project(project_api, None)
        self.assertEqual(status, 400)


class TestHandleUpdateTask(unittest.TestCase):
    def test_validates_project_name(self):
        """Invalid project names return 400."""
        task_api = MagicMock()
        payload, status = handle_update_task(task_api, "../etc", {"id": 1})
        self.assertEqual(status, 400)
        self.assertIn("Invalid project name", payload["error"])

    def test_none_body_returns_400(self):
        """None body returns 400."""
        task_api = MagicMock()
        payload, status = handle_update_task(task_api, "Test", None)
        self.assertEqual(status, 400)
        self.assertIn("Invalid JSON", payload["error"])

    def test_delegates_to_api(self):
        """Valid request delegates to task API."""
        task_api = MagicMock()
        task_api.update_task.return_value = ({"ok": True}, 200)
        payload, status = handle_update_task(task_api, "Test", {"id": 1, "fields": {}})
        self.assertEqual(status, 200)
        task_api.update_task.assert_called_once()


class TestHandleAddProjectTags(unittest.TestCase):
    def test_delegates_to_api(self):
        """Delegates to project API add_project_tags."""
        project_api = MagicMock()
        project_api.add_project_tags.return_value = ({"tags": ["a", "b"]}, 200)
        payload, status = handle_add_project_tags(project_api, "Test", {"tags": ["a", "b"]})
        self.assertEqual(status, 200)
        project_api.add_project_tags.assert_called_once()

    def test_none_body_returns_400(self):
        """None body returns 400."""
        project_api = MagicMock()
        payload, status = handle_add_project_tags(project_api, "Test", None)
        self.assertEqual(status, 400)

    def test_invalid_project_name_returns_400(self):
        """Invalid project name returns 400."""
        project_api = MagicMock()
        payload, status = handle_add_project_tags(project_api, ".hidden", {"tags": ["a"]})
        self.assertEqual(status, 400)
        self.assertIn("Invalid project name", payload["error"])
        project_api.add_project_tags.assert_not_called()


class TestHandleRemoveProjectTag(unittest.TestCase):
    def test_delegates_to_api(self):
        """Delegates to project API remove_project_tag."""
        project_api = MagicMock()
        project_api.remove_project_tag.return_value = ({"tags": ["a"]}, 200)
        payload, status = handle_remove_project_tag(project_api, "Test", {"tag": "b"})
        self.assertEqual(status, 200)
        project_api.remove_project_tag.assert_called_once()

    def test_none_body_returns_400(self):
        """None body returns 400."""
        project_api = MagicMock()
        payload, status = handle_remove_project_tag(project_api, "Test", None)
        self.assertEqual(status, 400)

    def test_invalid_project_name_returns_400(self):
        """Invalid project name returns 400."""
        project_api = MagicMock()
        payload, status = handle_remove_project_tag(project_api, ".hidden", {"tag": "a"})
        self.assertEqual(status, 400)
        self.assertIn("Invalid project name", payload["error"])
        project_api.remove_project_tag.assert_not_called()


class TestHandleHighlightTask(unittest.TestCase):
    def test_validates_project_name(self):
        """Invalid project names return 400."""
        task_api = MagicMock()
        payload, status = handle_highlight_task(task_api, ".hidden", {"id": 1, "highlight": True})
        self.assertEqual(status, 400)

    def test_requires_bool_highlight(self):
        """Non-boolean highlight value returns 400."""
        task_api = MagicMock()
        payload, status = handle_highlight_task(task_api, "Test", {"id": 1, "highlight": "yes"})
        self.assertEqual(status, 400)
        self.assertIn("Invalid highlight", payload["error"])

    def test_delegates_to_api(self):
        """Valid request delegates to task API update_task."""
        task_api = MagicMock()
        task_api.update_task.return_value = ({"ok": True, "task": {"highlight": True}}, 200)
        payload, status = handle_highlight_task(task_api, "Test", {"id": 1, "highlight": True})
        self.assertEqual(status, 200)
        task_api.update_task.assert_called_once()

    def test_exception_returns_500(self):
        """Exception in API returns 500."""
        task_api = MagicMock()
        task_api.update_task.side_effect = RuntimeError("boom")
        payload, status = handle_highlight_task(task_api, "Test", {"id": 1, "highlight": True})
        self.assertEqual(status, 500)
        self.assertIn("Failed to update highlight", payload["error"])


class TestHandleCreateTask(unittest.TestCase):
    def test_validates_project_name(self):
        """Invalid project names return 400."""
        task_api = MagicMock()
        payload, status = handle_create_task(task_api, "../etc", {})
        self.assertEqual(status, 400)

    def test_none_body_uses_empty_dict(self):
        """None body is treated as empty dict."""
        task_api = MagicMock()
        task_api.create_task.return_value = ({"ok": True, "id": 0}, 200)
        payload, status = handle_create_task(task_api, "Test", None)
        self.assertEqual(status, 200)
        task_api.create_task.assert_called_once_with("Test", {})

    def test_exception_returns_500(self):
        """Exception in API returns 500."""
        task_api = MagicMock()
        task_api.create_task.side_effect = RuntimeError("boom")
        payload, status = handle_create_task(task_api, "Test", {})
        self.assertEqual(status, 500)
        self.assertIn("Failed to create task", payload["error"])


class TestHandleDeleteTask(unittest.TestCase):
    def test_validates_project_name(self):
        """Invalid project names return 400."""
        task_api = MagicMock()
        payload, status = handle_delete_task(task_api, ".hidden", {"id": 0})
        self.assertEqual(status, 400)

    def test_delegates_to_api(self):
        """Valid request delegates to task API delete_task."""
        task_api = MagicMock()
        task_api.delete_task.return_value = ({"ok": True, "id": 0}, 200)
        payload, status = handle_delete_task(task_api, "Test", {"id": 0})
        self.assertEqual(status, 200)
        task_api.delete_task.assert_called_once()

    def test_exception_returns_500(self):
        """Exception in API returns 500."""
        task_api = MagicMock()
        task_api.delete_task.side_effect = RuntimeError("boom")
        payload, status = handle_delete_task(task_api, "Test", {"id": 0})
        self.assertEqual(status, 500)
        self.assertIn("Failed to delete task", payload["error"])


class TestRoutePatterns(unittest.TestCase):
    def test_post_route_patterns_match(self):
        """POST route patterns match expected paths."""
        test_cases = [
            ("/api/projects/test/tasks/update", "task_update"),
            ("/api/projects/my-project/tags/add", "tags_add"),
            ("/api/projects/123/tags/remove", "tags_remove"),
            ("/api/projects/foo/tasks/highlight", "task_highlight"),
            ("/api/projects/bar/tasks/create", "task_create"),
            ("/api/projects/baz/tasks/delete", "task_delete"),
        ]
        for path, expected_key in test_cases:
            matched = False
            for pattern, key in POST_ROUTE_PATTERNS:
                if pattern.match(path):
                    self.assertEqual(key, expected_key, f"Path {path} matched wrong key")
                    matched = True
                    break
            self.assertTrue(matched, f"Path {path} did not match any pattern")

    def test_get_route_patterns_match(self):
        """GET route patterns match expected paths."""
        test_cases = [
            ("/api/projects/test/tasks", "project_tasks"),
            ("/api/projects/my-project/tags", "project_tags"),
        ]
        for path, expected_key in test_cases:
            matched = False
            for pattern, key in GET_ROUTE_PATTERNS:
                if pattern.match(path):
                    self.assertEqual(key, expected_key, f"Path {path} matched wrong key")
                    matched = True
                    break
            self.assertTrue(matched, f"Path {path} did not match any pattern")

    def test_patterns_extract_project_name(self):
        """Route patterns correctly extract project name."""
        for pattern, _ in POST_ROUTE_PATTERNS:
            match = pattern.match("/api/projects/test-project/tasks/update")
            if match:
                self.assertEqual(match.group(1), "test-project")
                break


if __name__ == "__main__":
    unittest.main()
