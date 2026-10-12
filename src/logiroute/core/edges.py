"""配送网络有向带权边。

``Edge`` 表示从一个节点指向另一个节点的物理道路，承载三类基础权重：
``distance``、``travel_time``、``cost``，外加交通状态这一辅助属性。

注意：

* A → B 的存在并不意味着 B → A 存在。
* 同一对 (source_id, target_id) 暂时不支持多重边（无并联道路），
  若需扩展请在后续 Phase 引入 multi-edge 支持。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from logiroute.core.enums import TrafficStatus


def _validate_non_negative(value: float, name: str) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if value < 0 or value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite non-negative number")


def _validate_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass
class Edge:
    """有向带权边。

    Attributes:
        source_id: 起始节点 ID。
        target_id: 目标节点 ID。
        distance: 距离（公里）。
        travel_time: 通行时间（分钟）。
        cost: 运输成本（元）。
        traffic_status: 当前交通状态。
        metadata: 预留扩展字段（不参与算法逻辑）。
    """

    source_id: str
    target_id: str
    distance: float
    travel_time: float
    cost: float
    traffic_status: TrafficStatus = TrafficStatus.CLEAR
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_id(self.source_id, "source_id")
        _validate_id(self.target_id, "target_id")
        if self.source_id == self.target_id:
            raise ValueError("edge cannot be a self-loop (source_id == target_id)")
        _validate_non_negative(self.distance, "distance")
        _validate_non_negative(self.travel_time, "travel_time")
        _validate_non_negative(self.cost, "cost")
        if not isinstance(self.traffic_status, TrafficStatus):
            raise ValueError(
                "traffic_status must be a TrafficStatus enum, "
                f"got {type(self.traffic_status).__name__}"
            )
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    @property
    def key(self) -> tuple[str, str]:
        """返回 (source_id, target_id) 作为边的唯一键。"""
        return (self.source_id, self.target_id)

    def weight(self, metric: str = "distance") -> float:
        """按指定度量返回该边的权重值。

        Args:
            metric: 必须是 ``"distance"`` / ``"travel_time"`` / ``"cost"`` 之一。
        """
        if metric == "distance":
            return self.distance
        if metric == "travel_time":
            return self.travel_time
        if metric == "cost":
            return self.cost
        raise ValueError(f"unknown weight metric: {metric!r}")
