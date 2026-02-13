import unittest

from core.confirmation_queue import ConfirmationQueue
from core.control import Control
from core.events import Event


class ConfirmationQueueTest(unittest.TestCase):
    def test_queue_add_list_approve_reject(self):
        queue = ConfirmationQueue()

        first = queue.add({"action": "optimize"})
        second = queue.add({"id": "fixed-id", "action": "ship"})

        pending = queue.list_pending()
        self.assertEqual(len(pending), 2)
        self.assertIn(first, pending)
        self.assertIn(second, pending)

        approved = queue.approve(first["id"])
        self.assertEqual(approved, first)

        rejected = queue.reject("fixed-id")
        self.assertEqual(rejected, second)
        self.assertEqual(queue.list_pending(), [])

    def test_control_confirmation_events(self):
        control = Control()

        await_actions = control.consume(
            Event(type="ActionPlanGenerated", payload={"id": "p1", "action": "optimize"}, source="test")
        )
        self.assertEqual(len(await_actions), 1)
        self.assertEqual(await_actions[0].type, "AwaitingConfirmation")

        confirm_actions = control.consume(
            Event(type="ConfirmAction", payload={"plan_id": "p1"}, source="test")
        )
        self.assertEqual(len(confirm_actions), 1)
        self.assertEqual(confirm_actions[0].type, "ActionConfirmed")

        control.consume(
            Event(type="ActionPlanGenerated", payload={"id": "p2", "action": "optimize"}, source="test")
        )
        reject_actions = control.consume(
            Event(type="RejectAction", payload={"plan_id": "p2"}, source="test")
        )
        self.assertEqual(len(reject_actions), 1)
        self.assertEqual(reject_actions[0].type, "ActionRejected")


if __name__ == "__main__":
    unittest.main()
