from __future__ import annotations

from typing import Any


class DailyLoopEngine:
    def __init__(self, opportunity_store, proposal_store, launch_store, strategy_store):
        self.opportunity_store = opportunity_store
        self.proposal_store = proposal_store
        self.launch_store = launch_store
        self.strategy_store = strategy_store

    def compute_phase(self) -> str:
        pending_strategy_actions = self.strategy_store.list(status="pending_confirmation")
        if pending_strategy_actions:
            return "EXECUTE"

        proposals = self.proposal_store.list()
        if any(str(item.get("status", "")).strip().lower() == "draft" for item in proposals):
            return "DECIDE"

        if any(str(item.get("status", "")).strip().lower() == "approved" for item in proposals):
            return "BUILD"

        opportunities = self.opportunity_store.list(status="new")
        if opportunities:
            return "SCAN"

        return "IDLE"

    def get_loop_state(self) -> dict[str, Any]:
        phase = self.compute_phase()

        if phase == "EXECUTE":
            pending_count = len(self.strategy_store.list(status="pending_confirmation"))
            label = "Execute Strategy"
            summary = f"{pending_count} pending strategy action{'s' if pending_count != 1 else ''} ready for execution."
            return {
                "phase": phase,
                "summary": summary,
                "next_action_label": label,
                "route": "#/strategy",
            }

        if phase == "DECIDE":
            draft_count = len([item for item in self.proposal_store.list() if str(item.get("status", "")).strip().lower() == "draft"])
            label = "Review Drafts"
            summary = f"{draft_count} draft proposal{'s' if draft_count != 1 else ''} awaiting decision."
            return {
                "phase": phase,
                "summary": summary,
                "next_action_label": label,
                "route": "#/work",
            }

        if phase == "BUILD":
            approved_count = len([item for item in self.proposal_store.list() if str(item.get("status", "")).strip().lower() == "approved"])
            label = "Start Build"
            summary = f"{approved_count} approved proposal{'s' if approved_count != 1 else ''} ready to be built."
            return {
                "phase": phase,
                "summary": summary,
                "next_action_label": label,
                "route": "#/work",
            }

        if phase == "SCAN":
            pending_opportunities = len(self.opportunity_store.list(status="new"))
            label = "Scan Opportunities"
            summary = f"{pending_opportunities} {'opportunity' if pending_opportunities == 1 else 'opportunities'} pending evaluation."
            return {
                "phase": phase,
                "summary": summary,
                "next_action_label": label,
                "route": "#/work",
            }

        return {
            "phase": "IDLE",
            "summary": "System operating normally.",
            "next_action_label": "No Immediate Action",
            "route": None,
        }
