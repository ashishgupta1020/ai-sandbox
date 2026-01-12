# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Taskman is a project and task manager with two interfaces sharing the same SQLite backend:
- **Browser UI**: Lightweight HTTP server with HTML/CSS/JS frontend (`taskman-ui`)
- **CLI**: Menu-driven command-line client that talks to the UI server via REST API (`taskman-cli`)

The CLI is a thin client—it requires the UI server to be running.

## Commands

```bash
# Install for development
pip install -e .

# Run tests with coverage
pytest

# Run a single test file
pytest tests/test_task.py

# Run a specific test
pytest tests/test_task.py::test_function_name -v

# Start UI server (required for CLI)
taskman-ui --config config.json

# Start CLI (server must be running)
taskman-cli --config config.json
```

## Architecture

```
src/taskman/
├── server/           # HTTP server + API handlers
│   ├── tasker_server.py   # Main server, routes, static file serving
│   ├── project_api.py     # Project CRUD operations
│   ├── task_api.py        # Task CRUD operations
│   ├── task_store.py      # SQLite persistence for tasks
│   └── todo/              # Todo checklist feature (separate DB)
├── cli/              # Command-line interface
│   ├── task_manager.py    # Main CLI entry, menu loops
│   └── interaction.py     # User input handling
├── client/           # REST API client (used by CLI)
│   ├── api_client.py      # HTTP client for server endpoints
│   └── project_adapter.py # Project-like wrapper over API
├── ui/               # Frontend assets
│   ├── *.html             # Page templates
│   ├── *.js               # Page scripts (index, project, tasks, todo, filter)
│   └── styles/*.css       # Modular CSS (base, layout, components, etc.)
└── config.py         # Configuration loading
```

**Key patterns:**
- Server uses Python's built-in `http.server` with no external dependencies
- All data stored in SQLite: `taskman.db` (projects/tasks), `taskman_todo.db` (todos)
- UI assets are served with cache-busting hashes for CSS/JS
- CLI talks to server via `TaskmanApiClient`, never directly to database

## Configuration

Both commands require `--config` pointing to a JSON file:
```json
{
  "DATA_STORE_PATH": "/path/to/data/directory"
}
```

## Coding Guidelines

- Add comments where relevant, when generating code
