import unittest

from core.bus import EventBus
from core.control import Control
from core.events import Event


class ConfirmationFlowTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_action_plan_generated_emits_awaiting_confirmation(self):
        control = Control(bus=self.bus)

        actions = control.consume(
            Event(
                type="ActionPlanGenerated",
                payload={"action": "optimize", "steps": ["one"]},
                source="test",
            )
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "AwaitingConfirmation")
        self.assertIn("plan_id", actions[0].payload)
        self.assertEqual(actions[0].payload["plan"], {"action": "optimize", "steps": ["one"]})


if __name__ == "__main__":
    unittest.main()
