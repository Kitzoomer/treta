import unittest

from core.bus import EventBus
from core.confirmation_queue import ConfirmationQueue
from core.control import Control
from core.events import Event


class ConfirmationQueueTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_queue_add_list_approve_reject(self):
        queue = ConfirmationQueue()

        first_id = queue.add({"action": "optimize"})
        second_id = queue.add({"id": "fixed-id", "action": "ship"})

        pending = queue.list_pending()
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0]["status"], "pending")
        self.assertEqual(pending[0]["id"], first_id)
        self.assertEqual(pending[1]["id"], second_id)

        approved = queue.approve(first_id)
        self.assertIsNotNone(approved)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["plan"], {"action": "optimize"})

        rejected = queue.reject(second_id)
        self.assertIsNotNone(rejected)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["plan"], {"id": "fixed-id", "action": "ship"})

        self.assertEqual(queue.list_pending(), [])

    def test_control_confirm_reject_and_list_pending(self):
        control = Control(bus=self.bus)

        first = control.consume(
            Event(type="ActionPlanGenerated", payload={"id": "p1", "action": "optimize"}, source="test")
        )[0].payload["plan_id"]
        second = control.consume(
            Event(type="ActionPlanGenerated", payload={"id": "p2", "action": "ship"}, source="test")
        )[0].payload["plan_id"]

        listed = control.consume(
            Event(type="ListPendingConfirmations", payload={}, source="test")
        )
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].type, "PendingConfirmationsListed")
        self.assertEqual(len(listed[0].payload["items"]), 2)

        confirm_actions = control.consume(
            Event(type="ConfirmAction", payload={"plan_id": first}, source="test")
        )
        self.assertEqual(len(confirm_actions), 1)
        self.assertEqual(confirm_actions[0].type, "ActionConfirmed")
        self.assertEqual(confirm_actions[0].payload, {"plan_id": first, "plan": {"id": "p1", "action": "optimize"}})

        reject_actions = control.consume(
            Event(type="RejectAction", payload={"plan_id": second}, source="test")
        )
        self.assertEqual(len(reject_actions), 1)
        self.assertEqual(reject_actions[0].type, "ActionRejected")
        self.assertEqual(reject_actions[0].payload, {"plan_id": second, "plan": {"id": "p2", "action": "ship"}})


if __name__ == "__main__":
    unittest.main()
