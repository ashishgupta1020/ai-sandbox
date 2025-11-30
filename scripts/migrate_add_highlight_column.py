#!/usr/bin/env python3
"""One-time migration to add the 'highlight' column to all project task tables."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Tuple

from taskman.server.project_manager import ProjectManager

def migrate_highlight_columns(db_path: Path | str | None = None) -> Tuple[int, int]:
    """
    Add the highlight column to all existing tasks_* tables.

    Returns:
        tuple[int, int]: (tables_altered, tables_unchanged)
    """
    target = Path(db_path) if db_path is not None else Path(ProjectManager.PROJECTS_DIR) / "taskman.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row

    tables = [
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'tasks_%'").fetchall()
    ]
    altered = 0
    unchanged = 0
    for table in tables:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "highlight" not in columns:
            print(f"Updating table '{table}'...")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN highlight INTEGER NOT NULL DEFAULT 0")
            altered += 1
            print(f" - added 'highlight' column to '{table}'")
        else:
            unchanged += 1
            print(f"Skipping table '{table}': already has 'highlight'")
        # Normalize any NULLs that may have existed before adding the column.
        try:
            conn.execute(f"UPDATE {table} SET highlight = 0 WHERE highlight IS NULL")
            print(f" - normalized NULL highlight values in '{table}'")
        except sqlite3.OperationalError:
            # If the column does not exist (unlikely after the ALTER), skip normalization.
            pass

    conn.commit()
    conn.close()
    return altered, unchanged


def main() -> None:
    parser = argparse.ArgumentParser(description="Add 'highlight' column to all Taskman project tables.")
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Optional path to taskman.db. Defaults to <PROJECTS_DIR>/taskman.db",
    )
    args = parser.parse_args()
    altered, unchanged = migrate_highlight_columns(args.db_path)
    print(f"Highlight migration complete. Updated {altered} table(s); {unchanged} already had the column.")


if __name__ == "__main__":
    main()
