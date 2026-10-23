from .base import DispatchPolicy
from .arrival_order import ArrivalOrderPolicy
from .earliest_due import EarliestDuePolicy
from .multilevel import MultilevelFeedbackPolicy, MultilevelQueuePolicy
from .round_robin import RoundRobinPolicy
from .shortest_effort import ShortestEffortPolicy, ShortestRemainingPolicy

POLICIES = {
    "arrival-order": ArrivalOrderPolicy,
    "shortest-effort": ShortestEffortPolicy,
    "shortest-remaining": ShortestRemainingPolicy,
    "round-robin": RoundRobinPolicy,
    "multilevel-queue": MultilevelQueuePolicy,
    "multilevel-feedback": MultilevelFeedbackPolicy,
    "earliest-due": EarliestDuePolicy,
}

# Textbook names accepted on the command line.
ALIASES = {
    "fcfs": "arrival-order",
    "sjf": "shortest-effort",
    "srtf": "shortest-remaining",
    "rr": "round-robin",
    "mlq": "multilevel-queue",
    "mlfq": "multilevel-feedback",
    "edf": "earliest-due",
}


def make_policy(key: str, quantum: int = 4) -> DispatchPolicy:
    """Build a policy by name or alias; `quantum` applies to Round Robin."""
    key = ALIASES.get(key, key)
    if key not in POLICIES:
        raise KeyError(f"unknown policy: {key}")
    if key == "round-robin":
        return RoundRobinPolicy(quantum)
    return POLICIES[key]()


__all__ = [
    "DispatchPolicy", "ArrivalOrderPolicy", "ShortestEffortPolicy",
    "ShortestRemainingPolicy", "RoundRobinPolicy", "MultilevelQueuePolicy",
    "MultilevelFeedbackPolicy", "EarliestDuePolicy", "POLICIES", "ALIASES",
    "make_policy",
]
