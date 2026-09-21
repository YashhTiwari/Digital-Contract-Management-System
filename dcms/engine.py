"""Workflow engine: processes a queue of contract requests minute by minute."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .lifecycle import AuditTrail, change_status
from .models import ContractRequest, RequestStatus as St
from .policies.base import DispatchPolicy

IDLE = "Idle"
TimelineSegment = Tuple[str, int, int]


@dataclass
class RunResult:
    policy_name: str
    requests: List[ContractRequest]
    timeline: List[TimelineSegment]
    audit: AuditTrail
    total_time: int


class WorkflowEngine:
    """Runs a set of requests under a dispatch policy, advancing one minute at a time."""

    def __init__(self, requests: List[ContractRequest], policy: DispatchPolicy) -> None:
        self.requests = copy.deepcopy(requests)
        self.policy = policy
        self.audit = AuditTrail()

    def run(self) -> RunResult:
        clock = 0
        active: Optional[ContractRequest] = None
        incoming = sorted(self.requests, key=lambda r: (r.submitted_at, r.request_id))
        queue: List[ContractRequest] = []
        timeline: List[TimelineSegment] = []
        finished, total = 0, len(self.requests)

        while finished < total:
            while incoming and incoming[0].submitted_at <= clock:
                req = incoming.pop(0)
                change_status(req, St.QUEUED, clock, self.audit, "request accepted")
                queue.append(req)

            chosen = self.policy.pick_next(queue, active, clock)

            if chosen is not active:
                if active is not None:
                    change_status(active, St.QUEUED, clock, self.audit,
                                  "paused for a more urgent request")
                    queue.append(active)
                if chosen is not None:
                    queue.remove(chosen)
                    change_status(chosen, St.IN_PROGRESS, clock, self.audit, "handling started")
                    if chosen.started_at is None:
                        chosen.started_at = clock
                active = chosen

            self._record(timeline, active.request_id if active else IDLE, clock)
            clock += 1

            if active is not None:
                active.remaining_effort -= 1
                if active.remaining_effort == 0:
                    active.completed_at = clock
                    change_status(active, St.COMPLETED, clock, self.audit, "request completed")
                    active = None
                    finished += 1

        return RunResult(
            policy_name=self.policy.name,
            requests=sorted(self.requests, key=lambda r: r.request_id),
            timeline=timeline,
            audit=self.audit,
            total_time=clock,
        )

    @staticmethod
    def _record(timeline: List[TimelineSegment], label: str, clock: int) -> None:
        if timeline and timeline[-1][0] == label and timeline[-1][2] == clock:
            timeline[-1] = (label, timeline[-1][1], clock + 1)
        else:
            timeline.append((label, clock, clock + 1))
