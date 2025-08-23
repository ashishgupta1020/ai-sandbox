#!/usr/bin/env python3
"""
JIRA-like Task Manager
A command-line tool for managing tasks per project with columns:
- summary
- assignee  
- remarks
- priority
- status
- tags
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from models import Task, Priority, Status
from markdown_utils import render_markdown
from interactive import interactive_create_task, interactive_update_task
from cli import print_help, parse_filters


class TaskManager:
    """Main task manager class"""
    
    def __init__(self, data_file: str = "tasks.json"):
        self.data_file = data_file
        self.projects: Dict[str, Dict[str, Task]] = self._load_data()
    
    def _load_data(self) -> Dict[str, Dict[str, Task]]:
        """Load tasks from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    projects = {}
                    for project_name, tasks_dict in data.items():
                        projects[project_name] = {}
                        for task_id, task_data in tasks_dict.items():
                            # Convert priority string back to enum
                            task_data['priority'] = Priority(task_data['priority'])
                            # Convert status string back to enum
                            if 'status' in task_data:
                                task_data['status'] = Status(task_data['status'])
                            else:
                                task_data['status'] = Status.TODO
                            projects[project_name][task_id] = Task(**task_data)
                    return projects
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Error loading data: {e}")
                return {}
        return {}
    
    def _save_data(self):
        """Save tasks to JSON file"""
        try:
            # Convert tasks to serializable format
            data = {}
            for project_name, tasks in self.projects.items():
                data[project_name] = {}
                for task_id, task in tasks.items():
                    task_dict = asdict(task)
                    task_dict['priority'] = task.priority.value
                    task_dict['status'] = task.status.value
                    data[project_name][task_id] = task_dict
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def _generate_task_id(self, project_name: str) -> str:
        """Generate unique task ID for a project"""
        if project_name not in self.projects:
            return "1"
        
        existing_ids = []
        for task_id in self.projects[project_name].keys():
            try:
                existing_ids.append(int(task_id))
            except ValueError:
                continue
        
        if not existing_ids:
            return "1"
        
        next_id = max(existing_ids) + 1
        return str(next_id)
    
    def create_project(self, project_name: str) -> bool:
        """Create a new project"""
        if project_name in self.projects:
            print(f"Project '{project_name}' already exists.")
            return False
        
        self.projects[project_name] = {}
        self._save_data()
        print(f"Project '{project_name}' created successfully.")
        return True
    
    def list_projects(self):
        """List all projects"""
        if not self.projects:
            print("No projects found.")
            return
        
        print("\n=== Projects ===")
        for i, project_name in enumerate(sorted(self.projects.keys()), 1):
            task_count = len(self.projects[project_name])
            print(f"{i}. {project_name} ({task_count} tasks)")
    
    def create_task(self, project_name: str, summary: str, assignee: str, 
                   remarks: str, priority: Priority, tags: List[str], status: Status = Status.TODO) -> bool:
        """Create a new task in a project"""
        if project_name not in self.projects:
            print(f"Project '{project_name}' does not exist.")
            return False
        
        task_id = self._generate_task_id(project_name)
        now = datetime.now().isoformat()
        
        task = Task(
            id=task_id,
            summary=summary,
            assignee=assignee,
            remarks=remarks,
            priority=priority,
            tags=tags,
            status=status,
            created_at=now,
            updated_at=now
        )
        
        self.projects[project_name][task_id] = task
        self._save_data()
        print(f"Task '{task_id}' created successfully in project '{project_name}'.")
        return True
    
    def list_tasks(self, project_name: str, filters: Optional[Dict[str, Any]] = None):
        """List tasks in a project with optional filtering"""
        if project_name not in self.projects:
            print(f"Project '{project_name}' does not exist.")
            return
        
        tasks = self.projects[project_name]
        if not tasks:
            print(f"No tasks found in project '{project_name}'.")
            return
        
        # Apply filters
        filtered_tasks = tasks
        if filters:
            filtered_tasks = {}
            for task_id, task in tasks.items():
                include_task = True
                
                if 'assignee' in filters and filters['assignee'].lower() not in task.assignee.lower():
                    include_task = False
                
                if 'priority' in filters and task.priority != filters['priority']:
                    include_task = False
                
                if 'tags' in filters:
                    task_tags_lower = [tag.lower() for tag in task.tags]
                    filter_tags_lower = [tag.lower() for tag in filters['tags']]
                    if not any(tag in task_tags_lower for tag in filter_tags_lower):
                        include_task = False
                
                if 'status' in filters and task.status != filters['status']:
                    include_task = False
                
                if include_task:
                    filtered_tasks[task_id] = task
        
        if not filtered_tasks:
            print("No tasks match the specified filters.")
            return
        
        print(f"\n=== Tasks in Project: {project_name} ===")
        print(f"{'ID':<15} {'Summary':<30} {'Assignee':<15} {'Priority':<10} {'Status':<10} {'Tags':<20}")
        print("-" * 100)
        
        for task in sorted(filtered_tasks.values(), key=lambda x: x.id):
            tags_str = ", ".join(task.tags[:3])  # Show first 3 tags
            if len(task.tags) > 3:
                tags_str += "..."
            
            print(f"{task.id:<15} {task.summary[:28]:<30} {task.assignee[:13]:<15} "
                  f"{task.priority.value:<10} {task.status.value:<10} {tags_str:<20}")
    
    def view_task(self, project_name: str, task_id: str):
        """View detailed information about a specific task"""
        if project_name not in self.projects:
            print(f"Project '{project_name}' does not exist.")
            return
        
        if task_id not in self.projects[project_name]:
            print(f"Task '{task_id}' does not exist in project '{project_name}'.")
            return
        
        task = self.projects[project_name][task_id]
        
        print(f"\n=== Task Details: {task_id} ===")
        print(f"Summary: {task.summary}")
        print(f"Assignee: {task.assignee}")
        print(f"Priority: {task.priority.value}")
        print(f"Status: {task.status.value}")
        print(f"Tags: {', '.join(task.tags)}")
        
        # Render remarks with markdown support
        if task.remarks:
            print(f"Remarks:")
            rendered_remarks = render_markdown(task.remarks)
            # Indent each line for better readability
            for line in rendered_remarks.split('\n'):
                print(f"  {line}")
        else:
            print(f"Remarks: (none)")
        
        print(f"Created: {task.created_at}")
        print(f"Updated: {task.updated_at}")
    
    def update_task(self, project_name: str, task_id: str, **kwargs) -> bool:
        """Update a task"""
        if project_name not in self.projects:
            print(f"Project '{project_name}' does not exist.")
            return False
        
        if task_id not in self.projects[project_name]:
            print(f"Task '{task_id}' does not exist in project '{project_name}'.")
            return False
        
        task = self.projects[project_name][task_id]
        
        # Update fields
        for field, value in kwargs.items():
            if hasattr(task, field):
                if field == 'priority' and isinstance(value, str):
                    try:
                        value = Priority(value)
                    except ValueError:
                        print(f"Invalid priority: {value}. Valid options: {[p.value for p in Priority]}")
                        return False
                
                if field == 'status' and isinstance(value, str):
                    try:
                        value = Status(value)
                    except ValueError:
                        print(f"Invalid status: {value}. Valid options: {[s.value for s in Status]}")
                        return False
                
                setattr(task, field, value)
        
        task.updated_at = datetime.now().isoformat()
        self._save_data()
        print(f"Task '{task_id}' updated successfully.")
        return True
    
    def delete_task(self, project_name: str, task_id: str) -> bool:
        """Delete a task"""
        if project_name not in self.projects:
            print(f"Project '{project_name}' does not exist.")
            return False
        
        if task_id not in self.projects[project_name]:
            print(f"Task '{task_id}' does not exist in project '{project_name}'.")
            return False
        
        del self.projects[project_name][task_id]
        self._save_data()
        print(f"Task '{task_id}' deleted successfully.")
        return True
    
    def delete_project(self, project_name: str) -> bool:
        """Delete a project and all its tasks"""
        if project_name not in self.projects:
            print(f"Project '{project_name}' does not exist.")
            return False
        
        task_count = len(self.projects[project_name])
        del self.projects[project_name]
        self._save_data()
        print(f"Project '{project_name}' and its {task_count} tasks deleted successfully.")
        return True


def main():
    """Main application entry point"""
    task_manager = TaskManager()
    
    print("=== JIRA-like Task Manager ===")
    print("Type 'help' for available commands or 'exit' to quit.")
    
    while True:
        try:
            command = input("\n> ").strip()
            
            if not command:
                continue
            
            parts = command.split()
            cmd = parts[0].lower()
            
            if cmd == 'exit':
                print("Goodbye!")
                break
            
            elif cmd == 'help':
                print_help()
            
            elif cmd == 'create-project':
                if len(parts) < 2:
                    print("Usage: create-project <project_name>")
                    continue
                project_name = ' '.join(parts[1:])
                task_manager.create_project(project_name)
            
            elif cmd == 'list-projects':
                task_manager.list_projects()
            
            elif cmd == 'delete-project':
                if len(parts) < 2:
                    print("Usage: delete-project <project_name>")
                    continue
                project_name = ' '.join(parts[1:])
                task_manager.delete_project(project_name)
            
            elif cmd == 'create-task':
                if len(parts) < 2:
                    print("Usage: create-task <project_name>")
                    continue
                project_name = ' '.join(parts[1:])
                interactive_create_task(task_manager, project_name)
            
            elif cmd == 'list-tasks':
                if len(parts) < 2:
                    print("Usage: list-tasks <project_name> [--assignee <name>] [--priority <level>] [--status <status>] [--tags <tag1,tag2>]")
                    continue
                
                project_name = ' '.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                filters = parse_filters(parts)
                
                task_manager.list_tasks(project_name, filters if filters else None)
            
            elif cmd == 'view-task':
                if len(parts) < 3:
                    print("Usage: view-task <project_name> <task_id>")
                    continue
                project_name = ' '.join(parts[1:-1])
                task_id = parts[-1]
                task_manager.view_task(project_name, task_id)
            
            elif cmd == 'update-task':
                if len(parts) < 3:
                    print("Usage: update-task <project_name> <task_id>")
                    continue
                project_name = ' '.join(parts[1:-1])
                task_id = parts[-1]
                interactive_update_task(task_manager, project_name, task_id)
            
            elif cmd == 'delete-task':
                if len(parts) < 3:
                    print("Usage: delete-task <project_name> <task_id>")
                    continue
                project_name = ' '.join(parts[1:-1])
                task_id = parts[-1]
                task_manager.delete_task(project_name, task_id)
            
            else:
                print(f"Unknown command: {cmd}")
                print("Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
