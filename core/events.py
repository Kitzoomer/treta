from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict
import uuid

@dataclass
class Event:
    type: str
    payload: Dict[str, Any]
    source: str = "core"
    request_id: str = ""
    trace_id: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
