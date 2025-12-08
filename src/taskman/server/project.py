"""Taskman project model backed by SQLite.

This module exposes the ``Project`` class, the primary in-memory representation
of a Taskman project. Tasks are persisted in a lightweight SQLite database
(`taskman.db` under the configured data store path), enabling transactional
updates and concurrent-safe reads with a simple file-based deployment.

The class maintains an in-memory dict of :class:`taskman.server.task.Task` objects
for fast lookups and defers actual storage to the helpers in
``taskman.server.sqlite_storage``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

from .project_manager import ProjectManager
from .sqlite_storage import ProjectTaskSession
from .task import Task, TaskPriority, TaskStatus


class Project:
    """Model representing a single Taskman project persisted in SQLite."""

    def __init__(self, name: str) -> None:
        """Create a project view for ``name`` and load tasks from SQLite."""
        self.name = name
        self._tasks_by_id: Dict[int, Task] = {}
        self.last_id: int = -1
        self.markdown_file_path = ProjectManager.get_markdown_file_path(self.name)
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Hydrate in-memory task cache from the database."""
        with ProjectTaskSession(self.name) as store:
            rows = store.fetch_all(self.name)
        tasks: Dict[int, Task] = {}
        max_id = -1
        for row in rows:
            task = Task(
                row["summary"] or "",
                row.get("assignee") or "",
                row.get("remarks") or "",
                row["status"] or TaskStatus.NOT_STARTED.value,
                row["priority"] or TaskPriority.MEDIUM.value,
                bool(row.get("highlight")),
            )
            task.id = int(row["task_id"])
            tasks[task.id] = task
            max_id = max(max_id, task.id)
        self._tasks_by_id = tasks
        self.last_id = max_id

    def _persist_task(self, task: Task) -> None:
        """Write the provided task to SQLite (insert or update)."""
        with ProjectTaskSession(self.name) as store:
            store.upsert_task(
                self.name,
                {
                    "task_id": int(task.id),
                    "summary": task.summary,
                    "assignee": task.assignee,
                    "remarks": task.remarks,
                    "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
                    "priority": task.priority.value if isinstance(task.priority, TaskPriority) else str(task.priority),
                    "highlight": bool(getattr(task, "highlight", False)),
                },
            )

    def _delete_task(self, task_id: int) -> None:
        """Remove the task row identified by ``task_id`` from SQLite."""
        with ProjectTaskSession(self.name) as store:
            store.delete_task(self.name, int(task_id))

    def iter_tasks(self) -> Iterator[Task]:
        """Iterate over tasks currently loaded for this project."""
        return iter(self._tasks_by_id.values())

    def add_task(self, task: Task) -> int:
        """Assign a new ID, persist the task, and return the ID."""
        self.last_id = self.last_id if isinstance(self.last_id, int) else -1
        task.id = self.last_id + 1
        self.last_id = task.id
        self._tasks_by_id[int(task.id)] = task
        self._persist_task(task)
        return int(task.id)

    def edit_task(self, task_id: int, new_task: Task) -> None:
        """Replace an existing task by ID with ``new_task`` and persist."""
        if int(task_id) not in self._tasks_by_id:
            print("Invalid task id.")
            return
        new_task.id = int(task_id)
        self._tasks_by_id[int(task_id)] = new_task
        self._persist_task(new_task)
        print("Task updated successfully.")

    def update_task_from_payload(self, payload: dict) -> tuple[dict, int]:
        """Patch fields of a task via API payload semantics."""
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        try:
            tid = int(payload.get("id", -1))
        except (TypeError, ValueError):
            return {"error": "'id' must be an integer"}, 400

        fields = payload.get("fields")
        if not isinstance(fields, dict) or not fields:
            return {"error": "'fields' must be a non-empty object"}, 400

        task = self._tasks_by_id.get(tid)
        if task is None:
            return {"error": "Task not found"}, 400

        allowed = {"id", "summary", "assignee", "remarks", "status", "priority", "highlight"}
        extra = set(fields) - allowed
        if extra:
            return {"error": "Unknown fields present"}, 400

        # Validate enum fields early so we fail fast without partial updates
        enum_fields = {"status": TaskStatus, "priority": TaskPriority}
        for key, enum_cls in enum_fields.items():
            if key in fields:
                try:
                    fields[key] = enum_cls(fields[key])  # type: ignore[arg-type]
                except Exception:
                    return {"error": f"Invalid {key}"}, 400

        if "highlight" in fields and not isinstance(fields["highlight"], bool):
            return {"error": "Invalid highlight"}, 400

        for attr in ("summary", "assignee", "remarks"):
            if attr in fields:
                value = fields[attr]
                setattr(task, attr, str(value) if value is not None else "")
        if "status" in fields:
            task.status = fields["status"]
        if "priority" in fields:
            task.priority = fields["priority"]
        if "highlight" in fields:
            task.highlight = fields["highlight"]

        try:
            self._persist_task(task)
        except Exception as exc:
            return {"error": f"Failed to save: {exc}"}, 500

        return {"ok": True, "id": tid, "task": task.to_dict()}, 200

    def create_task_from_payload(self, payload: Optional[dict]) -> Tuple[dict, int]:
        """Create a task from API payload, mirroring REST handler behaviour."""
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400

        summary = str(payload.get("summary", ""))
        assignee = str(payload.get("assignee", ""))
        remarks = str(payload.get("remarks", ""))
        status_val = payload.get("status", TaskStatus.NOT_STARTED.value)
        priority_val = payload.get("priority", TaskPriority.MEDIUM.value)
        highlight_raw = payload.get("highlight", False)
        highlight_val = highlight_raw if isinstance(highlight_raw, bool) else False

        try:
            TaskStatus(status_val)  # type: ignore[arg-type]
        except Exception:
            status_val = TaskStatus.NOT_STARTED.value
        try:
            TaskPriority(priority_val)  # type: ignore[arg-type]
        except Exception:
            priority_val = TaskPriority.MEDIUM.value

        new_task = Task(summary, assignee, remarks, status_val, priority_val, highlight_val)
        try:
            self.add_task(new_task)
        except Exception as exc:
            return {"error": f"Failed to save: {exc}"}, 500

        return {"ok": True, "id": new_task.id, "task": new_task.to_dict()}, 200

    def delete_task_from_payload(self, payload: Optional[dict]) -> Tuple[dict, int]:
        """Delete a task via API payload, syncing the database."""
        if payload is None or not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        try:
            tid = int(payload.get("id", -1))
        except (TypeError, ValueError):
            return {"error": "'id' must be an integer"}, 400
        if tid not in self._tasks_by_id:
            return {"error": "Task not found"}, 400

        removed = self._tasks_by_id.pop(tid, None)
        if removed is None:
            return {"error": "Task not found"}, 400
        try:
            self._delete_task(tid)
        except Exception as exc:
            return {"error": f"Failed to save: {exc}"}, 500
        return {"ok": True, "id": tid, "task": removed.to_dict()}, 200
