# JIRA-like Task Manager

A Python command-line application for managing tasks per project, similar to JIRA. Each task includes the following columns:
- **Summary**: Brief description of the task
- **Assignee**: Person responsible for the task
- **Remarks**: Additional notes or comments
- **Priority**: Task priority level (Low, Medium, High, Critical)
- **Status**: Task status (To Do, In Progress, Review, Done, Blocked, Cancelled)
- **Tags**: Categorization labels for the task

## Features

- **Project Management**: Create, list, and delete projects
- **Task Management**: Create, view, update, and delete tasks within projects
- **Status Management**: Track task status (To Do, In Progress, Review, Done, Blocked, Cancelled)
- **Filtering**: Filter tasks by assignee, priority, status, and tags
- **Persistent Storage**: Data is saved to JSON files
- **Interactive Interface**: User-friendly command-line interface
- **Task IDs**: Automatic generation of unique task IDs per project
- **Markdown Support**: Remarks support markdown formatting (bold, italic, code, lists, etc.)

## Requirements

- Python 3.7 or higher
- External dependencies: `markdown` library (install with `pip install markdown`)

## Installation

1. Clone or download the project files
2. Ensure you have Python 3.7+ installed
3. Install dependencies: `pip install -r requirements.txt`

## Usage

### Starting the Application

```bash
python task_manager.py
```

### Available Commands

#### Project Management

- `create-project <project_name>` - Create a new project
- `list-projects` - List all projects with task counts
- `delete-project <project_name>` - Delete a project and all its tasks

#### Task Management

- `create-task <project_name>` - Create a new task (interactive)
- `list-tasks <project_name>` - List all tasks in a project
- `list-tasks <project_name> --assignee <name> --priority <level> --status <status> --tags <tag1,tag2>` - List tasks with filters
- `view-task <project_name> <task_id>` - View detailed task information
- `update-task <project_name> <task_id>` - Update a task (interactive)
- `delete-task <project_name> <task_id>` - Delete a task

#### General

- `help` - Show help information
- `exit` - Exit the application

### Priority Levels

- **Low** - Low priority tasks
- **Medium** - Medium priority tasks  
- **High** - High priority tasks
- **Critical** - Critical priority tasks

### Status Levels

- **To Do** - Tasks that haven't been started
- **In Progress** - Tasks currently being worked on
- **Review** - Tasks ready for review/testing
- **Done** - Completed tasks
- **Blocked** - Tasks blocked by dependencies or issues
- **Cancelled** - Tasks that have been cancelled

## Examples

### Creating a Project

```
> create-project "Web Application"
Project 'Web Application' created successfully.
```

### Creating a Task

```
> create-task "Web Application"

=== Creating Task in Project: Web Application ===
Summary: Implement user authentication
Assignee: John Doe
Remarks (supports markdown, press Enter twice to finish):
Examples: **bold**, *italic*, `code`, - lists, > quotes, - [ ] checkboxes
  # Authentication Implementation
  
  ## Overview
  Use **JWT tokens** for secure authentication with refresh mechanism.
  
  ## Tasks
  - [ ] Add password validation
  - [x] Set up token storage
  - [ ] Implement refresh tokens
  - [ ] Add rate limiting
  
  ## Code Example
  ```javascript
  const token = jwt.sign(payload, secret, { expiresIn: '1h' });
  ```
  
  ## Notes
  *Important*: Follow OAuth 2.0 standards
  > Remember to test thoroughly in staging environment
  
Priority levels:
1. Low
2. Medium
3. High
4. Critical
Select priority (1-4): 3
Tags (comma-separated): auth, security, frontend
Task '1' created successfully in project 'Web Application'.
```

### Listing Tasks

```
> list-tasks "Web Application"

=== Tasks in Project: Web Application ===
ID              Summary                         Assignee        Priority   Status     Tags
----------------------------------------------------------------------------------------------------
1               Implement user authentication  John Doe        High       To Do      auth, security, frontend
2               Design database schema         Jane Smith      Medium      To Do      database, design
```

### Filtering Tasks

```
> list-tasks "Web Application" --assignee "John" --priority "High" --status "In Progress"

=== Tasks in Project: Web Application ===
ID              Summary                         Assignee        Priority   Status     Tags
----------------------------------------------------------------------------------------------------
1               Implement user authentication  John Doe        High       In Progress auth, security, frontend
```

### Viewing Task Details

```
> view-task "Web Application" "1"

=== Task Details: 1 ===
Summary: Implement user authentication
Assignee: John Doe
Priority: High
Status: To Do
Tags: auth, security, frontend
Remarks:
  Authentication Implementation
  
  Overview
  
  Use **JWT tokens** for secure authentication with refresh mechanism.
  
  Tasks
  
  • Add password validation
  • Set up token storage
  • Implement refresh tokens
  • Add rate limiting
  
  Code Example
  
  `const token = jwt.sign(payload, secret, { expiresIn: '1h' });`
  
  Notes
  
  *Important*: Follow OAuth 2.0 standards
  > Remember to test thoroughly in staging environment
Created: 2024-01-15T10:30:00.123456
Updated: 2024-01-15T10:30:00.123456
```

### Updating a Task

```
> update-task "Web Application" "1"

=== Updating Task: 1 ===
Press Enter to keep current value.
Summary [Implement user authentication]: Implement JWT authentication
Assignee [John Doe]: 
Remarks [Use JWT tokens for authentication]: Use JWT tokens with refresh token mechanism

Current priority: High
Priority levels:
1. Low
2. Medium
3. High
4. Critical
Select priority (1-4) or press Enter to keep current: 
Tags [auth, security, frontend]: auth, security, frontend, jwt
Status [To Do]: In Progress
Task '1' updated successfully.
```

## Data Storage

Tasks are stored in a `tasks.json` file in the same directory as the application. The file structure is:

```json
{
  "Project Name": {
    "1": {
      "id": "1",
      "summary": "Task summary",
      "assignee": "Assignee name",
      "remarks": "Task remarks",
      "priority": "High",
      "tags": ["tag1", "tag2"],
      "created_at": "2024-01-15T10:30:00.123456",
      "updated_at": "2024-01-15T10:30:00.123456",
      "status": "To Do"
    }
  }
}
```

## File Structure

```
.
├── task_manager.py        # Main application file
├── models.py             # Data models and enums
├── markdown_utils.py     # Markdown rendering utilities
├── interactive.py        # Interactive user input functions
├── cli.py               # Command-line interface helpers
├── test_task_manager.py  # Comprehensive unit tests
├── run_tests.py         # Test runner script
├── requirements.txt     # Dependencies
├── README.md           # This file
└── tasks.json          # Data file (created automatically)
```

## Testing

The application includes comprehensive unit tests to ensure reliability and functionality.

### Running Tests

```bash
# Run all tests
python3 test_task_manager.py

# Or use the test runner
python3 run_tests.py

# Run specific test class
python3 -m unittest test_task_manager.TestTaskManager

# Run specific test method
python3 -m unittest test_task_manager.TestTaskManager.test_create_project
```

### Test Coverage

The test suite covers:
- **Priority Enum**: All priority values and validation
- **Status Enum**: All status values and validation
- **Task Dataclass**: Task creation and default values
- **Markdown Rendering**: All markdown features and edge cases
- **TaskManager Class**: All CRUD operations
  - Project management (create, list, delete)
  - Task management (create, read, update, delete)
  - Task filtering (by assignee, priority, status, tags)
  - Data persistence (save/load)
  - Error handling
- **Interactive Functions**: User input validation
- **CLI Functions**: Command parsing and help system
- **Edge Cases**: Corrupted data, missing files, invalid inputs

### Test Results

```
Tests run: 44
Failures: 0
Errors: 0
Success rate: 100.0%
```

## Error Handling

The application includes comprehensive error handling for:
- Invalid project names
- Non-existent tasks
- Invalid priority levels
- File I/O errors
- JSON parsing errors

## Markdown Support

The task manager supports comprehensive markdown formatting in remarks:

### Text Formatting
- **Bold text**: `**text**` or `__text__`
- *Italic text*: `*text*` or `_text_`
- ***Bold italic***: `***text***` or `___text___`
- ~~Strikethrough~~: `~~text~~`
- `Inline code`: `` `code` ``
- **Subscript**: `H~2~O` (water)
- **Superscript**: `2^10^` (1024)

### Headers
- `# Header 1`
- `## Header 2`
- `### Header 3`
- `#### Header 4`

### Lists
- **Bullet lists**: `- item` or `* item`
- **Numbered lists**: `1. item`
- **Task lists**: `- [ ] unchecked` or `- [x] checked`
- **Nested lists**: Indent with spaces

### Code Blocks
- **Fenced code blocks**: 
  ```
  ```python
  def hello():
      print("Hello, World!")
  ```
  ```
- **Syntax highlighting**: Specify language after opening fence

### Blockquotes
- `> Single line quote`
- `> Multi-line quote`
- `> > Nested quote`

### Links and Images
- **Links**: `[text](url)`
- **Images**: `![alt text](image_url)`

### Tables
```
| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
```

### Horizontal Rules
- `---` or `***` or `___`

### Escaping
- Use `\` to escape special characters: `\*not italic\*`

## Contributing

Feel free to extend the application with additional features such as:
- Due dates for tasks
- Task dependencies
- Export functionality (CSV, Excel)
- Web interface
- Team collaboration features
- Time tracking

## License

This project is open source and available under the MIT License.