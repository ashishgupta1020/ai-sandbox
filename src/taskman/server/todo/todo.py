from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TodoPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    @classmethod
    def from_value(cls, value: str) -> "TodoPriority":
        try:
            return cls(value.lower())
        except Exception:
            return cls.MEDIUM


@dataclass
class Todo:
    """Represents a Todo entry."""

    title: str
    note: str = ""
    due_date: str = ""
    people: List[str] = field(default_factory=list)
    priority: TodoPriority = TodoPriority.MEDIUM
    done: bool = False
    id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "note": self.note,
            "due_date": self.due_date,
            "people": list(self.people),
            "priority": self.priority.value,
            "done": bool(self.done),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Todo":
        return cls(
            id=data.get("id"),
            title=data.get("title", ""),
            note=data.get("note", ""),
            due_date=data.get("due_date", ""),
            people=list(data.get("people") or []),
            priority=TodoPriority.from_value(str(data.get("priority") or "")),
            done=bool(data.get("done")),
        )
