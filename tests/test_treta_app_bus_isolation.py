import unittest

from core.app import TretaApp
from core.events import Event


class TretaAppBusIsolationTest(unittest.TestCase):
    def test_two_apps_have_isolated_event_buses(self):
        app1 = TretaApp()
        app2 = TretaApp()

        app1.bus.push(Event(type="IsolationProbe", payload={"id": 1}, source="test"))

        self.assertIsNotNone(app1.bus.pop(timeout=0.01))
        self.assertIsNone(app2.bus.pop(timeout=0.01))


if __name__ == "__main__":
    unittest.main()
