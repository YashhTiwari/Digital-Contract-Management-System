"""Software and hardware mutual-exclusion algorithms, compared on one contract record.

Each lock protects the critical section "update the contract record". The
trial runner checks two things:

* violations - times two threads were inside the critical section together;
* lost updates - expected minus actual final counter value.

Spinning threads call time.sleep(0) to yield the CPU (like a `pause`/yield
instruction); otherwise a busy-waiting Python thread holds the interpreter for
a whole switch interval and the trials become very slow.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, List


def _yield() -> None:
    time.sleep(0)


class LockVariable:
    """Single shared flag, checked then set. BROKEN: the check and the set are
    two separate steps, so two threads can both see the flag free."""

    name = "Lock variable"
    correct = False

    def __init__(self, n: int = 2) -> None:
        self.locked = False

    def acquire(self, i: int) -> None:
        while self.locked:
            _yield()
        _yield()               # the gap between "test" and "set"
        self.locked = True

    def release(self, i: int) -> None:
        self.locked = False


class StrictAlternation:
    """Two threads take turns. Mutual exclusion holds, but progress does not:
    a thread cannot enter twice in a row even if the other is not interested."""

    name = "Strict alternation"
    correct = True

    def __init__(self, n: int = 2) -> None:
        if n != 2:
            raise ValueError("strict alternation works for exactly two threads")
        self.turn = 0

    def acquire(self, i: int) -> None:
        while self.turn != i:
            _yield()

    def release(self, i: int) -> None:
        self.turn = 1 - i


class Peterson:
    """Peterson's solution for two threads: interest flags plus a turn variable.
    Satisfies mutual exclusion, progress and bounded waiting."""

    name = "Peterson's solution"
    correct = True

    def __init__(self, n: int = 2) -> None:
        if n != 2:
            raise ValueError("Peterson's solution is for exactly two threads")
        self.flag = [False, False]
        self.turn = 0

    def acquire(self, i: int) -> None:
        j = 1 - i
        self.flag[i] = True
        self.turn = j
        while self.flag[j] and self.turn == j:
            _yield()

    def release(self, i: int) -> None:
        self.flag[i] = False


class Bakery:
    """Lamport's bakery algorithm for n threads: take a ticket, lowest
    (ticket, thread id) enters first."""

    name = "Bakery algorithm"
    correct = True

    def __init__(self, n: int = 2) -> None:
        self.n = n
        self.choosing = [False] * n
        self.number = [0] * n

    def acquire(self, i: int) -> None:
        self.choosing[i] = True
        self.number[i] = 1 + max(self.number)
        self.choosing[i] = False
        for j in range(self.n):
            while self.choosing[j]:
                _yield()
            while self.number[j] != 0 and (self.number[j], j) < (self.number[i], i):
                _yield()

    def release(self, i: int) -> None:
        self.number[i] = 0


class TestAndSetLock:
    """Spin lock built on an atomic Test-and-Set instruction.

    Python has no TSL instruction, so atomicity is emulated with a private
    lock standing in for the hardware's locked memory bus.
    """

    name = "Test-and-Set"
    correct = True
    __test__ = False   # not a pytest test class despite the name

    def __init__(self, n: int = 2) -> None:
        self.flag = False
        self._bus = threading.Lock()

    def test_and_set(self) -> bool:
        with self._bus:
            old, self.flag = self.flag, True
            return old

    def acquire(self, i: int = 0) -> None:
        while self.test_and_set():
            _yield()

    def release(self, i: int = 0) -> None:
        self.flag = False


ALGORITHMS = [LockVariable, StrictAlternation, Peterson, Bakery, TestAndSetLock]


@dataclass(frozen=True)
class MutexTrial:
    algorithm: str
    threads: int
    expected: int
    actual: int
    violations: int
    seconds: float

    @property
    def lost_updates(self) -> int:
        return self.expected - self.actual

    @property
    def safe(self) -> bool:
        return self.violations == 0 and self.lost_updates == 0


def run_trial(factory: Callable[[int], object], threads: int = 2,
              iterations: int = 200) -> MutexTrial:
    """Each thread adds `iterations` approvals to one shared contract record."""
    lock = factory(threads)
    record = {"approvals": 0}
    inside = [0]
    violations = [0]
    probe = threading.Lock()   # measurement only, not part of the algorithm

    def worker(i: int) -> None:
        for _ in range(iterations):
            lock.acquire(i)
            with probe:
                inside[0] += 1
                if inside[0] > 1:
                    violations[0] += 1
            current = record["approvals"]
            _yield()                       # e.g. writing to disk mid-update
            record["approvals"] = current + 1
            with probe:
                inside[0] -= 1
            lock.release(i)

    workers: List[threading.Thread] = [
        threading.Thread(target=worker, args=(i,), name=f"approver-{i}") for i in range(threads)]
    start = time.perf_counter()
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    return MutexTrial(lock.name, threads, threads * iterations, record["approvals"],
                      violations[0], time.perf_counter() - start)


def run_without_lock(threads: int = 2, iterations: int = 200) -> MutexTrial:
    class NoLock:
        name = "No lock (race condition)"

        def __init__(self, n: int) -> None:
            pass

        def acquire(self, i: int) -> None:
            pass

        def release(self, i: int) -> None:
            pass

    return run_trial(NoLock, threads, iterations)
