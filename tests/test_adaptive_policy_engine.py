import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.adaptive_policy_engine import AdaptivePolicyEngine
from core.migrations.runner import run_migrations
from core.storage import Storage
from core.stores import AdaptivePolicyStore


class AdaptivePolicyEngineTest(unittest.TestCase):
    def test_defaults_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": str(data_dir)}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                engine = AdaptivePolicyEngine(store=AdaptivePolicyStore(storage.conn), storage=storage)

                self.assertEqual(
                    engine.tracked_metrics(),
                    {
                        "total_auto_executed_actions": 0,
                        "successful_actions": 0,
                        "revenue_delta_per_action": [],
                    },
                )
                status = engine.adaptive_status()
                self.assertEqual(status["success_rate"], 0.0)
                self.assertEqual(status["avg_revenue_delta"], 0.0)
                self.assertEqual(status["impact_threshold"], 6)
                self.assertEqual(status["max_auto_executions_per_24h"], 3)
                self.assertEqual(status["strategy_weights"]["scale"], 1.0)

    def test_adapts_up_and_down_with_bounds(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": str(data_dir)}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                engine = AdaptivePolicyEngine(store=AdaptivePolicyStore(storage.conn), storage=storage)

                for _ in range(3):
                    engine.record_action_outcome(150)
                high_status = engine.adaptive_status()

                self.assertEqual(high_status["success_rate"], 1.0)
                self.assertEqual(high_status["avg_revenue_delta"], 150.0)
                self.assertEqual(high_status["impact_threshold"], 4)
                self.assertEqual(high_status["max_auto_executions_per_24h"], 5)

                for _ in range(13):
                    engine.record_action_outcome(-50)
                low_status = engine.adaptive_status()

                self.assertLess(low_status["success_rate"], 0.4)
                self.assertLess(low_status["avg_revenue_delta"], 0)
                self.assertEqual(low_status["impact_threshold"], 8)
                self.assertEqual(low_status["max_auto_executions_per_24h"], 1)

    def test_refresh_strategy_weights_with_smoothing(self):
        storage = Mock()
        storage.get_strategy_performance.return_value = {
            "scale": {
                "total_decisions": 8,
                "avg_revenue": 20.0,
                "success_rate": 0.5,
                "avg_predicted_risk": 1.0,
                "score": 5.0,
            },
            "review": {
                "total_decisions": 8,
                "avg_revenue": 5.0,
                "success_rate": 0.4,
                "avg_predicted_risk": 1.0,
                "score": 1.0,
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": str(data_dir)}, clear=False):
                real_storage = Storage()
                run_migrations(real_storage.conn)
                engine = AdaptivePolicyEngine(store=AdaptivePolicyStore(real_storage.conn), storage=storage)
                updated = engine.refresh_strategy_weights()

        self.assertAlmostEqual(updated["scale"], 1.0)
        self.assertAlmostEqual(updated["review"], 0.76)
        self.assertEqual(engine.prioritized_strategy_types(["review", "scale"]), ["scale", "review"])

    def test_refresh_strategy_weights_skips_when_insufficient_metrics(self):
        storage = Mock()
        storage.get_strategy_performance.return_value = {
            "scale": {
                "total_decisions": 4,
                "avg_revenue": 20.0,
                "success_rate": 0.5,
                "avg_predicted_risk": 1.0,
                "score": 5.0,
            }
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": str(data_dir)}, clear=False):
                real_storage = Storage()
                run_migrations(real_storage.conn)
                engine = AdaptivePolicyEngine(store=AdaptivePolicyStore(real_storage.conn), storage=storage)
                original = dict(engine.adaptive_status()["strategy_weights"])
                updated = engine.refresh_strategy_weights()

        self.assertEqual(updated, original)

    def test_refresh_strategy_weights_clamps_extremes_and_logs(self):
        storage = Mock()
        storage.get_strategy_performance.return_value = {
            "scale": {
                "total_decisions": 8,
                "avg_revenue": 20.0,
                "success_rate": 0.5,
                "avg_predicted_risk": 1.0,
                "score": 100.0,
            },
            "review": {
                "total_decisions": 8,
                "avg_revenue": -50.0,
                "success_rate": 0.1,
                "avg_predicted_risk": 1.0,
                "score": -5000.0,
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": str(data_dir)}, clear=False):
                real_storage = Storage()
                run_migrations(real_storage.conn)
                engine = AdaptivePolicyEngine(store=AdaptivePolicyStore(real_storage.conn), storage=storage)
                engine._state["strategy_weights"]["scale"] = 4.0
                engine._state["strategy_weights"]["review"] = 0.0

                with self.assertLogs("treta.adaptive_policy", level="INFO") as captured:
                    updated = engine.refresh_strategy_weights()

        self.assertEqual(updated["scale"], engine.MAX_STRATEGY_WEIGHT)
        self.assertEqual(updated["review"], engine.MIN_STRATEGY_WEIGHT)
        clamp_logs = "\n".join(captured.output)
        self.assertIn("adaptive_strategy_weight_clamped", clamp_logs)
        self.assertIn("weight_clamped", clamp_logs)


class AdaptivePolicyStoreTest(unittest.TestCase):
    def test_adaptive_policy_load_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                store = AdaptivePolicyStore(storage.conn)
                payload = {"a": 1, "nested": {"k": [1, 2]}}
                store.save(payload)
                loaded = store.load()
                self.assertEqual(loaded, payload)

    def test_import_from_json_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                store = AdaptivePolicyStore(storage.conn)

                json_path = Path(tmp_dir) / "adaptive_policy_state.json"
                first = {"total_auto_executed_actions": 1}
                json_path.write_text(json.dumps(first), encoding="utf-8")

                imported = store.ensure_import_from_json_once(str(json_path))
                self.assertTrue(imported)
                self.assertEqual(store.load(), first)

                second = {"total_auto_executed_actions": 99}
                json_path.write_text(json.dumps(second), encoding="utf-8")

                imported_again = store.ensure_import_from_json_once(str(json_path))
                self.assertFalse(imported_again)
                self.assertEqual(store.load(), first)

    def test_engine_uses_sqlite_not_filesystem(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with unittest.mock.patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                store = AdaptivePolicyStore(storage.conn)
                json_path = Path(tmp_dir) / "adaptive_policy_state.json"

                engine = AdaptivePolicyEngine(
                    path=json_path,
                    store=store,
                    storage=storage,
                )
                engine.record_action_outcome(42)

                row = storage.conn.execute(
                    "SELECT scope, state_json FROM adaptive_policy_state WHERE scope = 'global'"
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "global")
                self.assertFalse(json_path.exists())


if __name__ == "__main__":
    unittest.main()
