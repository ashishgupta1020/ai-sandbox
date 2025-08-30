# Jira2 Task Manager

This is a simple command-line project and task management tool implemented in Python. It allows you to manage multiple projects and their associated tasks, with persistent storage using JSON files.

## Features

- **Project Management**
  - List all projects
  - Create/open a project
  - Switch between projects
  - Projects are stored in `~/sandbox/data/ai-sandbox/projects.json`

- **Task Management**
  - Add tasks to a project
  - List all tasks in a project (pretty table view)
  - Edit tasks (summary, assignee, remarks, status, priority)
  - Tasks are stored in `~/sandbox/data/ai-sandbox/<project_name>_tasks.json`
  - Export tasks to Markdown (`<project_name>_tasks_export.md` in `~/sandbox/data/ai-sandbox/`)

- **Interactive CLI**
  - User-friendly menus for project and task operations
  - Input validation and helpful prompts
  - Interactive selection for status and priority

- **Remarks Field**
  - Remarks field accepts any text, including markdown syntax, but does not render markdown

- **Status Levels**
  - Not Started, In Progress, Completed

- **Priority Levels**
  - Low, Medium, High

- **Data Storage**
  - All data is stored locally in JSON files per project
  - Exported Markdown file for tasks

## How It Works

- When you open or create a project, its name is saved in `~/sandbox/data/ai-sandbox/projects.json`.
- Each project has its own task file named `<project_name>_tasks.json` in `~/sandbox/data/ai-sandbox/`.
- Tasks have the following fields: summary, assignee, remarks (any text), status (Not Started/In Progress/Completed), and priority (Low/Medium/High).
- All data is stored locally in JSON format for easy access and modification, in `~/sandbox/data/ai-sandbox/`.
- You can export all tasks to a Markdown file for sharing or documentation.

## Usage (CLI)

1. Run the main script:
  ```bash
  python3 -m taskman.cli.task_manager
  # or
  python3 src/taskman/cli/task_manager.py
  ```
2. Follow the on-screen prompts to manage projects and tasks.
3. Use the interactive CLI to add, list, edit, switch, and export tasks.

## UI Server (Experimental)

A minimal web UI is bundled for basic project navigation:

- Lists all projects with bullets
- Add a new project via a plus icon next to the "Projects" title
- Rename a project via an inline pencil icon next to each project (shows on hover/focus)
- Open a project to view its tasks in a simple HTML table
- Exit the server via a button on the main page

Start the UI server:

```bash
python -m taskman.tasker_ui
# or from Python
from taskman.tasker_ui import start_ui
start_ui(host="127.0.0.1", port=8765)
```

Open http://127.0.0.1:8765 in your browser.

Available endpoints (for reference):

- GET  `/health` — health check (JSON)
- GET  `/` — projects list UI
- GET  `/project.html?name=<name>` — project view (tasks table)
- GET  `/api/projects` — JSON list of projects + current project
- GET  `/api/state` — JSON current project name
- GET  `/api/projects/<name>/tasks` — JSON tasks for a project
- POST `/api/projects/open` — open/create project `{ "name": "..." }`
- POST `/api/projects/edit-name` — rename project `{ "old_name": "...", "new_name": "..." }`
- POST `/api/exit` — graceful shutdown

Notes:

- Data paths are the same as the CLI (under `~/sandbox/data/ai-sandbox`).
- The UI is intentionally minimal and dependency-free.
- Icons show on hover/focus to keep the UI clean.

## Requirements

- Python 3.8+
- `prettytable` package
- `pytest` (for running tests)

Install requirements:
```bash
pip install -r requirements.txt
```
Or install manually:
```bash
pip install prettytable pytest
```

## Running Tests

To run all tests:
```bash
pytest
```

## File Structure

- `cli/task_manager.py`: Main CLI and logic for project/task management
- `projects.json`: List of all project names (stored in `~/sandbox/data/ai-sandbox/`)
- `<project_name>_tasks.json`: Tasks for each project (stored in `~/sandbox/data/ai-sandbox/`)
- `<project_name>_tasks_export.md`: Markdown export of all tasks in a project (stored in `~/sandbox/data/ai-sandbox/`)

## Example

### Creating and Opening a Project
```
Welcome to the Task Manager!
==============================
Main Menu:
------------------------------
1. List all projects
2. Open a project
3. Edit a project name
4. Exit
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
-- Task Management --
1. Add a task
2. List all tasks
3. List tasks with custom sort
4. Edit a task
5. Export tasks to Markdown

-- Project Management --
6. Edit current project name
7. List all projects
8. Switch project

-- Application --
9. Exit
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
```bash
Enter your choice: 4
Editing tasks in project: 'DemoProject'
------------------------------
+-------+---------------------+----------+-------------+----------+----------------------+
| Index | Summary             | Assignee | Status      | Priority | Remarks              |
+-------+---------------------+----------+-------------+----------+----------------------+
| 1     | Implement login     | Alice    | In Progress | High     | Initial implementation |
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

### Exporting Tasks to Markdown
```bash
Enter your choice: 5
Tasks exported to Markdown file: '<project_name>_tasks_export.md'
```

## License

This project is provided for educational and personal use.
