from __future__ import annotations

import importlib.util
from pathlib import Path

_module_path = Path(__file__).with_name("001_base_schema.py")
_spec = importlib.util.spec_from_file_location("core.migrations.migration_001_base_schema", _module_path)
migration_001_base_schema = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(migration_001_base_schema)

__all__ = ["migration_001_base_schema"]
