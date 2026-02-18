class DomainIntegrityError(Exception):
    pass


class DomainIntegrityPolicy:
    ACTIVE_STATUSES = ["approved", "building", "ready_to_launch"]
    PLAN_BUILDABLE_STATUSES = {"approved", "building", "ready_to_launch", "ready_for_review"}
    ALLOWED_TRANSITIONS = {
        "draft": {"approved", "rejected"},
        "approved": {"building", "archived"},
        "building": {"ready_to_launch"},
        "ready_to_launch": {"ready_for_review"},
        "ready_for_review": {"launched", "executed"},
        "launched": {"archived"},
        "rejected": {"archived"},
        "archived": set(),
    }

    def validate_global_invariants(self, proposals):
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

        # Rule 1: only one active proposal
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

        # Rule 2: building requires approved
        if new_status == "building" and current_status != "approved":
            raise DomainIntegrityError(
                "Cannot move to building unless proposal is approved."
            )

        # Rule 3: ready_to_launch requires building
        if new_status == "ready_to_launch" and current_status != "building":
            raise DomainIntegrityError(
                "Cannot move to ready_to_launch unless building."
            )

        # Rule 4: execute requires ready_to_launch
        if new_status == "executed" and current_status != "ready_to_launch":
            raise DomainIntegrityError("Cannot execute unless ready_to_launch.")

    def validate_plan_build_precondition(self, proposal):
        status = str(proposal.get("status", "")).strip()
        if status not in self.PLAN_BUILDABLE_STATUSES:
            raise DomainIntegrityError(
                f"Cannot build plan for proposal in status: {status}."
            )
