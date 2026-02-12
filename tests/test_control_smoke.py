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


if __name__ == "__main__":
    unittest.main()
