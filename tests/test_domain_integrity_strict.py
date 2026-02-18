import unittest

from core.domain.integrity import DomainIntegrityError, DomainIntegrityPolicy


def _proposal(proposal_id: str, status: str = "draft") -> dict:
    return {"id": proposal_id, "status": status}


class DomainIntegrityStrictTest(unittest.TestCase):
    def test_cannot_approve_second_proposal_when_one_is_already_approved(self):
        policy = DomainIntegrityPolicy()
        first = _proposal("proposal-1")
        second = _proposal("proposal-2")
        proposals = [first, second]

        policy.validate_transition(first, "approved", proposals)
        first["status"] = "approved"

        with self.assertRaises(DomainIntegrityError):
            policy.validate_transition(second, "approved", proposals)

    def test_cannot_approve_proposal_when_another_is_building(self):
        policy = DomainIntegrityPolicy()
        building = _proposal("proposal-1", status="building")
        candidate = _proposal("proposal-2")
        proposals = [building, candidate]

        with self.assertRaises(DomainIntegrityError):
            policy.validate_transition(candidate, "approved", proposals)

    def test_global_invariant_fails_with_two_active_proposals(self):
        policy = DomainIntegrityPolicy()
        proposals = [
            _proposal("proposal-1", status="approved"),
            _proposal("proposal-2", status="building"),
        ]

        with self.assertRaises(DomainIntegrityError):
            policy.validate_global_invariants(proposals)

    def test_cannot_transition_directly_from_draft_to_ready_to_launch(self):
        policy = DomainIntegrityPolicy()
        proposal = _proposal("proposal-1", status="draft")
        proposals = [proposal]

        with self.assertRaises(DomainIntegrityError):
            policy.validate_transition(proposal, "ready_to_launch", proposals)

    def test_illegal_backward_transition_from_ready_to_launch_to_draft_raises(self):
        policy = DomainIntegrityPolicy()
        proposal = _proposal("proposal-1", status="ready_to_launch")
        proposals = [proposal]

        with self.assertRaises(DomainIntegrityError):
            policy.validate_transition(proposal, "draft", proposals)

    def test_valid_lifecycle_transitions_do_not_raise_errors(self):
        policy = DomainIntegrityPolicy()
        proposal = _proposal("proposal-1", status="draft")
        proposals = [proposal]

        policy.validate_transition(proposal, "approved", proposals)
        proposal["status"] = "approved"

        policy.validate_transition(proposal, "building", proposals)
        proposal["status"] = "building"

        policy.validate_transition(proposal, "ready_to_launch", proposals)

    def test_corrupted_proposal_state_with_two_active_proposals_is_detected(self):
        policy = DomainIntegrityPolicy()
        proposals = [
            {"id": "proposal-a", "status": "approved"},
            {"id": "proposal-b", "status": "building"},
        ]

        with self.assertRaises(DomainIntegrityError):
            policy.validate_global_invariants(proposals)


if __name__ == "__main__":
    unittest.main()
