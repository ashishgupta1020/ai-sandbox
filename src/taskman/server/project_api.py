from __future__ import annotations

"""Project and task API helpers backed directly by TaskStore."""

from typing import Callable, Dict, Optional, Tuple
from pathlib import Path

from taskman.config import get_data_store_dir
from .task_store import TaskStore


class ProjectAPI:
    """Encapsulate project/tag operations for HTTP handlers."""

    def __init__(self, store_factory: Optional[Callable[[], TaskStore]] = None) -> None:
        self._store_factory = store_factory or (lambda: TaskStore())

    @staticmethod
    def _invalid_name(name: str) -> bool:
        return (not name) or (".." in name) or name.startswith(".") or ("/" in name)

    @staticmethod
    def _current_name(cur_obj: object) -> Optional[str]:
        try:
            return getattr(cur_obj, "name", None)
        except Exception:
            return None

    @staticmethod
    def _markdown_file_path(project_name: str) -> Path:
        base = get_data_store_dir()
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{project_name.lower()}_tasks_export.md"

    def list_projects(self, current_project: Optional[object]) -> Tuple[Dict[str, object], int]:
        with self._store_factory() as store:
            projects = store.list_projects()
        current = self._current_name(current_project)
        return {"projects": projects, "currentProject": current}, 200

    def list_project_names(self, case_insensitive: bool = False) -> list[str]:
        with self._store_factory() as store:
            projects = store.list_projects()
        if case_insensitive:
            return [p.lower() for p in projects]
        return projects

    def list_project_tags(self) -> Tuple[Dict[str, object], int]:
        try:
            with self._store_factory() as store:
                tags = store.get_tags_for_all_projects()
            return {"tagsByProject": tags}, 200
        except Exception as exc:
            return {"error": f"Failed to fetch project tags: {exc}"}, 500

    def get_state(self, current_project: Optional[object]) -> Tuple[Dict[str, object], int]:
        current = self._current_name(current_project)
        return {"currentProject": current}, 200

    def get_project_tags(self, name: str) -> Tuple[Dict[str, object], int]:
        if self._invalid_name(name):
            return {"error": "Invalid project name"}, 400
        with self._store_factory() as store:
            tags = store.get_tags_for_project(name)
        return {"project": name, "tags": tags}, 200

    def add_project_tags(self, name: str, tags_val: object) -> Tuple[Dict[str, object], int]:
        if self._invalid_name(name):
            return {"error": "Invalid project name"}, 400
        tags: list[str] = []
        if isinstance(tags_val, list):
            tags = [str(t) for t in tags_val]
        if not tags:
            return {"error": "No tags provided"}, 400
        with self._store_factory() as store:
            updated = store.add_tags(name, tags)
        return {"project": name, "tags": updated}, 200

    def remove_project_tag(self, name: str, tag_val: object) -> Tuple[Dict[str, object], int]:
        if self._invalid_name(name):
            return {"error": "Invalid project name"}, 400
        if not isinstance(tag_val, str) or not tag_val.strip():
            return {"error": "No tag provided"}, 400
        with self._store_factory() as store:
            updated = store.remove_tag(name, tag_val.strip())
        return {"project": name, "tags": updated}, 200

    def open_project(self, name: object) -> Tuple[Dict[str, object], int, Optional[str]]:
        if name is None:
            return {"error": "Missing 'name'"}, 400, None
        clean = str(name).strip()
        if not clean:
            return {"error": "Missing 'name'"}, 400, None
        try:
            with self._store_factory() as store:
                canonical = store.upsert_project_name(clean)
            return {"ok": True, "currentProject": canonical}, 200, canonical
        except Exception as exc:
            return {"error": str(exc)}, 500, None

    def edit_project_name(
        self, old_name: object, new_name: object, current_project: Optional[object] = None
    ) -> Tuple[Dict[str, object], int, Optional[str]]:
        old = str(old_name or "").strip()
        new = str(new_name or "").strip()
        if not old or not new:
            return {"error": "'old_name' and 'new_name' required"}, 400, None

        try:
            with self._store_factory() as store:
                store.rename_project(old, new)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}, 400, None

        # Rename markdown export if present
        old_md = self._markdown_file_path(old)
        new_md = self._markdown_file_path(new)
        try:
            if old_md.exists():
                old_md.rename(new_md)
        except Exception:
            # Non-fatal; keep going
            pass

        cur_name = self._current_name(current_project)
        new_current = new if (cur_name and cur_name.lower() == old.lower()) else cur_name

        return {"ok": True, "currentProject": new_current}, 200, new_current
