import unittest
from unittest.mock import Mock

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




    def test_action_approved_generates_action_plan(self):
        control = Control()
        event = Event(type="ActionApproved", payload={"type": "top_product"}, source="test")

        actions = control.consume(event)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "ActionPlanGenerated")
        self.assertEqual(
            actions[0].payload,
            {
                "action": "optimize",
                "steps": [
                    "Add upsell",
                    "Improve landing page copy",
                    "Collect testimonials",
                ],
                "priority": 9,
            },
        )

    def test_gumroad_stats_requested_returns_structured_payload(self):
        gumroad_client = Mock()
        gumroad_client.get_products.return_value = {"products": [{"id": "p1"}]}
        gumroad_client.get_sales.return_value = {"sales": [{"id": "s1"}], "limit": 10}
        gumroad_client.get_balance.return_value = {"balance": 123.45, "currency": "USD"}

        control = Control(gumroad_client=gumroad_client)
        event = Event(type="GumroadStatsRequested", payload={}, source="test")

        actions = control.consume(event)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "GumroadStatsReady")
        self.assertEqual(
            actions[0].payload,
            {
                "products": [{"id": "p1"}],
                "sales": [{"id": "s1"}],
                "balance": {"balance": 123.45, "currency": "USD"},
            },
        )

        gumroad_client.get_products.assert_called_once_with()
        gumroad_client.get_sales.assert_called_once_with()
        gumroad_client.get_balance.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
