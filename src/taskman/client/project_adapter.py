from __future__ import annotations

import textwrap
from typing import Dict, List, Optional
from prettytable import PrettyTable

from taskman.client.api_client import TaskmanApiClient
from taskman.server.task import Task, TaskStatus, TaskPriority
from taskman.config import get_data_store_dir


class ProjectAdapter:
    """
    Adapter exposing a subset of the Project interface, backed by REST API.

    Methods mirror what's used by the CLI so we can swap it in without
    changing CLI flows much.
    """

    def __init__(self, name: str, client: TaskmanApiClient) -> None:
        self.name = name
        self._client = client
        # Local cache keyed by task ID for fast lookups; populated on demand
        self.tasks: Dict[int, Task] = {}
        # Maintain display order mapping: 1-based index -> task ID
        self._index_to_id: List[int] = []
        self._refresh_cache()

    # ----- internals -----
    def _refresh_cache(self) -> None:
        items = self._client.get_tasks(self.name)
        self.tasks = {}
        self._index_to_id = []
        for it in items:
            t = Task.from_dict(it)
            if t.id is None:
                continue
            tid = int(t.id)
            self.tasks[tid] = t
            self._index_to_id.append(tid)

    # ----- CLI-compatible methods -----
    def add_task(self, task: Task) -> None:
        self._client.create_task(self.name, task.to_dict())

    def edit_task(self, task_id: int, new_task: Task) -> None:
        if task_id is None or int(task_id) not in self.tasks:
            print("Invalid task id.")
            return
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

        # Build (display_index, Task) pairs using current display order
        indexed_tasks = [(idx, self.tasks[tid]) for idx, tid in enumerate(self._index_to_id, start=1)]
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
            for idx, tid in enumerate(self._index_to_id, start=1):
                task = self.tasks[tid]
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

        base = get_data_store_dir()
        base.mkdir(parents=True, exist_ok=True)
        md_path = base / f"{self.name.lower()}_tasks_export.md"
        with open(md_path, "w") as md_file:
            md_file.write(md_output)
        print(f"\nTasks exported to Markdown file: '{md_path}'")

    # ----- ID-centric helpers for CLI -----
    def get_task_id_by_index(self, task_index: int) -> Optional[int]:
        if task_index < 1 or task_index > len(self._index_to_id):
            return None
        return self._index_to_id[task_index - 1]

    def get_task_by_index(self, task_index: int) -> Optional[Task]:
        tid = self.get_task_id_by_index(task_index)
        return self.tasks.get(tid) if tid is not None else None
