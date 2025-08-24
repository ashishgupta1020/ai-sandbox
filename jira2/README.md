# Jira2 Task Manager

This is a simple command-line project and task management tool implemented in Python. It allows you to manage multiple projects and their associated tasks, with persistent storage using JSON files.

## Features

- **Project Management**
  - List all projects
  - Create/open a project
  - Switch between projects
  - Projects are stored in `projects.json`

- **Task Management**
  - Add tasks to a project
  - List all tasks in a project (pretty table view)
  - Edit tasks (summary, assignee, remarks, status, priority)
  - Tasks are stored in `<project_name>_tasks.json`

- **Interactive CLI**
  - User-friendly menus for project and task operations
  - Input validation and helpful prompts

## How It Works

- When you open or create a project, its name is saved in `projects.json`.
- Each project has its own task file named `<project_name>_tasks.json`.
- Tasks have the following fields: summary, assignee, remarks, status (Not Started/In Progress/Completed), and priority (Low/Medium/High).
- All data is stored locally in JSON format for easy access and modification.

## Usage

1. Run the main script:
   ```bash
   python jira2/task_manager.py
   ```
2. Follow the on-screen prompts to manage projects and tasks.

## Requirements

- Python 3.9+
- `prettytable` package

Install dependencies:
```bash
pip install prettytable
```

## File Structure

- `task_manager.py`: Main CLI and logic for project/task management
- `projects.json`: List of all project names
- `<project_name>_tasks.json`: Tasks for each project

## Example

### Creating and Opening a Project
```
Welcome to the Task Manager!
==============================
Main Menu:
------------------------------
1. List all projects
2. Open a project
3. Exit
------------------------------
Enter your choice: 2
Enter the project name: DemoProject
Opened project: 'DemoProject'
```

### Adding a Task
```
Project Menu:
==============================
Current Project: DemoProject
------------------------------
1. Add a task to the current project
2. List all tasks in the current project
3. Edit a task in the current project
4. List all projects
5. Switch project
6. Exit
------------------------------
Enter your choice: 1
Adding a new task:
------------------------------
Enter the task summary: Implement login
Enter the assignee: Alice
Enter remarks: Initial implementation
Select the status of the task:
1. Not Started
2. In Progress
3. Completed
Enter the number corresponding to the status: 2
Select the priority of the task:
1. Low
2. Medium
3. High
Enter the number corresponding to the priority: 3

Task added successfully to project: 'DemoProject'
```

### Listing Tasks
```
Enter your choice: 2
Listing tasks in project: 'DemoProject'
------------------------------
+-------+---------------------+----------+-------------+----------+----------------------+
| Index | Summary             | Assignee | Status      | Priority | Remarks              |
+-------+---------------------+----------+-------------+----------+----------------------+
| 1     | Implement login     | Alice    | In Progress | High     | Initial implementation|
+-------+---------------------+----------+-------------+----------+----------------------+
```

### Editing a Task
```
Enter your choice: 3
Editing tasks in project: 'DemoProject'
------------------------------
+-------+---------------------+----------+-------------+----------+----------------------+
| Index | Summary             | Assignee | Status      | Priority | Remarks              |
+-------+---------------------+----------+-------------+----------+----------------------+
| 1     | Implement login     | Alice    | In Progress | High     | Initial implementation|
+-------+---------------------+----------+-------------+----------+----------------------+

Enter the index of the task to edit: 1
Editing Task 1:
Current Summary: Implement login
Enter new summary (leave blank to keep current): Implement login and logout
Current Assignee: Alice
Enter new assignee (leave blank to keep current): Bob
Current Remarks: Initial implementation
Enter new remarks (leave blank to keep current): Add logout functionality
Current Status: In Progress
Select new status:
1. Not Started
2. In Progress
3. Completed
Enter the number corresponding to the new status (leave blank to keep current): 3
Current Priority: High
Select new priority:
1. Low
2. Medium
3. High
Enter the number corresponding to the new priority (leave blank to keep current):

Task updated successfully.
```

## License

This project is provided for educational and personal use.
