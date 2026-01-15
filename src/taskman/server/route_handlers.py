"""
Route handlers for the Taskman HTTP server.

This module contains all the handler functions for GET and POST routes,
extracted from the main request handler for better organization and testability.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote

from .project_api import ProjectAPI
from .task_api import TaskAPI
from .todo import TodoAPI


# Type aliases for clarity
JsonResponse = Tuple[Dict[str, Any], int]
LogWarningFn = Callable[[str], None]


def is_valid_project_name(name: Optional[str]) -> bool:
    """
    Validate a project name for safety.

    Returns False if the name is empty, contains path traversal sequences,
    starts with a dot, or contains slashes.
    """
    if not name:
        return False
    if ".." in name or name.startswith(".") or "/" in name:
        return False
    return True


def aggregate_tasks(
    project_api: ProjectAPI,
    task_api: TaskAPI,
    filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    transform_fn: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Iterate all tasks across projects, optionally filtering and transforming.

    Args:
        project_api: The project API instance.
        task_api: The task API instance.
        filter_fn: Optional function to filter tasks. Receives a task dict,
                   returns True to include it.
        transform_fn: Optional function to transform tasks. Receives
                      (project_name, task_dict), returns transformed dict.

    Returns:
        List of tasks (filtered and/or transformed).
    """
    results: List[Dict[str, Any]] = []
    projects = project_api.list_project_names()

    for project_name in projects:
        payload, status = task_api.list_tasks(project_name)
        if status != 200:
            continue

        for task in payload.get("tasks", []):
            # Apply filter if provided
            if filter_fn and not filter_fn(task):
                continue

            # Apply transform if provided, otherwise use task as-is
            if transform_fn:
                results.append(transform_fn(project_name, task))
            else:
                results.append(task)

    return results


# GET route handlers


def handle_health() -> JsonResponse:
    """Handle GET /health - basic health check."""
    return {"status": "ok"}, 200


def handle_list_projects(project_api: ProjectAPI) -> JsonResponse:
    """Handle GET /api/projects - list all project names."""
    return project_api.list_projects()


def handle_project_tags(project_api: ProjectAPI) -> JsonResponse:
    """Handle GET /api/project-tags - map of all project tags."""
    return project_api.list_project_tags()


def handle_assignees(project_api: ProjectAPI, task_api: TaskAPI) -> JsonResponse:
    """Handle GET /api/assignees - list unique assignees across all projects."""
    try:
        def extract_assignee(_project_name: str, task: Dict[str, Any]) -> Optional[str]:
            assignee = (task.get("assignee", "") or "").strip()
            return assignee if assignee else None

        # Extract all assignees, filter out None values, then dedupe
        all_assignees = aggregate_tasks(
            project_api, task_api, transform_fn=extract_assignee
        )
        # Dedupe case-insensitively while preserving original casing
        seen: Dict[str, str] = {}
        for assignee in all_assignees:
            if assignee is not None:
                key = assignee.lower()
                if key not in seen:
                    seen[key] = assignee

        # Sort case-insensitively for predictable UI ordering
        sorted_assignees = sorted(seen.values(), key=lambda s: s.lower())
        return {"assignees": sorted_assignees}, 200

    except Exception as e:
        return {"error": f"Failed to fetch assignees: {e}"}, 500


def handle_tasks_list(
    project_api: ProjectAPI,
    task_api: TaskAPI,
    query_string: str,
) -> JsonResponse:
    """Handle GET /api/tasks - list tasks filtered by assignee."""
    try:
        qs = parse_qs(query_string or "")
        raw_assignees = qs.get("assignee", [])
        wanted = {a.strip().lower() for a in raw_assignees if a and a.strip()}

        def filter_by_assignee(task: Dict[str, Any]) -> bool:
            if not wanted:
                return True  # No filter, include all
            assignee = (task.get("assignee", "") or "").strip()
            return assignee.lower() in wanted

        def transform_task(project_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "project": project_name,
                "id": task.get("id"),
                "summary": task.get("summary", ""),
                "assignee": (task.get("assignee", "") or "").strip(),
                "status": task.get("status", ""),
                "priority": task.get("priority", ""),
            }

        tasks = aggregate_tasks(
            project_api, task_api,
            filter_fn=filter_by_assignee,
            transform_fn=transform_task,
        )
        return {"tasks": tasks}, 200

    except Exception as e:
        return {"error": f"Failed to fetch tasks: {e}"}, 500


def handle_highlights(project_api: ProjectAPI, task_api: TaskAPI) -> JsonResponse:
    """Handle GET /api/highlights - aggregate highlighted tasks across projects."""
    try:
        def filter_highlighted(task: Dict[str, Any]) -> bool:
            return bool(task.get("highlight"))

        def transform_task(project_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "project": project_name,
                "id": task.get("id"),
                "summary": task.get("summary", ""),
                "assignee": task.get("assignee", "") or "",
                "status": task.get("status", ""),
                "priority": task.get("priority", ""),
            }

        highlights = aggregate_tasks(
            project_api, task_api,
            filter_fn=filter_highlighted,
            transform_fn=transform_task,
        )
        return {"highlights": highlights}, 200

    except Exception as e:
        return {"error": f"Failed to fetch highlights: {e}"}, 500


def handle_todo_list(todo_api: TodoAPI) -> JsonResponse:
    """Handle GET /api/todo - list todo items."""
    return todo_api.list_todos()


def handle_todo_archive(todo_api: TodoAPI) -> JsonResponse:
    """Handle GET /api/todo/archive - list archived todo items."""
    return todo_api.list_archived_todos()


def handle_project_tasks(
    project_api: ProjectAPI,
    task_api: TaskAPI,
    project_name: str,
    log_warning: Optional[LogWarningFn] = None,
) -> JsonResponse:
    """Handle GET /api/projects/<name>/tasks - list tasks for a project."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400
    return task_api.list_tasks(name, log_warning=log_warning)


def handle_get_project_tags(project_api: ProjectAPI, project_name: str) -> JsonResponse:
    """Handle GET /api/projects/<name>/tags - get tags for a project."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400
    return project_api.get_project_tags(name)


# POST route handlers


def handle_open_project(project_api: ProjectAPI, body: Optional[Dict]) -> JsonResponse:
    """Handle POST /api/projects/open - open/create a project."""
    return project_api.open_project(body.get("name") if body is not None else None)


def handle_edit_project_name(project_api: ProjectAPI, body: Optional[Dict]) -> JsonResponse:
    """Handle POST /api/projects/edit-name - rename a project."""
    if body is None:
        return {"error": "Invalid JSON"}, 400
    return project_api.edit_project_name(body.get("old_name"), body.get("new_name"))


def handle_delete_project(project_api: ProjectAPI, body: Optional[Dict]) -> JsonResponse:
    """Handle POST /api/projects/delete - delete a project."""
    if body is None:
        return {"error": "Invalid JSON"}, 400
    return project_api.delete_project(body.get("name"))


def handle_update_task(
    task_api: TaskAPI,
    project_name: str,
    body: Optional[Dict],
) -> JsonResponse:
    """Handle POST /api/projects/<name>/tasks/update - update a task."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400
    if body is None:
        return {"error": "Invalid JSON"}, 400
    if not isinstance(body, dict):
        return {"error": "Invalid payload"}, 400
    return task_api.update_task(name, body)


def handle_add_project_tags(
    project_api: ProjectAPI,
    project_name: str,
    body: Optional[Dict],
) -> JsonResponse:
    """Handle POST /api/projects/<name>/tags/add - add tags to a project."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400
    if body is None or not isinstance(body, dict):
        return {"error": "Invalid payload"}, 400
    return project_api.add_project_tags(name, body.get("tags"))


def handle_remove_project_tag(
    project_api: ProjectAPI,
    project_name: str,
    body: Optional[Dict],
) -> JsonResponse:
    """Handle POST /api/projects/<name>/tags/remove - remove a tag from a project."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400
    if body is None or not isinstance(body, dict):
        return {"error": "Invalid payload"}, 400
    return project_api.remove_project_tag(name, body.get("tag"))


def handle_highlight_task(
    task_api: TaskAPI,
    project_name: str,
    body: Optional[Dict],
) -> JsonResponse:
    """Handle POST /api/projects/<name>/tasks/highlight - toggle task highlight."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400
    if body is None or not isinstance(body, dict):
        return {"error": "Invalid payload"}, 400

    highlight_val = body.get("highlight")
    if not isinstance(highlight_val, bool):
        return {"error": "Invalid highlight"}, 400

    try:
        return task_api.update_task(
            name, {"id": body.get("id"), "fields": {"highlight": highlight_val}}
        )
    except Exception as e:
        return {"error": f"Failed to update highlight: {e}"}, 500


def handle_create_task(
    task_api: TaskAPI,
    project_name: str,
    body: Optional[Dict],
) -> JsonResponse:
    """Handle POST /api/projects/<name>/tasks/create - create a new task."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400

    # Treat invalid JSON as empty object
    if body is None:
        body = {}

    try:
        return task_api.create_task(name, body)
    except Exception as e:
        return {"error": f"Failed to create task: {e}"}, 500


def handle_delete_task(
    task_api: TaskAPI,
    project_name: str,
    body: Optional[Dict],
) -> JsonResponse:
    """Handle POST /api/projects/<name>/tasks/delete - delete a task."""
    name = unquote(project_name)
    if not is_valid_project_name(name):
        return {"error": "Invalid project name"}, 400

    try:
        return task_api.delete_task(name, body)
    except Exception as e:
        return {"error": f"Failed to delete task: {e}"}, 500


def handle_todo_add(todo_api: TodoAPI, body: Optional[Dict]) -> JsonResponse:
    """Handle POST /api/todo/add - create a todo item."""
    return todo_api.add_todo(body if body is not None else {})


def handle_todo_mark(todo_api: TodoAPI, body: Optional[Dict]) -> JsonResponse:
    """Handle POST /api/todo/mark - mark todo done/undone."""
    return todo_api.mark_done(body if body is not None else {})


def handle_todo_edit(todo_api: TodoAPI, body: Optional[Dict]) -> JsonResponse:
    """Handle POST /api/todo/edit - edit a todo item."""
    return todo_api.edit_todo(body if body is not None else {})


# Route pattern definitions for POST endpoints
# Each tuple is (compiled_regex, handler_key)
POST_ROUTE_PATTERNS = [
    (re.compile(r"^/api/projects/([^/]+)/tasks/update$"), "task_update"),
    (re.compile(r"^/api/projects/([^/]+)/tags/add$"), "tags_add"),
    (re.compile(r"^/api/projects/([^/]+)/tags/remove$"), "tags_remove"),
    (re.compile(r"^/api/projects/([^/]+)/tasks/highlight$"), "task_highlight"),
    (re.compile(r"^/api/projects/([^/]+)/tasks/create$"), "task_create"),
    (re.compile(r"^/api/projects/([^/]+)/tasks/delete$"), "task_delete"),
]

# Route pattern definitions for GET endpoints with path parameters
GET_ROUTE_PATTERNS = [
    (re.compile(r"^/api/projects/([^/]+)/tasks$"), "project_tasks"),
    (re.compile(r"^/api/projects/([^/]+)/tags$"), "project_tags"),
]
