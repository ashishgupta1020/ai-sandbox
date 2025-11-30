"""SQLite-backed task storage utilities for Taskman.

This module encapsulates the low-level operations required to persist tasks
in an SQLite database. Each project is stored in its own table whose name is
derived from the project's lowercase identifier.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .project_manager import ProjectManager

_TABLE_PREFIX = "tasks_"


def _project_table_name(project_name: str) -> str:
    """Return a safe table name for the given project."""
    base = project_name.strip().lower()
    if not base:
        raise ValueError("Project name must be a non-empty string")
    sanitized = re.sub(r"[^a-z0-9_]", "_", base)
    return f"{_TABLE_PREFIX}{sanitized}"


class SQLiteTaskStore:
    """Encapsulates CRUD helpers for per-project task tables."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        root = Path(ProjectManager.PROJECTS_DIR)
        root.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path) if db_path is not None else root / "taskman.db"
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

    def open(self) -> None:
        """Open an SQLite connection if not already open."""
        if self._conn is not None:
            return
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage explicit transactions
        )
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SQLiteTaskStore":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_table(self, project_name: str) -> str:
        """Ensure the tasks table for the project exists."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        table = _project_table_name(project_name)
        with self._lock:
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    task_id   INTEGER PRIMARY KEY,
                    summary   TEXT NOT NULL,
                    assignee  TEXT,
                    remarks   TEXT,
                    status    TEXT NOT NULL,
                    priority  TEXT NOT NULL,
                    highlight INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        return table

    def fetch_all(self, project_name: str) -> List[Dict[str, object]]:
        """Return all tasks for the project ordered by task_id."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        table = self._ensure_table(project_name)
        with self._lock:
            cursor = self._conn.execute(
                f"SELECT task_id, summary, assignee, remarks, status, priority, highlight "
                f"FROM {table} ORDER BY task_id ASC"
            )
            rows = cursor.fetchall()
        result: List[Dict[str, object]] = []
        for row in rows:
            as_dict = dict(row)
            as_dict["highlight"] = bool(as_dict.get("highlight"))
            result.append(as_dict)
        return result

    def upsert_task(self, project_name: str, task: Dict[str, object]) -> None:
        """Insert or update a single task row."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        required = {"task_id", "summary", "status", "priority"}
        missing = required - task.keys()
        if missing:
            raise ValueError(f"Task payload missing required fields: {sorted(missing)}")
        table = self._ensure_table(project_name)
        payload = {
            "task_id": task["task_id"],
            "summary": task.get("summary") or "",
            "assignee": task.get("assignee") or "",
            "remarks": task.get("remarks") or "",
            "status": task.get("status") or "",
            "priority": task.get("priority") or "",
            "highlight": 1 if task.get("highlight") else 0,
        }
        with self._lock:
            self._conn.execute(
                f"""
                INSERT INTO {table} (task_id, summary, assignee, remarks, status, priority, highlight)
                VALUES (:task_id, :summary, :assignee, :remarks, :status, :priority, :highlight)
                ON CONFLICT(task_id) DO UPDATE SET
                    summary  = excluded.summary,
                    assignee = excluded.assignee,
                    remarks  = excluded.remarks,
                    status   = excluded.status,
                    priority = excluded.priority,
                    highlight = excluded.highlight
                """,
                payload,
            )

    def bulk_replace(self, project_name: str, tasks: Iterable[Dict[str, object]]) -> None:
        """Replace all task rows for the project with the provided iterable."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        table = self._ensure_table(project_name)
        normalized: List[Dict[str, Optional[str]]] = []
        for task in tasks:
            if "task_id" not in task:
                raise ValueError("Each task must include 'task_id' for bulk_replace")
            normalized.append(
                {
                    "task_id": task["task_id"],
                    "summary": task.get("summary") or "",
                    "assignee": task.get("assignee") or "",
                    "remarks": task.get("remarks") or "",
                    "status": task.get("status") or "",
                    "priority": task.get("priority") or "",
                    "highlight": 1 if task.get("highlight") else 0,
                }
            )

        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.execute(f"DELETE FROM {table}")
                self._conn.executemany(
                    f"""
                    INSERT INTO {table} (task_id, summary, assignee, remarks, status, priority, highlight)
                    VALUES (:task_id, :summary, :assignee, :remarks, :status, :priority, :highlight)
                    """,
                    normalized,
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def delete_task(self, project_name: str, task_id: int) -> None:
        """Delete a single task by its ID."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        table = self._ensure_table(project_name)
        with self._lock:
            self._conn.execute(
                f"DELETE FROM {table} WHERE task_id = ?",
                (int(task_id),),
            )


class ProjectTaskSession:
    """Context manager scoped to a project-specific tasks table."""

    def __init__(self, project_name: str, db_path: Optional[Path] = None) -> None:
        self.project_name = project_name
        self._store = SQLiteTaskStore(db_path=db_path)

    def __enter__(self) -> SQLiteTaskStore:
        store = self._store.__enter__()
        store._ensure_table(self.project_name)
        return store

    def __exit__(self, exc_type, exc, tb) -> None:
        self._store.__exit__(exc_type, exc, tb)
