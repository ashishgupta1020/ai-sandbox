#!/usr/bin/env python3
"""One-time migration of JSON-backed tasks into the SQLite store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from taskman.server.project_manager import ProjectManager
    from taskman.server.sqlite_storage import SQLiteTaskStore
except ImportError:  # pragma: no cover
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from taskman.server.project_manager import ProjectManager
    from taskman.server.sqlite_storage import SQLiteTaskStore


def _load_json_tasks(project_name: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Load tasks from the existing JSON file for a project."""
    path = Path(ProjectManager.get_task_file_path(project_name))
    if not path.exists():
        return -1, []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        return -1, []
    if not isinstance(data, dict):
        return -1, []

    last_id_raw = data.get("last_id", -1)
    try:
        last_id = int(last_id_raw)
    except (TypeError, ValueError):
        last_id = -1

    tasks_payload = data.get("tasks", [])
    tasks: List[Dict[str, Any]] = []
    if isinstance(tasks_payload, list):
        for entry in tasks_payload:
            if not isinstance(entry, dict):
                continue
            tid = entry.get("id")
            try:
                task_id = int(tid)
            except (TypeError, ValueError):
                continue
            tasks.append(
                {
                    "task_id": task_id,
                    "summary": entry.get("summary") or "",
                    "assignee": entry.get("assignee") or "",
                    "remarks": entry.get("remarks") or "",
                    "status": entry.get("status") or "",
                    "priority": entry.get("priority") or "",
                }
            )
    return last_id, tasks


def migrate_project(store: SQLiteTaskStore, project_name: str) -> int:
    """Migrate tasks for a single project into SQLite."""
    _, tasks = _load_json_tasks(project_name)
    if not tasks:
        return 0

    store.bulk_replace(project_name, tasks)
    return len(tasks)


def migrate_all() -> None:
    """Iterate through all projects recorded in projects.json and migrate."""
    os.makedirs(ProjectManager.PROJECTS_DIR, exist_ok=True)

    projects = ProjectManager.load_project_names(False)
    if not projects:
        print("No projects found to migrate.")
        return

    report: List[str] = []
    migrated_count = 0
    with SQLiteTaskStore() as store:
        for name in projects:
            migrated = migrate_project(store, name)
            migrated_count += migrated
            report.append(f"{name}: migrated {migrated} tasks")

    print("Migration complete.")
    for line in report:
        print(" -", line)
    print(f"Total tasks migrated: {migrated_count}")


if __name__ == "__main__":
    migrate_all()
