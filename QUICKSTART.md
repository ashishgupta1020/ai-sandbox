# Quick Start

This project has both a browser UI and a CLI. The UI is the primary experience; the CLI remains supported for its current features.

Hosting model
- The UI server is intended to be centrally hosted so teams can share a single instance.
- For development and testing, you can run the same server locally on localhost.
- The CLI is a client of the UI server API and requires the server to be running and reachable.

## Install

- Python 3.8+
- From PyPI (recommended): `pip install ataskman` (adds `taskman-ui`, `taskman-cli`)
- From source for dev: `pip install -e .`
- Alternative: `pip install -r requirements.txt` and run via `python -m ...`

## Configuration

- Create a JSON config file:
  ```json
  {
    "DATA_STORE_PATH": "/absolute/path/to/taskman/data",
    "LOG_LEVEL": "INFO"
  }
  ```
- Optional: set `LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, or a numeric level.
- Pass it to both commands: `taskman-ui --config /path/to/config.json` and `taskman-cli --config /path/to/config.json`.

## UI

- Central: open the shared URL for your hosted server.
- Local (dev/testing): start with `taskman-ui --config /path/to/config.json` (or `python -m taskman.server.tasker_server --config /path/to/config.json`) and open `http://127.0.0.1:8765`.
- Do: Add/rename/delete projects, manage project tags, filter by tags, open a project, then add/edit/delete tasks inline. Remarks support markdown with preview.

## CLI

- Requires the server: make sure the UI server is running and reachable.
- Run: `taskman-cli --config /path/to/config.json` (or `python -m taskman.cli.task_manager --config /path/to/config.json`).
- Do: From the menus, open/create a project, add tasks, list/sort, edit, and export to markdown.

## Data Location

- All data lives under `DATA_STORE_PATH` from the config file you provide.
- Projects registry and tasks database: `<DATA_STORE_PATH>/taskman.db`
- Todo database: `<DATA_STORE_PATH>/taskman_todo.db`
- Markdown export: `<DATA_STORE_PATH>/<project>_tasks_export.md`
