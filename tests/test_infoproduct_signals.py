import unittest

from core.control import Control
from core.dispatcher import Dispatcher
from core.events import Event
from core.opportunity_store import OpportunityStore
from core.state_machine import State, StateMachine
from core.bus import event_bus


class InfoproductSignalsTest(unittest.TestCase):
    def test_run_infoproduct_scan_populates_opportunity_store(self):
        while event_bus.pop(timeout=0.001) is not None:
            pass

        opportunity_store = OpportunityStore()
        control = Control(opportunity_store=opportunity_store)
        dispatcher = Dispatcher(state_machine=StateMachine(initial_state=State.IDLE), control=control)

        dispatcher.handle(Event(type="RunInfoproductScan", payload={}, source="test"))

        while True:
            queued = event_bus.pop(timeout=0.01)
            if queued is None:
                break
            dispatcher.handle(queued)

        items = opportunity_store.list()
        self.assertEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main()
