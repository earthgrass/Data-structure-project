"""配送订单模型。

订单包含送达点、需求量与时间窗口约束；订单状态在生命周期内会发生变化，
因此 ``Order`` 使用非冻结 dataclass。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import math
from typing import Any

from logiroute.core.enums import OrderPriority, OrderStatus
from logiroute.core.quantities import Quantity, decimal_quantity


ORDER_TRANSITIONS: dict[OrderStatus, tuple[OrderStatus, ...]] = {
    OrderStatus.CREATED: (OrderStatus.PENDING, OrderStatus.CANCELLED),
    OrderStatus.PENDING: (OrderStatus.PLANNED, OrderStatus.CANCELLED, OrderStatus.EXPIRED),
    OrderStatus.PLANNED: (OrderStatus.PENDING, OrderStatus.IN_TRANSIT,
                          OrderStatus.CANCELLED, OrderStatus.EXPIRED),
    OrderStatus.IN_TRANSIT: (OrderStatus.DELIVERED,),
    OrderStatus.DELIVERED: (), OrderStatus.CANCELLED: (), OrderStatus.EXPIRED: (),
}


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _validate_non_negative(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite non-negative number")
    if value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")


@dataclass
class Order:
    """配送订单。

    Attributes:
        id: 订单唯一标识。
        destination_id: 配送目标节点 ID（客户点）。
        demand: 货物需求量（与车辆容量共用业务单位）。
        time_window_start: 送达时间窗口起点（分钟，相对于当日零点）。
        time_window_end: 送达时间窗口终点（分钟，相对于当日零点）。
        priority: 优先级。
        status: 订单状态。
        metadata: 预留扩展字段。
    """

    id: str
    destination_id: str
    demand: Quantity
    time_window_start: float
    time_window_end: float
    priority: OrderPriority = OrderPriority.NORMAL
    status: OrderStatus = OrderStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)

    def __setattr__(self, name: str, value: Any) -> None:
        # Private exact sources are not dataclass fields: existing asdict/DTOs
        # retain their float schema. New load code must use demand_decimal.
        if name == "demand":
            exact = decimal_quantity(value, "demand")
            display = float(exact)
            if not math.isfinite(display):
                raise ValueError("demand exceeds the finite legacy numeric range")
            object.__setattr__(self, "_demand_decimal", exact)
            value = display
        object.__setattr__(self, name, value)

    @property
    def demand_decimal(self) -> Decimal:
        """Original per-order quantity, before float compatibility view. Time/Space O(1)."""
        return self._demand_decimal

    def __post_init__(self) -> None:
        _validate_id(self.id, "order id")
        _validate_id(self.destination_id, "destination_id")
        _validate_non_negative(self.demand, "demand")
        if not isinstance(self.time_window_start, (int, float)):
            raise ValueError("time_window_start must be a number")
        if not isinstance(self.time_window_end, (int, float)):
            raise ValueError("time_window_end must be a number")
        if self.time_window_end != self.time_window_end or self.time_window_end in (
            float("inf"),
            float("-inf"),
        ):
            raise ValueError("time_window_end must be finite")
        if (
            self.time_window_start != self.time_window_start
            or self.time_window_start in (float("inf"), float("-inf"))
        ):
            raise ValueError("time_window_start must be finite")
        if self.time_window_end <= self.time_window_start:
            raise ValueError(
                "time_window_end must be strictly greater than time_window_start"
            )
        if not isinstance(self.priority, OrderPriority):
            raise ValueError(
                f"priority must be an OrderPriority enum, got {type(self.priority).__name__}"
            )
        if not isinstance(self.status, OrderStatus):
            raise ValueError(
                f"status must be an OrderStatus enum, got {type(self.status).__name__}"
            )
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    # ------------------------------------------------------------------ #
    #  业务方法                                                            #
    # ------------------------------------------------------------------ #

    def transition_to(self, status: OrderStatus) -> None:
        """Apply an explicit legal transition; no clock or queue side effects.

        planned -> pending withdraws a plan before departure; expired/cancelled/
        delivered are terminal. Duplicate transitions are rejected.
        Time / Space O(1).
        """
        if (not isinstance(status, OrderStatus) or not isinstance(self.status, OrderStatus)
                or status not in ORDER_TRANSITIONS[self.status]):
            raise ValueError(f"illegal order transition: {self.status!r} -> {status!r}")
        self.status = status

    @property
    def time_window_length(self) -> float:
        """时间窗口长度（分钟）。"""
        return self.time_window_end - self.time_window_start

    def is_within_window(self, arrival_minute: float) -> bool:
        """判断 ``arrival_minute`` 是否落在合法时间窗口内（闭区间）。"""
        return self.time_window_start <= arrival_minute <= self.time_window_end
