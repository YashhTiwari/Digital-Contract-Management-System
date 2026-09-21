"""Performance summary for a completed run."""

from __future__ import annotations

from dataclasses import dataclass

from .engine import IDLE, RunResult


@dataclass(frozen=True)
class PerformanceSummary:
    policy: str
    avg_queue_wait: float
    avg_handling_time: float
    avg_first_response: float
    sla_breaches: int
    total_requests: int
    utilization: float
    total_time: int


def summarize(result: RunResult) -> PerformanceSummary:
    reqs = result.requests
    n = len(reqs)
    busy = sum(end - start for label, start, end in result.timeline if label != IDLE)
    return PerformanceSummary(
        policy=result.policy_name,
        avg_queue_wait=sum(r.queue_wait for r in reqs) / n,
        avg_handling_time=sum(r.total_handling_time for r in reqs) / n,
        avg_first_response=sum(r.first_response_delay for r in reqs) / n,
        sla_breaches=sum(1 for r in reqs if r.sla_breached),
        total_requests=n,
        utilization=100.0 * busy / result.total_time,
        total_time=result.total_time,
    )
