"""Multilevel Queue (MLQ) and Multilevel Feedback Queue (MLFQ) policies.

Three queues are used throughout the project:

    level 0  Urgent      deadline alerts and critical approvals   RR, q=2
    level 1  Standard    retrievals, approvals, signatures        RR, q=4
    level 2  Background  archival and compliance audits           FCFS

A lower level number always has priority. A request arriving in a higher
queue pauses a running request from a lower queue.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..models import ContractRequest
from .base import DispatchPolicy, TimeSlice

LEVEL_NAMES = ("Urgent", "Standard", "Background")
DEFAULT_QUANTA = (2, 4, None)   # None = first-come first-served


def level_for_priority(priority: int) -> int:
    """Fixed MLQ assignment: 1 -> Urgent, 2-3 -> Standard, 4 -> Background."""
    if priority <= 1:
        return 0
    if priority <= 3:
        return 1
    return 2


class _LevelledPolicy(DispatchPolicy):
    """Shared selection logic: highest level first, FIFO within a level,
    round robin inside a level when it has a quantum."""

    allows_interruption = True

    def __init__(self, quanta: Sequence[Optional[int]] = DEFAULT_QUANTA) -> None:
        if len(quanta) != len(LEVEL_NAMES):
            raise ValueError(f"expected {len(LEVEL_NAMES)} quanta, got {len(quanta)}")
        self.quanta = tuple(quanta)
        self.slice = TimeSlice()
        self.requeue_active = False   # set when the active request must go to the tail

    def reset(self) -> None:
        self.slice = TimeSlice()
        self.requeue_active = False

    def level_of(self, request: ContractRequest) -> int:
        raise NotImplementedError

    def _select(self, queue: List[ContractRequest],
                active: Optional[ContractRequest]) -> Optional[ContractRequest]:
        expired = self.requeue_active or self.slice.expired(active, self._quantum(active))
        self.requeue_active = False

        if not queue:
            self.slice.charge(active, active, restarted=expired)
            return active

        best = min(self.level_of(r) for r in queue)
        head = next(r for r in queue if self.level_of(r) == best)

        if active is None:
            chosen = head
        else:
            mine = self.level_of(active)
            if best < mine:
                chosen = head                          # higher queue pre-empts
                self.pause_reason = "paused for a higher-priority queue"
            elif best == mine and expired:
                chosen = head                          # round robin within level
                self.pause_reason = "time quantum expired"
            else:
                chosen = active
        self.slice.charge(chosen, active, restarted=chosen is active and expired)
        return chosen

    def _quantum(self, request: Optional[ContractRequest]) -> Optional[int]:
        return None if request is None else self.quanta[self.level_of(request)]


class MultilevelQueuePolicy(_LevelledPolicy):
    """MLQ: a request stays in the queue its priority places it in."""

    name = "Multilevel Queue (MLQ)"

    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        return self._select(queue, active)

    def level_of(self, request: ContractRequest) -> int:
        return level_for_priority(request.priority)


class MultilevelFeedbackPolicy(_LevelledPolicy):
    """MLFQ: every request starts in the Urgent queue.

    * Demotion - a request that uses its whole quantum without finishing
      moves down one level (long routine work sinks to Background).
    * Aging    - a request that has waited `aging_threshold` minutes since it
      last ran moves up one level, so Background work cannot starve.
    """

    name = "Multilevel Feedback Queue (MLFQ)"

    def __init__(self, quanta: Sequence[Optional[int]] = DEFAULT_QUANTA,
                 aging_threshold: int = 12) -> None:
        super().__init__(quanta)
        self.aging_threshold = aging_threshold
        self.levels: Dict[str, int] = {}
        self.waiting_since: Dict[str, int] = {}
        self.promotions = 0
        self.demotions = 0

    def reset(self) -> None:
        super().reset()
        self.levels.clear()
        self.waiting_since.clear()
        self.promotions = self.demotions = 0

    def level_of(self, request: ContractRequest) -> int:
        return self.levels.setdefault(request.request_id, 0)

    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        if active is not None and self.slice.expired(active, self._quantum(active)):
            if self.level_of(active) < len(self.quanta) - 1:
                self.levels[active.request_id] += 1
                self.demotions += 1
            self.requeue_active = True   # go behind requests waiting at the new level

        for r in queue:
            since = self.waiting_since.setdefault(r.request_id, now)
            if now - since >= self.aging_threshold and self.level_of(r) > 0:
                self.levels[r.request_id] -= 1
                self.waiting_since[r.request_id] = now
                self.promotions += 1

        chosen = self._select(queue, active)
        if chosen is not None:
            self.waiting_since[chosen.request_id] = now + 1
        return chosen
