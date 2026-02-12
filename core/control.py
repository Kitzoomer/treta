from dataclasses import dataclass
from typing import Any, Dict, List

from core.events import Event


@dataclass(frozen=True)
class Action:
    type: str
    payload: Dict[str, Any]


class Control:
    """Deterministic event -> action mapper (stub-only)."""

    def consume(self, event: Event) -> List[Action]:
        if event.type == "DailyBriefRequested":
            print("[CONTROL] DailyBriefRequested -> would build daily brief summary (stub)")
            return [Action(type="BuildDailyBrief", payload={"dry_run": True})]

        if event.type == "OpportunityScanRequested":
            print("[CONTROL] OpportunityScanRequested -> would run opportunity scan (stub)")
            return [Action(type="RunOpportunityScan", payload={"dry_run": True})]

        if event.type == "EmailTriageRequested":
            print("[CONTROL] EmailTriageRequested -> would triage inbox in dry-run mode (stub)")
            return [Action(type="RunEmailTriage", payload={"dry_run": True})]

        return []
