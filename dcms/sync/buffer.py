"""Bounded request queue: the producer-consumer (bounded buffer) problem.

Intake threads (producers) put requests in; scheduler workers (consumers)
take them out. Three semaphores coordinate them:

    free_slots  counting, starts at capacity - producers wait when the queue is full
    filled      counting, starts at 0        - consumers sleep when the queue is empty
    mutex       binary                       - one thread touches the deque at a time

A consumer sleeping on an empty queue is the "sleeping barber"; try_put()
gives the barber-shop variant where a customer leaves if every chair is taken.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Generic, Optional, TypeVar

from .primitives import BinarySemaphore, Semaphore

T = TypeVar("T")


class BoundedRequestQueue(Generic[T]):

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._items: Deque[T] = deque()
        self.free_slots = Semaphore(capacity, bound=capacity)
        self.filled = Semaphore(0, bound=capacity)
        self.mutex = BinarySemaphore()
        self.max_seen = 0
        self.rejected = 0

    def put(self, item: T) -> None:
        self.free_slots.wait()
        self._insert(item)

    def try_put(self, item: T) -> bool:
        """Put without waiting; returns False (and counts a rejection) if full."""
        if not self.free_slots.wait(timeout=0):
            self.rejected += 1
            return False
        self._insert(item)
        return True

    def get(self, timeout: Optional[float] = None) -> T:
        if not self.filled.wait(timeout):
            raise TimeoutError("no request arrived in time")
        with self.mutex:
            item = self._items.popleft()
        self.free_slots.signal()
        return item

    def _insert(self, item: T) -> None:
        with self.mutex:
            self._items.append(item)
            self.max_seen = max(self.max_seen, len(self._items))
        self.filled.signal()

    def __len__(self) -> int:
        return len(self._items)

    @property
    def producer_waits(self) -> int:
        return self.free_slots.blocked_waits

    @property
    def consumer_sleeps(self) -> int:
        return self.filled.blocked_waits
