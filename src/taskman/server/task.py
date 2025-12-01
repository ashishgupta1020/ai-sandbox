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
    """Represents a single task with core metadata and highlight flag."""

    def __init__(
        self,
        summary: str,
        assignee: str,
        remarks: str,
        status: str,
        priority: str,
        highlight: bool = False,
        id: Optional[int] = None,
    ) -> None:
        """
        Initialize a task.

        ``status`` and ``priority`` accept :class:`TaskStatus` / :class:`TaskPriority`
        values or their string representations. ``id`` is assigned by :class:`Project`
        when the task is persisted.
        """
        # Stable identifier for the task within a project; assigned during persistence.
        self.id: Optional[int] = id
        self.summary = summary
        self.assignee = assignee
        self.remarks = remarks
        self.status: TaskStatus = TaskStatus(status)
        self.priority: TaskPriority = TaskPriority(priority)
        self.highlight: bool = bool(highlight)

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
            "highlight": bool(self.highlight),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """
        Create a Task object from a dictionary payload (API or DB row).
        Expects an 'id' field to be present and coerces highlight to bool.
        """
        raw_id = data["id"]  # may be None for freshly created, not yet assigned tasks
        tid = int(raw_id) if raw_id is not None else None
        return cls(
            summary=data["summary"],
            assignee=data["assignee"],
            remarks=data["remarks"],
            status=data["status"],
            priority=data["priority"],
            highlight=bool(data.get("highlight")),
            id=tid,
        )
