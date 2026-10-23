"""Shortest-effort policies (SJF and SRTF).

Both rank requests by *estimated* effort, because real handling time is not
known until a request finishes. See dcms/estimation.py for how estimates are
derived from request history.
"""

from __future__ import annotations

from typing import List, Optional

from ..models import ContractRequest
from .base import DispatchPolicy


class ShortestEffortPolicy(DispatchPolicy):
    """Shortest Job First: non-preemptive, picks the smallest estimated effort."""

    name = "Shortest Effort First (SJF)"
    allows_interruption = False

    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        if active is not None:
            return active
        if not queue:
            return None
        return min(queue, key=lambda r: (r.estimated_effort, r.submitted_at, r.request_id))


class ShortestRemainingPolicy(DispatchPolicy):
    """Shortest Remaining Time First: preemptive SJF.

    A newly queued request with less remaining effort pauses the active one,
    so short urgent work (deadline alerts) is not stuck behind long routine work.
    On a tie the active request keeps running to avoid a needless switch.
    """

    name = "Shortest Remaining First (SRTF)"
    allows_interruption = True
    pause_reason = "paused for a shorter request"

    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        candidates = queue + ([active] if active is not None else [])
        if not candidates:
            return None
        return min(candidates, key=lambda r: (
            r.estimated_remaining, r is not active, r.submitted_at, r.request_id))
