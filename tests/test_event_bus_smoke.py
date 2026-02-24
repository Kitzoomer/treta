from __future__ import annotations

import unittest


class EventBusSmokeTest(unittest.TestCase):
    def test_event_bus_publish_consume_smoke(self) -> None:
        try:
            from core.bus import EventBus
            from core.events import Event
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"event bus module unavailable: {exc}")

        bus = EventBus()
        payload = {"audit": True}
        bus.push(Event(type="AuditEvent", payload=payload, source="audit"))
        event = bus.pop(timeout=0.5)

        self.assertIsNotNone(event)
        self.assertEqual(event.type, "AuditEvent")
        self.assertEqual(event.payload, payload)


if __name__ == "__main__":
    unittest.main()
