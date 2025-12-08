"""Shared configuration loader for Taskman."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Defaults to the legacy location; overridden when a config file is provided.
_data_store_dir: Path = Path("~/taskman/data").expanduser()


def set_data_store_dir(path: Path) -> Path:
    """
    Update the global data store directory and ensure it exists.

    Returns the resolved path for convenience.
    """
    global _data_store_dir
    resolved = Path(path).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    _data_store_dir = resolved
    return _data_store_dir


def get_data_store_dir() -> Path:
    """Return the currently configured data store directory."""
    return _data_store_dir


def load_config(config_path: Optional[str]) -> Path:
    """
    Load configuration from a JSON file containing ``DATA_STORE_PATH``.

    If ``config_path`` is falsy, the default data directory is used.
    """
    if not config_path:
        return set_data_store_dir(_data_store_dir)

    cfg_path = Path(str(config_path)).expanduser()
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    try:
        raw = json.loads(cfg_path.read_text())
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to read config: {exc}") from exc

    data_dir = raw.get("DATA_STORE_PATH")
    if data_dir is None or str(data_dir).strip() == "":
        raise ValueError("Config missing 'DATA_STORE_PATH'")

    return set_data_store_dir(Path(str(data_dir)))
