from queue import Queue, Empty
from typing import Optional
from core.events import Event

class EventQueue:
    def __init__(self):
        self._queue = Queue()

    def push(self, event: Event):
        self._queue.put(event)

    def pop(self, timeout: float = 0.1) -> Optional[Event]:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None
