import pytest

from dcms.lifecycle import AuditTrail, InvalidStatusChange, change_status
from dcms.models import ContractRequest, RequestStatus as St


def make_request():
    return ContractRequest("REQ-1", "CON-1", "Contract Retrieval", 0, 4, 10)


def test_valid_lifecycle():
    req, trail = make_request(), AuditTrail()
    for status in (St.QUEUED, St.IN_PROGRESS, St.COMPLETED):
        change_status(req, status, 0, trail)
    assert req.status is St.COMPLETED
    assert len(trail.entries) == 3


def test_paused_request_returns_to_queue():
    req, trail = make_request(), AuditTrail()
    change_status(req, St.QUEUED, 0, trail)
    change_status(req, St.IN_PROGRESS, 1, trail)
    change_status(req, St.QUEUED, 2, trail, "paused")
    assert req.status is St.QUEUED


@pytest.mark.parametrize("target", [St.IN_PROGRESS, St.AWAITING_APPROVAL, St.COMPLETED])
def test_submitted_can_only_be_queued(target):
    with pytest.raises(InvalidStatusChange):
        change_status(make_request(), target, 0, AuditTrail())


def test_queued_cannot_complete_directly():
    req, trail = make_request(), AuditTrail()
    change_status(req, St.QUEUED, 0, trail)
    with pytest.raises(InvalidStatusChange):
        change_status(req, St.COMPLETED, 1, trail)


def test_completed_is_final():
    req, trail = make_request(), AuditTrail()
    for status in (St.QUEUED, St.IN_PROGRESS, St.COMPLETED):
        change_status(req, status, 0, trail)
    with pytest.raises(InvalidStatusChange):
        change_status(req, St.QUEUED, 5, trail)


def test_rejected_change_is_not_recorded():
    req, trail = make_request(), AuditTrail()
    with pytest.raises(InvalidStatusChange):
        change_status(req, St.IN_PROGRESS, 0, trail)
    assert trail.entries == []
