"""配送员模型。

配送员 (Courier) 与车辆 (Vehicle) 是 1:1 关系但分别建模：
* ``vehicle_id`` 仅作为引用，避免与车辆字段双向同步；
* 如果后续需要「人车分离」或共享车队的场景，可直接扩展。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from logiroute.core.enums import CourierStatus


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass
class Courier:
    """配送员。

    Attributes:
        id: 配送员唯一标识。
        name: 姓名 / 编号。
        vehicle_id: 当前所持车辆 ID。
        status: 当前工作状态，初始为 ``IDLE``。
        metadata: 预留扩展字段。
    """

    id: str
    name: str
    vehicle_id: str
    status: CourierStatus = CourierStatus.IDLE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_id(self.id, "courier id")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("courier name must be a non-empty string")
        _validate_id(self.vehicle_id, "vehicle_id")
        if not isinstance(self.status, CourierStatus):
            raise ValueError(
                f"status must be a CourierStatus enum, got {type(self.status).__name__}"
            )
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    @property
    def is_dispatchable(self) -> bool:
        """该配送员当前是否可以被派出新任务。"""
        return self.status in (CourierStatus.IDLE, CourierStatus.DELIVERING)

    def assign_vehicle(self, vehicle_id: str) -> None:
        """更换配送员所持车辆。"""
        _validate_id(vehicle_id, "vehicle_id")
        self.vehicle_id = vehicle_id

    def mark_delivering(self) -> None:
        """切换为配送中状态（若已离线则拒绝）。"""
        if self.status == CourierStatus.OFFLINE:
            raise ValueError("offline courier cannot be marked as delivering")
        self.status = CourierStatus.DELIVERING

    def mark_idle(self) -> None:
        """切换为空闲状态。"""
        self.status = CourierStatus.IDLE
