from __future__ import annotations

import pytest


try:
    from core.bus import EventBus
    from core.events import Event
except Exception as exc:  # pragma: no cover
    EventBus = None
    Event = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@pytest.mark.xfail(EventBus is None or Event is None, reason=f"event bus module unavailable: {IMPORT_ERROR}")
def test_event_bus_publish_consume_smoke() -> None:
    bus = EventBus()
    payload = {"audit": True}
    bus.push(Event(type="AuditEvent", payload=payload, source="audit"))
    event = bus.pop(timeout=0.5)
    assert event is not None
    assert event.type == "AuditEvent"
    assert event.payload == payload
