import pytest

from core.domain.integrity import DomainIntegrityError, DomainIntegrityPolicy


def _proposal(proposal_id: str, status: str = "draft") -> dict:
    return {"id": proposal_id, "status": status}


def test_cannot_approve_second_proposal_when_one_is_already_approved():
    policy = DomainIntegrityPolicy()
    first = _proposal("proposal-1")
    second = _proposal("proposal-2")
    proposals = [first, second]

    policy.validate_transition(first, "approved", proposals)
    first["status"] = "approved"

    with pytest.raises(DomainIntegrityError):
        policy.validate_transition(second, "approved", proposals)


def test_cannot_approve_proposal_when_another_is_building():
    policy = DomainIntegrityPolicy()
    building = _proposal("proposal-1", status="building")
    candidate = _proposal("proposal-2")
    proposals = [building, candidate]

    with pytest.raises(DomainIntegrityError):
        policy.validate_transition(candidate, "approved", proposals)


def test_global_invariant_fails_with_two_active_proposals():
    policy = DomainIntegrityPolicy()
    proposals = [
        _proposal("proposal-1", status="approved"),
        _proposal("proposal-2", status="building"),
    ]

    with pytest.raises(DomainIntegrityError):
        policy.validate_global_invariants(proposals)
