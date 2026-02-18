class DomainIntegrityError(Exception):
    pass


class DomainIntegrityPolicy:
    ACTIVE_STATUSES = ["approved", "building", "ready_to_launch"]

    def validate_global_invariants(self, proposals):
        active = [p for p in proposals if p["status"] in self.ACTIVE_STATUSES]
        if len(active) > 1:
            raise DomainIntegrityError("More than one active proposal detected.")

    def validate_transition(self, proposal, new_status, proposals):
        current_status = proposal["status"]

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
