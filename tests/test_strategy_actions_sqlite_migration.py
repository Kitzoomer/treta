import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.migrations.runner import run_migrations
from core.strategy_action_store import StrategyActionStore
from core.storage import get_db_path


class StrategyActionsSQLiteMigrationTest(unittest.TestCase):
    def test_legacy_json_is_migrated_to_sqlite_on_store_startup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                db_path = get_db_path()
                db_path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(db_path) as conn:
                    run_migrations(conn)

                json_path = Path(tmp_dir) / "strategy_actions.json"
                json_path.write_text(
                    json.dumps([
                        {
                            "id": "action-000111",
                            "type": "review",
                            "target_id": "proposal-1",
                            "reasoning": "legacy",
                            "status": "pending_confirmation",
                            "created_at": "2026-01-01T00:00:00+00:00",
                            "decision_id": "dec-1",
                            "event_id": "ev-1",
                        }
                    ]),
                    encoding="utf-8",
                )

                store = StrategyActionStore(path=json_path)
                items = store.list()
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["id"], "action-000111")

                with sqlite3.connect(db_path) as conn:
                    row = conn.execute(
                        "SELECT id, decision_id, event_id FROM strategy_actions WHERE id = ?",
                        ("action-000111",),
                    ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "action-000111")
                self.assertEqual(row[1], "dec-1")
                self.assertEqual(row[2], "ev-1")

    def test_new_action_is_written_to_sqlite_only_and_json_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                db_path = get_db_path()
                db_path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(db_path) as conn:
                    run_migrations(conn)

                json_path = Path(tmp_dir) / "strategy_actions.json"
                json_path.write_text(json.dumps([{"id":"legacy-1","type":"review","target_id":"p1","reasoning":"legacy","status":"pending_confirmation","created_at":"2026-01-01T00:00:00+00:00"}]), encoding="utf-8")
                original_json = json_path.read_text(encoding="utf-8")

                store = StrategyActionStore(path=json_path)
                created = store.add(
                    action_type="scale",
                    target_id="launch-1",
                    reasoning="grow",
                    decision_id="dec-2",
                    event_id="ev-2",
                )

                self.assertTrue(json_path.exists())
                self.assertEqual(json_path.read_text(encoding="utf-8"), original_json)

                with sqlite3.connect(db_path) as conn:
                    row = conn.execute(
                        "SELECT id, decision_id, event_id FROM strategy_actions WHERE id = ?",
                        (created["id"],),
                    ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[1], "dec-2")
                self.assertEqual(row[2], "ev-2")


if __name__ == "__main__":
    unittest.main()
