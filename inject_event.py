from core.events import Event
from core.bus import event_bus

print("Injecting WakeWordDetected event...")
event_bus.push(Event(
    type="WakeWordDetected",
    payload={},
    source="manual"
))
print("Event injected.")
