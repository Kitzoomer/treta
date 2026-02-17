import unittest

from core.alignment_engine import AlignmentEngine


class AlignmentEngineTest(unittest.TestCase):
    def test_evaluate_returns_aligned_when_signals_are_strong(self):
        engine = AlignmentEngine()
        result = engine.evaluate(
            {
                "title": "Creator onboarding system kit",
                "summary": "Automation for client acquisition and revenue growth",
                "opportunity": {"confidence": 8},
            },
            context={"recent_proposals": []},
        )

        self.assertTrue(result["aligned"])
        self.assertGreaterEqual(result["alignment_score"], 60)
        self.assertIn("Audience matches", result["reason"])

    def test_evaluate_penalizes_distraction_and_similarity(self):
        engine = AlignmentEngine()
        result = engine.evaluate(
            {
                "title": "Template kit for creators",
                "summary": "Revenue automation templates for service professionals",
                "tags": ["distraction"],
                "opportunity": {"confidence": 9},
            },
            context={
                "recent_proposals": [
                    {
                        "product_name": "Template kit for creators",
                        "product_type": "kit",
                        "target_audience": "service professionals",
                        "core_problem": "revenue automation",
                        "solution": "template system",
                    }
                ]
            },
        )

        self.assertFalse(result["aligned"])
        self.assertEqual(result["alignment_score"], 40.0)
        self.assertIn("distraction/non-core", result["reason"])
        self.assertIn("Too similar", result["reason"])


if __name__ == "__main__":
    unittest.main()
