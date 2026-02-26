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

migration_005_creator_product_suggestions = _load_migration(
    "005_creator_product_suggestions.py", "core.migrations.migration_005_creator_product_suggestions"
)

migration_006_creator_offer_drafts = _load_migration(
    "006_creator_offer_drafts.py", "core.migrations.migration_006_creator_offer_drafts"
)

migration_007_creator_demand_validations = _load_migration(
    "007_creator_demand_validations.py", "core.migrations.migration_007_creator_demand_validations"
)

migration_008_creator_launch_tracking = _load_migration(
    "008_creator_launch_tracking.py", "core.migrations.migration_008_creator_launch_tracking"
)

migration_009_decision_logs_traceability = _load_migration(
    "009_decision_logs_traceability.py", "core.migrations.migration_009_decision_logs_traceability"
)

migration_010_runtime_overrides = _load_migration(
    "010_runtime_overrides.py", "core.migrations.migration_010_runtime_overrides"
)

migration_011_processed_events = _load_migration(
    "011_processed_events.py", "core.migrations.migration_011_processed_events"
)

migration_012_strategy_actions_sqlite = _load_migration(
    "012_strategy_actions_sqlite.py", "core.migrations.migration_012_strategy_actions_sqlite"
)

migration_013_decision_outcomes = _load_migration(
    "013_decision_outcomes.py", "core.migrations.migration_013_decision_outcomes"
)

migration_014_action_executions = _load_migration(
    "014_action_executions.py", "core.migrations.migration_014_action_executions"
)

__all__ = [
    "migration_001_base_schema",
    "migration_003_unify_reddit_db",
    "migration_004_creator_pain_analysis",
    "migration_005_creator_product_suggestions",
    "migration_006_creator_offer_drafts",
    "migration_007_creator_demand_validations",
    "migration_008_creator_launch_tracking",
    "migration_009_decision_logs_traceability",
    "migration_010_runtime_overrides",
    "migration_011_processed_events",
    "migration_012_strategy_actions_sqlite",
    "migration_013_decision_outcomes",
    "migration_014_action_executions",
]
