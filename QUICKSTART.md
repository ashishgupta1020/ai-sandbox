# Quick Start

This project has both a browser UI and a CLI. The UI is the primary experience; the CLI remains supported for its current features.

## Install

- Python 3.8+
- Recommended: `pip install -e .` (editable install)
  - Adds commands: `taskman-ui`, `taskman-cli`
  - Works from any directory
- Alternative: `pip install -r requirements.txt` and run via `python -m ...`

## UI (recommended)

- Start server: `taskman-ui` (or `python -m taskman.tasker_ui`)
- Open: `http://127.0.0.1:8765`
- Do: Add/rename projects, open a project, then add/edit/delete tasks inline. Remarks support markdown with preview.

## CLI

- Run: `taskman-cli` (or `python -m taskman.cli.task_manager`)
- Do: From the menus, open/create a project, add tasks, list/sort, edit, and export to markdown.

## Data Location

- Projects: `~/sandbox/data/ai-sandbox/projects.json`
- Tasks: `~/sandbox/data/ai-sandbox/<project>_tasks.json`
- Export: `~/sandbox/data/ai-sandbox/<project>_tasks_export.md`
