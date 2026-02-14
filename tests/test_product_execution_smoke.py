import unittest

from core.bus import event_bus
from core.control import Control
from core.dispatcher import Dispatcher
from core.events import Event
from core.state_machine import StateMachine


class ProductExecutionSmokeTest(unittest.TestCase):
    def test_generate_proposal_then_execute(self):
        dispatcher = Dispatcher(state_machine=StateMachine(), control=Control())
        history_before = len(event_bus.recent(limit=300))

        dispatcher.handle(
            Event(
                type="OpportunityDetected",
                source="test",
                payload={
                    "id": "opp-exec-1",
                    "source": "reddit",
                    "title": "Freelancers asking for proposal and pricing templates",
                    "summary": "Repeated demand for proposal framework and pricing scripts.",
                    "opportunity": {"money": 7, "growth": 6},
                },
            )
        )

        events_after_proposal = event_bus.recent(limit=300)
        new_events = events_after_proposal[history_before:]
        generated = [event for event in new_events if event.type == "ProductProposalGenerated"]
        self.assertEqual(len(generated), 1)

        proposal_id = generated[0].payload["proposal_id"]
        dispatcher.handle(
            Event(
                type="ExecuteProductPlanRequested",
                source="test",
                payload={"proposal_id": proposal_id},
            )
        )

        events_after_execution = event_bus.recent(limit=300)
        execution_events = [
            event
            for event in events_after_execution[history_before:]
            if event.type == "ProductPlanExecuted"
        ]
        self.assertEqual(len(execution_events), 1)

        package = execution_events[0].payload["execution_package"]
        self.assertTrue(package.get("reddit_post", {}).get("title"))
        self.assertTrue(package.get("gumroad_description"))
        self.assertTrue(package.get("pricing_strategy"))


if __name__ == "__main__":
    unittest.main()
