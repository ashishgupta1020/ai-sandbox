# Taskman (CLI + UI)

Simple project and task manager with both a command‑line interface and a lightweight browser UI. Task data is persisted in a lightweight SQLite database on disk.

Hosting model: the UI server is intended to be centrally hosted in a shared environment. You can still run it locally for development and testing using the localhost instructions below. The CLI is a thin client for the server API and requires the server to be running and reachable.

## Features

- Keep projects organized: browse projects, open or create new ones, and rename them when they change
- Track tasks quickly: add tasks with summary, assignee, status, priority, and rich-text/Markdown remarks
- Highlight milestones: star important tasks so they appear on the shared Highlights board
- Edit in place: update any task field right inside the table, including Markdown preview for remarks
- Export anytime: save a project’s tasks to a Markdown file for sharing
- Choose your interface: use the browser UI or the guided CLI menus—the same data is shared either way
- Capture quick todos: lightweight checklist with due dates, people, priorities, add/edit inline, and mark done

## Components

- Browser UI (central by default; optional local run)
  - Open the hosted URL from your team, or run locally with `taskman-ui` (or `python -m taskman.server.tasker_server`) and visit `http://127.0.0.1:8765`.
  - From the landing page you can add/rename projects, jump into a project, and see starred tasks across projects. Inside a project you get a sortable/searchable table, inline edits, highlights, delete, and a quick add-task panel. A Todo tab gives you a checklist view with add/edit inline forms and checkbox completion.
- CLI (uses the same server)
  - Run `taskman-cli` (or `python -m taskman.cli.task_manager`).
  - Menus guide you to list/open/create/rename projects, add or edit tasks by index, sort task listings by status or priority, export to Markdown, and switch projects.

## Install

- Python 3.8+
- From PyPI (recommended): `pip install ataskman` (adds `taskman-ui`, `taskman-cli`)
- From source for dev: `pip install -e .`
- Alternative: `pip install -r requirements.txt` (then run via `python -m ...`)

## Configuration

- Create a JSON config file and pass it to both commands:
  ```json
  {
    "DATA_STORE_PATH": "/absolute/path/to/taskman/data"
  }
  ```
- Run the UI: `taskman-ui --config /path/to/config.json`
- Run the CLI: `taskman-cli --config /path/to/config.json`

UI loads its JS libraries from CDNs; the Python server has no extra UI deps.

## Quick Start

- UI (central or local)
  - Central: open the shared UI URL provided by your team.
  - Local dev: run `taskman-ui --config /path/to/config.json` (or `python -m taskman.server.tasker_server --config /path/to/config.json`) and visit `http://127.0.0.1:8765`.
- CLI (server required)
  - Run: `taskman-cli --config /path/to/config.json` (or `python -m taskman.cli.task_manager --config /path/to/config.json`).
  - Ensure the UI server is running and reachable; the CLI talks to the server API.

See `QUICKSTART.md` for brief usage notes.

## Data Storage

- All data lives under `DATA_STORE_PATH` from the config file you provide.
- Projects registry and tasks database: `<DATA_STORE_PATH>/taskman.db`
- Todo database: `<DATA_STORE_PATH>/taskman_todo.db`
- Markdown export: `<DATA_STORE_PATH>/<project>_tasks_export.md`

## Tests

Run all tests with `pytest`.

## License

Educational and personal use.
