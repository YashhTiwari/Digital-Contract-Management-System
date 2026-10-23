"""Scheduling policies checked against hand-calculated (textbook) results."""

from pathlib import Path

import pytest

from dcms.analytics import compare_policies, quantum_sweep, summarize
from dcms.engine import WorkflowEngine
from dcms.intake import load_requests
from dcms.lifecycle import ALLOWED_CHANGES
from dcms.models import ContractRequest, RequestStatus as St
from dcms.policies import (EarliestDuePolicy, MultilevelFeedbackPolicy,
                           MultilevelQueuePolicy, RoundRobinPolicy,
                           ShortestEffortPolicy, ShortestRemainingPolicy, make_policy)

DATA = Path(__file__).resolve().parent.parent / "data" / "sample_requests.csv"


def req(rid, arrival, effort, priority=3, due=None):
    return ContractRequest(rid, f"C-{rid}", "Contract Retrieval", arrival, effort,
                           due if due is not None else 200, priority)


def waits(result):
    return {r.request_id: r.queue_wait for r in result.requests}


# Classic example: P1(0,8) P2(1,4) P3(2,9) P4(3,5)
CLASSIC = [req("P1", 0, 8), req("P2", 1, 4), req("P3", 2, 9), req("P4", 3, 5)]


def test_sjf_non_preemptive():
    result = WorkflowEngine(CLASSIC, ShortestEffortPolicy()).run()
    assert result.timeline == [("P1", 0, 8), ("P2", 8, 12), ("P4", 12, 17), ("P3", 17, 26)]
    assert waits(result) == {"P1": 0, "P2": 7, "P3": 15, "P4": 9}
    assert result.preemptions == 0


def test_srtf_preempts_longer_request():
    result = WorkflowEngine(CLASSIC, ShortestRemainingPolicy()).run()
    assert result.timeline == [("P1", 0, 1), ("P2", 1, 5), ("P4", 5, 10),
                               ("P1", 10, 17), ("P3", 17, 26)]
    assert summarize(result).avg_queue_wait == pytest.approx(6.5)
    assert result.preemptions == 1


def test_srtf_keeps_active_request_on_tie():
    reqs = [req("A", 0, 3), req("B", 1, 2)]
    result = WorkflowEngine(reqs, ShortestRemainingPolicy()).run()
    assert result.timeline == [("A", 0, 3), ("B", 3, 5)]


def test_round_robin_quantum_4():
    reqs = [req("P1", 0, 24), req("P2", 0, 3), req("P3", 0, 3)]
    result = WorkflowEngine(reqs, RoundRobinPolicy(4)).run()
    assert result.timeline == [("P1", 0, 4), ("P2", 4, 7), ("P3", 7, 10), ("P1", 10, 30)]
    assert waits(result) == {"P1": 6, "P2": 4, "P3": 7}


def test_round_robin_new_arrival_queued_before_paused_request():
    reqs = [req("A", 0, 4), req("B", 2, 2)]
    result = WorkflowEngine(reqs, RoundRobinPolicy(2)).run()
    assert result.timeline == [("A", 0, 2), ("B", 2, 4), ("A", 4, 6)]


def test_round_robin_rejects_bad_quantum():
    with pytest.raises(ValueError):
        RoundRobinPolicy(0)


def test_multilevel_queue_higher_queue_preempts():
    reqs = [req("A", 0, 5, priority=4), req("B", 1, 3, priority=1), req("C", 2, 2, priority=2)]
    result = WorkflowEngine(reqs, MultilevelQueuePolicy()).run()
    assert result.timeline == [("A", 0, 1), ("B", 1, 4), ("C", 4, 6), ("A", 6, 10)]
    assert waits(result) == {"A": 5, "B": 0, "C": 2}


def test_mlfq_demotes_long_request():
    policy = MultilevelFeedbackPolicy()
    result = WorkflowEngine([req("A", 0, 10)], policy).run()
    assert result.timeline == [("A", 0, 10)]
    assert policy.demotions == 2          # Urgent -> Standard -> Background


def test_mlfq_demoted_request_yields_to_new_arrival():
    reqs = [req("A", 0, 6), req("B", 1, 2)]
    result = WorkflowEngine(reqs, MultilevelFeedbackPolicy()).run()
    assert result.timeline == [("A", 0, 2), ("B", 2, 4), ("A", 4, 8)]


def test_mlfq_aging_prevents_starvation():
    stream = [req("LONG", 0, 10)] + [req(f"S{i:02}", 1 + 2 * i, 2) for i in range(15)]
    starved = WorkflowEngine(stream, MultilevelFeedbackPolicy(aging_threshold=1000)).run()
    aged_policy = MultilevelFeedbackPolicy(aging_threshold=5)
    aged = WorkflowEngine(stream, aged_policy).run()
    done = lambda res: next(r.completed_at for r in res.requests if r.request_id == "LONG")
    assert aged_policy.promotions > 0
    assert done(aged) < done(starved)


def test_earliest_due_first():
    reqs = [req("A", 0, 5, due=30), req("B", 1, 2, due=4)]
    result = WorkflowEngine(reqs, EarliestDuePolicy()).run()
    assert result.timeline == [("A", 0, 1), ("B", 1, 3), ("A", 3, 7)]
    assert not any(r.sla_breached for r in result.requests)


def test_estimated_effort_drives_ranking():
    a, b = req("A", 0, 2), req("B", 0, 6)
    a.estimated_effort, b.estimated_effort = 9, 1    # predictions are wrong
    result = WorkflowEngine([a, b], ShortestEffortPolicy()).run()
    assert result.timeline == [("B", 0, 6), ("A", 6, 8)]


# Results on data/sample_requests.csv (SRTF traced by hand in docs/results.md).
SAMPLE_EXPECTED = {
    "arrival-order": (12.00, 6),
    "shortest-effort": (9.75, 5),
    "shortest-remaining": (7.875, 2),
    "round-robin": (13.75, 6),
    "multilevel-queue": (10.125, 4),
    "multilevel-feedback": (14.625, 6),
    "earliest-due": (8.25, 2),
}


@pytest.mark.parametrize("key", sorted(SAMPLE_EXPECTED))
def test_sample_data_results(key):
    s = summarize(WorkflowEngine(load_requests(DATA), make_policy(key)).run())
    wait, breaches = SAMPLE_EXPECTED[key]
    assert s.avg_queue_wait == pytest.approx(wait)
    assert s.sla_breaches == breaches
    assert s.utilization == pytest.approx(100.0)


@pytest.mark.parametrize("key", sorted(SAMPLE_EXPECTED))
def test_every_policy_follows_lifecycle_rules(key):
    result = WorkflowEngine(load_requests(DATA), make_policy(key)).run()
    for r in result.requests:
        trail = result.audit.for_request(r.request_id)
        assert trail[0].from_status is St.SUBMITTED
        assert trail[-1].to_status is St.COMPLETED
        assert all(e.to_status in ALLOWED_CHANGES[e.from_status] for e in trail)
        assert sum(end - start for label, start, end in result.timeline
                   if label == r.request_id) == r.effort


def test_srtf_serves_urgent_requests_faster_than_fcfs():
    results = {r.policy_name: summarize(r) for r in compare_policies(load_requests(DATA))}
    assert results["Shortest Remaining First (SRTF)"].urgent_avg_wait < \
        results["Arrival Order"].urgent_avg_wait


def test_quantum_sweep_trades_switches_for_response():
    sweep = quantum_sweep(load_requests(DATA), (1, 8))
    small, large = sweep
    assert small.context_switches > large.context_switches
    assert small.avg_first_response < large.avg_first_response


def test_aliases():
    assert isinstance(make_policy("srtf"), ShortestRemainingPolicy)
    assert make_policy("rr", 3).quantum == 3
    with pytest.raises(KeyError):
        make_policy("lottery")


def test_admission_limit_holds_requests_in_job_pool():
    result = WorkflowEngine(load_requests(DATA), ShortestRemainingPolicy(),
                            admission_limit=1).run()
    # With one slot nothing can be pre-empted: requests run in arrival order.
    assert [label for label, _, _ in result.timeline] == [f"REQ-10{i}" for i in range(1, 9)]
    admitted = result.audit.for_request("REQ-102")[0]
    assert admitted.to_status is St.QUEUED and admitted.time == 8


def test_admission_limit_must_be_positive():
    with pytest.raises(ValueError):
        WorkflowEngine(CLASSIC, ShortestEffortPolicy(), admission_limit=0)


def test_policy_reused_across_runs_gives_same_result():
    policy = RoundRobinPolicy(3)
    first = WorkflowEngine(load_requests(DATA), policy).run().timeline
    second = WorkflowEngine(load_requests(DATA), policy).run().timeline
    assert first == second
