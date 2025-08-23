#!/usr/bin/env python3
"""
Data models and enums for the task manager
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class Priority(Enum):
    """Task priority levels"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class Status(Enum):
    """Task status levels"""
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    REVIEW = "Review"
    DONE = "Done"
    BLOCKED = "Blocked"
    CANCELLED = "Cancelled"


@dataclass
class Task:
    """Task data structure"""
    id: str
    summary: str
    assignee: str
    remarks: str
    priority: Priority
    tags: List[str]
    created_at: str
    updated_at: str
    status: Status = Status.TODO
