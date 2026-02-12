import unittest

from core.control import Action, Control
from core.events import Event


class ControlSmokeTest(unittest.TestCase):
    def test_deterministic_mapping_for_requested_events(self):
        control = Control()

        cases = {
            "DailyBriefRequested": [Action(type="BuildDailyBrief", payload={"dry_run": True})],
            "OpportunityScanRequested": [Action(type="RunOpportunityScan", payload={"dry_run": True})],
            "EmailTriageRequested": [Action(type="RunEmailTriage", payload={"dry_run": True})],
        }

        for event_type, expected in cases.items():
            with self.subTest(event_type=event_type):
                event = Event(type=event_type, payload={}, source="test")
                first = control.consume(event)
                second = control.consume(event)

                self.assertEqual(first, expected)
                self.assertEqual(second, expected)
                self.assertEqual(first, second)


    def test_evaluate_opportunity_event_returns_structured_decision(self):
        control = Control()
        event = Event(
            type="EvaluateOpportunity",
            payload={
                "money": 8,
                "growth": 6,
                "energy": 3,
                "health": 2,
                "relationships": 5,
                "risk": 2,
            },
            source="test",
        )

        actions = control.consume(event)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "OpportunityEvaluated")
        self.assertIn("score", actions[0].payload)
        self.assertIn("decision", actions[0].payload)
        self.assertIn("reasoning", actions[0].payload)


if __name__ == "__main__":
    unittest.main()
