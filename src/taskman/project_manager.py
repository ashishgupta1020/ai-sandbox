import json
import os

class ProjectManager:
    PROJECTS_DIR = os.path.expanduser("~/sandbox/data/ai-sandbox")
    PROJECTS_FILE = os.path.join(PROJECTS_DIR, "projects.json")  # File to store project names

    @staticmethod
    def get_task_file_path(project_name: str) -> str:
        """Returns the path to the task file for a given project."""
        return os.path.join(ProjectManager.PROJECTS_DIR, f"{project_name}_tasks.json")

    @staticmethod
    def get_markdown_file_path(project_name: str) -> str:
        """Returns the path to the markdown export file for a given project."""
        return os.path.join(ProjectManager.PROJECTS_DIR, f"{project_name}_tasks_export.md")

    @staticmethod
    def save_project_name(project_name: str) -> None:
        """
        Save a new project name to the projects file if not already present.
        """
        projects = ProjectManager.load_project_names()
        if project_name not in projects:
            projects.append(project_name)
            with open(ProjectManager.PROJECTS_FILE, "w") as file:
                json.dump(projects, file, indent=4)

    @staticmethod
    def edit_project_name(old_name: str, new_name: str) -> bool:
        """
        Edit a project's name. This includes updating the projects file
        and renaming the associated task and markdown files.
        Returns True if successful, False otherwise.
        """
        projects = ProjectManager.load_project_names()
        if old_name not in projects:
            print(f"Error: Project '{old_name}' not found.")
            return False
        if new_name in projects:
            print(f"Error: Project name '{new_name}' already exists.")
            return False

        # Update project name in the list
        projects[projects.index(old_name)] = new_name
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
    def load_project_names() -> list[str]:
        """
        Load all project names from the projects file.
        """
        if os.path.exists(ProjectManager.PROJECTS_FILE):
            with open(ProjectManager.PROJECTS_FILE, "r") as file:
                return json.load(file)
        return []
