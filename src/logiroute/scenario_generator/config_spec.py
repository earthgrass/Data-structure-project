"""Phase 4 Generator 的配置 schema 与运行统计。

约束来源：

* :class:`GeneratorConfig` 强制 ``AGENTS.md`` §3.6 固定场景最低规模：
  ``min_nodes >= 30``、``min_warehouses >= 2``、``min_customers >= 15``、
  ``min_transfers >= 3``、``min_edges >= 50``；并允许更大范围。

* 不在 Python 源代码内硬编码"节点数 / 容量 / 默认 ID" —— 全部从本配置 +
  业务调用方传入的 ``seed`` 派生。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GeneratorConfig:
    """生成器的输入配置（不可变）。

    默认规模（baseline）与 ``AGENTS.md`` §3.6 完全兼容。

    Attributes:
        name: 场景名（输出 ``ScenarioBundle.name``）。
        min_nodes, max_nodes: 节点数范围 [min, max]。
        min_warehouses, min_customers, min_transfers: 各类型节点下限。
        min_edges, max_edges: 边数范围。
        max_extra_edges_per_node: 在骨架环上每节点额外随机有向边的期望上限。
        orders_count: 订单总数（订单 = 入站配送请求）。
        capacity: 唯一启用车辆的容量（生成器强制 ``total_demand <= capacity``）。
        service_time: 服务时间（分钟）—— 与 Phase 1 ``simulation.service_time`` 一致。
        initial_time: 出发时刻 —— 与 Phase 1 ``simulation.initial_time`` 一致。
        time_window_early_slack: backbone 反推 ``time_window_start`` 时向前留出的 slack。
        time_window_late_slack: 反推 ``time_window_end`` 时向后留出的 slack。
        min_demand, max_demand: 每订单需求上下限（kg）。
        urgent_fraction: URGENT 订单占比（0..1）。
        max_rejection_attempts: backbone 不可达 / 容量不够时的最大重试次数。
    """

    name: str = "logiroute.random.30"
    # 节点规模（与 AGENTS §3.6 兼容）
    min_nodes: int = 30
    max_nodes: int = 60
    min_warehouses: int = 2
    min_customers: int = 15
    min_transfers: int = 3
    min_edges: int = 50
    max_edges: int = 220
    # 骨架 + 随机边
    max_extra_edges_per_node: int = 4
    # 订单
    orders_count: int = 20
    capacity: float = 250.0
    service_time: float = 5.0
    initial_time: float = 540.0
    # window slack（围绕 backbone 到达时刻）
    time_window_early_slack: float = 30.0
    time_window_late_slack: float = 60.0
    # 需求
    min_demand: float = 5.0
    max_demand: float = 15.0
    # 优先级
    urgent_fraction: float = 0.10
    # 拒绝重试上限（为安全保险，可行性主源是 backbone-first）
    max_rejection_attempts: int = 16

    def __post_init__(self) -> None:
        if self.min_nodes < self.min_warehouses + self.min_customers + self.min_transfers:
            raise ValueError(
                f"min_nodes={self.min_nodes} too small for the type quotas "
                f"(W={self.min_warehouses}+C={self.min_customers}+T={self.min_transfers})"
            )
        if self.max_nodes < self.min_nodes:
            raise ValueError("max_nodes must be >= min_nodes")
        # §3.6 最小基线
        if self.min_nodes < 30:
            raise ValueError("AGENTS §3.6 fix-scenario baseline: min_nodes >= 30")
        if self.min_warehouses < 2:
            raise ValueError("AGENTS §3.6: min_warehouses >= 2")
        if self.min_customers < 15:
            raise ValueError("AGENTS §3.6: min_customers >= 15")
        if self.min_transfers < 3:
            raise ValueError("AGENTS §3.6: min_transfers >= 3")
        if self.min_edges < 50:
            raise ValueError("AGENTS §3.6: min_edges >= 50")
        if self.orders_count < 1:
            raise ValueError("orders_count must be >= 1")
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if self.time_window_early_slack < 0 or self.time_window_late_slack < 0:
            raise ValueError("time window slacks must be non-negative")
        if not 0.0 <= self.urgent_fraction <= 1.0:
            raise ValueError("urgent_fraction must be in [0, 1]")
        if self.max_demand > self.capacity:
            # 单订单需求极端时可能超过车辆上限 = 单车不可承载 → 拒绝
            raise ValueError(
                f"max_demand ({self.max_demand}) must be <= vehicle capacity "
                f"({self.capacity}) to keep every order individually serviceable"
            )


#: 默认生成器配置 — 与 ``AGENTS.md`` §3.6 固定场景最低规模一致。
DEFAULT_GENERATOR_CONFIG: GeneratorConfig = GeneratorConfig()


@dataclass(frozen=True)
class GeneratorStats:
    """``generate_scenario`` 内部计数器 / 用于诊断。"""

    attempts: int = 0
    success: bool = False
    seed: int | None = None
    config_name: str = ""
    rng_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "success": self.success,
            "seed": self.seed,
            "config_name": self.config_name,
            "rng_calls": self.rng_calls,
        }


__all__ = ["GeneratorConfig", "DEFAULT_GENERATOR_CONFIG", "GeneratorStats"]
