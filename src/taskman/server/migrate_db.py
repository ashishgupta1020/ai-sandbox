from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Callable, Iterable, Optional

from taskman.config import get_data_store_dir, load_config
from taskman.server.task_store import _project_table_name


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    )
    return cur.fetchone() is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {str(row["name"]) for row in cur.fetchall()}


def _list_task_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'tasks_*' ORDER BY name"
    )
    return [str(row[0]) for row in cur.fetchall()]


def _rename_table(conn: sqlite3.Connection, old: str, new: str) -> None:
    if not _table_exists(conn, old):
        return
    if _table_exists(conn, new):
        raise RuntimeError(f"Cannot rename '{old}' to '{new}': '{new}' already exists.")
    conn.execute(f"ALTER TABLE {old} RENAME TO {new}")


def _create_projects_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_lower TEXT NOT NULL UNIQUE
        )
        """
    )


def _create_tasks_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            project_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            summary TEXT NOT NULL,
            assignee TEXT,
            remarks TEXT,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            highlight INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (project_id, task_id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_highlight ON tasks(highlight)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee)")


def _create_project_tags_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_tags (
            project_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY (project_id, tag),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_project_tags_tag ON project_tags(tag)")


def _select_task_rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    columns = _table_columns(conn, table)
    required = {"task_id", "summary", "status", "priority"}
    missing = required - columns
    if missing:
        raise RuntimeError(f"Legacy table '{table}' missing columns: {sorted(missing)}")

    select_cols: list[str] = []
    for col in ("task_id", "summary", "assignee", "remarks", "status", "priority"):
        if col in columns:
            select_cols.append(col)
        else:
            select_cols.append(f"'' AS {col}")
    if "highlight" in columns:
        select_cols.append("highlight")
    else:
        select_cols.append("0 AS highlight")

    query = f"SELECT {', '.join(select_cols)} FROM {table} ORDER BY task_id ASC"
    cur = conn.execute(query)
    return cur.fetchall()


def _unique_name(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    candidate = f"{base}_migrated"
    if candidate not in existing:
        return candidate
    idx = 2
    while f"{base}_migrated_{idx}" in existing:
        idx += 1
    return f"{base}_migrated_{idx}"


def migrate_taskman_db(
    db_path: Path,
    *,
    log: Callable[[str], None] = print,
) -> None:
    db_path = Path(db_path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Using database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        if _table_exists(conn, "tasks"):
            log("Found 'tasks' table already; migration appears complete. No changes made.")
            return

        if _table_exists(conn, "projects") and "id" in _table_columns(conn, "projects"):
            log("Found v2 'projects' table but no 'tasks' table; creating tasks/project_tags only.")
            _create_tasks_table(conn)
            _create_project_tags_table(conn)
            return

        conn.execute("BEGIN")
        warnings: list[str] = []

        if _table_exists(conn, "projects"):
            _rename_table(conn, "projects", "projects_legacy")
            log("Renamed legacy table: projects -> projects_legacy")
        legacy_projects_table = "projects_legacy" if _table_exists(conn, "projects_legacy") else None

        if _table_exists(conn, "project_tags"):
            _rename_table(conn, "project_tags", "project_tags_legacy")
            log("Renamed legacy table: project_tags -> project_tags_legacy")
        legacy_tags_table = "project_tags_legacy" if _table_exists(conn, "project_tags_legacy") else None

        _create_projects_table(conn)
        _create_tasks_table(conn)
        _create_project_tags_table(conn)

        projects_by_lower: dict[str, int] = {}
        projects_by_name: dict[str, int] = {}
        if legacy_projects_table:
            cur = conn.execute(
                f"SELECT name, name_lower FROM {legacy_projects_table} ORDER BY rowid ASC"
            )
            for row in cur.fetchall():
                name = str(row["name"])
                name_lower = str(row["name_lower"])
                insert = conn.execute(
                    "INSERT INTO projects (name, name_lower) VALUES (?, ?)",
                    (name, name_lower),
                )
                pid = int(insert.lastrowid)
                projects_by_lower[name_lower] = pid
                projects_by_name[name] = pid

        legacy_task_tables = _list_task_tables(conn)
        table_to_projects: dict[str, list[tuple[str, int]]] = {}
        for name, pid in projects_by_name.items():
            table = _project_table_name(name)
            table_to_projects.setdefault(table, []).append((name, pid))

        for table, entries in table_to_projects.items():
            if len(entries) > 1:
                names = ", ".join(entry[0] for entry in entries)
                warnings.append(
                    f"Legacy table '{table}' mapped from multiple projects ({names}); "
                    "tasks will be duplicated across those projects."
                )

        for table in legacy_task_tables:
            if table in table_to_projects:
                continue
            suffix = table[len("tasks_") :]
            name_lower = _unique_name(suffix, set(projects_by_lower.keys()))
            name = name_lower
            insert = conn.execute(
                "INSERT INTO projects (name, name_lower) VALUES (?, ?)",
                (name, name_lower),
            )
            pid = int(insert.lastrowid)
            projects_by_lower[name_lower] = pid
            projects_by_name[name] = pid
            table_to_projects.setdefault(table, []).append((name, pid))
            warnings.append(
                f"Created project '{name}' for orphan legacy table '{table}'."
            )

        tags_migrated = 0
        if legacy_tags_table:
            cur = conn.execute(
                f"SELECT project_lower, tag FROM {legacy_tags_table} ORDER BY rowid ASC"
            )
            for row in cur.fetchall():
                project_lower = str(row["project_lower"])
                tag = str(row["tag"])
                pid = projects_by_lower.get(project_lower)
                if pid is None:
                    warnings.append(
                        f"Skipping tag '{tag}' for unknown project '{project_lower}'."
                    )
                    continue
                res = conn.execute(
                    "INSERT OR IGNORE INTO project_tags (project_id, tag) VALUES (?, ?)",
                    (pid, tag),
                )
                if res.rowcount:
                    tags_migrated += res.rowcount

        tasks_migrated = 0
        for table, project_entries in table_to_projects.items():
            if not _table_exists(conn, table):
                warnings.append(f"Legacy task table '{table}' not found; skipping.")
                continue
            rows = _select_task_rows(conn, table)
            if not rows:
                continue
            base_rows: list[tuple[int, str, str, str, str, str, int]] = []
            for row in rows:
                try:
                    task_id = int(row["task_id"])
                except (TypeError, ValueError):
                    warnings.append(
                        f"Skipping row with invalid task_id in '{table}'."
                    )
                    continue
                base_rows.append(
                    (
                        task_id,
                        str(row["summary"] or ""),
                        str(row["assignee"] or ""),
                        str(row["remarks"] or ""),
                        str(row["status"] or ""),
                        str(row["priority"] or ""),
                        1 if row["highlight"] else 0,
                    )
                )
            if not base_rows:
                continue
            for _name, pid in project_entries:
                payload = [
                    (pid, *row) for row in base_rows
                ]
                conn.executemany(
                    """
                    INSERT INTO tasks (
                        project_id, task_id, summary, assignee, remarks, status, priority, highlight
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
                tasks_migrated += len(base_rows)

        conn.execute("COMMIT")
        log(f"Projects migrated: {len(projects_by_name)}")
        log(f"Tasks migrated: {tasks_migrated}")
        log(f"Project tags migrated: {tags_migrated}")
        if warnings:
            log("Warnings:")
            for warning in warnings:
                log(f"- {warning}")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate legacy Taskman per-project tables to unified tables."
    )
    parser.add_argument(
        "--config",
        help="Path to config JSON (uses DATA_STORE_PATH).",
    )
    parser.add_argument(
        "--db",
        help="Path to taskman.db (overrides --config).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    if args.config and args.db:
        raise ValueError("Use either --config or --db, not both.")

    if args.config:
        load_config(args.config)
        db_path = get_data_store_dir() / "taskman.db"
    elif args.db:
        db_path = Path(args.db)
    else:
        db_path = get_data_store_dir() / "taskman.db"

    migrate_taskman_db(db_path)
    return 0
