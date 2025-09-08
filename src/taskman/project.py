import json
import os
from typing import Optional, Tuple, Iterator, Dict
from taskman.task import Task, TaskStatus, TaskPriority
from taskman.project_manager import ProjectManager

class Project:
    def __init__(self, name: str, file=None) -> None:
        """
        Initialize a Project with a name and load its tasks from file.
        """
        self.name = name
        # Backing store: dict keyed by task ID for fast lookups/updates
        self._tasks_by_id: Dict[int, Task] = {}
        # Tracks the last assigned task ID for this project. Starts at -1 so first is 0.
        self.last_id: int = -1
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
        payload = {
            "last_id": self.last_id,
            "tasks": [task.to_dict() for task in self._tasks_by_id.values()],
        }
        json.dump(payload, self.file, indent=4)
        self.file.flush()

    def load_tasks_from_file(self) -> None:
        """
        Load tasks from the project's tasks file.
        """
        # Strict loader: expect {"last_id": int, "tasks": [ ... ]}
        try:
            self.file.seek(0)
            data = json.load(self.file)
            if not isinstance(data, dict):
                self._tasks_by_id = {}
                self.last_id = -1
                return
            raw_tasks = data.get("tasks", [])
            if not isinstance(raw_tasks, list):
                raw_tasks = []
            # Build tasks and compute max id
            tasks_map: dict[int, Task] = {}
            computed_last_id = -1
            for d in raw_tasks:
                t = Task.from_dict(d)
                tid = getattr(t, "id", None)
                if tid is None:
                    continue
                itid = int(tid)
                tasks_map[itid] = t
                computed_last_id = max(computed_last_id, itid)
            self._tasks_by_id = tasks_map

            try:
                self.last_id = int(data.get("last_id", -1))
            except (TypeError, ValueError):
                self.last_id = -1
            if computed_last_id != self.last_id:
                self.last_id = computed_last_id
                # Persist corrected metadata while keeping tasks unchanged
                self.save_tasks_to_file()
        except json.JSONDecodeError:
            # If file is empty/corrupt, start with an empty task list.
            self._tasks_by_id = {}
            self.last_id = -1

    def iter_tasks(self) -> Iterator[Task]:
        """Iterate over tasks in their current order."""
        return iter(self._tasks_by_id.values())

    def add_task(self, task: 'Task') -> int:
        """
        Add a new task to the project and save to file.
        """
        # Always assign a new monotonically increasing ID, ignoring any provided value
        self.last_id = (self.last_id if isinstance(self.last_id, int) else -1)
        task.id = self.last_id + 1
        self.last_id = task.id
        # Insert into dict keyed by id
        self._tasks_by_id[int(task.id)] = task
        self.save_tasks_to_file()
        return int(task.id)


    def edit_task(self, task_id: int, new_task: 'Task') -> None:
        """
        Update the details of a task identified by ID using a new Task object.
        """
        # Find task by ID
        if int(task_id) not in self._tasks_by_id:
            print("Invalid task id.")
            return
        # Preserve the original task ID
        new_task.id = int(task_id)
        self._tasks_by_id[int(task_id)] = new_task
        self.save_tasks_to_file()
        print("Task updated successfully.")

    # API support: validate and apply partial updates from request JSON
    def update_task_from_payload(self, payload: dict) -> tuple[dict, int]:
        """
        Validate an edit payload and update a single task, saving to file.

        Expected payload:
          { "id": <int task id>, "fields": {allowed partial fields} }

        Returns a tuple of (response_json, http_status).
        """
        if not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        # Validate id
        try:
            tid = int(payload.get("id", -1))
        except (TypeError, ValueError):
            return {"error": "'id' must be an integer"}, 400
        fields = payload.get("fields")
        if not isinstance(fields, dict) or not fields:
            return {"error": "'fields' must be a non-empty object"}, 400

        allowed = {"id", "summary", "assignee", "remarks", "status", "priority"}
        if any(k not in allowed for k in fields.keys()):
            return {"error": "Unknown fields present"}, 400

        # Resolve task by ID
        task = self._tasks_by_id.get(tid)
        if task is None:
            return {"error": "Task not found"}, 400

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

        return {"ok": True, "id": tid, "task": task.to_dict()}, 200

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
        
        try:
            # Use the common add_task path to assign ID and persist
            self.add_task(new_task)
        except Exception as e:
            return {"error": f"Failed to save: {e}"}, 500

        # Return new task id for clients; index is derivable client-side
        return {"ok": True, "id": new_task.id, "task": new_task.to_dict()}, 200


    # API support: validate and delete a task from request JSON
    def delete_task_from_payload(self, payload: Optional[dict]) -> Tuple[dict, int]:
        """
        Validate a deletion payload and remove a task by ID, saving to file.

        Expected payload:
          { "id": <int task id> }

        Returns a tuple of (response_json, http_status).
        """
        if payload is None or not isinstance(payload, dict):
            return {"error": "Invalid payload"}, 400
        try:
            tid = int(payload.get("id", -1))
        except (TypeError, ValueError):
            return {"error": "'id' must be an integer"}, 400
        if tid not in self._tasks_by_id:
            return {"error": "Task not found"}, 400
        # Remove and persist
        removed = self._tasks_by_id.pop(tid, None)
        if removed is None:
            return {"error": "Task not found"}, 400
        try:
            self.save_tasks_to_file()
        except Exception as e:
            return {"error": f"Failed to save: {e}"}, 500
        return {"ok": True, "id": tid, "task": removed.to_dict()}, 200
