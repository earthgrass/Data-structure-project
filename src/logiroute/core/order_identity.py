"""Order IDs, result partitions and service assignments independent of route nodes."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from logiroute.core.orders import Order


@dataclass(frozen=True)
class ServiceAssignment:
    """An order served during a route visit; many orders may share visit_index."""

    order_id: str
    visit_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id.strip():
            raise ValueError("assignment.order_id must be a non-empty string")
        if (isinstance(self.visit_index, bool) or not isinstance(self.visit_index, int)
                or self.visit_index < 0):
            raise ValueError("assignment.visit_index must be a non-negative integer")


@dataclass(frozen=True)
class OrderCoverageReport:
    """A valid partition can contain unserved orders; it is not full delivery."""

    valid: bool
    all_orders_served: bool
    violations: tuple[str, ...]


def index_orders(orders: Iterable[Order]) -> dict[str, Order]:
    """Validate input identities, reject duplicates. Time/Space O(K)."""
    result: dict[str, Order] = {}
    for order in orders:
        if not isinstance(order, Order):
            raise ValueError("orders must contain Order objects")
        order.__post_init__()
        if order.id in result:
            raise ValueError(f"duplicate order id: {order.id!r}")
        result[order.id] = order
    return result


def validate_order_coverage(
    orders: Iterable[Order], served_order_ids: Iterable[str],
    unserved_order_ids: Iterable[str] = (),
) -> OrderCoverageReport:
    """Check unique, disjoint, exhaustive result partitions by ID.

    Invalid input orders raise ValueError; invalid output identities are reported.
    Time O(K+S+U); Space O(K+S+U), using ID maps and membership sets.
    """
    inputs = index_orders(orders)
    violations: list[str] = []

    def collect(values: Iterable[str], name: str) -> set[str]:
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value.strip():
                violations.append(f"{name}: invalid order id {value!r}")
                continue
            if value in seen:
                violations.append(f"{name}: duplicate order id {value!r}")
            if value not in inputs:
                violations.append(f"{name}: unknown order id {value!r}")
            seen.add(value)
        return seen

    served = collect(served_order_ids, "served")
    unserved = collect(unserved_order_ids, "unserved")
    for order_id in inputs:
        if order_id in served and order_id in unserved:
            violations.append(f"served/unserved overlap: {order_id!r}")
        if order_id not in served and order_id not in unserved:
            violations.append(f"missing result for order: {order_id!r}")
    return OrderCoverageReport(not violations, not violations and not unserved, tuple(violations))
