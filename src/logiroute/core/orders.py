"""配送订单模型。

订单包含送达点、需求量与时间窗口约束；订单状态在生命周期内会发生变化，
因此 ``Order`` 使用非冻结 dataclass。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from logiroute.core.enums import OrderPriority, OrderStatus


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _validate_non_negative(value: float, name: str) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if value < 0 or value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite non-negative number")


@dataclass
class Order:
    """配送订单。

    Attributes:
        id: 订单唯一标识。
        destination_node_id: 配送目标节点 ID（客户点）。
        demand: 货物需求量（与车辆容量共用单位）。
        time_window_start: 送达时间窗口起点（分钟，相对于当日零点）。
        time_window_end: 送达时间窗口终点（分钟，相对于当日零点）。
        priority: 优先级。
        status: 订单状态。
        metadata: 预留扩展字段。
    """

    id: str
    destination_node_id: str
    demand: float
    time_window_start: float
    time_window_end: float
    priority: OrderPriority = OrderPriority.NORMAL
    status: OrderStatus = OrderStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_id(self.id, "order id")
        _validate_id(self.destination_node_id, "destination_node_id")
        _validate_non_negative(self.demand, "demand")
        if not isinstance(self.time_window_start, (int, float)):
            raise ValueError("time_window_start must be a number")
        if not isinstance(self.time_window_end, (int, float)):
            raise ValueError("time_window_end must be a number")
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

    @property
    def time_window_length(self) -> float:
        """时间窗口长度（分钟）。"""
        return self.time_window_end - self.time_window_start

    def is_within_window(self, arrival_minute: float) -> bool:
        """判断 ``arrival_minute`` 是否落在合法时间窗口内。"""
        return self.time_window_start <= arrival_minute <= self.time_window_end
