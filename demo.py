"""Concurrency and deadlock demonstrations (Unit 3).

    python demo.py race        lost update without a lock, fixed with one
    python demo.py mutex       lock variable vs strict alternation, Peterson, Bakery, TSL
    python demo.py buffer      producer-consumer on a bounded request queue
    python demo.py server      full multithreaded server (semaphores + readers-writers)
    python demo.py dining      approval desks: naive vs ordered locking
    python demo.py bankers     Banker's Algorithm safety check and requests
    python demo.py detect      wait-for graph deadlock detection and recovery
    python demo.py all         everything above
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

from dcms.deadlock import BankersState, OrderedLocks, WaitForGraph, recover
from dcms.sync.buffer import BoundedRequestQueue
from dcms.sync.dining import run_dining
from dcms.sync.mutex import ALGORITHMS, run_trial, run_without_lock
from dcms.sync.server import ContractServer, generate_workload
from dcms.sync.store import lost_update_demo


def heading(text: str) -> None:
    print(f"\n=== {text} ===\n")


def demo_race(args) -> None:
    heading("Race condition: several signers update one contract")
    unsafe = lost_update_demo(args.threads, 50, safe=False)
    safe = lost_update_demo(args.threads, 50, safe=True)
    print(f"{'':<28}{'Expected':>9}{'Actual':>8}{'Lost':>6}")
    print(f"{'No lock':<28}{unsafe['expected']:>9}{unsafe['actual']:>8}{unsafe['lost']:>6}")
    print(f"{'Readers-writers lock':<28}{safe['expected']:>9}{safe['actual']:>8}{safe['lost']:>6}")
    print("\nEach signer reads the signature count, pauses (e.g. disk write), then"
          "\nwrites count+1. Without mutual exclusion, signers overwrite each other.")


def demo_mutex(args) -> None:
    heading("Mutual exclusion algorithms on one contract record (2 threads)")
    print(f"{'Algorithm':<26}{'Expected':>9}{'Actual':>8}{'Lost':>6}{'Overlaps':>10}"
          f"{'Time (s)':>10}  Result")
    trials = [run_without_lock(2, args.iterations)]
    trials += [run_trial(cls, 2, args.iterations) for cls in ALGORITHMS]
    for t in trials:
        print(f"{t.algorithm:<26}{t.expected:>9}{t.actual:>8}{t.lost_updates:>6}"
              f"{t.violations:>10}{t.seconds:>10.3f}  {'safe' if t.safe else 'UNSAFE'}")
    bakery = run_trial(ALGORITHMS[3], 4, args.iterations // 2)
    print(f"\nBakery with 4 threads: {bakery.actual}/{bakery.expected}, "
          f"{bakery.violations} overlaps -> {'safe' if bakery.safe else 'UNSAFE'}")
    print("\nStrict alternation is safe here only because both threads want the record"
          "\nequally often; if one stops, the other blocks forever (no progress).")


def demo_buffer(args) -> None:
    heading("Producer-consumer: bounded request queue (capacity 3)")
    queue: BoundedRequestQueue[str] = BoundedRequestQueue(3)
    log, lock = [], threading.Lock()
    start = time.perf_counter()

    def note(msg: str) -> None:
        with lock:
            log.append(f"{(time.perf_counter() - start) * 1000:6.1f} ms  {msg}")

    def producer() -> None:
        for i in range(8):
            queue.put(f"REQ-{101 + i}")
            note(f"intake   put REQ-{101 + i}   (queue length {len(queue)})")

    def consumer() -> None:
        for _ in range(8):
            time.sleep(0.01)            # slower than intake, so the queue fills up
            item = queue.get()
            note(f"worker   got {item}")

    threads = [threading.Thread(target=producer), threading.Thread(target=consumer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("\n".join(log))
    print(f"\nLongest queue: {queue.max_seen} (capacity {queue.capacity}); "
          f"producer blocked {queue.producer_waits} times on a full queue.")


def demo_server(args) -> None:
    heading("Multithreaded contract server")
    requests = generate_workload(args.requests, contracts=4)
    report = ContractServer(workers=args.workers, queue_capacity=5,
                            session_limit=3).run(requests)
    if args.verbose:
        print("\n".join(report.log) + "\n")
    print(f"Server process PID         : {report.pid} (one process, many threads)")
    print(f"Logical CPUs               : {report.logical_cpus} (hyper-threads included)")
    print(f"Worker kernel thread ids   : {report.native_thread_ids}")
    print(f"Requests processed         : {report.processed} / {report.submitted}")
    print(f"Handled per worker         : {report.per_worker}")
    print(f"Concurrent sessions (max)  : {report.max_sessions} (limit {report.session_limit})")
    print(f"Queue length (max)         : {report.max_queue_length} (capacity {report.queue_capacity})")
    print(f"Workers slept on empty queue: {report.consumer_sleeps}")
    print(f"Intake blocked on full queue: {report.producer_waits}")
    print(f"Concurrent readers (max)   : {report.max_concurrent_readers}")
    print(f"Readers-writers violations : {report.rule_violations}")
    print(f"Contract versions expected : {report.expected_versions}")
    print(f"Contract versions actual   : {report.actual_versions}")
    print(f"Consistent                 : {'yes' if report.consistent else 'NO'}")
    print(f"Elapsed                    : {report.seconds:.2f} s")


def demo_dining(args) -> None:
    heading("Approval desks (Dining Philosophers), 5 approvers")
    for strategy in ("naive", "ordered"):
        r = run_dining(strategy)
        verdict = "DEADLOCK (circular wait, detected by timeout)" if r.deadlocked else "no deadlock"
        print(f"{strategy:<8} approvals {r.approvals:>2}/{r.approvers * r.rounds}  "
              f"timed-out waits {r.timed_out}  -> {verdict}")
    print("\nOrdered: every approver locks the lower-numbered resource first,"
          "\nwhich breaks the circular-wait condition.")


def demo_bankers(args) -> None:
    heading("Banker's Algorithm")
    state = BankersState.from_json(args.bankers)
    res = state.resources
    print("Resources:", ", ".join(f"{r}" for r in res))
    print(f"Available: {state.available}\n")
    print(f"{'Request':<9}{'Allocation':<14}{'Max':<14}{'Need':<14}")
    for p, a, m, n in zip(state.processes, state.allocation, state.maximum, state.need):
        print(f"{p:<9}{str(a):<14}{str(m):<14}{str(n):<14}")
    result = state.safety()
    print(f"\nSafety check: {'SAFE' if result.safe else 'UNSAFE'}")
    for s in result.steps:
        print(f"  {s.process}: need {s.need} <= work {s.work_before} -> work {s.work_after}")
    print("  Safe sequence: <" + ", ".join(result.sequence) + ">")

    for process, vector in (("REQ-102", [1, 0, 2]), ("REQ-105", [3, 3, 0]),
                            ("REQ-101", [0, 2, 0])):
        r = state.request(process, vector)
        extra = f"  sequence <{', '.join(r.safety.sequence)}>" if r.granted else ""
        print(f"\n{process} requests {vector}: {r.reason}{extra}")
        print(f"  available now {state.available}")


def demo_detect(args) -> None:
    heading("Deadlock detection and recovery (wait-for graph)")
    holders = {"CON-001": "REQ-101", "CON-002": "REQ-102", "CON-003": "REQ-103",
               "CON-004": "REQ-104"}
    waiting = {"REQ-101": ["CON-002"], "REQ-102": ["CON-003"],
               "REQ-103": ["CON-001"], "REQ-104": ["CON-001"]}
    priorities = {"REQ-101": 2, "REQ-102": 1, "REQ-103": 4, "REQ-104": 3}
    print("Lock table (contract -> holder):", holders)
    print("Waiting (request -> contracts) :", waiting)
    graph = WaitForGraph.from_locks(holders, waiting)
    print("Wait-for edges:", {k: v for k, v in graph.edges.items() if v})
    cycle = graph.find_cycle()
    print("Cycle found   :", " -> ".join(cycle + [cycle[0]]) if cycle else "none")
    for victim, broken in recover(graph, priorities):
        print(f"Recovery      : abort {victim} (priority {priorities[victim]}, lowest in cycle)"
              f" and release its locks")
    print("After recovery:", "no cycle" if graph.find_cycle() is None else "still deadlocked")

    heading("Prevention: fixed lock order with lock-wait timeout")
    locks = OrderedLocks(["CON-001", "CON-002"])
    done = []

    def transfer(name: str, first: str, second: str) -> None:
        for _ in range(200):
            taken = locks.acquire(first, second, timeout=1.0)
            locks.release(*taken)
        done.append(name)

    a = threading.Thread(target=transfer, args=("A", "CON-001", "CON-002"))
    b = threading.Thread(target=transfer, args=("B", "CON-002", "CON-001"))
    a.start(); b.start(); a.join(); b.join()
    print("Two requests asked for the same two contracts in opposite orders;"
          f"\nboth locked them in sorted order and finished: {sorted(done)}")


DEMOS = {"race": demo_race, "mutex": demo_mutex, "buffer": demo_buffer,
         "server": demo_server, "dining": demo_dining, "bankers": demo_bankers,
         "detect": demo_detect}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("demo", choices=list(DEMOS) + ["all"])
    parser.add_argument("--threads", type=int, default=8, help="signer threads for 'race'")
    parser.add_argument("--iterations", type=int, default=200, help="updates per thread for 'mutex'")
    parser.add_argument("--workers", type=int, default=4, help="worker threads for 'server'")
    parser.add_argument("--requests", type=int, default=40, help="generated requests for 'server'")
    parser.add_argument("--bankers", default="data/bankers_state.json",
                        help="Banker's state file for 'bankers'")
    parser.add_argument("--verbose", action="store_true", help="print the server event log")
    args = parser.parse_args(argv)
    try:
        for name in (DEMOS if args.demo == "all" else [args.demo]):
            DEMOS[name](args)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
