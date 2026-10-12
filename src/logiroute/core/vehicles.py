"""配送车辆模型。

车辆与配送员相互独立：同一辆车在不同时刻可由不同配送员驾驶，
同一配送员在不同时刻可使用不同车辆。这样保留后续重新分配资源的能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _validate_vehicle_id(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("vehicle id must be a non-empty string")


def _validate_non_negative_number(value: float, name: str) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if value < 0 or value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite non-negative number")


@dataclass
class Vehicle:
    """配送车辆。

    Attributes:
        id: 车辆唯一标识。
        max_capacity: 最大载重（单位与上层约定一致，如 kg）。
        current_load: 当前载重，初始默认为 0。
        current_node_id: 车辆所在节点 ID（无则为空字符串）。
        metadata: 预留扩展字段。
    """

    id: str
    max_capacity: float
    current_load: float = 0.0
    current_node_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_vehicle_id(self.id)
        _validate_non_negative_number(self.max_capacity, "max_capacity")
        _validate_non_negative_number(self.current_load, "current_load")
        if self.current_load > self.max_capacity:
            raise ValueError(
                "current_load cannot exceed max_capacity "
                f"(current_load={self.current_load}, max_capacity={self.max_capacity})"
            )
        if not isinstance(self.current_node_id, str):
            raise ValueError("current_node_id must be a string")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    @property
    def remaining_capacity(self) -> float:
        """剩余可装载量。"""
        return self.max_capacity - self.current_load

    @property
    def is_available(self) -> bool:
        """车辆当前是否没有承载货物（可用于装载）。"""
        return self.current_load == 0

    def can_load(self, amount: float) -> bool:
        """判断是否可以继续装载 ``amount`` 单位的货物。"""
        if not isinstance(amount, (int, float)) or amount < 0:
            return False
        return self.current_load + amount <= self.max_capacity

    def load(self, amount: float) -> None:
        """装载 ``amount`` 单位的货物到车上。"""
        if not isinstance(amount, (int, float)):
            raise ValueError("load amount must be a number")
        if amount < 0:
            raise ValueError("load amount cannot be negative")
        if not self.can_load(amount):
            raise ValueError(
                f"cannot load {amount}: exceeds remaining capacity "
                f"({self.remaining_capacity})"
            )
        self.current_load += amount

    def unload(self, amount: float) -> None:
        """从车上卸下 ``amount`` 单位的货物。"""
        if not isinstance(amount, (int, float)):
            raise ValueError("unload amount must be a number")
        if amount < 0:
            raise ValueError("unload amount cannot be negative")
        if amount > self.current_load:
            raise ValueError(
                f"cannot unload {amount}: current_load is {self.current_load}"
            )
        self.current_load -= amount
