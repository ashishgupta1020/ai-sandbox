"""SQLite-backed task storage utilities for Taskman.

This module encapsulates the low-level operations required to persist tasks
in an SQLite database. Each project is stored in its own table whose name is
derived from the project's lowercase identifier. Highlight flags are stored
as INTEGER columns for simple boolean mapping.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from taskman.config import get_data_store_dir

_TABLE_PREFIX = "tasks_"
_PROJECTS_TABLE = "projects"
_PROJECT_TAGS_TABLE = "project_tags"


def _project_table_name(project_name: str) -> str:
    """Return a safe table name for the given project."""
    base = project_name.strip().lower()
    if not base:
        raise ValueError("Project name must be a non-empty string")
    sanitized = re.sub(r"[^a-z0-9_]", "_", base)
    return f"{_TABLE_PREFIX}{sanitized}"


class TaskStore:
    """Encapsulates CRUD helpers for per-project task tables and project registry."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is not None:
            root = Path(db_path).expanduser().resolve().parent
            self.db_path = Path(db_path)
        else:
            root = get_data_store_dir()
            self.db_path = root / "taskman.db"
        root.mkdir(parents=True, exist_ok=True)
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

    def __enter__(self) -> "TaskStore":
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

    def _ensure_registry_tables(self) -> None:
        """Ensure the projects and project_tags registry tables exist."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        with self._lock:
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_PROJECTS_TABLE} (
                    name        TEXT NOT NULL,
                    name_lower  TEXT NOT NULL UNIQUE,
                    PRIMARY KEY (name)
                )
                """
            )
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_PROJECT_TAGS_TABLE} (
                    project_lower TEXT NOT NULL,
                    tag           TEXT NOT NULL,
                    PRIMARY KEY (project_lower, tag)
                )
                """
            )

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

    def fetch_task(self, project_name: str, task_id: int) -> Optional[Dict[str, object]]:
        """Return a single task row by id or None if not found."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        table = self._ensure_table(project_name)
        with self._lock:
            cur = self._conn.execute(
                f"SELECT task_id, summary, assignee, remarks, status, priority, highlight "
                f"FROM {table} WHERE task_id = ?",
                (int(task_id),),
            )
            row = cur.fetchone()
        if row is None:
            return None
        as_dict = dict(row)
        as_dict["highlight"] = bool(as_dict.get("highlight"))
        return as_dict

    def next_task_id(self, project_name: str) -> int:
        """Return the next available task_id for the project."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        table = self._ensure_table(project_name)
        with self._lock:
            cur = self._conn.execute(f"SELECT MAX(task_id) FROM {table}")
            row = cur.fetchone()
        max_id = row[0] if row and row[0] is not None else -1
        return int(max_id) + 1

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

    # ----- Project registry helpers -----
    def list_projects(self) -> List[str]:
        """Return project names in insertion order."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_registry_tables()
        with self._lock:
            cur = self._conn.execute(
                f"SELECT name FROM {_PROJECTS_TABLE} ORDER BY rowid ASC"
            )
            rows = cur.fetchall()
        return [str(row[0]) for row in rows]

    def upsert_project_name(self, project_name: str) -> str:
        """Insert a project if missing, returning the canonical stored name."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_registry_tables()
        name = project_name.strip()
        if not name:
            raise ValueError("Project name must be non-empty")
        name_lower = name.lower()
        with self._lock:
            cur = self._conn.execute(
                f"SELECT name FROM {_PROJECTS_TABLE} WHERE name_lower = ?",
                (name_lower,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
            self._conn.execute(
                f"INSERT INTO {_PROJECTS_TABLE} (name, name_lower) VALUES (?, ?)",
                (name, name_lower),
            )
        return name

    def rename_project(self, old_name: str, new_name: str) -> None:
        """Rename a project, update registry/tags, and rename the tasks table."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_registry_tables()
        old_lower = old_name.strip().lower()
        new_lower = new_name.strip().lower()
        if not old_lower or not new_lower:
            raise ValueError("Project names must be non-empty")
        with self._lock:
            cur = self._conn.execute(
                f"SELECT name FROM {_PROJECTS_TABLE} WHERE name_lower = ?",
                (old_lower,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Project '{old_name}' not found.")

            cur = self._conn.execute(
                f"SELECT name FROM {_PROJECTS_TABLE} WHERE name_lower = ?",
                (new_lower,),
            )
            existing = cur.fetchone()
            if existing and existing[0].lower() != old_lower:
                raise ValueError(f"Project name '{new_name}' already exists.")

            # Update registry
            self._conn.execute(
                f"UPDATE {_PROJECTS_TABLE} SET name = ?, name_lower = ? WHERE name_lower = ?",
                (new_name, new_lower, old_lower),
            )
            # Rename tasks table if it exists
            old_table = _project_table_name(old_name)
            new_table = _project_table_name(new_name)
            cur = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                (old_table,),
            )
            if cur.fetchone():
                if old_table != new_table:
                    self._conn.execute(f"ALTER TABLE {old_table} RENAME TO {new_table}")
            # Migrate tags
            self._conn.execute(
                f"UPDATE {_PROJECT_TAGS_TABLE} SET project_lower = ? WHERE project_lower = ?",
                (new_lower, old_lower),
            )

    def get_tags_for_project(self, project_name: str) -> List[str]:
        """Return tags for a project (case-insensitive)."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_registry_tables()
        key = project_name.strip().lower()
        with self._lock:
            cur = self._conn.execute(
                f"SELECT tag FROM {_PROJECT_TAGS_TABLE} WHERE project_lower = ? ORDER BY rowid ASC",
                (key,),
            )
            rows = cur.fetchall()
        return [str(row[0]) for row in rows]

    def add_tags(self, project_name: str, tags: Iterable[str]) -> List[str]:
        """Add tags to a project, returning updated list."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_registry_tables()
        # Ensure the project is present in the registry when tagging
        self.upsert_project_name(project_name)
        key = project_name.strip().lower()
        to_insert: List[str] = []
        for tag in tags:
            if not isinstance(tag, str):
                continue
            val = tag.strip()
            if not val:
                continue
            to_insert.append(val)
        with self._lock:
            for tag in to_insert:
                self._conn.execute(
                    f"INSERT OR IGNORE INTO {_PROJECT_TAGS_TABLE} (project_lower, tag) VALUES (?, ?)",
                    (key, tag),
            )
        return self.get_tags_for_project(project_name)

    def remove_tag(self, project_name: str, tag: str) -> List[str]:
        """Remove a tag from a project, returning updated list."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_registry_tables()
        key = project_name.strip().lower()
        with self._lock:
            self._conn.execute(
                f"DELETE FROM {_PROJECT_TAGS_TABLE} WHERE project_lower = ? AND tag = ?",
                (key, tag),
            )
        return self.get_tags_for_project(project_name)

    def get_tags_for_all_projects(self) -> Dict[str, List[str]]:
        """Return a mapping of project name -> tags for all known projects."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_registry_tables()
        projects = self.list_projects()
        by_lower = {p.lower(): p for p in projects}
        tags_by_project: Dict[str, List[str]] = {p: [] for p in projects}
        with self._lock:
            cur = self._conn.execute(
                f"SELECT project_lower, tag FROM {_PROJECT_TAGS_TABLE} ORDER BY rowid ASC"
            )
            rows = cur.fetchall()
        for row in rows:
            project_lower = str(row[0])
            tag = str(row[1])
            name = by_lower.get(project_lower)
            if name is None:
                continue
            tags_by_project[name].append(tag)
        return tags_by_project


class ProjectTaskSession:
    """Context manager scoped to a project-specific tasks table."""

    def __init__(self, project_name: str, db_path: Optional[Path] = None) -> None:
        self.project_name = project_name
        self._store = TaskStore(db_path=db_path)

    def __enter__(self) -> TaskStore:
        store = self._store.__enter__()
        store._ensure_table(self.project_name)
        return store

    def __exit__(self, exc_type, exc, tb) -> None:
        self._store.__exit__(exc_type, exc, tb)
