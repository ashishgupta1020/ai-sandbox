from __future__ import annotations

"""API-style helper for task CRUD operations backed by TaskStore."""

from typing import Callable, Dict, Optional, Tuple

from .task_store import TaskStore
from .task import Task, TaskPriority, TaskStatus


class TaskAPI:
    """Encapsulate task CRUD for HTTP handlers without holding in-memory state."""

    def __init__(self, store_factory: Optional[Callable[[], TaskStore]] = None) -> None:
        self._store_factory = store_factory or (lambda: TaskStore())

    @staticmethod
    def _invalid_name(name: str) -> bool:
        return (not name) or (".." in name) or name.startswith(".") or ("/" in name)

    @staticmethod
    def _row_to_task(row: Dict[str, object]) -> Dict[str, object]:
        """Normalize a TaskStore row into a task dict, validating enums."""
        status_val = row.get("status") or TaskStatus.NOT_STARTED.value
        priority_val = row.get("priority") or TaskPriority.MEDIUM.value
        task_id = row.get("task_id")
        tid = int(task_id) if task_id is not None else None
        task = Task(
            row.get("summary") or "",
            row.get("assignee") or "",
            row.get("remarks") or "",
            status_val,
            priority_val,
            bool(row.get("highlight")),
            id=tid,
        )
        return task.to_dict()

    def list_tasks(
        self, project_name: str, log_warning: Optional[Callable[[str], None]] = None
    ) -> Tuple[Dict[str, object], int]:
        if self._invalid_name(project_name):
            return {"error": "Invalid project name"}, 400
        try:
            with self._store_factory() as store:
                rows = store.fetch_all(project_name)
            tasks = [self._row_to_task(r) for r in rows]
        except Exception as exc:
            if log_warning:
                try:
                    log_warning(f"Failed loading tasks for project '{project_name}': {exc}")
                except Exception:
                    pass
            tasks = []
        return {"project": project_name, "tasks": tasks}, 200

    def update_task(self, project_name: str, payload: object) -> Tuple[Dict[str, object], int]:
        if self._invalid_name(project_name):
            return {"error": "Invalid project name"}, 400
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        try:
            task_id = int(payload.get("id", -1))
        except (TypeError, ValueError):
            return {"error": "'id' must be an integer"}, 400
        fields = payload.get("fields")
        if not isinstance(fields, dict) or not fields:
            return {"error": "'fields' must be a non-empty object"}, 400
        allowed = {"id", "summary", "assignee", "remarks", "status", "priority", "highlight"}
        extra = set(fields) - allowed
        if extra:
            return {"error": "Unknown fields present"}, 400

        with self._store_factory() as store:
            current = store.fetch_task(project_name, task_id)
            if current is None:
                return {"error": "Task not found"}, 400

            updated = {
                "task_id": task_id,
                "summary": str(current.get("summary") or ""),
                "assignee": str(current.get("assignee") or ""),
                "remarks": str(current.get("remarks") or ""),
                "status": current.get("status") or TaskStatus.NOT_STARTED.value,
                "priority": current.get("priority") or TaskPriority.MEDIUM.value,
                "highlight": bool(current.get("highlight")),
            }

            if "summary" in fields:
                updated["summary"] = str(fields["summary"] or "")
            if "assignee" in fields:
                updated["assignee"] = str(fields["assignee"] or "")
            if "remarks" in fields:
                updated["remarks"] = str(fields["remarks"] or "")
            if "status" in fields:
                try:
                    updated["status"] = TaskStatus(fields["status"]).value  # type: ignore[arg-type]
                except Exception:
                    return {"error": "Invalid status"}, 400
            if "priority" in fields:
                try:
                    updated["priority"] = TaskPriority(fields["priority"]).value  # type: ignore[arg-type]
                except Exception:
                    return {"error": "Invalid priority"}, 400
            if "highlight" in fields:
                if not isinstance(fields["highlight"], bool):
                    return {"error": "Invalid highlight"}, 400
                updated["highlight"] = fields["highlight"]

            try:
                store.upsert_task(project_name, updated)
            except Exception as exc:
                return {"error": f"Failed to save: {exc}"}, 500

        task_obj = Task(
            updated["summary"],
            updated["assignee"],
            updated["remarks"],
            updated["status"],
            updated["priority"],
            bool(updated["highlight"]),
            id=task_id,
        )
        return {"ok": True, "id": task_id, "task": task_obj.to_dict()}, 200

    def create_task(self, project_name: str, payload: Optional[object]) -> Tuple[Dict[str, object], int]:
        if self._invalid_name(project_name):
            return {"error": "Invalid project name"}, 400
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
            status_val = TaskStatus(status_val).value  # type: ignore[arg-type]
        except Exception:
            status_val = TaskStatus.NOT_STARTED.value
        try:
            priority_val = TaskPriority(priority_val).value  # type: ignore[arg-type]
        except Exception:
            priority_val = TaskPriority.MEDIUM.value

        with self._store_factory() as store:
            new_id = store.next_task_id(project_name)
            payload_row = {
                "task_id": new_id,
                "summary": summary,
                "assignee": assignee,
                "remarks": remarks,
                "status": status_val,
                "priority": priority_val,
                "highlight": highlight_val,
            }
            try:
                store.upsert_task(project_name, payload_row)
            except Exception as exc:
                return {"error": f"Failed to save: {exc}"}, 500

        task_obj = Task(summary, assignee, remarks, status_val, priority_val, highlight_val, id=new_id)
        return {"ok": True, "id": new_id, "task": task_obj.to_dict()}, 200

    def delete_task(self, project_name: str, payload: Optional[object]) -> Tuple[Dict[str, object], int]:
        if self._invalid_name(project_name):
            return {"error": "Invalid project name"}, 400
        if payload is None or not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        try:
            task_id = int(payload.get("id", -1))
        except (TypeError, ValueError):
            return {"error": "'id' must be an integer"}, 400

        with self._store_factory() as store:
            current = store.fetch_task(project_name, task_id)
            if current is None:
                return {"error": "Task not found"}, 400

            try:
                store.delete_task(project_name, task_id)
            except Exception as exc:
                return {"error": f"Failed to save: {exc}"}, 500

        try:
            task_dict = self._row_to_task({**current, "task_id": task_id})
        except Exception:
            task_dict = {
                "id": task_id,
                "summary": current.get("summary", "") if isinstance(current, dict) else "",
                "assignee": current.get("assignee", "") if isinstance(current, dict) else "",
                "remarks": current.get("remarks", "") if isinstance(current, dict) else "",
                "status": current.get("status", "") if isinstance(current, dict) else "",
                "priority": current.get("priority", "") if isinstance(current, dict) else "",
                "highlight": bool(current.get("highlight")) if isinstance(current, dict) else False,
            }
        return {"ok": True, "id": task_id, "task": task_dict}, 200
