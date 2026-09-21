import pytest

from dcms.models import ContractRequest, RequestStatus


def test_initial_status():
    req = ContractRequest("REQ-1", "CON-1", "Deadline Alert", 2, 3, 10)
    assert req.status is RequestStatus.SUBMITTED
    assert req.remaining_effort == 3
    assert req.queue_wait is None


def test_rejects_invalid_effort():
    with pytest.raises(ValueError):
        ContractRequest("REQ-1", "CON-1", "Deadline Alert", 0, 0, 10)


def test_rejects_unreachable_due_date():
    with pytest.raises(ValueError):
        ContractRequest("REQ-1", "CON-1", "Deadline Alert", 5, 4, 8)


def test_derived_times():
    req = ContractRequest("REQ-1", "CON-1", "Deadline Alert", 2, 3, 20)
    req.started_at, req.completed_at = 6, 9
    assert req.total_handling_time == 7
    assert req.queue_wait == 4
    assert req.first_response_delay == 4
    assert req.sla_breached is False
