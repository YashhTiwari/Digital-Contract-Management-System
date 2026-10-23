"""Performance summary for a completed run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from .engine import IDLE, RunResult, WorkflowEngine
from .models import ContractRequest
from .policies import RoundRobinPolicy, make_policy


@dataclass(frozen=True)
class PerformanceSummary:
    policy: str
    avg_queue_wait: float        # waiting time
    avg_handling_time: float     # turnaround time
    avg_first_response: float    # response time
    sla_breaches: int
    total_requests: int
    utilization: float
    total_time: int
    preemptions: int = 0
    context_switches: int = 0
    urgent_avg_wait: float = 0.0  # waiting time of priority-1 requests

    @property
    def throughput(self) -> float:
        """Requests completed per 10 minutes."""
        return 10.0 * self.total_requests / self.total_time


def summarize(result: RunResult) -> PerformanceSummary:
    reqs = result.requests
    n = len(reqs)
    busy = sum(end - start for label, start, end in result.timeline if label != IDLE)
    urgent = [r.queue_wait for r in reqs if r.priority == 1]
    return PerformanceSummary(
        policy=result.policy_name,
        avg_queue_wait=sum(r.queue_wait for r in reqs) / n,
        avg_handling_time=sum(r.total_handling_time for r in reqs) / n,
        avg_first_response=sum(r.first_response_delay for r in reqs) / n,
        sla_breaches=sum(1 for r in reqs if r.sla_breached),
        total_requests=n,
        utilization=100.0 * busy / result.total_time,
        total_time=result.total_time,
        preemptions=result.preemptions,
        context_switches=result.context_switches,
        urgent_avg_wait=sum(urgent) / len(urgent) if urgent else 0.0,
    )


COMPARED_POLICIES = ("arrival-order", "shortest-effort", "shortest-remaining",
                     "round-robin", "multilevel-queue", "multilevel-feedback",
                     "earliest-due")


def compare_policies(requests: List[ContractRequest], quantum: int = 4,
                     keys: Sequence[str] = COMPARED_POLICIES,
                     admission_limit=None) -> List[RunResult]:
    """Run the same request set under every policy."""
    return [WorkflowEngine(requests, make_policy(k, quantum), admission_limit).run()
            for k in keys]


def quantum_sweep(requests: List[ContractRequest],
                  quanta: Sequence[int] = (1, 2, 3, 4, 6, 8)) -> List[PerformanceSummary]:
    """Round Robin on the same request set with several quantum values."""
    return [summarize(WorkflowEngine(requests, RoundRobinPolicy(q)).run()) for q in quanta]
