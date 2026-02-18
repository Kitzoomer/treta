import unittest

from core.bus import EventBus
from core.control import Control
from core.dispatcher import Dispatcher
from core.events import Event
from core.state_machine import StateMachine


class ProductPlanSmokeTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_opportunity_to_proposal_to_plan_flow(self):
        dispatcher = Dispatcher(state_machine=StateMachine(), control=Control(bus=self.bus), bus=self.bus)
        history_before = len(self.bus.recent(limit=200))

        dispatcher.handle(
            Event(
                type="OpportunityDetected",
                source="test",
                payload={
                    "id": "opp-plan-1",
                    "source": "twitter",
                    "title": "Creators need a better media kit for sponsorship pitches",
                    "summary": "Need rate sheet, examples and repeatable pitch flow.",
                    "opportunity": {"money": 8, "growth": 7},
                },
            )
        )

        events_after_opportunity = self.bus.recent(limit=200)
        new_events = events_after_opportunity[history_before:]
        proposals = [event for event in new_events if event.type == "ProductProposalGenerated"]
        self.assertEqual(len(proposals), 1)
        proposal_id = proposals[0].payload["proposal_id"]

        dispatcher.handle(
            Event(
                type="BuildProductPlanRequested",
                source="test",
                payload={"proposal_id": proposal_id},
            )
        )

        events_after_plan = self.bus.recent(limit=200)
        newer_events = events_after_plan[history_before:]
        built_events = [event for event in newer_events if event.type == "ProductPlanBuilt"]
        self.assertEqual(len(built_events), 1)

        listed_actions = dispatcher.control.consume(
            Event(type="ListProductPlansRequested", source="test", payload={})
        )
        self.assertEqual(len(listed_actions), 1)
        self.assertEqual(listed_actions[0].type, "ProductPlansListed")
        items = listed_actions[0].payload["items"]
        self.assertGreaterEqual(len(items), 1)

        required_fields = {
            "plan_id",
            "proposal_id",
            "created_at",
            "product_name",
            "target_audience",
            "format",
            "price_suggestion",
            "outline",
            "deliverables",
            "build_steps",
            "launch_plan",
        }
        self.assertTrue(required_fields.issubset(set(items[0].keys())))


if __name__ == "__main__":
    unittest.main()
