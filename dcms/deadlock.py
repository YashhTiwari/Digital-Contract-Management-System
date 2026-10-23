"""Deadlock handling for contract resources.

* Avoidance  - Banker's Algorithm: grant a request only if the system stays
               in a safe state.
* Detection  - wait-for graph: a cycle means the requests in it are deadlocked.
* Recovery   - abort the lowest-priority request in the cycle until none is left.
* Prevention - OrderedLocks: always lock contracts in one global order, which
               removes circular wait (with a timeout, as databases such as
               MySQL/InnoDB and Oracle use for lock waits).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Vector = List[int]


def _leq(a: Sequence[int], b: Sequence[int]) -> bool:
    return all(x <= y for x, y in zip(a, b))


@dataclass
class SafetyStep:
    process: str
    work_before: Vector
    need: Vector
    work_after: Vector


@dataclass
class SafetyResult:
    safe: bool
    sequence: List[str]
    steps: List[SafetyStep]


@dataclass
class RequestResult:
    granted: bool
    reason: str
    safety: Optional[SafetyResult] = None


@dataclass
class BankersState:
    processes: List[str]
    resources: List[str]
    available: Vector
    maximum: List[Vector]
    allocation: List[Vector]

    def __post_init__(self) -> None:
        n, m = len(self.processes), len(self.resources)
        if len(self.available) != m:
            raise ValueError("available must have one entry per resource")
        for name, matrix in (("maximum", self.maximum), ("allocation", self.allocation)):
            if len(matrix) != n or any(len(row) != m for row in matrix):
                raise ValueError(f"{name} must be {n} x {m}")
        for p, alloc, mx in zip(self.processes, self.allocation, self.maximum):
            if not _leq(alloc, mx):
                raise ValueError(f"{p}: allocation exceeds its declared maximum")
        if any(v < 0 for v in self.available):
            raise ValueError("available cannot be negative")

    @classmethod
    def from_json(cls, path: str | Path) -> "BankersState":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data["processes"], data["resources"], data["available"],
                   data["maximum"], data["allocation"])

    @property
    def need(self) -> List[Vector]:
        return [[m - a for m, a in zip(mx, al)]
                for mx, al in zip(self.maximum, self.allocation)]

    def index(self, process: str) -> int:
        try:
            return self.processes.index(process)
        except ValueError:
            raise KeyError(f"unknown process: {process}") from None

    def safety(self) -> SafetyResult:
        """Safety algorithm: repeatedly find a request whose remaining need fits
        in `work`, let it finish, and reclaim its allocation."""
        work = list(self.available)
        finish = [False] * len(self.processes)
        need = self.need
        sequence: List[str] = []
        steps: List[SafetyStep] = []
        progressed = True
        while progressed:
            progressed = False
            for i, p in enumerate(self.processes):
                if not finish[i] and _leq(need[i], work):
                    before = list(work)
                    work = [w + a for w, a in zip(work, self.allocation[i])]
                    finish[i] = True
                    sequence.append(p)
                    steps.append(SafetyStep(p, before, need[i], list(work)))
                    progressed = True
        return SafetyResult(all(finish), sequence, steps)

    def request(self, process: str, vector: Sequence[int]) -> RequestResult:
        """Resource-request algorithm. The state changes only if the request is granted."""
        i = self.index(process)
        if len(vector) != len(self.resources) or any(v < 0 for v in vector):
            return RequestResult(False, "malformed request")
        if not _leq(vector, self.need[i]):
            return RequestResult(False, "request exceeds the declared maximum need")
        if not _leq(vector, self.available):
            return RequestResult(False, "not enough resources available - must wait")

        saved = (list(self.available), [list(r) for r in self.allocation])
        self.available = [a - v for a, v in zip(self.available, vector)]
        self.allocation[i] = [a + v for a, v in zip(self.allocation[i], vector)]
        result = self.safety()
        if result.safe:
            return RequestResult(True, "granted - system stays in a safe state", result)
        self.available, self.allocation = saved
        return RequestResult(False, "would leave the system unsafe - must wait", result)


@dataclass
class WaitForGraph:
    """Edge A -> B means request A waits for a contract lock held by request B."""

    edges: Dict[str, List[str]] = field(default_factory=dict)

    def add_wait(self, waiter: str, holder: str) -> None:
        self.edges.setdefault(waiter, [])
        if holder not in self.edges[waiter]:
            self.edges[waiter].append(holder)
        self.edges.setdefault(holder, [])

    @classmethod
    def from_locks(cls, holders: Dict[str, str],
                   waiting_for: Dict[str, Iterable[str]]) -> "WaitForGraph":
        """Build from lock tables: resource -> holder, request -> resources it waits on."""
        graph = cls()
        for request, resources in waiting_for.items():
            for res in resources:
                holder = holders.get(res)
                if holder is not None and holder != request:
                    graph.add_wait(request, holder)
        return graph

    def remove(self, node: str) -> None:
        self.edges.pop(node, None)
        for targets in self.edges.values():
            if node in targets:
                targets.remove(node)

    def find_cycle(self) -> Optional[List[str]]:
        """Depth-first search; returns the nodes of one cycle, or None."""
        WHITE, GREY, BLACK = 0, 1, 2
        colour = {n: WHITE for n in self.edges}
        stack: List[str] = []

        def visit(node: str) -> Optional[List[str]]:
            colour[node] = GREY
            stack.append(node)
            for nxt in self.edges.get(node, []):
                if colour.get(nxt, WHITE) == GREY:
                    return stack[stack.index(nxt):]
                if colour.get(nxt, WHITE) == WHITE:
                    found = visit(nxt)
                    if found:
                        return found
            stack.pop()
            colour[node] = BLACK
            return None

        for node in sorted(self.edges):
            if colour[node] == WHITE:
                cycle = visit(node)
                if cycle:
                    return list(cycle)
        return None


def recover(graph: WaitForGraph, priorities: Dict[str, int]) -> List[Tuple[str, List[str]]]:
    """Abort victims until the graph has no cycle.

    The victim is the lowest-priority request in the cycle (largest priority
    number; ties broken by id). Returns (victim, cycle it broke) pairs.
    """
    victims = []
    while (cycle := graph.find_cycle()) is not None:
        victim = max(cycle, key=lambda r: (priorities.get(r, 4), r))
        graph.remove(victim)
        victims.append((victim, cycle))
    return victims


class OrderedLocks:
    """Locks contracts in sorted id order so no circular wait can form."""

    def __init__(self, contract_ids: Iterable[str]) -> None:
        self._locks = {c: threading.Lock() for c in contract_ids}

    def acquire(self, *contract_ids: str, timeout: float = -1) -> List[str]:
        """Acquire every lock or none. Returns the ids locked, in order."""
        taken: List[str] = []
        for c in sorted(set(contract_ids)):
            if not self._locks[c].acquire(timeout=timeout):
                self.release(*taken)
                raise TimeoutError(f"lock wait timeout on {c}")
            taken.append(c)
        return taken

    def release(self, *contract_ids: str) -> None:
        for c in sorted(set(contract_ids), reverse=True):
            self._locks[c].release()
