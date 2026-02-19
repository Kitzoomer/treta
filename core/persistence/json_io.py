from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(tmp_path, path)


def atomic_read_json(path: Path, default: Any, *, quarantine_corrupt: bool = True) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        if not quarantine_corrupt:
            raise
        quarantine_corrupt_file(path, exc)
        return default


def quarantine_corrupt_file(path: Path, reason: Exception) -> None:
    if not path.exists():
        logger.warning("Failed to quarantine corrupt JSON store at %s: %s", path, reason)
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    corrupt_path = path.with_suffix(path.suffix + f".{timestamp}.corrupt")
    try:
        path.replace(corrupt_path)
    except OSError:
        fallback = path.with_suffix(path.suffix + ".corrupt")
        try:
            path.replace(fallback)
        except OSError:
            logger.warning("Failed to quarantine corrupt JSON store at %s: %s", path, reason)
            return
        logger.warning("Corrupt JSON store moved from %s to %s: %s", path, fallback, reason)
        return

    logger.warning("Corrupt JSON store moved from %s to %s: %s", path, corrupt_path, reason)
