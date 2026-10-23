"""Dispatch policy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import ContractRequest


class DispatchPolicy(ABC):
    """Decides which queued request the reviewer handles next."""

    name: str = "base"
    allows_interruption: bool = False
    pause_reason: str = "paused for a more urgent request"

    def reset(self) -> None:
        """Clear any state kept between calls; the engine calls this before a run."""

    @abstractmethod
    def pick_next(self, queue: List[ContractRequest],
                  active: Optional[ContractRequest],
                  now: int) -> Optional[ContractRequest]:
        """Return the request that should be handled now, or None if idle."""


class TimeSlice:
    """Tracks how much of its time quantum the running request has used."""

    def __init__(self) -> None:
        self.used = 0

    def expired(self, active: Optional[ContractRequest], quantum: Optional[int]) -> bool:
        return active is not None and quantum is not None and self.used >= quantum

    def charge(self, chosen: Optional[ContractRequest],
               active: Optional[ContractRequest], restarted: bool = False) -> None:
        """Account for the minute `chosen` is about to run."""
        if chosen is None:
            self.used = 0
        elif chosen is active and not restarted:
            self.used += 1
        else:
            self.used = 1
