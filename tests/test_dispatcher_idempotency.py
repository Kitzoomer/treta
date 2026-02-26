import tempfile
import unittest
from unittest.mock import patch

from core.bus import EventBus
from core.dispatcher import Dispatcher
from core.events import Event
from core.state_machine import StateMachine
from core.storage import Storage


class _CountingControl:
    def __init__(self):
        self.calls = 0

    def consume(self, event):
        self.calls += 1
        return []


class _FailingControl:
    def consume(self, _event):
        raise RuntimeError("boom")


class DispatcherIdempotencyTest(unittest.TestCase):
    def test_event_generates_event_id_when_missing(self):
        event = Event(type="ListOpportunities", payload={}, source="test")
        self.assertTrue(event.event_id)

    def test_duplicate_event_id_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                bus = EventBus()
                control = _CountingControl()
                dispatcher = Dispatcher(state_machine=StateMachine(), control=control, bus=bus, storage=storage)

                event = Event(
                    type="ListOpportunities",
                    payload={},
                    source="test",
                    event_id="evt-dup-1",
                )

                dispatcher.handle(event)
                dispatcher.handle(event)

                self.assertEqual(control.calls, 1)
                self.assertTrue(storage.is_event_processed("evt-dup-1"))

    def test_failed_handler_is_not_marked_processed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                dispatcher = Dispatcher(state_machine=StateMachine(), control=_FailingControl(), bus=EventBus(), storage=storage)
                event = Event(type="ListOpportunities", payload={}, source="test", event_id="evt-fail-1")

                with self.assertRaises(RuntimeError):
                    dispatcher.handle(event)

                self.assertFalse(storage.is_event_processed("evt-fail-1"))


if __name__ == "__main__":
    unittest.main()
