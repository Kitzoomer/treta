import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.adaptive_policy_engine import AdaptivePolicyEngine


class AdaptivePolicyEngineTest(unittest.TestCase):
    def test_defaults_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            engine = AdaptivePolicyEngine(path=Path(tmp_dir) / "adaptive.json")

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
            engine = AdaptivePolicyEngine(path=Path(tmp_dir) / "adaptive.json")

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

    def test_persists_adaptive_parameters_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "adaptive.json"
            engine = AdaptivePolicyEngine(path=path)
            engine.record_action_outcome(120)
            engine.record_action_outcome(-20)

            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["total_auto_executed_actions"], 2)
            self.assertEqual(raw["successful_actions"], 1)
            self.assertEqual(raw["revenue_delta_per_action"], [120.0, -20.0])

            reloaded = AdaptivePolicyEngine(path=path)
            self.assertEqual(reloaded.tracked_metrics()["total_auto_executed_actions"], 2)
            self.assertEqual(reloaded.tracked_metrics()["successful_actions"], 1)
            self.assertEqual(reloaded.adaptive_status()["impact_threshold"], raw["impact_threshold"])
            self.assertEqual(
                reloaded.adaptive_status()["max_auto_executions_per_24h"],
                raw["max_auto_executions_per_24h"],
            )

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
            engine = AdaptivePolicyEngine(path=Path(tmp_dir) / "adaptive.json", storage=storage)
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
            engine = AdaptivePolicyEngine(path=Path(tmp_dir) / "adaptive.json", storage=storage)
            original = dict(engine.adaptive_status()["strategy_weights"])
            updated = engine.refresh_strategy_weights()

        self.assertEqual(updated, original)


if __name__ == "__main__":
    unittest.main()
