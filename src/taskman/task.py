from enum import Enum

class TaskStatus(Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"

class Task:
    """
    Represents a single task with summary, assignee, remarks, status, and priority.
    """

    def __init__(self, summary: str, assignee: str, remarks: str, status: str, priority: str) -> None:
        self.summary = summary  # Short description of the task
        self.assignee = assignee  # Person responsible for the task
        self.remarks = remarks  # Additional notes or comments
        # Store status as string for compatibility, but use enum for sorting
        # TODO: store as enum too
        self.status = status  # Task status (e.g., Not Started, In Progress, Completed)
        self.priority = priority  # Task priority (Low, Medium, High)

    def to_dict(self) -> dict:
        """
        Convert the Task object to a dictionary for serialization.
        """
        return {
            "summary": self.summary,
            "assignee": self.assignee,
            "remarks": self.remarks,
            "status": self.status,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """
        Create a Task object from a dictionary.
        """
        return cls(
            summary=data["summary"],
            assignee=data["assignee"],
            remarks=data["remarks"],
            status=data["status"],
            priority=data["priority"],
        )
