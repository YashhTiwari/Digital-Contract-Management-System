"""Effort estimation from request history (exponential averaging).

SJF and SRTF need a request's handling time before it runs, which is never
known exactly. Like CPU burst prediction, the next effort for a request type
is predicted from the efforts actually measured for past requests of that type:

    tau(n+1) = alpha * t(n) + (1 - alpha) * tau(n)

alpha = 1 trusts only the latest measurement; alpha = 0 ignores history.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .models import ContractRequest


def exponential_average(measured: Sequence[float], alpha: float = 0.5,
                        initial: float = 5.0) -> List[float]:
    """Return the predictions tau(0)..tau(n) for a series of measured efforts."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between 0 and 1")
    predictions = [initial]
    for t in measured:
        predictions.append(alpha * t + (1 - alpha) * predictions[-1])
    return predictions


def load_history(path: str | Path) -> List[Tuple[str, int]]:
    """Read (request_type, actual_effort) rows in chronological order."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"History file not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"request_type", "actual_effort"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing columns in {path.name}: {sorted(missing)}")
        return [(row["request_type"], int(row["actual_effort"])) for row in reader]


def estimate_by_type(history: Iterable[Tuple[str, int]], alpha: float = 0.5,
                     initial: float = 5.0) -> Dict[str, float]:
    """Predicted next effort for every request type seen in the history."""
    by_type: Dict[str, List[int]] = {}
    for request_type, effort in history:
        by_type.setdefault(request_type, []).append(effort)
    return {t: round(exponential_average(v, alpha, initial)[-1], 2)
            for t, v in by_type.items()}


def apply_estimates(requests: Iterable[ContractRequest], estimates: Dict[str, float],
                    default: float = 5.0) -> None:
    """Replace each request's estimated effort with the prediction for its type."""
    for r in requests:
        r.estimated_effort = estimates.get(r.request_type, default)
