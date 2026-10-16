"""配送调度模块 —— 单车辆闭环路径规划。

承担：

* Phase 3 — ``plan_deliveries(scenario, algorithm, objective)`` 统一入口
  * 自实现三种算法：Nearest-Neighbor / Cheapest Feasible Insertion /
    受约束 2-opt 局部搜索
  * 通过 :class:`PathProvider` 单次调度作用域缓存复用 Phase 2 Dijkstra
  * 强制单车、强制闭合、如实报告不可行订单（见 :doc:`AGENTS` §3.6）

依据教师原始题目（单车辆：从仓库出发遍历全部待配送点后返回仓库），
本模块拒绝任何多车辆调度 / 车队优化 / 拆单策略 —— 历史多车辆方案一律作废。
"""

from __future__ import annotations

from logiroute.scheduling.depot import DepotChoice, select_depot
from logiroute.scheduling.feasibility import check_feasibility
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.planner import plan_deliveries
from logiroute.scheduling.types import (
    DeliveryStop,
    DepotNotFoundError,
    EmptyOrdersError,
    FeasibilityReport,
    InfeasibleSeedError,
    InvalidObjectiveError,
    NoAvailableVehicleError,
    PlanningContext,
    PlanningError,
    PlanningStats,
    RoutePlan,
    ScheduleResult,
    UnknownAlgorithmError,
    Violation,
)

__all__ = [
    # 入口
    "plan_deliveries",
    # 选择
    "DepotChoice",
    "select_depot",
    # 路径
    "PathProvider",
    # 可行性
    "check_feasibility",
    # 数据类型
    "DeliveryStop",
    "FeasibilityReport",
    "PlanningContext",
    "PlanningError",
    "PlanningStats",
    "RoutePlan",
    "ScheduleResult",
    "Violation",
    # 错误子类
    "DepotNotFoundError",
    "EmptyOrdersError",
    "InfeasibleSeedError",
    "InvalidObjectiveError",
    "NoAvailableVehicleError",
    "UnknownAlgorithmError",
]
