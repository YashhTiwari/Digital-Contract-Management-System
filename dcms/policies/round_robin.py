"""Round Robin: each request gets a fixed time quantum in turn."""

from __future__ import annotations

from typing import List, Optional

from ..models import ContractRequest
from .base import DispatchPolicy, TimeSlice


class RoundRobinPolicy(DispatchPolicy):
    """Requests are served from the head of a FIFO queue for at most `quantum`
    minutes; an unfinished request then goes to the back of the queue.

    The engine adds requests that arrive in the same minute a quantum expires
    to the queue before the paused request, as in the usual textbook convention.
    """

    allows_interruption = True
    pause_reason = "time quantum expired"

    def __init__(self, quantum: int = 4) -> None:
        if quantum < 1:
            raise ValueError("quantum must be at least 1")
        self.quantum = quantum
        self.name = f"Round Robin (q={quantum})"
        self.slice = TimeSlice()

    def reset(self) -> None:
        self.slice = TimeSlice()

    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        restarted = False
        if active is not None and not self.slice.expired(active, self.quantum):
            chosen = active
        elif queue:
            chosen = queue[0]
        else:
            chosen, restarted = active, True   # nobody else waiting: start a new quantum
        self.slice.charge(chosen, active, restarted)
        return chosen
