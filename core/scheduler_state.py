from __future__ import annotations

import os
from pathlib import Path

from core.persistence.json_io import atomic_read_json, atomic_write_json

_DEFAULT_DATA_DIR = "./.treta_data"
_STATE_FILENAME = "scheduler_state.json"


def _scheduler_state_path() -> Path:
    data_dir = Path(os.getenv("TRETA_DATA_DIR", _DEFAULT_DATA_DIR))
    return data_dir / _STATE_FILENAME


def load_scheduler_state() -> dict[str, str]:
    path = _scheduler_state_path()
    state = atomic_read_json(path, default={})

    if not isinstance(state, dict):
        return {}

    last_run_date = state.get("last_run_date")
    last_run_timestamp = state.get("last_run_timestamp")

    loaded_state: dict[str, str] = {}
    if isinstance(last_run_date, str):
        loaded_state["last_run_date"] = last_run_date
    if isinstance(last_run_timestamp, str):
        loaded_state["last_run_timestamp"] = last_run_timestamp

    return loaded_state


def save_scheduler_state(date_str: str, timestamp_str: str) -> None:
    path = _scheduler_state_path()
    atomic_write_json(
        path,
        {
            "last_run_date": date_str,
            "last_run_timestamp": timestamp_str,
        },
    )
