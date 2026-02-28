import logging
import unittest

from core.bus import EventBus
from core.dispatcher import Dispatcher
from core.events import Event, make_event
from core.event_catalog import EventType
from core.state_machine import StateMachine


class _NoopControl:
    def consume(self, event):
        return []


class EventCatalogAndBudgetTest(unittest.TestCase):
    def test_unknown_event_logs_warning(self):
        dispatcher = Dispatcher(state_machine=StateMachine(), control=_NoopControl(), bus=EventBus())
        event = Event(type="UnknownEventX", payload={"trace_id": "tr-x"}, source="test", trace_id="tr-x")
        with self.assertLogs("treta.dispatcher", level="WARNING") as captured:
            dispatcher.handle(event)
        self.assertTrue(any("Unknown event type not in catalog" in msg for msg in captured.output))

    def test_invalid_payload_logs_warning_and_marks_invalid(self):
        dispatcher = Dispatcher(state_machine=StateMachine(), control=_NoopControl(), bus=EventBus())
        event = Event(type=EventType.EXECUTE_STRATEGY_ACTION, payload={}, source="test", trace_id="tr-y")
        with self.assertLogs("treta.dispatcher", level="WARNING") as captured:
            dispatcher.handle(event)
        self.assertTrue(event.invalid)
        self.assertTrue(any("Invalid event payload for catalog schema" in msg for msg in captured.output))

    def test_budget_drops_event_after_limit(self):
        bus = EventBus(max_events_per_cycle=1)
        first = make_event(EventType.LIST_OPPORTUNITIES, {}, trace_id="tr-budget")
        second = make_event(EventType.LIST_OPPORTUNITIES, {}, trace_id="tr-budget")
        bus.push(first)
        with self.assertLogs("treta.event_bus", level="CRITICAL") as captured:
            bus.push(second)

        popped = bus.pop(timeout=0.01)
        self.assertIsNotNone(popped)
        self.assertIsNone(bus.pop(timeout=0.01))
        self.assertTrue(any("Event cascade budget exceeded" in msg for msg in captured.output))


if __name__ == "__main__":
    unittest.main()
