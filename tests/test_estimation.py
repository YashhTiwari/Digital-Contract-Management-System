from pathlib import Path

import pytest

from dcms.estimation import (apply_estimates, estimate_by_type, exponential_average,
                             load_history)
from dcms.models import ContractRequest

HISTORY = Path(__file__).resolve().parent.parent / "data" / "request_history.csv"


def test_exponential_average_textbook():
    # tau0 = 10, alpha = 0.5, bursts 6, 4, 6, 4 -> 10, 8, 6, 6, 5
    assert exponential_average([6, 4, 6, 4], 0.5, 10) == [10, 8, 6, 6, 5]


def test_alpha_extremes():
    assert exponential_average([3, 9], alpha=1.0, initial=5)[-1] == 9
    assert exponential_average([3, 9], alpha=0.0, initial=5)[-1] == 5


def test_alpha_validated():
    with pytest.raises(ValueError):
        exponential_average([1], alpha=1.5)


def test_estimates_from_history_file():
    estimates = estimate_by_type(load_history(HISTORY), alpha=0.5)
    assert estimates["Deadline Alert"] < estimates["Compliance Audit"]
    assert set(estimates) == {"Contract Retrieval", "Approval Workflow", "Deadline Alert",
                              "Archive Request", "Signature Verification", "Compliance Audit"}


def test_apply_estimates_uses_default_for_unknown_type():
    a = ContractRequest("A", "C", "Deadline Alert", 0, 2, 10)
    b = ContractRequest("B", "C", "Something New", 0, 2, 10)
    apply_estimates([a, b], {"Deadline Alert": 1.5}, default=4.0)
    assert (a.estimated_effort, b.estimated_effort) == (1.5, 4.0)


def test_estimated_remaining_never_negative():
    r = ContractRequest("A", "C", "T", 0, 5, 10, estimated_effort=2)
    r.remaining_effort = 1
    assert r.estimated_remaining == 0


def test_missing_history_file():
    with pytest.raises(FileNotFoundError):
        load_history("nope.csv")
