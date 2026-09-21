"""Domain model: contract requests and their lifecycle status."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RequestStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"


@dataclass
class ContractRequest:
    """One piece of contract work submitted to the system.

    All times are expressed in minutes from the start of the workday.
    """

    request_id: str
    contract_id: str
    request_type: str
    submitted_at: int
    effort: int          # estimated handling time
    due_at: int          # absolute time the request must be finished by
    priority: int = 3    # 1 (critical) to 4 (routine)
    remaining_effort: int = field(init=False)
    status: RequestStatus = field(default=RequestStatus.SUBMITTED, init=False)
    started_at: Optional[int] = field(default=None, init=False)
    completed_at: Optional[int] = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.effort <= 0:
            raise ValueError(f"{self.request_id}: effort must be positive")
        if self.submitted_at < 0:
            raise ValueError(f"{self.request_id}: submitted_at cannot be negative")
        if self.due_at < self.submitted_at + self.effort:
            raise ValueError(f"{self.request_id}: due date is unreachable")
        self.remaining_effort = self.effort

    @property
    def total_handling_time(self) -> Optional[int]:
        if self.completed_at is None:
            return None
        return self.completed_at - self.submitted_at

    @property
    def queue_wait(self) -> Optional[int]:
        if self.total_handling_time is None:
            return None
        return self.total_handling_time - self.effort

    @property
    def first_response_delay(self) -> Optional[int]:
        if self.started_at is None:
            return None
        return self.started_at - self.submitted_at

    @property
    def sla_breached(self) -> Optional[bool]:
        if self.completed_at is None:
            return None
        return self.completed_at > self.due_at
