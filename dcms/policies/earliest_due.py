"""Earliest Due First (EDF): the real-time scheduling idea from the RTOS case study."""

from __future__ import annotations

from typing import List, Optional

from ..models import ContractRequest
from .base import DispatchPolicy


class EarliestDuePolicy(DispatchPolicy):
    """Preemptive: the request with the nearest due time always runs.

    Used for the deadline-alert module, which needs a time-bound response.
    """

    name = "Earliest Due First (EDF)"
    allows_interruption = True
    pause_reason = "paused for a request due sooner"

    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        candidates = queue + ([active] if active is not None else [])
        if not candidates:
            return None
        return min(candidates, key=lambda r: (
            r.due_at, r is not active, r.submitted_at, r.request_id))
