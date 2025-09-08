from __future__ import annotations

import textwrap
from typing import List, Optional
from prettytable import PrettyTable

from taskman.client.api_client import TaskmanApiClient
from taskman.project_manager import ProjectManager
from taskman.task import Task, TaskStatus, TaskPriority


class ProjectAdapter:
    """
    Adapter exposing a subset of the Project interface, backed by REST API.

    Methods mirror what's used by the CLI so we can swap it in without
    changing CLI flows much.
    """

    def __init__(self, name: str, client: TaskmanApiClient) -> None:
        self.name = name
        self._client = client
        # local cache to support CLI flows that inspect length; populated on demand
        self.tasks: List[Task] = []
        self._refresh_cache()

    # ----- internals -----
    def _refresh_cache(self) -> None:
        items = self._client.get_tasks(self.name)
        self.tasks = [Task.from_dict(it) for it in items]

    # ----- CLI-compatible methods -----
    def add_task(self, task: Task) -> None:
        self._client.create_task(self.name, task.to_dict())

    def edit_task(self, task_index: int, new_task: Task) -> None:
        # CLI passes 1-based index
        if task_index < 1:
            print("Invalid task index.")
            return
        # Map index to ID using current cache snapshot (matches last list shown)
        index0 = task_index - 1
        if index0 < 0 or index0 >= len(self.tasks):
            print("Invalid task index.")
            return
        task_id = getattr(self.tasks[index0], "id", None)
        if task_id is None:
            print("Invalid task index.")
            return

        # Perform update by ID
        self._client.update_task(self.name, int(task_id), new_task.to_dict())
        print("Task updated successfully.")

    def list_tasks(self, sort_by: Optional[str] = None) -> None:
        self._refresh_cache()
        if not self.tasks:
            print("No tasks found in this project.")
            return

        print(f"Tasks in project '{self.name}':")
        table = PrettyTable(["Index", "Summary", "Assignee", "Status", "Priority", "Remarks"])
        table.align = "l"

        indexed_tasks = list(enumerate(self.tasks, start=1))
        if sort_by == "status":
            status_order = [s.value.lower() for s in TaskStatus]
            def status_key(item):
                _idx, t = item
                status = t.status.value.lower()
                return status_order.index(status) if status in status_order else len(status_order)
            indexed_tasks = sorted(indexed_tasks, key=status_key)
        elif sort_by == "priority":
            priority_order = [p.value.lower() for p in TaskPriority]
            def priority_key(item):
                _idx, t = item
                priority = t.priority.value.lower()
                return priority_order.index(priority) if priority in priority_order else len(priority_order)
            indexed_tasks = sorted(indexed_tasks, key=priority_key)

        for idx, task in indexed_tasks:
            wrapped_summary = textwrap.fill(task.summary, width=40)
            wrapped_assignee = textwrap.fill(task.assignee, width=20)
            wrapped_status = textwrap.fill(task.status.value, width=15)
            wrapped_priority = textwrap.fill(task.priority.value, width=10)
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

    def export_tasks_to_markdown_file(self) -> None:
        self._refresh_cache()
        if not self.tasks:
            md_output = "No tasks found in this project."
        else:
            headers = ["Index", "Summary", "Assignee", "Status", "Priority", "Remarks"]
            lines = []
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            for idx, task in enumerate(self.tasks, start=1):
                row = [
                    str(idx),
                    task.summary.replace("|", "\\|"),
                    task.assignee.replace("|", "\\|"),
                    task.status.value.replace("|", "\\|"),
                    task.priority.value.replace("|", "\\|"),
                    task.remarks.replace("|", "\\|"),
                ]
                lines.append("| " + " | ".join(row) + " |")
            md_output = "\n".join(lines) + "\n"

        md_path = ProjectManager.get_markdown_file_path(self.name)
        with open(md_path, "w") as md_file:
            md_file.write(md_output)
        print(f"\nTasks exported to Markdown file: '{md_path}'")
