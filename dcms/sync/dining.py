"""Approval desks as the Dining Philosophers problem.

N approvers sit in a ring. Between each pair of neighbours is one shared
resource; to approve, an approver needs the resource on the left (the
contract record) and the one on the right (the signature slot), just as a
philosopher needs two forks.

    naive   - take left, then right. If everyone takes their left at the same
              moment, every approver holds one resource and waits for the
              next: a circular wait, i.e. deadlock.
    ordered - always take the lower-numbered resource first (a fixed global
              lock order). The circular wait can no longer form.

Waits use a timeout so the naive run reports the deadlock instead of hanging.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DiningReport:
    strategy: str
    approvers: int
    rounds: int
    approvals: int
    timed_out: int

    @property
    def deadlocked(self) -> bool:
        return self.timed_out > 0


def run_dining(strategy: str = "ordered", approvers: int = 5, rounds: int = 3,
               hold_delay: float = 0.02, timeout: float = 0.5) -> DiningReport:
    if strategy not in ("naive", "ordered"):
        raise ValueError("strategy must be 'naive' or 'ordered'")
    resources = [threading.Lock() for _ in range(approvers)]
    start_line = threading.Barrier(approvers)
    approvals: List[int] = [0] * approvers
    timed_out: List[int] = [0] * approvers

    def approver(i: int) -> None:
        left, right = i, (i + 1) % approvers
        first, second = (left, right) if strategy == "naive" else sorted((left, right))
        start_line.wait()
        for _ in range(rounds):
            resources[first].acquire()
            time.sleep(hold_delay)              # holding one, about to ask for the other
            got = resources[second].acquire(timeout=timeout)
            if got:
                approvals[i] += 1               # critical section: record + signature slot
                resources[second].release()
            else:
                timed_out[i] += 1               # circular wait detected
            resources[first].release()
            if not got:
                return

    threads = [threading.Thread(target=approver, args=(i,), name=f"approver-{i}")
               for i in range(approvers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return DiningReport(strategy, approvers, rounds, sum(approvals), sum(timed_out))
