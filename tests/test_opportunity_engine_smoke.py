import unittest

from core.opportunity_engine import OpportunityEngine


class OpportunityEngineSmokeTest(unittest.TestCase):
    def test_generate_opportunities_returns_decision_engine_shape(self):
        engine = OpportunityEngine()
        data = [
            {
                "title": "Build landing page for service offer",
                "summary": "High engagement idea with clear monetization path.",
                "engagement": 85,
                "source": "linkedin",
            },
            {
                "title": "Unknown trend",
                "summary": "Very early signal.",
                "engagement": 10,
                "source": "unknown",
            },
        ]

        results = engine.generate_opportunities(data)

        self.assertEqual(len(results), 2)
        for opp in results:
            self.assertEqual(
                set(opp.keys()),
                {"money", "growth", "energy", "health", "relationships", "risk", "source", "context"},
            )

        self.assertGreaterEqual(results[0]["money"], results[1]["money"])
        self.assertGreaterEqual(results[0]["growth"], results[1]["growth"])
        self.assertGreater(results[1]["risk"], results[0]["risk"])


if __name__ == "__main__":
    unittest.main()
