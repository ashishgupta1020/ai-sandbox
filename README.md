# Taskman (CLI + UI)

Simple project and task manager with both a command‑line interface and a lightweight browser UI. Data persists to local JSON files per project.

Note on direction: the UI is where new development happens. The CLI remains supported for its current, basic feature set.

## Features

- Project lists, open/create, and rename
- Tasks with summary, assignee, remarks, status, priority
- Task CRUD in the UI with inline editing and markdown preview for remarks
- Markdown export per project
- Local JSON storage under `~/sandbox/data/ai-sandbox`

## Components

- UI server: `python -m taskman.tasker_ui` then open `http://127.0.0.1:8765`
  - Projects list with add/rename and per‑project tasks table
  - Inline edit for task fields, add/delete tasks, basic search/sort
- CLI app: `python -m taskman.cli.task_manager`
  - Menu‑driven flow to add/list/edit/sort/export tasks and rename/switch projects

## Install

- Python 3.8+
- Install deps: `pip install -r requirements.txt`

UI loads its JS libraries from CDNs; the Python server itself has no extra UI dependencies.

## Quick Start

- UI
  - Run: `python -m taskman.tasker_ui`
  - Visit: `http://127.0.0.1:8765` and use the Projects list
- CLI
  - Run: `python -m taskman.cli.task_manager`
  - Follow prompts to create a project and add tasks

See `QUICKSTART.md` for brief usage notes.

## Data Storage

- Projects file: `~/sandbox/data/ai-sandbox/projects.json`
- Tasks file per project: `~/sandbox/data/ai-sandbox/<project>_tasks.json`
- Markdown export: `~/sandbox/data/ai-sandbox/<project>_tasks_export.md`

## Tests

Run all tests with `pytest`.

## License

Educational and personal use.
