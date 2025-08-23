#!/usr/bin/env python3
"""
Interactive functions for user input and task creation/updates
"""

from models import Priority, Status


def interactive_create_task(task_manager, project_name: str):
    """Interactive task creation"""
    print(f"\n=== Creating Task in Project: {project_name} ===")
    
    summary = input("Summary: ").strip()
    if not summary:
        print("Summary is required.")
        return False
    
    assignee = input("Assignee: ").strip()
    if not assignee:
        print("Assignee is required.")
        return False
    
    print("Remarks (supports markdown, press Enter twice to finish):")
    print("Examples: **bold**, *italic*, `code`, - lists, > quotes")
    remarks_lines = []
    while True:
        line = input("  ").strip()
        if line == "" and (not remarks_lines or remarks_lines[-1] == ""):
            break
        remarks_lines.append(line)
    
    remarks = "\n".join(remarks_lines[:-1] if remarks_lines and remarks_lines[-1] == "" else remarks_lines)
    
    print("\nPriority levels:")
    for i, priority in enumerate(Priority, 1):
        print(f"{i}. {priority.value}")
    
    while True:
        try:
            priority_choice = input("Select priority (1-4): ").strip()
            priority = list(Priority)[int(priority_choice) - 1]
            break
        except (ValueError, IndexError):
            print("Invalid choice. Please enter 1-4.")
    
    tags_input = input("Tags (comma-separated): ").strip()
    tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
    
    print("\nStatus levels:")
    for i, status in enumerate(Status, 1):
        print(f"{i}. {status.value}")
    
    while True:
        try:
            status_choice = input("Select status (1-6): ").strip()
            status = list(Status)[int(status_choice) - 1]
            break
        except (ValueError, IndexError):
            print("Invalid choice. Please enter 1-6.")
    
    return task_manager.create_task(project_name, summary, assignee, remarks, priority, tags, status)


def interactive_update_task(task_manager, project_name: str, task_id: str):
    """Interactive task update"""
    print(f"\n=== Updating Task: {task_id} ===")
    print("Press Enter to keep current value.")
    
    current_task = task_manager.projects[project_name][task_id]
    
    summary = input(f"Summary [{current_task.summary}]: ").strip()
    if not summary:
        summary = current_task.summary
    
    assignee = input(f"Assignee [{current_task.assignee}]: ").strip()
    if not assignee:
        assignee = current_task.assignee
    
    print(f"Remarks (supports markdown, press Enter twice to finish):")
    print("Examples: **bold**, *italic*, `code`, - lists, > quotes")
    print(f"Current: {current_task.remarks}")
    remarks_lines = []
    while True:
        line = input("  ").strip()
        if line == "" and (not remarks_lines or remarks_lines[-1] == ""):
            break
        remarks_lines.append(line)
    
    remarks = "\n".join(remarks_lines[:-1] if remarks_lines and remarks_lines[-1] == "" else remarks_lines)
    if not remarks:
        remarks = current_task.remarks
    
    print(f"\nCurrent priority: {current_task.priority.value}")
    print("Priority levels:")
    for i, priority in enumerate(Priority, 1):
        print(f"{i}. {priority.value}")
    
    priority_choice = input("Select priority (1-4) or press Enter to keep current: ").strip()
    if priority_choice:
        try:
            priority = list(Priority)[int(priority_choice) - 1]
        except (ValueError, IndexError):
            print("Invalid choice. Keeping current priority.")
            priority = current_task.priority
    else:
        priority = current_task.priority
    
    tags_input = input(f"Tags [{', '.join(current_task.tags)}]: ").strip()
    if tags_input:
        tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
    else:
        tags = current_task.tags
    
    print(f"\nCurrent status: {current_task.status.value}")
    print("Status levels:")
    for i, status_enum in enumerate(Status, 1):
        print(f"{i}. {status_enum.value}")
    
    status_choice = input("Select status (1-6) or press Enter to keep current: ").strip()
    if status_choice:
        try:
            status = list(Status)[int(status_choice) - 1]
        except (ValueError, IndexError):
            print("Invalid choice. Keeping current status.")
            status = current_task.status
    else:
        status = current_task.status
    
    return task_manager.update_task(project_name, task_id, 
                                   summary=summary, assignee=assignee, 
                                   remarks=remarks, priority=priority, 
                                   tags=tags, status=status)
