"""Lightweight registry for Taskman projects and their backing files."""

import os

from taskman.config import get_data_store_dir
from .sqlite_storage import SQLiteTaskStore

class ProjectManager:
    """Helper for tracking project names and related filesystem paths."""

    @staticmethod
    def _projects_dir() -> str:
        """Resolve and ensure the projects directory exists."""
        base = get_data_store_dir()
        base.mkdir(parents=True, exist_ok=True)
        return str(base)

    @staticmethod
    def get_markdown_file_path(project_name: str) -> str:
        """Returns the path to the markdown export file for a given project."""
        return os.path.join(ProjectManager._projects_dir(), f"{project_name.lower()}_tasks_export.md")

    @staticmethod
    def save_project_name(project_name: str) -> str:
        """
        Save a project name if not already present, and return the stored name.

        Behavior:
        - If a project already exists with the same name ignoring case,
          do not create a duplicate; return the existing (canonical) name.
        - Otherwise, append the provided name and return it.
        """
        with SQLiteTaskStore() as store:
            return store.upsert_project_name(project_name)

    @staticmethod
    def edit_project_name(old_name: str, new_name: str) -> bool:
        """
        Edit a project's name. This includes updating the projects file
        and renaming the associated task and markdown files.
        Returns True if successful, False otherwise.
        """
        try:
            with SQLiteTaskStore() as store:
                store.rename_project(old_name, new_name)
        except ValueError as exc:
            print(f"Error: {exc}")
            return False

        # Rename the associated markdown export file if it exists
        old_md_file = ProjectManager.get_markdown_file_path(old_name)
        new_md_file = ProjectManager.get_markdown_file_path(new_name)
        if os.path.exists(old_md_file):
            os.rename(old_md_file, new_md_file)

        print(f"Project '{old_name}' has been renamed to '{new_name}'.")
        return True

    @staticmethod
    def load_project_names(case_insensitive: bool = False) -> list[str]:
        """
        Load project names from the projects file.

        - When case_insensitive is False (default): returns List[str] of names
          as stored (canonical casing).
        - When case_insensitive is True: returns List[str] of names converted
          to lowercase for convenient case-insensitive membership checks.
        """
        with SQLiteTaskStore() as store:
            projects = store.list_projects()
        if case_insensitive:
            return [p.lower() for p in projects]
        return projects

    # ----- Tags helpers -----
    @staticmethod
    def get_tags_for_project(project_name: str) -> list[str]:
        """Return tags for a project (case-insensitive lookup, keys stored lowercase)."""
        with SQLiteTaskStore() as store:
            return store.get_tags_for_project(project_name)

    @staticmethod
    def get_tags_for_all_projects() -> dict[str, list[str]]:
        """Return tags for all known projects as a mapping of name -> tags list."""
        with SQLiteTaskStore() as store:
            return store.get_tags_for_all_projects()

    @staticmethod
    def add_tags_for_project(project_name: str, tags: list[str]) -> list[str]:
        """Add tags to a project, returning the updated list."""
        with SQLiteTaskStore() as store:
            return store.add_tags(project_name, tags)

    @staticmethod
    def remove_tag_for_project(project_name: str, tag: str) -> list[str]:
        """Remove a single tag from a project, returning the updated list."""
        with SQLiteTaskStore() as store:
            return store.remove_tag(project_name, tag)
