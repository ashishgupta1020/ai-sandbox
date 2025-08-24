import json
import os
import textwrap
from prettytable import PrettyTable

class ProjectManager:
    PROJECTS_FILE = "projects.json"

    @staticmethod
    def save_project_name(project_name: str) -> None:
        # Save a new project name to the projects file if not already present
        projects = ProjectManager.load_project_names()
        if project_name not in projects:
            projects.append(project_name)
            with open(ProjectManager.PROJECTS_FILE, "w") as file:
                json.dump(projects, file, indent=4)

    @staticmethod
    def load_project_names() -> list[str]:
        # Load all project names from the projects file
        if os.path.exists(ProjectManager.PROJECTS_FILE):
            with open(ProjectManager.PROJECTS_FILE, "r") as file:
                return json.load(file)
        return []

    @staticmethod
    def list_projects() -> None:
        # Print all available projects
        projects = ProjectManager.load_project_names()
        if not projects:
            print("No projects found.")
        else:
            print("Projects:")
            for idx, project_name in enumerate(projects, start=1):
                print(f"{idx}. {project_name}")


class Project:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tasks = []
        # Open the task file for this project in append+read mode
        self.file = open(f"{self.name}_tasks.json", "a+")
        self.file.seek(0)  # Move to the beginning of the file
        self.load_tasks_from_file()

    def __del__(self) -> None:
        # Ensure the file is closed when the object is deleted
        self.file.close()

    def save_tasks_to_file(self) -> None:
        # Save all tasks to the project's task file
        self.file.seek(0)
        self.file.truncate()
        json.dump([task.to_dict() for task in self.tasks], self.file, indent=4)
        self.file.flush()

    def load_tasks_from_file(self) -> None:
        # Load all tasks from the project's task file
        try:
            self.file.seek(0)
            tasks_data = json.load(self.file)
            self.tasks = [Task.from_dict(data) for data in tasks_data]
        except json.JSONDecodeError:
            self.tasks = []  # Handle empty or invalid JSON

    def add_task(self, task: 'Task') -> None:
        # Add a new task and save to file
        self.tasks.append(task)
        self.save_tasks_to_file()

    def list_tasks(self) -> None:
        # Print all tasks in a pretty table
        if not self.tasks:
            print("No tasks found in this project.")
        else:
            print(f"Tasks in project '{self.name}':")
            table = PrettyTable(["Index", "Summary", "Assignee", "Status", "Priority", "Remarks"])
            table.align = "l"

            for idx, task in enumerate(self.tasks, start=1):
                wrapped_summary = textwrap.fill(task.summary, width=40)
                wrapped_assignee = textwrap.fill(task.assignee, width=20)
                wrapped_status = textwrap.fill(task.status, width=15)
                wrapped_priority = textwrap.fill(task.priority, width=10)
                wrapped_remarks = textwrap.fill(task.remarks, width=80)

                table.add_row([
                    idx,
                    wrapped_summary,
                    wrapped_assignee,
                    wrapped_status,
                    wrapped_priority,
                    wrapped_remarks
                ])
            print(table)

    def edit_task(self, task_index: int) -> None:
        # Edit an existing task by index
        if task_index < 1 or task_index > len(self.tasks):
            print("Invalid task index.")
            return

        task = self.tasks[task_index - 1]
        print(f"Editing Task {task_index}:")
        print(f"Current Summary: {task.summary}")
        new_summary = input("Enter new summary (leave blank to keep current): ")
        if new_summary:
            task.summary = new_summary

        print(f"Current Assignee: {task.assignee}")
        new_assignee = input("Enter new assignee (leave blank to keep current): ")
        if new_assignee:
            task.assignee = new_assignee

        print(f"Current Remarks: {task.remarks}")
        new_remarks = input("Enter new remarks (leave blank to keep current): ")
        if new_remarks:
            task.remarks = new_remarks

        # Status selection
        status_options = ["Not Started", "In Progress", "Completed"]
        print(f"Current Status: {task.status}")
        print("Select new status:")
        for idx, option in enumerate(status_options, start=1):
            print(f"{idx}. {option}")
        new_status = None
        while new_status not in range(1, len(status_options) + 1):
            try:
                new_status = int(input("Enter the number corresponding to the new status (leave blank to keep current): "))
            except ValueError:
                break
        if new_status:
            task.status = status_options[new_status - 1]

        # Priority selection
        priority_options = ["Low", "Medium", "High"]
        print(f"Current Priority: {task.priority}")
        print("Select new priority:")
        for idx, option in enumerate(priority_options, start=1):
            print(f"{idx}. {option}")
        new_priority = None
        while new_priority not in range(1, len(priority_options) + 1):
            try:
                new_priority = int(input("Enter the number corresponding to the new priority (leave blank to keep current): "))
            except ValueError:
                break
        if new_priority:
            task.priority = priority_options[new_priority - 1]

        self.save_tasks_to_file()
        print("Task updated successfully.")


    def export_tasks_to_markdown(self) -> str:
        """
        Export all tasks of the project into a Markdown table.
        Returns the Markdown string.
        """
        if not self.tasks:
            return "No tasks found in this project."

        headers = ["Index", "Summary", "Assignee", "Status", "Priority", "Remarks"]
        md = "| " + " | ".join(headers) + " |\n"
        # Proper separator row for Markdown tables
        md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for idx, task in enumerate(self.tasks, start=1):
            row = [
                str(idx),
                task.summary.replace("|", "\\|"),
                task.assignee.replace("|", "\\|"),
                task.status.replace("|", "\\|"),
                task.priority.replace("|", "\\|"),
                task.remarks.replace("|", "\\|"),
            ]
            md += "| " + " | ".join(row) + " |\n"
        return md

    def export_tasks_to_markdown_file(self, filename: str = "tasks_export.md") -> None:
        """
        Export all tasks to a markdown file.
        """
        md_output = self.export_tasks_to_markdown()
        with open(filename, "w") as md_file:
            md_file.write(md_output)
        print(f"\nTasks exported to Markdown file: '{filename}'")
class Task:
    def __init__(self, summary: str, assignee: str, remarks: str, status: str, priority: str) -> None:
        # Initialize a Task object
        self.summary = summary
        self.assignee = assignee
        self.remarks = remarks
        self.status = status
        self.priority = priority

    def to_dict(self) -> dict:
        # Convert the Task object to a dictionary for JSON serialization
        return {
            "summary": self.summary,
            "assignee": self.assignee,
            "remarks": self.remarks,
            "status": self.status,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        # Create a Task object from a dictionary
        return cls(
            summary=data["summary"],
            assignee=data["assignee"],
            remarks=data["remarks"],
            status=data["status"],
            priority=data["priority"],
        )


class Interaction:
    @staticmethod
    def get_project_name() -> str:
        # Prompt user for project name
        return input("Enter the project name: ")

    @staticmethod
    def get_task_details() -> 'Task':
        # Prompt user for all task details and return a Task object
        summary = input("Enter the task summary: ")
        assignee = input("Enter the assignee: ")
        remarks = input("Enter remarks: ")

        # Status selection
        status_options = ["Not Started", "In Progress", "Completed"]
        print("Select the status of the task:")
        for idx, option in enumerate(status_options, start=1):
            print(f"{idx}. {option}")
        status = None
        while status not in range(1, len(status_options) + 1):
            try:
                status = int(input("Enter the number corresponding to the status: "))
            except ValueError:
                pass
        status = status_options[status - 1]

        # Priority selection
        priority_options = ["Low", "Medium", "High"]
        print("Select the priority of the task:")
        for idx, option in enumerate(priority_options, start=1):
            print(f"{idx}. {option}")
        priority = None
        while priority not in range(1, len(priority_options) + 1):
            try:
                priority = int(input("Enter the number corresponding to the priority: "))
            except ValueError:
                pass
        priority = priority_options[priority - 1]

        return Task(summary, assignee, remarks, status, priority)


def main_cli() -> None:
    # Main entry point for the CLI application
    interaction = Interaction()
    current_project = None

    print("\nWelcome to the Task Manager!")
    print("=" * 30)

    while not current_project:
        print("\nMain Menu:")
        print("-" * 30)
        print("1. List all projects")
        print("2. Open a project")
        print("3. Exit")
        print("-" * 30)
        choice = input("Enter your choice: ")

        if choice == "1":
            print("\nListing all projects:")
            print("-" * 30)
            ProjectManager.list_projects()
        elif choice == "2":
            project_name = interaction.get_project_name()
            ProjectManager.save_project_name(project_name)
            current_project = Project(project_name)
            print(f"\nOpened project: '{current_project.name}'")
        elif choice == "3":
            print("\nExiting Task Manager. Goodbye!")
            return
        else:
            print("\nInvalid choice. Please try again.")

    while True:
        print("\nProject Menu:")
        print("=" * 30)
        print(f"Current Project: {current_project.name}")
        print("-" * 30)
        print("1. Add a task to the current project")
        print("2. List all tasks in the current project")
        print("3. Edit a task in the current project")
        print("4. List all projects")
        print("5. Switch project")
        print("6. Export tasks to Markdown")
        print("7. Exit")
        print("-" * 30)
        choice = input("Enter your choice: ")

        if choice == "1":
            print("\nAdding a new task:")
            print("-" * 30)
            task = interaction.get_task_details()
            current_project.add_task(task)
            print(f"\nTask added successfully to project: '{current_project.name}'")
        elif choice == "2":
            print(f"\nListing tasks in project: '{current_project.name}'")
            print("-" * 30)
            current_project.list_tasks()
        elif choice == "3":
            print(f"\nEditing tasks in project: '{current_project.name}'")
            print("-" * 30)
            current_project.list_tasks()
            try:
                task_index = int(input("\nEnter the index of the task to edit: "))
                current_project.edit_task(task_index)
            except ValueError:
                print("\nInvalid input. Please enter a valid task index.")
        elif choice == "4":
            print("\nListing all projects:")
            print("-" * 30)
            ProjectManager.list_projects()
        elif choice == "5":
            print("\nSwitching project:")
            print("-" * 30)
            project_name = interaction.get_project_name()
            ProjectManager.save_project_name(project_name)
            current_project = Project(project_name)
            print(f"\nSwitched to project: '{current_project.name}'")
        elif choice == "6":
            current_project.export_tasks_to_markdown_file()
        elif choice == "7":
            print("\nExiting Task Manager. Goodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")

if __name__ == "__main__":
    main_cli()