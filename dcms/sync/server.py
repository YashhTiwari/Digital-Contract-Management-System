"""Multithreaded contract server.

Puts the Unit 3 pieces together in one process:

    intake threads  --put-->  BoundedRequestQueue  --get-->  worker threads
     (producers)              (semaphores, mutex)            (consumers)
                                                                 |
                                         session limit (counting semaphore)
                                                                 |
                                       ContractStore (readers-writers rule)

Every request is handled by a kernel-level worker thread inside the single
server process (one-to-one model). The report checks that no update was lost
and that the session limit and readers-writers rule were never broken.
"""

from __future__ import annotations

import os
import random
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..models import ContractRequest
from .buffer import BoundedRequestQueue
from .primitives import Semaphore
from .store import ContractStore, add_signature

WRITE_TYPES = {"Approval Workflow", "Signature Verification", "Archive Request"}
REQUEST_TYPES = ["Contract Retrieval", "Approval Workflow", "Deadline Alert",
                 "Signature Verification", "Archive Request", "Compliance Audit"]


def is_write(request: ContractRequest) -> bool:
    return request.request_type in WRITE_TYPES


def generate_workload(count: int = 40, contracts: int = 4, seed: int = 7) -> List[ContractRequest]:
    """Many requests on few contracts, so threads really contend for records."""
    rng = random.Random(seed)
    requests, clock = [], 0
    for i in range(count):
        clock += rng.randint(0, 2)
        effort = rng.randint(1, 6)
        requests.append(ContractRequest(
            request_id=f"REQ-{201 + i}",
            contract_id=f"CON-2026-{rng.randint(1, contracts):03d}",
            request_type=rng.choice(REQUEST_TYPES),
            submitted_at=clock, effort=effort,
            due_at=clock + effort + rng.randint(2, 20),
            priority=rng.randint(1, 4)))
    return requests


@dataclass
class ServerReport:
    pid: int
    logical_cpus: int
    workers: int
    submitted: int
    processed: int
    rejected: int
    per_worker: Dict[str, int]
    native_thread_ids: Dict[str, int]
    session_limit: int
    max_sessions: int
    queue_capacity: int
    max_queue_length: int
    consumer_sleeps: int
    producer_waits: int
    max_concurrent_readers: int
    rule_violations: int
    expected_versions: Dict[str, int]
    actual_versions: Dict[str, int]
    seconds: float
    log: List[str] = field(default_factory=list)

    @property
    def consistent(self) -> bool:
        return self.expected_versions == self.actual_versions and self.rule_violations == 0


class ContractServer:

    def __init__(self, workers: int = 4, queue_capacity: int = 5, session_limit: int = 3,
                 time_scale: float = 0.002, reject_when_full: bool = False) -> None:
        self.workers = workers
        self.queue_capacity = queue_capacity
        self.session_limit = session_limit
        self.time_scale = time_scale
        self.reject_when_full = reject_when_full

    def run(self, requests: List[ContractRequest], producers: int = 2) -> ServerReport:
        queue: BoundedRequestQueue[Optional[ContractRequest]] = BoundedRequestQueue(
            self.queue_capacity)
        sessions = Semaphore(self.session_limit, bound=self.session_limit)
        store = ContractStore(sorted({r.contract_id for r in requests}))
        handled: Counter = Counter()
        native_ids: Dict[str, int] = {}
        accepted: List[ContractRequest] = []
        log: List[str] = []
        guard = threading.Lock()
        active_sessions = [0]
        max_sessions = [0]
        start = time.perf_counter()

        def stamp() -> str:
            return f"{(time.perf_counter() - start) * 1000:7.1f} ms"

        def intake(batch: List[ContractRequest]) -> None:
            for req in batch:
                delay = req.submitted_at * self.time_scale - (time.perf_counter() - start)
                if delay > 0:
                    time.sleep(delay)
                if self.reject_when_full:
                    ok = queue.try_put(req)
                else:
                    queue.put(req)
                    ok = True
                with guard:
                    if ok:
                        accepted.append(req)
                    log.append(f"{stamp()}  {threading.current_thread().name:<9} "
                               f"{'queued' if ok else 'REJECTED (queue full)'} {req.request_id}")

        def worker() -> None:
            name = threading.current_thread().name
            native_ids[name] = threading.get_native_id()
            while True:
                req = queue.get()
                if req is None:               # shutdown signal
                    return
                sessions.wait()
                with guard:
                    active_sessions[0] += 1
                    max_sessions[0] = max(max_sessions[0], active_sessions[0])
                work = req.effort * self.time_scale
                if is_write(req):
                    store.update(req.contract_id, add_signature,
                                 f"{req.request_id} {req.request_type}", work)
                    action = "edited"
                else:
                    store.read(req.contract_id, work)
                    action = "read"
                with guard:
                    active_sessions[0] -= 1
                    handled[name] += 1
                    log.append(f"{stamp()}  {name:<9} {action:<6} {req.contract_id} "
                               f"for {req.request_id} ({req.request_type})")
                sessions.signal()

        ordered = sorted(requests, key=lambda r: (r.submitted_at, r.request_id))
        batches = [ordered[i::producers] for i in range(producers)]
        intake_threads = [threading.Thread(target=intake, args=(b,), name=f"intake-{i}")
                          for i, b in enumerate(batches)]
        worker_threads = [threading.Thread(target=worker, name=f"worker-{i}")
                          for i in range(self.workers)]
        for t in worker_threads + intake_threads:
            t.start()
        for t in intake_threads:
            t.join()
        for _ in worker_threads:
            queue.put(None)
        for t in worker_threads:
            t.join()

        expected = Counter(r.contract_id for r in accepted if is_write(r))
        return ServerReport(
            pid=os.getpid(),
            logical_cpus=os.cpu_count() or 1,
            workers=self.workers,
            submitted=len(requests),
            processed=sum(handled.values()),
            rejected=queue.rejected,
            per_worker=dict(sorted(handled.items())),
            native_thread_ids=dict(sorted(native_ids.items())),
            session_limit=self.session_limit,
            max_sessions=max_sessions[0],
            queue_capacity=self.queue_capacity,
            max_queue_length=queue.max_seen,
            consumer_sleeps=queue.consumer_sleeps,
            producer_waits=queue.producer_waits,
            max_concurrent_readers=store.max_readers,
            rule_violations=store.violations,
            expected_versions={c: expected.get(c, 0) for c in store.records},
            actual_versions={c: rec.version for c, rec in store.records.items()},
            seconds=time.perf_counter() - start,
            log=log,
        )
