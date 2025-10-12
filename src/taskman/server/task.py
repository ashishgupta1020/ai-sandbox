from enum import Enum
from typing import Optional

class TaskStatus(Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"

class TaskPriority(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class Task:
    """
    Represents a single task with summary, assignee, remarks, status, and priority.
    """

    def __init__(self, summary: str, assignee: str, remarks: str, status: str, priority: str, id: Optional[int] = None) -> None:
        # Stable identifier for the task within a project. Assigned by Project.
        self.id: Optional[int] = id
        self.summary = summary  # Short description of the task
        self.assignee = assignee  # Person responsible for the task
        self.remarks = remarks  # Additional notes or comments
        # Store status and priority as enums for type safety and consistency.
        self.status: TaskStatus = TaskStatus(status)  # Task status (e.g., Not Started, In Progress, Completed)
        self.priority: TaskPriority = TaskPriority(priority)  # Task priority (Low, Medium, High)

    def to_dict(self) -> dict:
        """
        Convert the Task object to a dictionary for serialization.
        """
        return {
            "id": self.id,
            "summary": self.summary,
            "assignee": self.assignee,
            "remarks": self.remarks,
            "status": self.status.value,
            "priority": self.priority.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """
        Create a Task object from a dictionary.
        Expects an 'id' field to be present.
        """
        raw_id = data["id"]  # may be None for freshly created, not yet assigned tasks
        tid = int(raw_id) if raw_id is not None else None
        return cls(
            summary=data["summary"],
            assignee=data["assignee"],
            remarks=data["remarks"],
            status=data["status"],
            priority=data["priority"],
            id=tid,
        )
