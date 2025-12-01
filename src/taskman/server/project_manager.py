"""Lightweight registry for Taskman projects and their backing files."""

import json
import os

class ProjectManager:
    """Helper for tracking project names and related filesystem paths."""
    PROJECTS_DIR = os.path.expanduser("~/taskman/data")
    PROJECTS_FILE = os.path.join(PROJECTS_DIR, "projects.json")  # File to store project names

    @staticmethod
    def get_task_file_path(project_name: str) -> str:
        """Returns the path to the task file for a given project."""
        return os.path.join(ProjectManager.PROJECTS_DIR, f"{project_name.lower()}_tasks.json")

    @staticmethod
    def get_markdown_file_path(project_name: str) -> str:
        """Returns the path to the markdown export file for a given project."""
        return os.path.join(ProjectManager.PROJECTS_DIR, f"{project_name.lower()}_tasks_export.md")

    @staticmethod
    def save_project_name(project_name: str) -> str:
        """
        Save a project name if not already present, and return the stored name.

        Behavior:
        - If a project already exists with the same name ignoring case,
          do not create a duplicate; return the existing (canonical) name.
        - Otherwise, append the provided name and return it.
        """
        # Prevent duplicates that differ only by case
        projects_lower = ProjectManager.load_project_names(True)
        if project_name.lower() in projects_lower:
            # Return canonical casing of existing name
            return ProjectManager.resolve_canonical_name(project_name)
        projects = ProjectManager.load_project_names(False)
        projects.append(project_name)
        with open(ProjectManager.PROJECTS_FILE, "w") as file:
            json.dump(projects, file, indent=4)
        return project_name

    @staticmethod
    def edit_project_name(old_name: str, new_name: str) -> bool:
        """
        Edit a project's name. This includes updating the projects file
        and renaming the associated task and markdown files.
        Returns True if successful, False otherwise.
        """
        projects_lower = ProjectManager.load_project_names(True)
        old_l = old_name.lower()
        new_l = new_name.lower()
        if old_l not in projects_lower:
            print(f"Error: Project '{old_name}' not found.")
            return False

        # Disallow renaming to an existing different project (case-insensitive);
        # allow case-only change for the same project
        old_idx = projects_lower.index(old_l)
        if new_l in projects_lower and projects_lower.index(new_l) != old_idx:
            print(f"Error: Project name '{new_name}' already exists.")
            return False

        projects = ProjectManager.load_project_names(False)
        # Update project name in the case-sensitive projects list
        projects[old_idx] = new_name
        with open(ProjectManager.PROJECTS_FILE, "w") as file:
            json.dump(projects, file, indent=4)

        # Rename the associated task file
        old_task_file = ProjectManager.get_task_file_path(old_name)
        new_task_file = ProjectManager.get_task_file_path(new_name)
        if os.path.exists(old_task_file):
            os.rename(old_task_file, new_task_file)

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
        if os.path.exists(ProjectManager.PROJECTS_FILE):
            with open(ProjectManager.PROJECTS_FILE, "r") as file:
                data = json.load(file)
                if not isinstance(data, list):
                    return []
                if not case_insensitive:
                    return data
                return [p.lower() for p in data]
        return []

    @staticmethod
    def resolve_canonical_name(name: str) -> str:
        """Return the canonical stored casing for a project name if it exists.

        If a project exists in the registry with the same name ignoring case,
        return that stored name; otherwise return the provided name.
        """
        projects = ProjectManager.load_project_names(False)
        nl = name.lower()
        for p in projects:
            if p.lower() == nl:
                return p
        return name
