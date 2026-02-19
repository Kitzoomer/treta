from __future__ import annotations

from core.domain.lifecycle import (
    ACTIVE_PROPOSAL_STATUSES,
    PLAN_BUILDABLE_STATUSES,
    PROPOSAL_TRANSITIONS,
)


class DomainIntegrityError(Exception):
    pass


class DomainIntegrityPolicy:
    ACTIVE_STATUSES = ACTIVE_PROPOSAL_STATUSES
    PLAN_BUILDABLE_STATUSES = PLAN_BUILDABLE_STATUSES
    ALLOWED_TRANSITIONS = PROPOSAL_TRANSITIONS

    def validate_global_invariants(self, proposals, launches=None, plans=None):
        active = [p for p in proposals if p["status"] in self.ACTIVE_STATUSES]
        if len(active) > 1:
            raise DomainIntegrityError("More than one active proposal detected.")

    def validate_transition(self, proposal, new_status, proposals):
        current_status = proposal["status"]

        allowed_targets = self.ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_targets:
            raise DomainIntegrityError(
                f"Invalid transition: {current_status} -> {new_status}."
            )

        if new_status in self.ACTIVE_STATUSES:
            active = [
                p
                for p in proposals
                if p["status"] in self.ACTIVE_STATUSES and p["id"] != proposal["id"]
            ]
            if active:
                raise DomainIntegrityError(
                    "Cannot activate proposal: another active proposal exists."
                )

    def validate_plan_build_precondition(self, proposal):
        status = str(proposal.get("status", "")).strip()
        if status not in self.PLAN_BUILDABLE_STATUSES:
            raise DomainIntegrityError(
                f"Cannot build plan for proposal in status: {status}."
            )
