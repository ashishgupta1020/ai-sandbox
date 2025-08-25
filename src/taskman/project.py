import json
import textwrap
from prettytable import PrettyTable
from taskman.task import Task

class Project:
    def __init__(self, name: str, file=None) -> None:
        """
        Initialize a Project with a name and load its tasks from file.
        """
        import os
        self.name = name
        self.tasks = []
        data_dir = os.path.expanduser("~/sandbox/data/ai-sandbox")
        os.makedirs(data_dir, exist_ok=True)
        self.task_file_path = os.path.join(data_dir, f"{self.name}_tasks.json")
        self.markdown_file_path = os.path.join(data_dir, f"{self.name}_tasks_export.md")
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
            self.tasks = []

    def add_task(self, task: 'Task') -> None:
        """
        Add a new task to the project and save to file.
        """
        self.tasks.append(task)
        self.save_tasks_to_file()

    def list_tasks(self) -> None:
        """
        Print all tasks in the project in a formatted table.
        """
        if not self.tasks:
            print("No tasks found in this project.")
        else:
            print(f"Tasks in project '{self.name}':")
            table = PrettyTable(["Index", "Summary", "Assignee", "Status", "Priority", "Remarks"])
            table.align = "l"
            for idx, task in enumerate(self.tasks, start=1):
                # Wrap text for better display
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
        """
        Edit the details of a task by its index.
        Prompts user for new values, allows skipping fields.
        """
        if task_index < 1 or task_index > len(self.tasks):
            print("Invalid task index.")
            return
        task = self.tasks[task_index - 1]
        print(f"Editing Task {task_index}:")
        # Edit summary
        print(f"Current Summary: {task.summary}")
        new_summary = input("Enter new summary (leave blank to keep current): ")
        if new_summary:
            task.summary = new_summary
        # Edit assignee
        print(f"Current Assignee: {task.assignee}")
        new_assignee = input("Enter new assignee (leave blank to keep current): ")
        if new_assignee:
            task.assignee = new_assignee
        # Edit remarks
        print(f"Current Remarks: {task.remarks}")
        new_remarks = input("Enter new remarks (leave blank to keep current): ")
        if new_remarks:
            task.remarks = new_remarks
        # Edit status
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
        # Edit priority
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
                task.status.replace("|", "\\|"),
                task.priority.replace("|", "\\|"),
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
