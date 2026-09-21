from pathlib import Path

import pytest

from dcms.analytics import summarize
from dcms.engine import WorkflowEngine
from dcms.intake import load_requests
from dcms.models import ContractRequest
from dcms.policies import ArrivalOrderPolicy

DATA = Path(__file__).resolve().parent.parent / "data" / "sample_requests.csv"


def run(requests):
    return WorkflowEngine(requests, ArrivalOrderPolicy()).run()


def test_handled_in_submission_order():
    result = run(load_requests(DATA))
    assert [label for label, _, _ in result.timeline] == [f"REQ-10{i}" for i in range(1, 9)]


def test_known_queue_waits():
    result = run(load_requests(DATA))
    waits = {r.request_id: r.queue_wait for r in result.requests}
    assert waits == {
        "REQ-101": 0, "REQ-102": 7, "REQ-103": 10, "REQ-104": 11,
        "REQ-105": 15, "REQ-106": 17, "REQ-107": 16, "REQ-108": 20,
    }


def test_summary_values():
    s = summarize(run(load_requests(DATA)))
    assert s.avg_queue_wait == pytest.approx(12.0)
    assert s.avg_handling_time == pytest.approx(16.5)
    assert s.sla_breaches == 6
    assert s.utilization == pytest.approx(100.0)


def test_idle_gap_is_recorded():
    reqs = [ContractRequest("A", "C-1", "Contract Retrieval", 0, 2, 5),
            ContractRequest("B", "C-2", "Contract Retrieval", 5, 2, 9)]
    result = run(reqs)
    assert result.timeline == [("A", 0, 2), ("Idle", 2, 5), ("B", 5, 7)]
    assert result.requests[1].queue_wait == 0


def test_input_is_not_modified():
    reqs = load_requests(DATA)
    run(reqs)
    assert all(r.completed_at is None for r in reqs)


def test_each_request_follows_full_lifecycle():
    result = run(load_requests(DATA))
    for r in result.requests:
        statuses = [e.to_status.value for e in result.audit.for_request(r.request_id)]
        assert statuses == ["QUEUED", "IN_PROGRESS", "COMPLETED"]
