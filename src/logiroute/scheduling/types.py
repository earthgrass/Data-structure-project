"""Phase 3 调度器所用全部数据类型。

设计原则（与 AGENTS.md 强约束一致）：

* 全部 ``@dataclass``，关键类型 ``frozen=True``；
* 所有公开字段带类型注解；
* ``__post_init__`` 校验闭回路 / 长度 / 可达性不变量；
* 不依赖任何图算法 / Web 框架；
* ``to_dict()`` 便于 JSON 序列化与 Phase 5+ Dashboard 复用。

类型清单：

* :class:`DeliveryStop` —— 单个配送站或仓库的事件快照；
* :class:`RoutePlan` —— 单车闭合回路计划（``frozen``）；
* :class:`ScheduleResult` —— 一次 ``plan_deliveries`` 调用的完整结果（``frozen``）；
* :class:`Violation` —— 一条不可行订单 / 不可达腿 / 时间窗违反的描述（``frozen``）；
* :class:`FeasibilityReport` —— ``check_feasibility`` 的输出（``frozen``）；
* :class:`PlanningStats` —— 调度统计计数器（``frozen``）；
* :class:`PlanningContext` —— 调度作用域内的内部上下文（非公开，但同模块 import 方便测试）；
* :class:`PlanningError` —— 调度器主动抛出的错误（含若干子类）。

**不强制 service_end ≤ time_window_end**：AGENTS.md §3.7 明确本阶段仅要求
``service_start ≤ time_window_end``；``service_end`` 越界不视为违反，由后续
可配置策略决定。本模块不强加此语义，避免偷偷修改规划语义。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# 错误类型
# ---------------------------------------------------------------------------


class PlanningError(Exception):
    """调度器主动抛出的错误基类。

    子类用以区分不同的可恢复 / 不可恢复错误场景，便于上层捕获并精确报告。
    """


class NoAvailableVehicleError(PlanningError):
    """场景中找不到任何 ``status==IDLE`` 且 ``current_node_id`` 为仓库的车辆。"""


class EmptyOrdersError(PlanningError):
    """场景的订单列表为空，无法规划。"""


class UnknownAlgorithmError(PlanningError):
    """``algorithm`` 参数不在白名单中。"""


class InvalidObjectiveError(PlanningError):
    """``objective`` 不在白名单中（含 ``travel_time`` 不可作主目标的拒绝）。"""


class DepotNotFoundError(PlanningError):
    """显式指定的 ``depot_id`` 不存在 / 不是仓库 / 无对应 IDLE 车辆。"""


class InfeasibleSeedError(PlanningError):
    """2-opt / CFI 输入的种子路线本身不可行。"""


# ---------------------------------------------------------------------------
# 违反记录
# ---------------------------------------------------------------------------

#: ``Violation.kind`` 字符串白名单 —— 与 ``check_feasibility`` 输出一致；
#: 也作为调度器主动报告 unserved 订单的语义标签。
VIOLATION_KINDS: tuple[str, ...] = (
    "capacity_overflow",
    "time_window_miss",
    "unreachable_leg",
    "return_unreachable",
    "service_time_overflow",
    "depot_mismatch",
    "no_feasible_next_step",
    "no_feasible_insertion",
    "infeasible_seed",
)


@dataclass(frozen=True)
class Violation:
    """一条不满足约束的记录（不可变）。

    Time / Space：构造 O(1)，无附加开销。
    """

    order_id: str | None
    kind: str
    message: str

    def __post_init__(self) -> None:
        if self.kind not in VIOLATION_KINDS:
            raise ValueError(
                f"unknown violation kind: {self.kind!r}; "
                f"allowed: {VIOLATION_KINDS}"
            )
        if not isinstance(self.message, str) or not self.message:
            raise ValueError(
                "Violation.message must be a non-empty string"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 配送站事件
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeliveryStop:
    """一次配送 / 仓库的事件快照。

    序列中下标 0 = 出发仓库；下标 ``K + 1`` = 返回仓库，``K`` 为配送站数。
    depot stop 的 ``order_id`` 必为 ``None``，``demand`` 必为 ``0.0``，
    ``time_window_start/end`` 必为 ``None``。
    """

    sequence_index: int
    node_id: str
    arrival_time: float
    service_start: float
    service_end: float
    waiting_time: float
    order_id: str | None = None
    demand: float = 0.0
    cumulative_load: float = 0.0
    time_window_start: float | None = None
    time_window_end: float | None = None

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError(
                f"sequence_index must be non-negative, got {self.sequence_index}"
            )
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("node_id must be a non-empty string")
        for name in ("arrival_time", "service_start", "service_end"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number, got {type(value).__name__}")
        if self.waiting_time < -1e-9:
            raise ValueError(
                f"waiting_time must be non-negative, got {self.waiting_time}"
            )
        if self.demand < -1e-9:
            raise ValueError(f"demand must be non-negative, got {self.demand}")
        if self.cumulative_load < -1e-9:
            raise ValueError(
                f"cumulative_load must be non-negative, got {self.cumulative_load}"
            )
        is_depot_stop = self.order_id is None
        if is_depot_stop:
            if abs(self.demand) > 1e-9:
                raise ValueError("depot stops must have demand == 0.0")
            if self.time_window_start is not None or self.time_window_end is not None:
                raise ValueError(
                    "depot stops must have time_window_start/end = None"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 路线计划（单车闭合）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutePlan:
    """单车闭合配送回路。

    全部字段在构造时已校验完成；构造后不可变，确保 Hash 安全。
    """

    algorithm: str
    objective: str
    vehicle_id: str
    depot_id: str
    stop_sequence: tuple[str, ...]
    road_node_sequence: tuple[str, ...]
    legs: tuple[Any, ...]  # tuple[PathResult, ...];  Any 避免循环导入
    stops: tuple[DeliveryStop, ...]
    total_distance: float
    total_travel_time: float
    total_cost: float
    main_objective_total: float
    departure_time: float
    return_time: float
    capacity: float
    served_order_ids: tuple[str, ...]
    is_feasible: bool
    courier_id: str | None = None
    notes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 1. 闭合性
        if len(self.stop_sequence) < 2:
            raise ValueError(
                "stop_sequence must contain at least the depot start and end"
            )
        if self.stop_sequence[0] != self.depot_id:
            raise ValueError(
                f"stop_sequence[0] ({self.stop_sequence[0]!r}) "
                f"must equal depot_id ({self.depot_id!r})"
            )
        if self.stop_sequence[-1] != self.depot_id:
            raise ValueError(
                f"stop_sequence[-1] ({self.stop_sequence[-1]!r}) must equal "
                f"depot_id ({self.depot_id!r}) to form a closed tour"
            )
        # 2. legs 长度
        if len(self.legs) != len(self.stop_sequence) - 1:
            raise ValueError(
                f"len(legs) ({len(self.legs)}) must equal "
                f"len(stop_sequence) - 1 ({len(self.stop_sequence) - 1})"
            )
        # 3. 所有 leg 必须可达
        for idx, leg in enumerate(self.legs):
            if not getattr(leg, "reachable", False):
                raise ValueError(
                    f"leg #{idx} ({getattr(leg, 'source', None)!r} -> "
                    f"{getattr(leg, 'target', None)!r}) is unreachable; "
                    "RoutePlan cannot be constructed from an infeasible leg"
                )
        # 4. 主目标一致性
        if self.objective not in ("distance", "cost"):
            raise ValueError(
                f"objective must be 'distance' or 'cost', got {self.objective!r}"
            )
        # 5. main_objective_total 必须与对应列相等
        expected_main = (
            self.total_distance if self.objective == "distance" else self.total_cost
        )
        if abs(self.main_objective_total - expected_main) > 1e-6:
            raise ValueError(
                f"main_objective_total ({self.main_objective_total}) does not "
                f"match total_{self.objective} ({expected_main})"
            )
        # 6. stops 长度
        if len(self.stops) != len(self.stop_sequence):
            raise ValueError(
                f"len(stops) ({len(self.stops)}) must equal "
                f"len(stop_sequence) ({len(self.stop_sequence)})"
            )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "algorithm": self.algorithm,
            "objective": self.objective,
            "vehicle_id": self.vehicle_id,
            "courier_id": self.courier_id,
            "depot_id": self.depot_id,
            "stop_sequence": list(self.stop_sequence),
            "road_node_sequence": list(self.road_node_sequence),
            "legs": [
                {
                    "source": getattr(leg, "source", None),
                    "target": getattr(leg, "target", None),
                    "metric": getattr(leg, "metric", None),
                    "path": list(getattr(leg, "path", ())),
                    "total_weight": getattr(leg, "total_weight", None),
                    "reachable": getattr(leg, "reachable", None),
                    "cross_metrics": dict(
                        getattr(leg, "cross_metrics", {}) or {}
                    ),
                }
                for leg in self.legs
            ],
            "stops": [stop.to_dict() for stop in self.stops],
            "total_distance": self.total_distance,
            "total_travel_time": self.total_travel_time,
            "total_cost": self.total_cost,
            "main_objective_total": self.main_objective_total,
            "departure_time": self.departure_time,
            "return_time": self.return_time,
            "capacity": self.capacity,
            "served_order_ids": list(self.served_order_ids),
            "is_feasible": self.is_feasible,
            "notes": dict(self.notes),
        }
        return result


# ---------------------------------------------------------------------------
# 可行性报告
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeasibilityReport:
    """可行性评估结果（不可变）。"""

    is_feasible: bool
    violations: tuple[Violation, ...] = ()

    def __post_init__(self) -> None:
        if self.is_feasible and self.violations:
            raise ValueError(
                "is_feasible=True is incompatible with non-empty violations"
            )
        if not self.is_feasible and not self.violations:
            raise ValueError(
                "is_feasible=False requires at least one Violation"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_feasible": self.is_feasible,
            "violations": [v.to_dict() for v in self.violations],
        }


# ---------------------------------------------------------------------------
# 调度统计
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanningStats:
    """调度器内部计数器聚合；由 planner 层构造 ``ScheduleResult`` 时填入。"""

    cache_hits: int = 0
    cache_misses: int = 0
    dijkstra_calls: int = 0
    paths_evaluated: int = 0
    feasibility_checks: int = 0
    iterations: int = 0
    runtime_seconds: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "cache_hits",
            "cache_misses",
            "dijkstra_calls",
            "paths_evaluated",
            "feasibility_checks",
            "iterations",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"{name} must be a non-negative int, got {value!r}"
                )
        if not isinstance(self.runtime_seconds, (int, float)):
            raise ValueError(
                f"runtime_seconds must be a number, got {type(self.runtime_seconds).__name__}"
            )
        if self.runtime_seconds < 0:
            raise ValueError(
                f"runtime_seconds must be non-negative, got {self.runtime_seconds}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 调度最终结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScheduleResult:
    """``plan_deliveries`` 调用的完整输出。

    包含 ``RoutePlan``、未服务订单列表、统计计数器与全局可行性标记；
    完整 ``to_dict()`` 输出可被 ``json.dumps`` 序列化（``Phase 5+`` Dashboard 直接消费）。
    """

    scenario_name: str
    algorithm: str
    objective: str
    depot_id: str
    vehicle_id: str
    route_plan: RoutePlan
    served_order_ids: tuple[str, ...]
    unserved_orders: tuple[Violation, ...]
    total_distance: float
    total_travel_time: float
    total_cost: float
    main_objective_total: float
    planning_stats: PlanningStats
    is_feasible: bool
    courier_id: str | None = None
    notes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_feasible and self.unserved_orders:
            # 路线可行但仍有未服务订单 —— 全局标为不可行；防止"伪造 100%"
            object.__setattr__(self, "is_feasible", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "algorithm": self.algorithm,
            "objective": self.objective,
            "depot_id": self.depot_id,
            "vehicle_id": self.vehicle_id,
            "courier_id": self.courier_id,
            "route_plan": self.route_plan.to_dict(),
            "served_order_ids": list(self.served_order_ids),
            "unserved_orders": [v.to_dict() for v in self.unserved_orders],
            "total_distance": self.total_distance,
            "total_travel_time": self.total_travel_time,
            "total_cost": self.total_cost,
            "main_objective_total": self.main_objective_total,
            "planning_stats": self.planning_stats.to_dict(),
            "is_feasible": self.is_feasible,
            "notes": dict(self.notes),
        }


# ---------------------------------------------------------------------------
# 内部上下文
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanningContext:
    """调度器作用范围内的内部上下文。

    **不在 ``__all__`` 中导出**，避免被外部直接 ``import``；外部访问
    ``scenario / graph / vehicle`` 等应通过 ``ScheduleResult`` 或显式参数。
    ``frozen`` 保证调度算法不可偷偷修改上下文以绕过不变量。
    """

    scenario: Any  # ScenarioBundle
    graph: Any  # LogisticsGraph
    path_provider: Any  # PathProvider
    objective: str
    service_time: float
    initial_time: float
    depot_id: str
    vehicle: Any  # Vehicle
    courier: Any  # Courier | None
    capacity: float

    def __post_init__(self) -> None:
        if self.objective not in ("distance", "cost"):
            raise ValueError(
                f"PlanningContext.objective must be 'distance' or 'cost', "
                f"got {self.objective!r}"
            )
        if not isinstance(self.service_time, (int, float)) or self.service_time < 0:
            raise ValueError(
                f"service_time must be a non-negative number, got {self.service_time!r}"
            )
        if not isinstance(self.initial_time, (int, float)):
            raise ValueError(
                f"initial_time must be a number, got {type(self.initial_time).__name__}"
            )
        if self.capacity < 0:
            raise ValueError(f"capacity must be non-negative, got {self.capacity!r}")
