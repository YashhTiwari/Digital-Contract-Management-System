"""Synchronization: semaphores, mutual exclusion, bounded buffer, readers-writers, server."""

import threading
import time

import pytest

from dcms.sync.buffer import BoundedRequestQueue
from dcms.sync.dining import run_dining
from dcms.sync.mutex import Bakery, Peterson, StrictAlternation, TestAndSetLock, run_trial
from dcms.sync.primitives import BinarySemaphore, Semaphore
from dcms.sync.server import ContractServer, generate_workload
from dcms.sync.store import ContractStore, add_signature, lost_update_demo


def test_semaphore_counts_and_times_out():
    s = Semaphore(2)
    assert s.wait() and s.wait()
    assert s.wait(timeout=0.01) is False
    s.signal()
    assert s.wait(timeout=0.01)


def test_binary_semaphore_bound():
    b = BinarySemaphore()
    with pytest.raises(RuntimeError):
        b.signal()


def test_semaphore_serves_waiters_in_fifo_order():
    s = Semaphore(0)
    order = []

    def waiter(i):
        s.wait()
        order.append(i)

    threads = []
    for i in range(4):
        t = threading.Thread(target=waiter, args=(i,))
        t.start()
        threads.append(t)
        time.sleep(0.02)          # make sure they queue in order 0, 1, 2, 3
    for _ in range(4):
        s.signal()
    for t in threads:
        t.join()
    assert order == [0, 1, 2, 3]


@pytest.mark.parametrize("algorithm", [StrictAlternation, Peterson, Bakery, TestAndSetLock])
def test_correct_algorithms_keep_mutual_exclusion(algorithm):
    trial = run_trial(algorithm, threads=2, iterations=100)
    assert trial.safe, trial


def test_bakery_with_four_threads():
    assert run_trial(Bakery, threads=4, iterations=50).safe


def test_two_thread_algorithms_reject_more_threads():
    with pytest.raises(ValueError):
        Peterson(3)


def test_lost_update_happens_without_lock():
    store = ContractStore(["C"])
    both_read = threading.Barrier(2)
    threads = [threading.Thread(target=store.update_unsafe, args=("C", both_read.wait))
               for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.records["C"].signatures == 1     # two signatures, one survived


def test_locked_update_loses_nothing():
    result = lost_update_demo(signers=6, signatures_each=30, safe=True)
    assert result["lost"] == 0


def test_readers_share_writers_exclusive():
    store = ContractStore(["C"])
    threads = [threading.Thread(target=store.read, args=("C", 0.02)) for _ in range(4)]
    threads += [threading.Thread(target=store.update, args=("C", add_signature, "", 0.005))
                for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.violations == 0
    assert store.max_readers > 1
    assert store.records["C"].version == 4


def test_bounded_queue_fifo_and_capacity():
    q = BoundedRequestQueue(2)
    q.put("a")
    q.put("b")
    assert q.try_put("c") is False and q.rejected == 1
    assert q.get() == "a" and q.get() == "b"
    with pytest.raises(TimeoutError):
        q.get(timeout=0.01)


def test_producer_blocks_until_consumer_frees_a_slot():
    q = BoundedRequestQueue(1)
    q.put(1)
    done = threading.Event()
    t = threading.Thread(target=lambda: (q.put(2), done.set()))
    t.start()
    assert not done.wait(0.05)        # still blocked: queue is full
    assert q.get() == 1
    assert done.wait(1.0)
    t.join()
    assert q.get() == 2


def test_server_processes_everything_consistently():
    report = ContractServer(workers=4, queue_capacity=4, session_limit=2,
                            time_scale=0.001).run(generate_workload(30))
    assert report.processed == 30
    assert report.consistent
    assert report.max_sessions <= 2
    assert report.max_queue_length <= 4
    assert len(set(report.native_thread_ids.values())) == 4   # one kernel thread each


def test_server_rejects_when_queue_full():
    burst = generate_workload(20)
    for r in burst:
        r.submitted_at = 0
    report = ContractServer(workers=1, queue_capacity=2, time_scale=0.002,
                            reject_when_full=True).run(burst, producers=1)
    assert report.rejected > 0
    assert report.processed + report.rejected == 20
    assert report.consistent


def test_ordered_locking_never_deadlocks():
    report = run_dining("ordered", approvers=5, rounds=3)
    assert not report.deadlocked
    assert report.approvals == 15


def test_naive_locking_deadlocks():
    assert run_dining("naive", approvers=5, rounds=1, hold_delay=0.05, timeout=0.3).deadlocked
