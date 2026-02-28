from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict
import uuid

from core.event_catalog import EventType, normalize_event_type


@dataclass
class Event:
    type: str | EventType
    payload: Dict[str, Any]
    source: str = "core"
    request_id: str = ""
    trace_id: str = ""
    timestamp: str = ""
    event_id: str = ""
    decision_id: str = ""
    invalid: bool = False
    invalid_reason: str = ""

    def __post_init__(self):
        self.type = normalize_event_type(self.type)
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if not self.event_id:
            self.event_id = str(uuid.uuid4())


def make_event(
    event_type: EventType | str,
    payload: Dict[str, Any],
    *,
    source: str = "core",
    request_id: str = "",
    trace_id: str = "",
    decision_id: str = "",
) -> Event:
    return Event(
        type=event_type,
        payload=payload,
        source=source,
        request_id=request_id,
        trace_id=trace_id,
        decision_id=decision_id,
    )
