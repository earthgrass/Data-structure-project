"""默认单车调度：Dijkstra 距离矩阵 + 有向 TSP 顺序搜索。"""
from __future__ import annotations

from logiroute.core.orders import Order
from logiroute.scheduling.algorithms.tsp import solve_tsp
from logiroute.scheduling.types import (
    PlanningContext,
    RoutePlan,
)


def unified_planner(
    ctx: PlanningContext,
    eligible_orders: list[Order],
) -> RoutePlan:
    """复用统一入口，默认运行 :func:`solve_tsp`。

    Time / Space 复杂度见 ``solve_tsp``；不调用历史 NN/CFI/2-opt。
    """
    return solve_tsp(ctx, eligible_orders)


__all__ = ["unified_planner"]
