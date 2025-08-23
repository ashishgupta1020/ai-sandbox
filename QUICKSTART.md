# Quick Start Guide

## Getting Started

1. **Run the application:**
   ```bash
   python3 task_manager.py
   ```

2. **Create your first project:**
   ```
   > create-project "My First Project"
   ```

3. **Create your first task:**
   ```
   > create-task "My First Project"
   ```
   Follow the interactive prompts to enter task details.

4. **List your tasks:**
   ```
   > list-tasks "My First Project"
   ```

5. **View task details:**
   ```
   > view-task "My First Project" "1"
   ```

## Quick Commands Reference

| Command | Description |
|---------|-------------|
| `help` | Show all available commands |
| `create-project <name>` | Create a new project |
| `list-projects` | List all projects |
| `create-task <project>` | Create a new task (interactive) |
| `list-tasks <project>` | List all tasks in a project |
| `view-task <project> <task_id>` | View detailed task information |
| `update-task <project> <task_id>` | Update a task (interactive) |
| `delete-task <project> <task_id>` | Delete a task |
| `exit` | Exit the application |

## Priority Levels
- **Low** - Low priority tasks
- **Medium** - Medium priority tasks
- **High** - High priority tasks
- **Critical** - Critical priority tasks

## Status Levels
- **To Do** - Tasks that haven't been started
- **In Progress** - Tasks currently being worked on
- **Review** - Tasks ready for review/testing
- **Done** - Completed tasks
- **Blocked** - Tasks blocked by dependencies
- **Cancelled** - Tasks that have been cancelled

## Example Workflow

```
> create-project "Website Redesign"
> create-task "Website Redesign"
  Summary: Update homepage layout
  Assignee: Alice Johnson
  Remarks (supports markdown, press Enter twice to finish):
  # Homepage Redesign
  
  ## Requirements
  - [ ] Make it mobile responsive
  - [ ] Improve loading speed
  - [ ] Add dark mode toggle
  
  ## Technical Notes
  *Use CSS Grid* for layout
  `npm run build` for production
  
  > Test on multiple devices
  Priority: 3 (High)
  Tags: frontend, responsive, homepage

> list-tasks "Website Redesign"
> view-task "Website Redesign" "1"
```

## Markdown Support
Remarks support comprehensive markdown formatting:

### Basic Formatting
- **Bold**: `**text**` or `__text__`
- *Italic*: `*text*` or `_text_`
- `Code`: `` `code` ``
- ~~Strikethrough~~: `~~text~~`

### Lists & Tasks
- Bullet lists: `- item` or `* item`
- Numbered lists: `1. item`
- **Task lists**: `- [ ] unchecked` or `- [x] checked`
- Nested lists: Indent with spaces

### Advanced Features
- Headers: `# Header 1`, `## Header 2`
- Code blocks: ``` ``` ```
- Blockquotes: `> quote`
- Tables: `| Header | Data |`
- Links: `[text](url)`

### Multi-line Input
Press Enter twice to finish multi-line remarks

## Data Storage
All your data is automatically saved to `tasks.json` in the same directory.
