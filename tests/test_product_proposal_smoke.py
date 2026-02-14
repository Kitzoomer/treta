import unittest

from core.bus import event_bus
from core.control import Control
from core.dispatcher import Dispatcher
from core.events import Event
from core.state_machine import StateMachine


class ProductProposalSmokeTest(unittest.TestCase):
    def test_opportunity_detected_emits_product_proposal_generated(self):
        dispatcher = Dispatcher(state_machine=StateMachine(), control=Control())
        history_before = len(event_bus.recent(limit=200))

        dispatcher.handle(
            Event(
                type="OpportunityDetected",
                source="test",
                payload={
                    "id": "opp-media-1",
                    "source": "twitter",
                    "title": "Need a better media kit for brand collaboration deals",
                    "summary": "Creators ask for sponsorship rate sheet and ugc examples.",
                    "opportunity": {"money": 7, "growth": 6},
                },
            )
        )

        history_after = event_bus.recent(limit=200)
        new_events = history_after[history_before:]
        generated = [event for event in new_events if event.type == "ProductProposalGenerated"]

        self.assertEqual(len(generated), 1)
        payload = generated[0].payload
        proposal = payload["proposal"]
        self.assertEqual(payload["proposal_id"], proposal["id"])

        required_fields = {
            "id",
            "created_at",
            "source_opportunity_id",
            "product_name",
            "product_type",
            "target_audience",
            "core_problem",
            "solution",
            "format",
            "price_suggestion",
            "deliverables",
            "positioning",
            "distribution_plan",
            "validation_plan",
            "confidence",
            "reasoning",
        }
        self.assertTrue(required_fields.issubset(set(proposal.keys())))
        self.assertGreaterEqual(proposal["confidence"], 6)


if __name__ == "__main__":
    unittest.main()
