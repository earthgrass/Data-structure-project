"""配送网络节点。

``Node`` 表示配送网络中的关键地点 —— 仓库、客户点或中转站。
节点在图中不可变（frozen=True），以保证 ID、坐标和类型在网络生命周期内稳定。
若需变更坐标，应通过 graph 层移除节点后重新插入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from logiroute.core.enums import NodeType


def _validate_id(node_id: str) -> None:
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError("node id must be a non-empty string")


def _validate_coordinate(value: float, axis: str) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{axis} coordinate must be a number, got {type(value).__name__}")
    # 仅拒绝 NaN / inf，避免坐标系被破坏；坐标具体范围由调用方决定
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{axis} coordinate must be a finite number")


@dataclass(frozen=True)
class Node:
    """配送网络中的节点。

    Attributes:
        id: 节点唯一标识（不可重复；由调用方保证全图唯一）。
        name: 节点可读名称（如「华中仓库」）。
        node_type: 节点角色（仓库 / 客户 / 中转站）。
        x: 横坐标（单位与上层约定一致，由调用方决定，如公里 / 米）。
        y: 纵坐标（同上）。
    """

    id: str
    name: str
    node_type: NodeType
    x: float
    y: float
    # 预留 metadata 以便扩展（如楼层、负责人、备注），不参与算法逻辑
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("node name must be a non-empty string")
        if not isinstance(self.node_type, NodeType):
            raise ValueError(
                f"node_type must be a NodeType enum, got {type(self.node_type).__name__}"
            )
        _validate_coordinate(self.x, "x")
        _validate_coordinate(self.y, "y")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    def distance_to(self, other: "Node") -> float:
        """与同图节点的欧氏距离。

        仅计算几何距离，不读取任何边权，不依赖图结构。
        """
        if not isinstance(other, Node):
            raise TypeError("distance_to requires another Node instance")
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
