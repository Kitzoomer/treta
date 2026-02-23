from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from core.migrations import (
    migration_001_base_schema,
    migration_003_unify_reddit_db,
    migration_004_creator_pain_analysis,
    migration_005_creator_product_suggestions,
    migration_006_creator_offer_drafts,
    migration_007_creator_demand_validations,
)


def _upgrade_scheduler_state(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduler_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


MIGRATIONS: list[tuple[int, callable]] = [
    (1, migration_001_base_schema.upgrade),
    (2, _upgrade_scheduler_state),
    (3, migration_003_unify_reddit_db.upgrade),
    (4, migration_004_creator_pain_analysis.upgrade),
    (5, migration_005_creator_product_suggestions.upgrade),
    (6, migration_006_creator_offer_drafts.upgrade),
    (7, migration_007_creator_demand_validations.upgrade),
]


def get_current_version(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    cur.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (0, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return 0
    return int(row[0])


def apply_migration(conn: sqlite3.Connection, version: int, upgrade_fn) -> None:
    upgrade_fn(conn)
    conn.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
        (version, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def run_migrations(conn: sqlite3.Connection) -> None:
    current_version = get_current_version(conn)
    for version, upgrade_fn in MIGRATIONS:
        if version > current_version:
            apply_migration(conn, version, upgrade_fn)
            current_version = version
