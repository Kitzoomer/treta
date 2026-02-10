from queue import Queue, Empty
from typing import Optional
from core.events import Event

class EventBus:
    def __init__(self):
        self._q = Queue()

    def push(self, event: Event):
        self._q.put(event)

    def pop(self, timeout: float = 0.2) -> Optional[Event]:
        try:
            return self._q.get(timeout=timeout)
        except Empty:
            return None

event_bus = EventBus()
