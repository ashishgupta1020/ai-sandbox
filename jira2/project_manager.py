import json
import os

class ProjectManager:
    PROJECTS_FILE = "projects.json"  # File to store project names

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
    def load_project_names() -> list[str]:
        """
        Load all project names from the projects file.
        """
        if os.path.exists(ProjectManager.PROJECTS_FILE):
            with open(ProjectManager.PROJECTS_FILE, "r") as file:
                return json.load(file)
        return []

    @staticmethod
    def list_projects() -> None:
        """
        Print all saved project names to the console.
        """
        projects = ProjectManager.load_project_names()
        if not projects:
            print("No projects found.")
        else:
            print("Projects:")
            for idx, project_name in enumerate(projects, start=1):
                print(f"{idx}. {project_name}")
