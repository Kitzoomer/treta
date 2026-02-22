from __future__ import annotations

import sqlite3
from pathlib import Path

from core.reddit_intelligence.models import get_legacy_db_path


def _create_reddit_signals_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reddit_signals (
            id TEXT PRIMARY KEY,
            subreddit TEXT NOT NULL,
            post_url TEXT NOT NULL,
            post_text TEXT NOT NULL,
            detected_pain_type TEXT,
            opportunity_score INTEGER,
            intent_level TEXT,
            suggested_action TEXT,
            generated_reply TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            karma INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            performance_score INTEGER DEFAULT 0,
            mention_used BOOLEAN DEFAULT 0
        )
        """
    )


def _copy_legacy_records(main_conn: sqlite3.Connection, legacy_db_path: Path) -> None:
    legacy_uri = f"file:{legacy_db_path}?mode=ro"
    with sqlite3.connect(legacy_uri, uri=True) as legacy_conn:
        table_exists = legacy_conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reddit_signals'"
        ).fetchone()
        if table_exists is None:
            return

        source_rows = legacy_conn.execute(
            """
            SELECT
                id,
                subreddit,
                post_url,
                post_text,
                detected_pain_type,
                opportunity_score,
                intent_level,
                suggested_action,
                generated_reply,
                status,
                created_at,
                updated_at,
                karma,
                replies,
                performance_score,
                mention_used
            FROM reddit_signals
            """
        ).fetchall()

    source_count = len(source_rows)
    if source_count == 0:
        return

    main_conn.executemany(
        """
        INSERT OR REPLACE INTO reddit_signals (
            id,
            subreddit,
            post_url,
            post_text,
            detected_pain_type,
            opportunity_score,
            intent_level,
            suggested_action,
            generated_reply,
            status,
            created_at,
            updated_at,
            karma,
            replies,
            performance_score,
            mention_used
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        source_rows,
    )

    main_conn.execute("CREATE TEMP TABLE IF NOT EXISTS _legacy_reddit_ids (id TEXT PRIMARY KEY)")
    main_conn.execute("DELETE FROM _legacy_reddit_ids")
    main_conn.executemany(
        "INSERT OR IGNORE INTO _legacy_reddit_ids (id) VALUES (?)",
        [(row[0],) for row in source_rows],
    )
    destination_count = main_conn.execute(
        """
        SELECT COUNT(*)
        FROM reddit_signals rs
        INNER JOIN _legacy_reddit_ids ids ON ids.id = rs.id
        """
    ).fetchone()[0]
    if destination_count != source_count:
        raise RuntimeError("Legacy reddit_signals migration count mismatch")


def upgrade(conn: sqlite3.Connection) -> None:
    _create_reddit_signals_table(conn)

    legacy_db_path = get_legacy_db_path()
    if legacy_db_path.exists():
        _copy_legacy_records(conn, legacy_db_path)

    conn.commit()
