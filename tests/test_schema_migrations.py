import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.migrations.runner import get_current_version, run_migrations
from core.storage import Storage


class SchemaMigrationsTest(unittest.TestCase):
    def test_run_migrations_creates_schema_and_version(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "memory" / "treta.sqlite"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db_path) as conn:
                run_migrations(conn)
                version = get_current_version(conn)
                self.assertGreaterEqual(version, 14)

                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }

            self.assertIn("schema_version", tables)
            self.assertIn("decision_logs", tables)
            self.assertIn("state", tables)
            self.assertIn("scheduler_state", tables)
            self.assertIn("reddit_signals", tables)
            self.assertIn("creator_pain_analysis", tables)
            self.assertIn("creator_product_suggestions", tables)
            self.assertIn("creator_offer_drafts", tables)
            self.assertIn("creator_demand_validations", tables)
            self.assertIn("creator_offer_launches", tables)
            self.assertIn("runtime_overrides", tables)
            self.assertIn("processed_events", tables)
            self.assertIn("strategy_actions", tables)
            self.assertIn("decision_outcomes", tables)
            self.assertIn("action_executions", tables)

            indexes = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
            }
            self.assertIn("idx_decision_logs_type", indexes)
            self.assertIn("idx_decision_outcomes_strategy_type", indexes)
            self.assertIn("idx_action_executions_action_id", indexes)
            self.assertIn("idx_action_executions_status", indexes)

    def test_storage_enables_foreign_keys(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                pragma = storage.conn.execute("PRAGMA foreign_keys").fetchone()[0]
                self.assertEqual(pragma, 1)
                journal_mode = str(storage.conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                self.assertEqual(journal_mode, "wal")
                busy_timeout = storage.conn.execute("PRAGMA busy_timeout").fetchone()[0]
                self.assertEqual(int(busy_timeout), 5000)

    def test_migration_unifies_legacy_reddit_db(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            legacy_db_path = Path(tmp_dir) / "reddit_intelligence.db"
            with sqlite3.connect(legacy_db_path) as legacy_conn:
                legacy_conn.execute(
                    """
                    CREATE TABLE reddit_signals (
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
                legacy_conn.execute(
                    """
                    INSERT INTO reddit_signals (
                        id, subreddit, post_url, post_text, detected_pain_type,
                        opportunity_score, intent_level, suggested_action,
                        generated_reply, status, created_at, updated_at,
                        karma, replies, performance_score, mention_used
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "legacy-1",
                        "startup",
                        "https://reddit.com/r/startup/legacy-1",
                        "legacy pain",
                        "direct",
                        90,
                        "direct",
                        "value",
                        "reply",
                        "pending",
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                        1,
                        2,
                        5,
                        0,
                    ),
                )
                legacy_conn.commit()

            main_db_path = Path(tmp_dir) / "memory" / "treta.sqlite"
            main_db_path.parent.mkdir(parents=True, exist_ok=True)

            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                with sqlite3.connect(main_db_path) as conn:
                    run_migrations(conn)
                    migrated_count = conn.execute(
                        "SELECT COUNT(*) FROM reddit_signals"
                    ).fetchone()[0]
                    self.assertEqual(migrated_count, 1)


if __name__ == "__main__":
    unittest.main()
