from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration(filename: str, module_name: str):
    module_path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


migration_001_base_schema = _load_migration("001_base_schema.py", "core.migrations.migration_001_base_schema")
migration_003_unify_reddit_db = _load_migration(
    "003_unify_reddit_db.py", "core.migrations.migration_003_unify_reddit_db"
)

migration_004_creator_pain_analysis = _load_migration(
    "004_creator_pain_analysis.py", "core.migrations.migration_004_creator_pain_analysis"
)

__all__ = [
    "migration_001_base_schema",
    "migration_003_unify_reddit_db",
    "migration_004_creator_pain_analysis",
]
