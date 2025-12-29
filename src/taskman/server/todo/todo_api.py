from __future__ import annotations

"""Todo API handlers and validation."""

import re
from typing import Callable, Dict, Optional, Tuple

from .todo import Todo, TodoPriority
from .todo_store import TodoStore


def _normalize_due_date(raw: str) -> str:
    """
    Normalize incoming due date strings to ISO YYYY-MM-DD for storage/sorting.
    Expects YYYY-MM-DD; returns empty string on parse failure/empty input.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    return ""


class TodoAPI:
    """Simple API wrapper for todo operations."""

    def __init__(self, store_factory: Optional[Callable[[], TodoStore]] = None) -> None:
        self._store_factory = store_factory or (lambda: TodoStore())

    def add_todo(self, payload: Dict[str, object]) -> Tuple[Dict[str, object], int]:
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        title = str(payload.get("title") or "").strip()
        if not title:
            return {"error": "Missing 'title'"}, 400
        note = str(payload.get("note") or "").strip()
        due_date = _normalize_due_date(str(payload.get("due_date") or ""))
        people_val = payload.get("people") or []
        if isinstance(people_val, str):
            people = [p.strip() for p in people_val.split(",") if p.strip()]
        elif isinstance(people_val, list):
            people = [str(p).strip() for p in people_val if str(p).strip()]
        else:
            people = []
        prio_raw = str(payload.get("priority") or "").strip().lower()
        priority = TodoPriority.from_value(prio_raw)
        done = bool(payload.get("done", False))

        todo = Todo(
            title=title,
            note=note,
            due_date=due_date,
            people=people,
            priority=priority,
            done=done,
        )
        try:
            with self._store_factory() as store:
                saved = store.add_item(todo)
            return {"ok": True, "item": saved.to_dict()}, 200
        except Exception as exc:
            return {"error": f"Failed to add todo: {exc}"}, 500

    def list_todos(self) -> Tuple[Dict[str, object], int]:
        try:
            with self._store_factory() as store:
                items = [t.to_dict() for t in store.list_items()]
            return {"items": items}, 200
        except Exception as exc:
            return {"error": f"Failed to fetch todos: {exc}"}, 500

    def list_archived_todos(self) -> Tuple[Dict[str, object], int]:
        try:
            with self._store_factory() as store:
                items = [t.to_dict() for t in store.list_archived_items()]
            return {"items": items}, 200
        except Exception as exc:
            return {"error": f"Failed to fetch archived todos: {exc}"}, 500

    def mark_done(self, payload: Dict[str, object]) -> Tuple[Dict[str, object], int]:
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        if "id" not in payload:
            return {"error": "Missing 'id'"}, 400
        try:
            todo_id = int(payload.get("id"))
        except Exception:
            return {"error": "Invalid 'id'"}, 400
        done_val = bool(payload.get("done", True))
        try:
            with self._store_factory() as store:
                updated = store.set_done(todo_id, done_val)
            if not updated:
                return {"error": "Todo not found"}, 404
            return {"ok": True, "id": todo_id, "done": done_val}, 200
        except Exception as exc:
            return {"error": f"Failed to update todo: {exc}"}, 500

    def edit_todo(self, payload: Dict[str, object]) -> Tuple[Dict[str, object], int]:
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        if "id" not in payload:
            return {"error": "Missing 'id'"}, 400
        try:
            todo_id = int(payload.get("id"))
        except Exception:
            return {"error": "Invalid 'id'"}, 400

        title = str(payload.get("title") or "").strip()
        if not title:
            return {"error": "Missing 'title'"}, 400
        note = str(payload.get("note") or "").strip()
        due_date = _normalize_due_date(str(payload.get("due_date") or ""))
        people_val = payload.get("people") or []
        if isinstance(people_val, str):
            people = [p.strip() for p in people_val.split(",") if p.strip()]
        elif isinstance(people_val, list):
            people = [str(p).strip() for p in people_val if str(p).strip()]
        else:
            people = []
        prio_raw = str(payload.get("priority") or "").strip().lower()
        priority = TodoPriority.from_value(prio_raw)

        todo = Todo(title=title, note=note, due_date=due_date, people=people, priority=priority)
        try:
            with self._store_factory() as store:
                updated = store.update_item(todo_id, todo)
            if not updated:
                return {"error": "Todo not found"}, 404
            todo.id = todo_id
            return {"ok": True, "item": todo.to_dict()}, 200
        except Exception as exc:
            return {"error": f"Failed to update todo: {exc}"}, 500
