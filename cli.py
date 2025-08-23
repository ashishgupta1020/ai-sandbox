#!/usr/bin/env python3
"""
Command-line interface and help functions
"""

from models import Priority, Status


def print_help():
    """Print help information"""
    help_text = """
JIRA-like Task Manager - Available Commands:

PROJECT MANAGEMENT:
  create-project <project_name>     - Create a new project
  list-projects                     - List all projects
  delete-project <project_name>     - Delete a project and all its tasks

TASK MANAGEMENT:
  create-task <project_name>        - Create a new task (interactive)
  list-tasks <project_name>         - List all tasks in a project
  list-tasks <project_name> --assignee <name> --priority <level> --status <status> --tags <tag1,tag2>
                                   - List tasks with filters
  view-task <project_name> <task_id> - View detailed task information
  update-task <project_name> <task_id> - Update a task (interactive)
  delete-task <project_name> <task_id> - Delete a task

FEATURES:
  • Remarks support markdown formatting (bold, italic, code, lists, etc.)
  • Multi-line remarks with Enter twice to finish

PRIORITY LEVELS:
  Low, Medium, High, Critical

STATUS LEVELS:
  To Do, In Progress, Review, Done, Blocked, Cancelled

EXAMPLES:
  python task_manager.py create-project "Web App"
  python task_manager.py create-task "Web App"
  python task_manager.py list-tasks "Web App" --assignee "John" --priority "High" --status "In Progress"
  python task_manager.py view-task "Web App" "1"

HELP:
  help                              - Show this help message
  exit                              - Exit the application
"""
    print(help_text)


def parse_filters(parts):
    """Parse filter arguments from command parts"""
    filters = {}
    i = 2  # Start after project name
    
    while i < len(parts):
        if parts[i] == '--assignee' and i + 1 < len(parts):
            filters['assignee'] = parts[i + 1]
            i += 2
        elif parts[i] == '--priority' and i + 1 < len(parts):
            try:
                filters['priority'] = Priority(parts[i + 1])
            except ValueError:
                print(f"Invalid priority: {parts[i + 1]}")
                break
            i += 2
        elif parts[i] == '--status' and i + 1 < len(parts):
            try:
                filters['status'] = Status(parts[i + 1])
            except ValueError:
                print(f"Invalid status: {parts[i + 1]}")
                break
            i += 2
        elif parts[i] == '--tags' and i + 1 < len(parts):
            filters['tags'] = [tag.strip() for tag in parts[i + 1].split(',')]
            i += 2
        else:
            i += 1
    
    return filters
