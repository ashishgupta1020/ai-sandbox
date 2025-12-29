from __future__ import annotations

"""Storage layer for todo items, using the shared Taskman SQLite database."""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from taskman.config import get_data_store_dir
from .todo import Todo, TodoPriority


class TodoStore:
    """Lightweight store for todo items."""

    _ARCHIVE_DAYS = 30

    def __init__(self, db_path: Optional[Path] = None) -> None:
        base_dir = get_data_store_dir()
        self.db_path = Path(db_path).expanduser().resolve() if db_path else (base_dir / "taskman_todo.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

    def open(self) -> None:
        if self._conn is not None:
            return
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit; explicit transactions handled via lock
        )
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "TodoStore":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_table(self) -> None:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  note TEXT,
                  due_date TEXT,         -- ISO YYYY-MM-DD
                  people TEXT,           -- JSON array of strings
                  priority TEXT NOT NULL DEFAULT 'medium',
                  done INTEGER NOT NULL DEFAULT 0,
                  done_at INTEGER,       -- epoch seconds when completed
                  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            self._ensure_columns()

    def _ensure_columns(self) -> None:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        cur = self._conn.execute("PRAGMA table_info(todos)")
        columns = {row["name"] for row in cur.fetchall()}
        if "done_at" not in columns:
            self._conn.execute("ALTER TABLE todos ADD COLUMN done_at INTEGER")
        if "created_at" not in columns:
            self._conn.execute("ALTER TABLE todos ADD COLUMN created_at INTEGER")

    def _archive_cutoff(self, now: int) -> int:
        return now - (self._ARCHIVE_DAYS * 24 * 60 * 60)

    def add_item(self, todo: Todo) -> Todo:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_table()
        payload = {
            "title": todo.title,
            "note": todo.note,
            "due_date": todo.due_date,
            "people": json.dumps(list(todo.people)),
            "priority": todo.priority.value,
            "done": 1 if todo.done else 0,
            "done_at": int(time.time()) if todo.done else None,
        }
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO todos (title, note, due_date, people, priority, done, done_at)
                VALUES (:title, :note, :due_date, :people, :priority, :done, :done_at)
                """,
                payload,
            )
            new_id = cur.lastrowid
        todo.id = int(new_id)
        return todo

    def list_items(self) -> list[Todo]:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_table()
        now = int(time.time())
        cutoff = self._archive_cutoff(now)
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT id, title, note, due_date, people, priority, done
                FROM todos
                WHERE done = 0
                   OR (done = 1 AND COALESCE(done_at, created_at, :now) >= :cutoff)
                ORDER BY done ASC, due_date ASC, id ASC
                """,
                {"cutoff": cutoff, "now": now},
            )
            rows = cur.fetchall()
        items: list[Todo] = []
        for row in rows:
            people_raw = row["people"]
            try:
                people = json.loads(people_raw) if people_raw else []
            except Exception:
                people = []
            items.append(
                Todo(
                    id=int(row["id"]),
                    title=row["title"] or "",
                    note=row["note"] or "",
                    due_date=row["due_date"] or "",
                    people=people,
                    priority=TodoPriority.from_value(row["priority"] or ""),
                    done=bool(row["done"]),
                )
            )
        return items

    def list_archived_items(self) -> list[Todo]:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_table()
        now = int(time.time())
        cutoff = self._archive_cutoff(now)
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT id, title, note, due_date, people, priority, done
                FROM todos
                WHERE done = 1
                  AND COALESCE(done_at, created_at, :now) < :cutoff
                ORDER BY COALESCE(done_at, created_at, :now) DESC, id DESC
                """,
                {"cutoff": cutoff, "now": now},
            )
            rows = cur.fetchall()
        items: list[Todo] = []
        for row in rows:
            people_raw = row["people"]
            try:
                people = json.loads(people_raw) if people_raw else []
            except Exception:
                people = []
            items.append(
                Todo(
                    id=int(row["id"]),
                    title=row["title"] or "",
                    note=row["note"] or "",
                    due_date=row["due_date"] or "",
                    people=people,
                    priority=TodoPriority.from_value(row["priority"] or ""),
                    done=bool(row["done"]),
                )
            )
        return items

    def set_done(self, todo_id: int, done: bool) -> bool:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_table()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE todos SET done = :done, done_at = :done_at WHERE id = :id",
                {"done": 1 if done else 0, "done_at": int(time.time()) if done else None, "id": int(todo_id)},
            )
            return cur.rowcount > 0

    def update_item(self, todo_id: int, updated: Todo) -> bool:
        if self._conn is None:
            raise RuntimeError("Database connection is not open")
        self._ensure_table()
        payload = {
            "id": int(todo_id),
            "title": updated.title,
            "note": updated.note,
            "due_date": updated.due_date,
            "people": json.dumps(list(updated.people)),
            "priority": updated.priority.value,
        }
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE todos
                SET title = :title,
                    note = :note,
                    due_date = :due_date,
                    people = :people,
                    priority = :priority
                WHERE id = :id
                """,
                payload,
            )
            return cur.rowcount > 0
