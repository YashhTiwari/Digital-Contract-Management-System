"""Request lifecycle rules and the audit trail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from .models import ContractRequest, RequestStatus as St

ALLOWED_CHANGES: Dict[St, Set[St]] = {
    St.SUBMITTED: {St.QUEUED},
    St.QUEUED: {St.IN_PROGRESS},
    St.IN_PROGRESS: {St.QUEUED, St.AWAITING_APPROVAL, St.COMPLETED},
    St.AWAITING_APPROVAL: {St.QUEUED},
    St.COMPLETED: set(),
}


class InvalidStatusChange(Exception):
    """Raised when a request is moved to a status its lifecycle forbids."""


@dataclass(frozen=True)
class AuditEntry:
    time: int
    request_id: str
    from_status: St
    to_status: St
    note: str = ""


class AuditTrail:
    """Chronological record of every status change."""

    def __init__(self) -> None:
        self.entries: List[AuditEntry] = []

    def add(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    def for_request(self, request_id: str) -> List[AuditEntry]:
        return [e for e in self.entries if e.request_id == request_id]

    def format(self) -> str:
        lines = [f"{'Time':>4}  {'Request':<9} {'Status Change':<32} Note"]
        for e in self.entries:
            change = f"{e.from_status.value} -> {e.to_status.value}"
            lines.append(f"{e.time:>4}  {e.request_id:<9} {change:<32} {e.note}")
        return "\n".join(lines)


def change_status(request: ContractRequest, new_status: St, time: int,
                  trail: AuditTrail, note: str = "") -> None:
    """Apply a status change after validating it against the lifecycle rules."""
    if new_status not in ALLOWED_CHANGES[request.status]:
        raise InvalidStatusChange(
            f"{request.request_id}: {request.status.value} -> "
            f"{new_status.value} is not permitted"
        )
    trail.add(AuditEntry(time, request.request_id, request.status, new_status, note))
    request.status = new_status
