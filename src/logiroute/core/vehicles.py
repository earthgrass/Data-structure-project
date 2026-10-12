"""配送车辆模型。

车辆与配送员相互独立：同一辆车在不同时刻可由不同配送员驾驶，
同一配送员在不同时刻可使用不同车辆。这样保留后续重新分配资源的能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from logiroute.core.enums import VehicleStatus


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _validate_non_negative_number(value: float, name: str) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    # 拒绝 NaN / inf，保持数值健康
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite non-negative number")
    if value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")


@dataclass
class Vehicle:
    """配送车辆。

    Attributes:
        id: 车辆唯一标识。
        capacity: 最大载重（kg / 件数等业务单位，由调用方约定）。
        current_load: 当前载重，初始默认为 0。
        current_node_id: 车辆所在节点 ID（无则为空字符串）。
        status: 车辆当前状态，初始为 ``IDLE``。
        metadata: 预留扩展字段（不参与算法逻辑）。
    """

    id: str
    capacity: float
    current_load: float = 0.0
    current_node_id: str = ""
    status: VehicleStatus = VehicleStatus.IDLE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_id(self.id, "vehicle id")
        _validate_non_negative_number(self.capacity, "capacity")
        _validate_non_negative_number(self.current_load, "current_load")
        if self.current_load > self.capacity:
            raise ValueError(
                "current_load cannot exceed capacity "
                f"(current_load={self.current_load}, capacity={self.capacity})"
            )
        if not isinstance(self.current_node_id, str):
            raise ValueError("current_node_id must be a string")
        if not isinstance(self.status, VehicleStatus):
            raise ValueError(
                f"status must be a VehicleStatus enum, got {type(self.status).__name__}"
            )
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    # ------------------------------------------------------------------ #
    #  业务方法                                                            #
    # ------------------------------------------------------------------ #

    @property
    def remaining_capacity(self) -> float:
        """剩余可装载量。"""
        return self.capacity - self.current_load

    @property
    def is_available(self) -> bool:
        """车辆当前是否没有承载货物（可用于装载）。"""
        return self.current_load == 0 and self.status is VehicleStatus.IDLE

    def can_load(self, amount: float) -> bool:
        """判断是否可以继续装载 ``amount`` 单位的货物。

        Args:
            amount: 待装载数量，负数或非数字一律返回 ``False``。
        """
        if not isinstance(amount, (int, float)) or amount < 0:
            return False
        return self.current_load + amount <= self.capacity

    def load(self, amount: float) -> None:
        """装载 ``amount`` 单位的货物到车上。"""
        if not isinstance(amount, (int, float)):
            raise ValueError("load amount must be a number")
        if amount < 0:
            raise ValueError("load amount cannot be negative")
        if amount != amount or amount in (float("inf"), float("-inf")):
            raise ValueError("load amount must be finite")
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
        if amount != amount or amount in (float("inf"), float("-inf")):
            raise ValueError("unload amount must be finite")
        if amount > self.current_load:
            raise ValueError(
                f"cannot unload {amount}: current_load is {self.current_load}"
            )
        self.current_load -= amount

    # ------------------------------------------------------------------ #
    #  状态迁移                                                            #
    # ------------------------------------------------------------------ #

    def mark_delivering(self) -> None:
        """切换为配送中状态。"""
        if self.status is VehicleStatus.MAINTENANCE:
            raise ValueError("vehicle in maintenance cannot deliver")
        self.status = VehicleStatus.DELIVERING

    def mark_idle(self) -> None:
        """切换为空闲状态（车辆在仓库待命）。"""
        self.status = VehicleStatus.IDLE
