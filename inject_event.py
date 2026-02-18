import requests

from core.events import Event

payload = Event(
    type="WakeWordDetected",
    payload={},
    source="injector",
).__dict__

requests.post("http://localhost:7777/event", json=payload, timeout=2)
print("Event sent")
