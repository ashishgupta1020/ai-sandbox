#!/usr/bin/env python3
"""
Demo script for the JIRA-like Task Manager
This script demonstrates how to use the TaskManager class programmatically.
"""

from task_manager import TaskManager, Priority

def main():
    """Demo the task manager functionality"""
    print("=== JIRA-like Task Manager Demo ===\n")
    
    # Initialize task manager
    task_manager = TaskManager("demo_tasks.json")
    
    # Create a project
    print("1. Creating a project...")
    task_manager.create_project("Demo Project")
    
    # Create some tasks
    print("\n2. Creating tasks...")
    
    # Task 1
    task_manager.create_task(
        project_name="Demo Project",
        summary="Implement user authentication",
        assignee="John Doe",
        remarks="Use JWT tokens for secure authentication",
        priority=Priority.HIGH,
        tags=["auth", "security", "frontend"]
    )
    
    # Task 2
    task_manager.create_task(
        project_name="Demo Project",
        summary="Design database schema",
        assignee="Jane Smith",
        remarks="Create ERD and implement database tables",
        priority=Priority.MEDIUM,
        tags=["database", "design", "backend"]
    )
    
    # Task 3
    task_manager.create_task(
        project_name="Demo Project",
        summary="Fix login bug",
        assignee="John Doe",
        remarks="Users cannot login with special characters in password",
        priority=Priority.CRITICAL,
        tags=["bug", "auth", "frontend"]
    )
    
    # List all projects
    print("\n3. Listing all projects...")
    task_manager.list_projects()
    
    # List all tasks in the project
    print("\n4. Listing all tasks...")
    task_manager.list_tasks("Demo Project")
    
    # Filter tasks by assignee
    print("\n5. Filtering tasks by assignee (John Doe)...")
    task_manager.list_tasks("Demo Project", {"assignee": "John"})
    
    # Filter tasks by priority
    print("\n6. Filtering tasks by priority (High)...")
    task_manager.list_tasks("Demo Project", {"priority": Priority.HIGH})
    
    # Filter tasks by tags
    print("\n7. Filtering tasks by tags (auth)...")
    task_manager.list_tasks("Demo Project", {"tags": ["auth"]})
    
    # View a specific task
    print("\n8. Viewing task details...")
    task_manager.view_task("Demo Project", "1")
    
    # Update a task
    print("\n9. Updating a task...")
    task_manager.update_task(
        "Demo Project", 
        "1",
        summary="Implement JWT user authentication",
        status="In Progress",
        tags=["auth", "security", "frontend", "jwt"]
    )
    
    # View the updated task
    print("\n10. Viewing updated task...")
    task_manager.view_task("Demo Project", "1")
    
    # List all tasks again to see changes
    print("\n11. Final task list...")
    task_manager.list_tasks("Demo Project")
    
    print("\n=== Demo completed! ===")
    print("Check 'demo_tasks.json' to see the saved data.")

if __name__ == "__main__":
    main()
