from .base import DispatchPolicy
from .arrival_order import ArrivalOrderPolicy

POLICIES = {
    "arrival-order": ArrivalOrderPolicy,
}

__all__ = ["DispatchPolicy", "ArrivalOrderPolicy", "POLICIES"]
