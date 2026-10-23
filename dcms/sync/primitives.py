"""Semaphores built as monitors.

`Semaphore` is written on top of a condition variable (a monitor: one lock
plus a wait queue), which is how wait()/signal() are implemented in practice.
The project uses its own class instead of `threading.Semaphore` so the P/V
operations are visible and can be instrumented.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Optional


class Semaphore:
    """Counting semaphore with a FIFO wait queue (a "strong" semaphore).

    wait()   (P / down): block while the value is 0, then decrement.
    signal() (V / up)  : increment and wake waiting threads.

    Waiters are served strictly in arrival order, and a thread that arrives
    while others are queued must queue too. This gives bounded waiting: a busy
    thread cannot keep re-taking the semaphore ahead of threads already asleep.
    """

    def __init__(self, value: int = 0, bound: Optional[int] = None) -> None:
        if value < 0:
            raise ValueError("semaphore value cannot be negative")
        if bound is not None and value > bound:
            raise ValueError("initial value exceeds bound")
        self._value = value
        self._bound = bound
        self._monitor = threading.Condition()
        self._waiting: Deque[object] = deque()
        self.blocked_waits = 0   # how often a caller had to sleep

    @property
    def value(self) -> int:
        return self._value

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Return False if the timeout expired before the semaphore was acquired."""
        with self._monitor:
            if self._value > 0 and not self._waiting:
                self._value -= 1
                return True
            if timeout == 0:
                return False
            self.blocked_waits += 1
            ticket = object()
            self._waiting.append(ticket)
            if not self._monitor.wait_for(
                    lambda: self._value > 0 and self._waiting[0] is ticket, timeout):
                self._waiting.remove(ticket)
                self._monitor.notify_all()   # the next in line may now be at the head
                return False
            self._waiting.popleft()
            self._value -= 1
            self._monitor.notify_all()
            return True

    def signal(self) -> None:
        with self._monitor:
            if self._bound is not None and self._value >= self._bound:
                raise RuntimeError("semaphore signalled beyond its bound")
            self._value += 1
            self._monitor.notify_all()

    def __enter__(self) -> "Semaphore":
        self.wait()
        return self

    def __exit__(self, *exc) -> None:
        self.signal()


class BinarySemaphore(Semaphore):
    """Semaphore whose value is only ever 0 or 1 (a mutex lock)."""

    def __init__(self, value: int = 1) -> None:
        super().__init__(value, bound=1)
