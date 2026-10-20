"""Single-trip cargo accounting; no route construction or fleet allocation."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from logiroute.core.enums import OrderStatus
from logiroute.core.order_identity import index_orders
from logiroute.core.orders import Order
from logiroute.core.quantities import Quantity, decimal_quantity, exact_difference, exact_sum


@dataclass(frozen=True)
class DeliveryLoadReport:
    """Quantities remain Decimal until the explicit JSON boundary."""

    capacity: Decimal
    initial_load: Decimal
    feasible: bool

    def to_dict(self) -> dict[str, str | bool]:
        """JSON boundary uses decimal strings, never rounded totals. Time/Space O(D)."""
        return {"capacity": str(self.capacity), "initial_load": str(self.initial_load),
                "feasible": self.feasible}


def check_delivery_load(capacity: Quantity, orders: Iterable[Order]) -> DeliveryLoadReport:
    """Validate original per-ID demand and compare exact total to one vehicle.

    No float subtotal/epsilon. Time O(K*D); Space O(K+D), aligned precision D.
    """
    exact_capacity = decimal_quantity(capacity, "capacity")
    indexed = index_orders(orders)
    total = exact_sum(order.demand_decimal for order in indexed.values())
    return DeliveryLoadReport(exact_capacity, total, total <= exact_capacity)


class DeliveryLoadState:
    """Independent cargo snapshot for one departure; never mutates Order or Vehicle.

    Only pending/planned orders can be loaded. Removing cargo does not create
    new onboard orders. No replenishment or cross-vehicle transfers are modeled.
    Space O(K+D); quantities are read-only Decimal properties.
    """

    __slots__ = ("_capacity", "_initial_load", "_current_load", "_remaining", "_delivered")

    def __init__(self, capacity: Quantity, orders: Iterable[Order]) -> None:
        """Time O(K*D); Space O(K+D), snapshot original ID/quantity pairs."""
        indexed = index_orders(orders)
        report = check_delivery_load(capacity, indexed.values())
        if not report.feasible:
            raise ValueError(f"initial_load={report.initial_load} exceeds capacity={report.capacity}")
        if any(order.status not in (OrderStatus.PENDING, OrderStatus.PLANNED)
               for order in indexed.values()):
            raise ValueError("only pending/planned orders may be loaded")
        self._capacity = report.capacity
        self._initial_load = report.initial_load
        self._current_load = report.initial_load
        self._remaining: dict[str, Decimal] = {
            order.id: order.demand_decimal for order in indexed.values()
        }
        self._delivered: set[str] = set()

    @property
    def capacity(self) -> Decimal:
        """Time / Space O(1)."""
        return self._capacity

    @property
    def initial_load(self) -> Decimal:
        """Time / Space O(1)."""
        return self._initial_load

    @property
    def current_load(self) -> Decimal:
        """Time / Space O(1)."""
        return self._current_load

    @property
    def free_capacity(self) -> Decimal:
        """Exact space available, not permission to reload. Time/Space O(D)."""
        return exact_difference(self._capacity, self._current_load)

    def deliver(self, order_id: str) -> None:
        """Unload one known order once, atomically. Time/Space O(D), ID lookup avg O(1)."""
        if order_id not in self._remaining:
            reason = "already delivered" if order_id in self._delivered else "unknown order"
            raise ValueError(f"{reason}: {order_id!r}")
        remaining_load = exact_difference(self._current_load, self._remaining[order_id])
        if not 0 <= remaining_load <= self._initial_load <= self._capacity:
            raise ValueError("cargo invariant violated")
        del self._remaining[order_id]
        self._delivered.add(order_id)
        self._current_load = remaining_load

    def to_dict(self) -> dict[str, object]:
        """Explicit exact JSON boundary; remaining records retain departure order.

        Time/Space O(K*D). No floating point serialization of quantities.
        """
        return {"capacity": str(self.capacity), "initial_load": str(self.initial_load),
                "current_load": str(self.current_load), "free_capacity": str(self.free_capacity),
                "remaining_orders": {key: str(value) for key, value in self._remaining.items()},
                "delivered_count": len(self._delivered)}
