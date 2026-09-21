"""Arrival-order policy: requests are handled in the order they were submitted."""

from __future__ import annotations

from typing import List, Optional

from ..models import ContractRequest
from .base import DispatchPolicy


class ArrivalOrderPolicy(DispatchPolicy):
    name = "Arrival Order"
    allows_interruption = False

    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        if active is not None:
            return active
        if not queue:
            return None
        return min(queue, key=lambda r: (r.submitted_at, r.request_id))
