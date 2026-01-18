# AGENTS.md

Codex instructions for this repository.

## Project Context
- Taskman is a lightweight project/task manager with two interfaces sharing the same SQLite data store.
- UI: dependency-free Python HTTP server serves static HTML/CSS/JS and a REST-ish API.
- CLI: thin client that talks to the UI server API; it does not touch the database directly.

## Repository Map
- `src/taskman/server/`: HTTP server, route handlers, APIs, SQLite stores.
- `src/taskman/cli/`: CLI entrypoint and interactive input helpers.
- `src/taskman/client/`: REST client + project adapter used by the CLI.
- `src/taskman/ui/`: static UI assets (HTML/CSS/JS); no bundler.
- `tests/`: pytest/unittest-style tests for server, API, CLI, stores, and UI assets.
- `dist/`: build artifacts; do not edit by hand.

## Coding Conventions
- Python 3.8+, standard library only on the server (no frameworks).
- Route handlers and API helpers return `(payload_dict, status_code)` tuples.
- Validate project names (no `..`, no leading `.`, no `/`); keep existing guardrails.
- UI code is plain JS with minimal `fetch` helpers; avoid introducing build tooling.
- Static asset hashing is handled by `asset_manifest`; HTML is rewritten on serve.
- Add concise comments to explain non-obvious logic when generating new code.
- Any new function added (any language) must include a function doc.

## Workflow & Commands
- Activate the virtualenv before running Python commands: `source ~/sandbox/venv/bin/activate`.
- Install for dev: `pip install -e .`
- Run UI server: `taskman-ui --config config.json` (or `python -m taskman.server.tasker_server`)
- Run CLI (server must be running): `taskman-cli --config config.json`
- Config file must include `DATA_STORE_PATH` (see `config.json`).

## Common Tasks
- Add/modify API endpoint:
  - Implement handler in `src/taskman/server/route_handlers.py`.
  - Wire it in `GET_ROUTE_PATTERNS`/`POST_ROUTE_PATTERNS`.
  - Add tests in `tests/server/test_route_handlers.py` and/or `tests/server/test_server.py`.
- Add new task fields:
  - Update `src/taskman/server/task.py`, `src/taskman/server/task_store.py`, and `src/taskman/server/task_api.py`.
  - Update UI render/edit flows in `src/taskman/ui/tasks.js`.
  - Update CLI display/edit logic in `src/taskman/client/project_adapter.py` if needed.
  - Add tests for API/store expectations.
- Add UI assets:
  - Place files in `src/taskman/ui/` or `src/taskman/ui/styles/`.
  - Update HTML includes and `pyproject.toml` package data if new patterns are introduced.

## Testing
- Activate the virtualenv first: `source ~/sandbox/venv/bin/activate`.
- Run all tests: `pytest`
- Target a file: `pytest tests/server/test_server.py`
- Tests use temporary data dirs and expect the default server host/port (`127.0.0.1:8765`) in CLI tests.

## Integrations & Data
- Data store root is `DATA_STORE_PATH` from config.
- Databases: `<DATA_STORE_PATH>/taskman.db` (projects/tasks), `<DATA_STORE_PATH>/taskman_todo.db` (todos).
- Markdown export: `<DATA_STORE_PATH>/<project>_tasks_export.md`.
- UI uses CDN scripts for Grid.js, marked, and DOMPurify; keep imports in HTML.

## Release/Docs
- Publishing steps are in `PUBLISHING.md`.
- Update `README.md` and `QUICKSTART.md` when behavior, commands, or UI flows change.
