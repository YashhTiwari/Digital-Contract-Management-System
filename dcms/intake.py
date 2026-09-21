"""Loading contract requests from CSV files."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from .models import ContractRequest

REQUIRED_COLUMNS = {
    "request_id", "contract_id", "request_type",
    "submitted_at", "effort", "due_at", "priority",
}


def load_requests(path: str | Path) -> List[ContractRequest]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Request file not found: {path}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing columns in {path.name}: {sorted(missing)}")

        requests: List[ContractRequest] = []
        seen = set()
        for row in reader:
            if row["request_id"] in seen:
                raise ValueError(f"Duplicate request_id: {row['request_id']}")
            seen.add(row["request_id"])
            requests.append(ContractRequest(
                request_id=row["request_id"],
                contract_id=row["contract_id"],
                request_type=row["request_type"],
                submitted_at=int(row["submitted_at"]),
                effort=int(row["effort"]),
                due_at=int(row["due_at"]),
                priority=int(row["priority"]),
            ))
    if not requests:
        raise ValueError(f"No requests found in {path.name}")
    return requests
