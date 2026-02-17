from __future__ import annotations

from typing import Any, Dict, Iterable, List


class ExecutionFocusEngine:
    """Selects and enforces a single active execution target across proposals and launches."""

    @staticmethod
    def select_active(proposals: Iterable[Dict[str, Any]], launches: Iterable[Dict[str, Any]]) -> str | None:
        """
        Returns ID of the single active execution target.
        Priority order:

        1) Proposal with status "building"
        2) Proposal with status "approved"
        3) Launch with status not "launched"
        4) None
        """
        proposal_items: List[Dict[str, Any]] = list(proposals)
        launch_items: List[Dict[str, Any]] = list(launches)

        for proposal in reversed(proposal_items):
            if str(proposal.get("status", "")).strip() == "building":
                return str(proposal.get("id", "")).strip() or None

        for proposal in reversed(proposal_items):
            if str(proposal.get("status", "")).strip() == "approved":
                return str(proposal.get("id", "")).strip() or None

        for launch in reversed(launch_items):
            if str(launch.get("status", "")).strip() != "launched":
                return str(launch.get("id", "")).strip() or None

        return None

    @staticmethod
    def enforce_single_active(target_id: str | None, store: Dict[str, Any]) -> None:
        """Ensures only one proposal/launch is marked as active_execution=True, all others False."""
        proposals = store.get("proposals", [])
        launches = store.get("launches", [])

        for item in proposals:
            item_id = str(item.get("id", "")).strip()
            item["active_execution"] = bool(target_id and item_id == target_id)

        for item in launches:
            item_id = str(item.get("id", "")).strip()
            item["active_execution"] = bool(target_id and item_id == target_id)
