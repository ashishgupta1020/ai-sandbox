"""Shared configuration loader for Taskman."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

# Defaults to the legacy location; overridden when a config file is provided.
_data_store_dir: Path = Path("~/taskman/data").expanduser()
_log_level: int = logging.INFO


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


def set_log_level(level: int) -> int:
    """Update the global log level and return it for convenience."""
    global _log_level
    _log_level = level
    return _log_level


def get_log_level() -> int:
    """Return the currently configured log level."""
    return _log_level


def _coerce_log_level(value: Optional[object]) -> int:
    if value is None:
        return logging.INFO
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        name = value.strip().upper()
        if not name:
            return logging.INFO
        if name.isdigit():
            return int(name)
        level = logging.getLevelName(name)
        return level if isinstance(level, int) else logging.INFO
    return logging.INFO


def load_config(config_path: Optional[str]) -> Path:
    """
    Load configuration from a JSON file containing ``DATA_STORE_PATH`` and
    optional ``LOG_LEVEL``.

    If ``config_path`` is falsy, the default data directory is used.
    """
    if not config_path:
        set_log_level(_log_level)
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

    set_log_level(_coerce_log_level(raw.get("LOG_LEVEL")))
    return set_data_store_dir(Path(str(data_dir)))
