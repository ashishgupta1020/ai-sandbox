import json
import os
import textwrap
from prettytable import PrettyTable
from taskman.task import Task, TaskStatus, TaskPriority
from taskman.project_manager import ProjectManager

class Project:
    def __init__(self, name: str, file=None) -> None:
        """
        Initialize a Project with a name and load its tasks from file.
        """
        self.name = name
        self.tasks = []
        os.makedirs(ProjectManager.PROJECTS_DIR, exist_ok=True)
        self.task_file_path = ProjectManager.get_task_file_path(self.name)
        self.markdown_file_path = ProjectManager.get_markdown_file_path(self.name)
        if file is not None:
            self.file = file
        else:
            self.file = open(self.task_file_path, "a+")
        self.file.seek(0)
        self.load_tasks_from_file()
    
    def __del__(self) -> None:
        """
        Ensure the file is closed when the Project object is deleted.
        """
        self.file.close()

    def save_tasks_to_file(self) -> None:
        """
        Save all tasks to the project's tasks file in JSON format.
        """
        self.file.seek(0)
        self.file.truncate()
        json.dump([task.to_dict() for task in self.tasks], self.file, indent=4)
        self.file.flush()

    def load_tasks_from_file(self) -> None:
        """
        Load tasks from the project's tasks file.
        """
        try:
            self.file.seek(0)
            tasks_data = json.load(self.file)
            self.tasks = [Task.from_dict(data) for data in tasks_data]
        except json.JSONDecodeError:
            # If file is empty/corrupt, start with an empty task list.
            self.tasks = []

    def add_task(self, task: 'Task') -> None:
        """
        Add a new task to the project and save to file.
        """
        self.tasks.append(task)
        self.save_tasks_to_file()

    def list_tasks(self, sort_by: str = None) -> None:
        """
        Print all tasks in the project in a formatted table.
        Optionally sort by 'status' or 'priority'.
        """
        if not self.tasks:
            print("No tasks found in this project.")
        else:
            print(f"Tasks in project '{self.name}':")
            table = PrettyTable(["Index", "Summary", "Assignee", "Status", "Priority", "Remarks"])
            table.align = "l"
            tasks = self.tasks
            if sort_by == "status":
                status_order = [s.value.lower() for s in TaskStatus]
                def status_key(t):
                    status = t.status.value.lower()
                    return status_order.index(status) if status in status_order else len(status_order)
                tasks = sorted(tasks, key=status_key)
            elif sort_by == "priority":
                priority_order = [p.value.lower() for p in TaskPriority]
                def priority_key(t):
                    priority = t.priority.value.lower()
                    return priority_order.index(priority) if priority in priority_order else len(priority_order)
                tasks = sorted(tasks, key=priority_key)
            for idx, task in enumerate(tasks, start=1):
                # Wrap text for better display
                wrapped_summary = textwrap.fill(task.summary, width=40)
                wrapped_assignee = textwrap.fill(task.assignee, width=20)
                wrapped_status = textwrap.fill(task.status.value, width=15)
                wrapped_priority = textwrap.fill(task.priority.value, width=10)
                # Preserve newlines in remarks by wrapping each line individually
                wrapped_remarks = '\n'.join(textwrap.fill(line, width=80) for line in task.remarks.splitlines())
                table.add_row([
                    idx,
                    wrapped_summary,
                    wrapped_assignee,
                    wrapped_status,
                    wrapped_priority,
                    wrapped_remarks
                ])
            print(table)

    def edit_task(self, task_index: int, new_task: 'Task') -> None:
        """
        Update the details of a task by its index using a new Task object.
        """
        if task_index < 1 or task_index > len(self.tasks):
            print("Invalid task index.")
            return
        self.tasks[task_index - 1] = new_task
        self.save_tasks_to_file()
        print("Task updated successfully.")

    def export_tasks_to_markdown(self) -> str:
        """
        Export all tasks to a Markdown table string.
        """
        if not self.tasks:
            return "No tasks found in this project."
        headers = ["Index", "Summary", "Assignee", "Status", "Priority", "Remarks"]
        md = "| " + " | ".join(headers) + " |\n"
        md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for idx, task in enumerate(self.tasks, start=1):
            row = [
                str(idx),
                task.summary.replace("|", "\\|"),
                task.assignee.replace("|", "\\|"),
                task.status.value.replace("|", "\\|"),
                task.priority.value.replace("|", "\\|"),
                task.remarks.replace("|", "\\|"),
            ]
            md += "| " + " | ".join(row) + " |\n"
        return md

    def export_tasks_to_markdown_file(self) -> None:
        """
        Write the Markdown table of tasks to the project's markdown file path.
        """
        md_output = self.export_tasks_to_markdown()
        with open(self.markdown_file_path, "w") as md_file:
            md_file.write(md_output)
        print(f"\nTasks exported to Markdown file: '{self.markdown_file_path}'")
