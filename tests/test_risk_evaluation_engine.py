import tempfile
import unittest
from pathlib import Path

from core.risk_evaluation_engine import RiskEvaluationEngine
from core.strategy_action_store import StrategyActionStore


class RiskEvaluationEngineTest(unittest.TestCase):
    def test_deterministic_rules(self):
        engine = RiskEvaluationEngine()

        self.assertEqual(
            engine.evaluate({"type": "scale", "sales": 5}),
            {"risk_level": "low", "expected_impact_score": 8, "auto_executable": True},
        )
        self.assertEqual(
            engine.evaluate({"type": "price_test"}),
            {"risk_level": "low", "expected_impact_score": 6, "auto_executable": True},
        )
        self.assertEqual(
            engine.evaluate({"type": "review"}),
            {"risk_level": "medium", "expected_impact_score": 5, "auto_executable": False},
        )
        self.assertEqual(
            engine.evaluate({"type": "new_product"}),
            {"risk_level": "medium", "expected_impact_score": 7, "auto_executable": False},
        )
        self.assertEqual(
            engine.evaluate({"type": "archive"}),
            {"risk_level": "high", "expected_impact_score": 4, "auto_executable": False},
        )

    def test_strategy_action_store_attaches_risk_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StrategyActionStore(path=Path(tmp_dir) / "strategy_actions.json")

            item = store.add(
                action_type="scale",
                target_id="launch-1",
                reasoning="Launch has 5 sales, which meets the scale threshold.",
                sales=5,
            )

            self.assertEqual(item["risk_level"], "low")
            self.assertEqual(item["expected_impact_score"], 8)
            self.assertTrue(item["auto_executable"])


if __name__ == "__main__":
    unittest.main()
