#!/usr/bin/env python3
"""One-time migration of project registry (projects/tags) into SQLite."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

try:
    from taskman.server.project_manager import ProjectManager
    from taskman.server.sqlite_storage import SQLiteTaskStore, _DEFAULT_DB_DIR
except ImportError:  # pragma: no cover
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from taskman.server.project_manager import ProjectManager
    from taskman.server.sqlite_storage import SQLiteTaskStore, _DEFAULT_DB_DIR


def _load_projects(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    if isinstance(data, list):
        return [str(p) for p in data if isinstance(p, str) and p.strip()]
    return []


def _load_tags(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned: Dict[str, List[str]] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, list):
            continue
        key_l = key.lower()
        tags: List[str] = []
        for tag in value:
            if isinstance(tag, (str, int, float)):
                val = str(tag).strip()
                if val:
                    tags.append(val)
        cleaned[key_l] = tags
    return cleaned


def migrate() -> None:
    os.makedirs(_DEFAULT_DB_DIR, exist_ok=True)
    projects_path = _DEFAULT_DB_DIR / "projects.json"
    tags_path = _DEFAULT_DB_DIR / "project_tags.json"

    projects = _load_projects(projects_path)
    tags = _load_tags(tags_path)

    if not projects and not tags:
        print("No legacy registry files found. Nothing to migrate.")
        return

    with SQLiteTaskStore() as store:
        for name in projects:
            store.upsert_project_name(name)
        for project_lower, tag_list in tags.items():
            store.add_tags(project_lower, tag_list)

    print(f"Migrated {len(projects)} projects and {sum(len(v) for v in tags.values())} tags into SQLite.")


if __name__ == "__main__":
    migrate()
