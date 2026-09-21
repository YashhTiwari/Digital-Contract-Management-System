"""Dispatch policy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import ContractRequest


class DispatchPolicy(ABC):
    """Decides which queued request the reviewer handles next."""

    name: str = "base"
    allows_interruption: bool = False

    @abstractmethod
    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        """Return the request that should be handled now, or None if idle."""
