from queue import Queue, Empty
from collections import deque
from typing import Optional
from core.events import Event

class EventBus:
    def __init__(self):
        self._q = Queue()
        self._history = deque(maxlen=200)

    def push(self, event: Event):
        self._q.put(event)
        self._history.append(event)

    def pop(self, timeout: float = 0.2) -> Optional[Event]:
        try:
            return self._q.get(timeout=timeout)
        except Empty:
            return None

    def recent(self, limit: int = 10) -> list[Event]:
        if limit <= 0:
            return []
        return list(self._history)[-limit:]

# TODO(arch): replace global singleton with instance-scoped bus injection to avoid cross-request bleed.
event_bus = EventBus()
