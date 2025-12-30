"""SQLite-backed task storage utilities for Taskman.

This module encapsulates the low-level operations required to persist tasks
in an SQLite database. Tasks live in a shared table keyed by project, with
separate project and tag tables for metadata.
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
_TASKS_TABLE = "tasks"
_PROJECT_TAGS_TABLE = "project_tags"


def _project_table_name(project_name: str) -> str:
    """Return a safe legacy table name for the given project."""
    base = project_name.strip().lower()
    if not base:
        raise ValueError("Project name must be a non-empty string")
    sanitized = re.sub(r"[^a-z0-9_]", "_", base)
    return f"{_TABLE_PREFIX}{sanitized}"


class TaskStore:
    """Encapsulates CRUD helpers for the shared tasks table and project registry."""

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

    def _ensure_schema(self) -> None:
        """Ensure the unified projects/tasks/tag tables exist."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        with self._lock:
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_PROJECTS_TABLE} (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    name_lower TEXT NOT NULL UNIQUE
                )
                """
            )
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_TASKS_TABLE} (
                    project_id INTEGER NOT NULL,
                    task_id INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    assignee TEXT,
                    remarks TEXT,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    highlight INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (project_id, task_id),
                    FOREIGN KEY (project_id) REFERENCES {_PROJECTS_TABLE}(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_tasks_highlight ON {_TASKS_TABLE}(highlight)"
            )
            self._conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON {_TASKS_TABLE}(assignee)"
            )
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_PROJECT_TAGS_TABLE} (
                    project_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (project_id, tag),
                    FOREIGN KEY (project_id) REFERENCES {_PROJECTS_TABLE}(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_project_tags_tag ON {_PROJECT_TAGS_TABLE}(tag)"
            )

    def _get_project(self, project_name: str, *, create: bool = False) -> Optional[Dict[str, object]]:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_schema()
        name = project_name.strip()
        if not name:
            raise ValueError("Project name must be non-empty")
        name_lower = name.lower()
        with self._lock:
            cur = self._conn.execute(
                f"SELECT id, name FROM {_PROJECTS_TABLE} WHERE name_lower = ?",
                (name_lower,),
            )
            row = cur.fetchone()
            if row:
                return {"id": int(row["id"]), "name": str(row["name"])}
            if not create:
                return None
            cur = self._conn.execute(
                f"INSERT INTO {_PROJECTS_TABLE} (name, name_lower) VALUES (?, ?)",
                (name, name_lower),
            )
            return {"id": int(cur.lastrowid), "name": name}

    def _get_project_id(self, project_name: str, *, create: bool = False) -> Optional[int]:
        project = self._get_project(project_name, create=create)
        if project is None:
            return None
        return int(project["id"])

    def fetch_all(self, project_name: str) -> List[Dict[str, object]]:
        """Return all tasks for the project ordered by task_id."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        project_id = self._get_project_id(project_name, create=False)
        if project_id is None:
            return []
        with self._lock:
            cursor = self._conn.execute(
                f"""
                SELECT task_id, summary, assignee, remarks, status, priority, highlight
                FROM {_TASKS_TABLE}
                WHERE project_id = ?
                ORDER BY task_id ASC
                """,
                (project_id,),
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
        project_id = self._get_project_id(project_name, create=False)
        if project_id is None:
            return None
        with self._lock:
            cur = self._conn.execute(
                f"""
                SELECT task_id, summary, assignee, remarks, status, priority, highlight
                FROM {_TASKS_TABLE}
                WHERE project_id = ? AND task_id = ?
                """,
                (project_id, int(task_id)),
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
        project_id = self._get_project_id(project_name, create=False)
        if project_id is None:
            return 0
        with self._lock:
            cur = self._conn.execute(
                f"SELECT MAX(task_id) FROM {_TASKS_TABLE} WHERE project_id = ?",
                (project_id,),
            )
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
        project_id = self._get_project_id(project_name, create=True)
        if project_id is None:
            raise RuntimeError(f"Failed to resolve project '{project_name}'")
        payload = {
            "project_id": project_id,
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
                INSERT INTO {_TASKS_TABLE}
                    (project_id, task_id, summary, assignee, remarks, status, priority, highlight)
                VALUES
                    (:project_id, :task_id, :summary, :assignee, :remarks, :status, :priority, :highlight)
                ON CONFLICT(project_id, task_id) DO UPDATE SET
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
        project_id = self._get_project_id(project_name, create=True)
        if project_id is None:
            raise RuntimeError(f"Failed to resolve project '{project_name}'")
        normalized: List[Dict[str, object]] = []
        for task in tasks:
            if "task_id" not in task:
                raise ValueError("Each task must include 'task_id' for bulk_replace")
            normalized.append(
                {
                    "project_id": project_id,
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
                self._conn.execute(
                    f"DELETE FROM {_TASKS_TABLE} WHERE project_id = ?",
                    (project_id,),
                )
                self._conn.executemany(
                    f"""
                    INSERT INTO {_TASKS_TABLE}
                        (project_id, task_id, summary, assignee, remarks, status, priority, highlight)
                    VALUES
                        (:project_id, :task_id, :summary, :assignee, :remarks, :status, :priority, :highlight)
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
        project_id = self._get_project_id(project_name, create=False)
        if project_id is None:
            return
        with self._lock:
            self._conn.execute(
                f"DELETE FROM {_TASKS_TABLE} WHERE project_id = ? AND task_id = ?",
                (project_id, int(task_id)),
            )

    # ----- Project registry helpers -----
    def list_projects(self) -> List[str]:
        """Return project names in insertion order."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_schema()
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
        project = self._get_project(project_name, create=True)
        if project is None:
            raise RuntimeError(f"Failed to create project '{project_name}'")
        return str(project["name"])

    def rename_project(self, old_name: str, new_name: str) -> None:
        """Rename a project, updating the registry."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_schema()
        old_lower = old_name.strip().lower()
        new_lower = new_name.strip().lower()
        if not old_lower or not new_lower:
            raise ValueError("Project names must be non-empty")
        with self._lock:
            cur = self._conn.execute(
                f"SELECT id, name FROM {_PROJECTS_TABLE} WHERE name_lower = ?",
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

            self._conn.execute(
                f"UPDATE {_PROJECTS_TABLE} SET name = ?, name_lower = ? WHERE name_lower = ?",
                (new_name, new_lower, old_lower),
            )

    def get_tags_for_project(self, project_name: str) -> List[str]:
        """Return tags for a project (case-insensitive)."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_schema()
        project_id = self._get_project_id(project_name, create=False)
        if project_id is None:
            return []
        with self._lock:
            cur = self._conn.execute(
                f"""
                SELECT tag FROM {_PROJECT_TAGS_TABLE}
                WHERE project_id = ?
                ORDER BY rowid ASC
                """,
                (project_id,),
            )
            rows = cur.fetchall()
        return [str(row[0]) for row in rows]

    def add_tags(self, project_name: str, tags: Iterable[str]) -> List[str]:
        """Add tags to a project, returning updated list."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_schema()
        # Ensure the project is present in the registry when tagging
        project_id = self._get_project_id(project_name, create=True)
        if project_id is None:
            raise RuntimeError(f"Failed to resolve project '{project_name}'")
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
                    f"""
                    INSERT OR IGNORE INTO {_PROJECT_TAGS_TABLE} (project_id, tag)
                    VALUES (?, ?)
                    """,
                    (project_id, tag),
                )
        return self.get_tags_for_project(project_name)

    def remove_tag(self, project_name: str, tag: str) -> List[str]:
        """Remove a tag from a project, returning updated list."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_schema()
        project_id = self._get_project_id(project_name, create=False)
        if project_id is None:
            return []
        with self._lock:
            self._conn.execute(
                f"DELETE FROM {_PROJECT_TAGS_TABLE} WHERE project_id = ? AND tag = ?",
                (project_id, tag),
            )
        return self.get_tags_for_project(project_name)

    def get_tags_for_all_projects(self) -> Dict[str, List[str]]:
        """Return a mapping of project name -> tags for all known projects."""
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_schema()
        with self._lock:
            cur = self._conn.execute(
                f"SELECT name FROM {_PROJECTS_TABLE} ORDER BY rowid ASC"
            )
            projects = [str(row[0]) for row in cur.fetchall()]
            tags_by_project: Dict[str, List[str]] = {p: [] for p in projects}
            cur = self._conn.execute(
                f"""
                SELECT p.name AS name, t.tag AS tag
                FROM {_PROJECTS_TABLE} p
                LEFT JOIN {_PROJECT_TAGS_TABLE} t ON p.id = t.project_id
                ORDER BY p.rowid ASC, t.rowid ASC
                """
            )
            rows = cur.fetchall()
        for row in rows:
            name = str(row["name"])
            tag = row["tag"]
            if tag is None:
                continue
            tags_by_project[name].append(str(tag))
        return tags_by_project
