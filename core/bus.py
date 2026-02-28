from __future__ import annotations

from queue import Queue, Empty
from collections import deque, defaultdict
from typing import Optional
import logging

from core.events import Event
import core.config as config


logger = logging.getLogger("treta.event_bus")


class EventBus:
    def __init__(self, max_events_per_cycle: int | None = None):
        self._q = Queue()
        self._history = deque(maxlen=200)
        self._max_events_per_cycle = max_events_per_cycle if max_events_per_cycle is not None else int(config.MAX_EVENTS_PER_CYCLE)
        self._cycle_budget_by_trace: dict[str, int] = defaultdict(int)

    def push(self, event: Event):
        trace_key = str(event.trace_id or event.request_id or "").strip() or "global"
        next_budget = int(self._cycle_budget_by_trace[trace_key]) + 1
        if next_budget > self._max_events_per_cycle:
            logger.critical(
                "Event cascade budget exceeded; dropping event",
                extra={
                    "event_type": event.type,
                    "trace_id": event.trace_id,
                    "request_id": event.request_id,
                    "event_id": event.event_id,
                    "max_events_per_cycle": self._max_events_per_cycle,
                    "events_seen": next_budget,
                },
            )
            return

        self._cycle_budget_by_trace[trace_key] = next_budget
        self._q.put(event)
        self._history.append(event)

    def pop(self, timeout: float = 0.2) -> Optional[Event]:
        try:
            event = self._q.get(timeout=timeout)
            trace_key = str(event.trace_id or event.request_id or "").strip() or "global"
            current = int(self._cycle_budget_by_trace.get(trace_key, 0))
            if current <= 1:
                self._cycle_budget_by_trace.pop(trace_key, None)
            else:
                self._cycle_budget_by_trace[trace_key] = current - 1
            return event
        except Empty:
            return None

    def recent(self, limit: int = 10) -> list[Event]:
        if limit <= 0:
            return []
        return list(self._history)[-limit:]
