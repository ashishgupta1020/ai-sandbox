# Quick Start Guide

## Getting Started

1. **Run the application:**
   ```bash
   python3 src/taskman/task_manager.py
   ```

2. **Open/Create Your First Project:**
   - From the `Main Menu`, choose option `2. Open a project`.
   - When prompted, enter a name for your project, for example: `My First Project`.
   - If the project doesn't exist, it will be created and opened for you.

3. **Add Your First Task:**
   - You will now be in the `Project Menu`.
   - Choose option `1. Add a task to the current project`.
   - Follow the interactive prompts to enter the task summary, assignee, remarks, status, and priority.

4. **List Your Tasks:**
   - In the `Project Menu`, choose option `2. List all tasks in the current project`.
   - Your tasks will be displayed in a formatted table.

## Menu Reference

### Main Menu
| Option | Description |
|--------|-------------|
| `1. List all projects` | Shows all projects you have created. |
| `2. Open a project` | Opens an existing project or creates a new one if it doesn't exist. |
| `3. Edit a project name` | Renames a project and its associated data files. |
| `4. Exit` | Closes the application. |

### Project Menu
| Option | Description |
|--------|-------------|
| `1. Add a task` | Interactively add a new task to the current project. |
| `2. List all tasks` | Display all tasks in a table. |
| `3. List tasks with custom sort` | Sort the task list by status or priority. |
| `4. Edit a task` | Interactively edit an existing task's details. |
| `5. Edit current project name` | Rename the currently open project. |
| `6. List all projects` | Show all available projects from within the project menu. |
| `7. Switch project` | Close the current project and open another. |
| `8. Export tasks to Markdown` | Save the task list to a Markdown file. |
| `9. Exit` | Closes the application. |

## Priority Levels
- **Low**
- **Medium**
- **High**

## Status Levels
- **Not Started**
- **In Progress**
- **Completed**

## Example Workflow

```
Welcome to the Task Manager!
==============================
Main Menu:
...
Enter your choice: 2
Enter the project name: Website Redesign

Project Menu:
Current Project: Website Redesign
...
Enter your choice: 1
Enter the task summary: Update homepage layout
Enter the assignee: Alice
Enter remarks (Markdown format is supported).
Press Enter twice to finish:
*Use CSS Grid* for layout
`npm run build` for production

Select the status of the task:
...
Enter the number corresponding to the status: 2
Select the priority of the task:
...
Enter the number corresponding to the priority: 3

Task added successfully to project: 'Website Redesign'
```

## Markdown Support
The remarks field accepts multi-line text input. While you can type markdown syntax into this field, the application does not render it. It is stored as plain text.

Press Enter twice to finish multi-line remarks

## Data Storage
All your data is automatically saved to JSON files in the `~/sandbox/data/ai-sandbox/` directory.
A list of all project names is stored in `projects.json`, and each project's tasks are stored in a corresponding `<project_name>_tasks.json` file.
