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
import json
import math
from pathlib import Path
from typing import Any


ROAD_DEFAULTS: dict[str, Any] = json.loads(
    Path(__file__).with_name("road_defaults.json").read_text(encoding="utf-8")
)


@dataclass(frozen=True)
class GeneratorConfig:
    """生成器的输入配置（不可变）。

    默认规模（baseline）与 ``AGENTS.md`` §3.6 完全兼容。

    Attributes:
        name: 场景名（输出 ``ScenarioBundle.name``）。
        min_nodes, max_nodes: 节点数范围 [min, max]。
        min_warehouses, min_customers, min_transfers: 各类型节点下限。
        min_edges, max_edges: 有向边数量硬预算，保留旧含义。
        physical_road_count: 精确物理连接数；None 时按预算选择。
        target_directed_edge_count: 期望有向边数；整数配额偏差写入道路报告。
        bidirectional_ratio: 以物理连接为分母的双向比例。
        max_extra_edges_per_node: 已废弃；显式传入将拒绝，不重新解释其含义。
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
    min_nodes: int = ROAD_DEFAULTS["min_nodes"]
    max_nodes: int = ROAD_DEFAULTS["max_nodes"]
    min_warehouses: int = ROAD_DEFAULTS["min_warehouses"]
    min_customers: int = ROAD_DEFAULTS["min_customers"]
    min_transfers: int = ROAD_DEFAULTS["min_transfers"]
    min_edges: int = ROAD_DEFAULTS["min_edges"]
    max_edges: int = ROAD_DEFAULTS["max_edges"]
    max_extra_edges_per_node: int | None = None
    # 订单
    orders_count: int = 20
    capacity: float = 250.0
    service_time: float = 5.0
    initial_time: float = 540.0
    # 窗口：所有订单共享一个扁平宽窗口，
    # tw_start = initial_time - 30 ; tw_end = last_return_time + extra
    # 默认 extra = 120 minutes —— 保证 NN / CFI / 2-opt 在不同访问顺序下都不漏
    window_total_extra: float = 120.0
    # 需求
    min_demand: float = 5.0
    max_demand: float = 15.0
    # 优先级
    urgent_fraction: float = 0.10
    tsp_beam_width: int = 1024
    # 拒绝重试上限（为安全保险，可行性主源是 backbone-first）
    max_rejection_attempts: int = 16

    # V2 road fields follow legacy fields to preserve positional field order.
    physical_road_count: int | None = ROAD_DEFAULTS["physical_road_count"]
    target_directed_edge_count: int | None = ROAD_DEFAULTS["target_directed_edge_count"]
    bidirectional_ratio: float = ROAD_DEFAULTS["bidirectional_ratio"]
    coordinate_range: tuple[float, float] = tuple(ROAD_DEFAULTS["coordinate_range"])
    longitude_range: tuple[float, float] = tuple(ROAD_DEFAULTS["longitude_range"])
    latitude_range: tuple[float, float] = tuple(ROAD_DEFAULTS["latitude_range"])
    distance_factor_range: tuple[float, float] = tuple(ROAD_DEFAULTS["distance_factor_range"])
    speed_range: tuple[float, float] = tuple(ROAD_DEFAULTS["speed_range"])
    unit_cost_range: tuple[float, float] = tuple(ROAD_DEFAULTS["unit_cost_range"])
    minimum_distance: float = ROAD_DEFAULTS["minimum_distance"]
    node_prefixes: dict[str, str] = field(
        default_factory=lambda: dict(ROAD_DEFAULTS["node_prefixes"])
    )

    def conservative_h_upper_bound(
        self, tau_max: float, n_vertices: int, n_orders: int,
    ) -> float:
        """Phase 5 规格 §四 — 完整配送时间保守上界：

            H = t0 + (K + 1) * (V - 1) * tau_max + S

        其中 ``K = n_orders``，``V = n_vertices``，``S = K * service_time``。

        任意合法路径长度 ≤ ``(V - 1) * tau_max``（最坏每条边都取最大权重）。
        闭合路线含 ``K + 1`` 段，故总行程时间上界为 ``(K + 1) * (V - 1) * tau_max``。
        服务时间总和 ``S`` 加在末尾。

        Returns:
            保守时间上界 H（分钟），与 ``initial_time`` 同量纲。
        """
        if n_vertices < 1 or n_orders < 1:
            return self.initial_time
        return self.initial_time + (n_orders + 1) * max(n_vertices - 1, 0) * tau_max \
            + n_orders * self.service_time

    def __post_init__(self) -> None:
        prefixes = self.node_prefixes
        if (not isinstance(prefixes, dict)
                or set(prefixes) != {"warehouse", "customer", "transfer"}
                or any(not isinstance(value, str) or not value.strip()
                       or ":" in value or ">" in value for value in prefixes.values())
                or len(set(prefixes.values())) != 3):
            raise ValueError("node_prefixes must define three distinct nonempty prefixes "
                             "without ':' or '>'")
        for name in ("min_nodes", "max_nodes", "min_warehouses", "min_customers",
                     "min_transfers", "min_edges", "max_edges"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("physical_road_count", "target_directed_edge_count"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 1
            ):
                raise ValueError(f"{name} must be a positive integer or None")
        if self.max_extra_edges_per_node is not None:
            raise ValueError("max_extra_edges_per_node is retired; use physical_road_count "
                             "or target_directed_edge_count (directed budget is unchanged)")
        ratio = self.bidirectional_ratio
        if (isinstance(ratio, bool) or not isinstance(ratio, (int, float))
                or not math.isfinite(ratio) or not 0 <= ratio <= 1):
            raise ValueError("bidirectional_ratio must be finite and in [0, 1]")
        for name in ("coordinate_range", "longitude_range", "latitude_range",
                     "distance_factor_range", "speed_range", "unit_cost_range"):
            values = getattr(self, name)
            if (not isinstance(values, (tuple, list)) or len(values) != 2
                    or any(isinstance(v, bool) or not isinstance(v, (int, float))
                           or not math.isfinite(v) for v in values)
                    or values[0] > values[1]):
                raise ValueError(f"{name} must contain finite ordered bounds")
            if name in ("distance_factor_range", "speed_range") and values[0] <= 0:
                raise ValueError(f"{name} must be strictly positive")
            if name == "unit_cost_range" and values[0] < 0:
                raise ValueError("unit_cost_range must be non-negative")
            object.__setattr__(self, name, tuple(values))
        if (isinstance(self.minimum_distance, bool)
                or not isinstance(self.minimum_distance, (int, float))
                or not math.isfinite(self.minimum_distance) or self.minimum_distance <= 0):
            raise ValueError("minimum_distance must be finite and positive")
        if self.max_edges < self.min_edges:
            raise ValueError("max_edges must be >= min_edges (directed edges)")
        if (self.target_directed_edge_count is not None
                and not self.min_edges <= self.target_directed_edge_count <= self.max_edges):
            raise ValueError("target_directed_edge_count is outside the directed edge budget")
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
        if self.window_total_extra < 0:
            raise ValueError("window_total_extra must be non-negative")
        if not 0.0 <= self.urgent_fraction <= 1.0:
            raise ValueError("urgent_fraction must be in [0, 1]")
        if (
            isinstance(self.tsp_beam_width, bool)
            or not isinstance(self.tsp_beam_width, int)
            or self.tsp_beam_width < 1
        ):
            raise ValueError("tsp_beam_width must be a positive integer")
        if self.max_demand > self.capacity:
            raise ValueError(
                f"max_demand ({self.max_demand}) must be <= vehicle capacity "
                f"({self.capacity}) to keep every order individually serviceable"
            )
        # Every permitted node count must admit the protected tree and quota.
        self.road_quota(self.min_nodes)
        self.road_quota(self.max_nodes)

    def road_quota(self, node_count: int) -> tuple[int, int]:
        """Return (physical connections, bidirectional connections), never trim a tree.

        Quota uses nearest integer, ties rounded upward. Explicit physical count
        is exact; if both counts are supplied they must agree. With only a target,
        choose the closest feasible directed count, preferring fewer roads on ties.
        Time O(min(V², max_edges)); Space O(1).
        """
        pair_limit = node_count * (node_count - 1) // 2
        target = self.target_directed_edge_count
        if target is None:
            target = self.max_edges
        best: tuple[int, int] | None = None
        best_delta: int | None = None
        if self.physical_road_count is not None:
            candidates = (self.physical_road_count,)
        else:
            candidates = range(node_count - 1, min(pair_limit, self.max_edges) + 1)
        for physical in candidates:
            bidirectional = math.floor(self.bidirectional_ratio * physical + 0.5)
            directed = physical + bidirectional
            if (physical > pair_limit or bidirectional < node_count - 1
                    or not self.min_edges <= directed <= self.max_edges):
                continue
            if (self.physical_road_count is not None
                    and self.target_directed_edge_count is not None
                    and directed != self.target_directed_edge_count):
                continue
            delta = abs(directed - target)
            if best_delta is None or delta < best_delta:
                best = (physical, bidirectional)
                best_delta = delta
        if best is None:
            raise ValueError(
                f"road configuration conflict for {node_count} nodes: protected "
                f"bidirectional tree needs {node_count - 1} roads; physical="
                f"{self.physical_road_count}, ratio={self.bidirectional_ratio}, "
                f"directed budget=[{self.min_edges}, {self.max_edges}], "
                f"target={self.target_directed_edge_count}"
            )
        return best


def load_generator_config(path: str | Path) -> GeneratorConfig:
    """Load explicit JSON overrides without aliasing old edge-count semantics.

    Unknown keys (including ambiguous 'edge_count') are rejected.
    Time O(JSON size + quota scan); Space O(JSON size).
    """
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("generator configuration must be a JSON object")
    try:
        return GeneratorConfig(**values)
    except TypeError as exc:
        raise ValueError(f"unknown or invalid generator configuration: {exc}") from exc


#: 默认生成器配置 — 与课程固定场景最低规模一致。
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


__all__ = ["GeneratorConfig", "DEFAULT_GENERATOR_CONFIG", "GeneratorStats",
           "load_generator_config"]
