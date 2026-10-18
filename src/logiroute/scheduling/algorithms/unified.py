"""Phase 5 — 统一配送调度器（Unified Planner）。

设计：

* 用户公开入口 ``plan_deliveries(scenario, objective)`` —— 只接受目标函数，
  **不** 接受算法名称；
* 内部统一流程：

  1. 可行插入与最近邻分别构造单车闭合候选路线；
  2. 对可行候选分别运行受约束 2-opt；
  3. 优先选择服务订单更多的路线，再按主目标选择较短/较便宜的路线。

* 不复制 Dijkstra / 路径求解 —— 全部走 :class:`PathProvider`；
* 不引入 ``heapq`` / ``sorted()`` —— 候选评估为手写线性扫描；
* 不可伪造完成率：选中分支的未服务订单如实传递到 :attr:`RoutePlan.notes`。
"""
from __future__ import annotations

from dataclasses import replace

from logiroute.core.orders import Order
from logiroute.scheduling.algorithms.insertion import cheapest_feasible_insertion
from logiroute.scheduling.algorithms.nearest_neighbor import nearest_neighbor
from logiroute.scheduling.algorithms.two_opt import constrained_two_opt
from logiroute.scheduling.types import (
    PlanningContext,
    RoutePlan,
)


def unified_planner(
    ctx: PlanningContext,
    eligible_orders: list[Order],
) -> RoutePlan:
    """统一调度器：双种子 + 受约束 2-opt + 完成率优先择优。

    Args:
        ctx: 调度上下文（路径 provider / 容量 / 仓库 / 车辆 ...）。
        eligible_orders: 已通过预过滤的订单列表。

    Returns:
        :class:`RoutePlan`：含 ``stops`` / ``legs`` / ``served_order_ids``，
        未排入订单写入 ``notes['unserved_orders']``。

    Notes:
        2-opt 只改变站点顺序，不增加订单。优先比较服务量，避免为了降低
        路程丢单；同服务量再比较主目标。两条种子共用本次调度的路径缓存。

    Time   : 两次构造 + 两次 2-opt，最坏 O(K^5·(V+E)log V)。
    Space  : O(K² + V + E)，主要为调度作用域内的路径缓存。
    """
    insertion_seed = cheapest_feasible_insertion(ctx, eligible_orders)
    best = constrained_two_opt(insertion_seed, ctx)

    neighbor_seed = nearest_neighbor(ctx, eligible_orders)
    if not neighbor_seed.is_feasible:
        return best
    neighbor_plan = constrained_two_opt(neighbor_seed, ctx)
    if len(neighbor_plan.served_order_ids) < len(best.served_order_ids):
        return best
    if (
        len(neighbor_plan.served_order_ids) == len(best.served_order_ids)
        and neighbor_plan.main_objective_total >= best.main_objective_total - 1e-9
    ):
        return best

    served = set(neighbor_plan.served_order_ids)
    unserved = tuple(
        {
            "order_id": order.id,
            "kind": "no_feasible_next_step",
            "message": (
                f"order {order.id!r} could not be served by nearest-neighbor "
                "while satisfying capacity and time-window constraints"
            ),
        }
        for order in eligible_orders
        if order.id not in served
    )
    notes = {**neighbor_plan.notes, "seed_algorithm": "nearest_neighbor"}
    if unserved:
        notes["unserved_orders"] = unserved
    return replace(neighbor_plan, notes=notes)


__all__ = ["unified_planner"]
