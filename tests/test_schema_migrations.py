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
                self.assertGreaterEqual(version, 2)

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

    def test_storage_enables_foreign_keys(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                pragma = storage.conn.execute("PRAGMA foreign_keys").fetchone()[0]
                self.assertEqual(pragma, 1)


if __name__ == "__main__":
    unittest.main()
