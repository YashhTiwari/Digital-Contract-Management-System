from pathlib import Path
import threading

import pytest

from dcms.deadlock import BankersState, OrderedLocks, WaitForGraph, recover

STATE = Path(__file__).resolve().parent.parent / "data" / "bankers_state.json"


def load():
    return BankersState.from_json(STATE)


def test_need_matrix():
    assert load().need == [[7, 4, 3], [1, 2, 2], [6, 0, 0], [0, 1, 1], [4, 3, 1]]


def test_initial_state_is_safe():
    result = load().safety()
    assert result.safe
    assert result.sequence == ["REQ-102", "REQ-104", "REQ-105", "REQ-101", "REQ-103"]


def test_request_that_keeps_state_safe_is_granted():
    state = load()
    r = state.request("REQ-102", [1, 0, 2])
    assert r.granted
    assert state.available == [2, 3, 0]
    assert state.allocation[1] == [3, 0, 2]


def test_request_beyond_available_must_wait():
    state = load()
    state.request("REQ-102", [1, 0, 2])
    r = state.request("REQ-105", [3, 3, 0])
    assert not r.granted and "available" in r.reason
    assert state.available == [2, 3, 0]


def test_unsafe_request_is_rolled_back():
    state = load()
    state.request("REQ-102", [1, 0, 2])
    r = state.request("REQ-101", [0, 2, 0])
    assert not r.granted and "unsafe" in r.reason
    assert state.available == [2, 3, 0]
    assert state.allocation[0] == [0, 1, 0]


def test_request_above_declared_need_is_an_error():
    r = load().request("REQ-104", [1, 0, 0])
    assert not r.granted and "maximum" in r.reason


def test_unsafe_state_detected():
    state = BankersState(["A", "B"], ["R"], [1], [[4], [4]], [[2], [2]])
    assert not state.safety().safe


def test_invalid_state_rejected():
    with pytest.raises(ValueError):
        BankersState(["A"], ["R"], [1], [[1]], [[2]])     # allocation above maximum


def test_wait_for_graph_cycle_and_recovery():
    graph = WaitForGraph.from_locks(
        holders={"C1": "R1", "C2": "R2", "C3": "R3"},
        waiting_for={"R1": ["C2"], "R2": ["C3"], "R3": ["C1"], "R4": ["C1"]})
    cycle = graph.find_cycle()
    assert set(cycle) == {"R1", "R2", "R3"}
    victims = recover(graph, {"R1": 1, "R2": 2, "R3": 4, "R4": 3})
    assert [v for v, _ in victims] == ["R3"]          # lowest priority in the cycle
    assert graph.find_cycle() is None


def test_no_cycle():
    graph = WaitForGraph()
    graph.add_wait("A", "B")
    graph.add_wait("B", "C")
    assert graph.find_cycle() is None


def test_two_separate_cycles_need_two_victims():
    graph = WaitForGraph()
    for a, b in [("A", "B"), ("B", "A"), ("C", "D"), ("D", "C")]:
        graph.add_wait(a, b)
    assert len(recover(graph, {})) == 2


def test_ordered_locks_prevent_deadlock():
    locks = OrderedLocks(["C1", "C2"])
    finished = []

    def worker(name, first, second):
        for _ in range(300):
            taken = locks.acquire(first, second, timeout=2)
            locks.release(*taken)
        finished.append(name)

    threads = [threading.Thread(target=worker, args=("a", "C1", "C2")),
               threading.Thread(target=worker, args=("b", "C2", "C1"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert sorted(finished) == ["a", "b"]


def test_ordered_locks_timeout_releases_partial_locks():
    locks = OrderedLocks(["C1", "C2"])
    locks.acquire("C2")
    with pytest.raises(TimeoutError):
        locks.acquire("C1", "C2", timeout=0.05)
    assert locks.acquire("C1", timeout=0.05) == ["C1"]   # C1 was released again
