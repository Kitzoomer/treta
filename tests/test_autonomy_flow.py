import unittest

from core.autonomy_controller import AutonomyController
from core.bus import EventBus


class AutonomyFlowTest(unittest.TestCase):
    def test_execute_emits_action_approved(self):
        bus = EventBus()
        controller = AutonomyController(bus=bus)

        emitted = controller.handle_evaluated_opportunity(
            {"score": 10.0, "decision": "execute", "reasoning": "good"}
        )

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].type, "ActionApproved")
        popped = bus.pop(timeout=0.01)
        self.assertIsNotNone(popped)
        self.assertEqual(popped.type, "ActionApproved")

    def test_warn_emits_action_requires_confirmation(self):
        bus = EventBus()
        controller = AutonomyController(bus=bus)

        emitted = controller.handle_evaluated_opportunity(
            {"score": 3.0, "decision": "warn", "reasoning": "careful"}
        )

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].type, "ActionRequiresConfirmation")
        popped = bus.pop(timeout=0.01)
        self.assertIsNotNone(popped)
        self.assertEqual(popped.type, "ActionRequiresConfirmation")

    def test_reject_emits_nothing(self):
        bus = EventBus()
        controller = AutonomyController(bus=bus)

        emitted = controller.handle_evaluated_opportunity(
            {"score": -1.0, "decision": "reject", "reasoning": "bad"}
        )

        self.assertEqual(emitted, [])
        popped = bus.pop(timeout=0.01)
        self.assertIsNone(popped)


if __name__ == "__main__":
    unittest.main()
