import json
import os
import textwrap
from typing import Optional, Tuple
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

    # API support: validate and apply partial updates from request JSON
    def update_task_from_payload(self, payload: dict) -> tuple[dict, int]:
        """
        Validate an edit payload and update a single task, saving to file.

        Expected payload:
          { "index": <int 0-based>, "fields": {allowed partial fields} }

        Returns a tuple of (response_json, http_status).
        """
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        # Validate index
        try:
            index = int(payload.get("index", -1))
        except (TypeError, ValueError):
            return {"error": "'index' must be an integer"}, 400
        fields = payload.get("fields")
        if not isinstance(fields, dict) or not fields:
            return {"error": "'fields' must be a non-empty object"}, 400

        allowed = {"summary", "assignee", "remarks", "status", "priority"}
        if any(k not in allowed for k in fields.keys()):
            return {"error": "Unknown fields present"}, 400

        # Bounds check
        if index < 0 or index >= len(self.tasks):
            return {"error": "Index out of range"}, 400

        # Enum validation
        if "status" in fields:
            try:
                TaskStatus(fields["status"])  # type: ignore[arg-type]
            except Exception:
                return {"error": "Invalid status"}, 400
        if "priority" in fields:
            try:
                TaskPriority(fields["priority"])  # type: ignore[arg-type]
            except Exception:
                return {"error": "Invalid priority"}, 400

        # Apply changes
        task = self.tasks[index]
        if "summary" in fields:
            task.summary = str(fields["summary"]) if fields["summary"] is not None else ""
        if "assignee" in fields:
            task.assignee = str(fields["assignee"]) if fields["assignee"] is not None else ""
        if "remarks" in fields:
            task.remarks = str(fields["remarks"]) if fields["remarks"] is not None else ""
        if "status" in fields:
            task.status = TaskStatus(fields["status"])  # validated above
        if "priority" in fields:
            task.priority = TaskPriority(fields["priority"])  # validated above

        # Persist
        try:
            self.save_tasks_to_file()
        except Exception as e:
            return {"error": f"Failed to save: {e}"}, 500

        return {"ok": True, "index": index, "task": task.to_dict()}, 200

    # API support: validate and create a new task from request JSON
    def create_task_from_payload(self, payload: Optional[dict]) -> Tuple[dict, int]:
        """
        Validate a creation payload and append a new task, saving to file.

        Expected payload (all fields optional; defaults applied when missing):
          { "summary": str, "assignee": str, "remarks": str,
            "status": one of TaskStatus values,
            "priority": one of TaskPriority values }

        Returns a tuple of (response_json, http_status).
        """
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400

        # Extract fields with sensible defaults
        summary = str(payload.get("summary", ""))
        assignee = str(payload.get("assignee", ""))
        remarks = str(payload.get("remarks", ""))
        status_val = payload.get("status", TaskStatus.NOT_STARTED.value)
        priority_val = payload.get("priority", TaskPriority.MEDIUM.value)

        # Validate enums; coerce invalid to defaults
        try:
            TaskStatus(status_val)  # type: ignore[arg-type]
        except Exception:
            status_val = TaskStatus.NOT_STARTED.value
        try:
            TaskPriority(priority_val)  # type: ignore[arg-type]
        except Exception:
            priority_val = TaskPriority.MEDIUM.value

        # Create and persist
        new_task = Task(summary, assignee, remarks, status_val, priority_val)
        self.tasks.append(new_task)
        try:
            self.save_tasks_to_file()
        except Exception as e:
            return {"error": f"Failed to save: {e}"}, 500

        index0 = len(self.tasks) - 1
        return {"ok": True, "index": index0, "task": new_task.to_dict()}, 200

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

    # API support: validate and delete a task from request JSON
    def delete_task_from_payload(self, payload: Optional[dict]) -> Tuple[dict, int]:
        """
        Validate a deletion payload and remove a task by index, saving to file.

        Expected payload:
          { "index": <int 0-based> }

        Returns a tuple of (response_json, http_status).
        """
        if payload is None or not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        try:
            index = int(payload.get("index", -1))
        except (TypeError, ValueError):
            return {"error": "'index' must be an integer"}, 400
        if index < 0 or index >= len(self.tasks):
            return {"error": "Index out of range"}, 400
        # Remove and persist
        removed = self.tasks.pop(index)
        try:
            self.save_tasks_to_file()
        except Exception as e:
            return {"error": f"Failed to save: {e}"}, 500
        return {"ok": True, "index": index, "task": removed.to_dict()}, 200
