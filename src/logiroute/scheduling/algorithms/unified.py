"""Phase 5 — 统一配送调度器（Unified Planner）。

设计：

* 用户公开入口 ``plan_deliveries(scenario, objective)`` —— 只接受目标函数，
  **不** 接受算法名称；
* 内部统一流程：

  1. ``cheapest_feasible_insertion`` —— 构造满足硬约束的初始可行路线；
  2. ``constrained_two_opt`` —— 受约束 2-opt 局部搜索改善路线；
  3. 重建完整时刻表 → 评估容量 / 时间窗 / 闭合约束 → 输出 ``RoutePlan``。

* 不复制 Dijkstra / 路径求解 —— 全部走 :class:`PathProvider`；
* 不引入 ``heapq`` / ``sorted()`` —— 候选评估为手写线性扫描；
* 不可伪造完成率：CFI 报告的未服务订单如实传递到 :attr:`RoutePlan.notes`。
"""
from __future__ import annotations

from logiroute.scheduling.algorithms.insertion import cheapest_feasible_insertion
from logiroute.scheduling.algorithms.two_opt import constrained_two_opt
from logiroute.scheduling.types import (
    PlanningContext,
    RoutePlan,
)


def unified_planner(
    ctx: PlanningContext,
    eligible_orders: list,
) -> RoutePlan:
    """统一调度器：CFI → 受约束 2-opt。

    Args:
        ctx: 调度上下文（路径 provider / 容量 / 仓库 / 车辆 ...）。
        eligible_orders: 已通过预过滤的订单列表。

    Returns:
        :class:`RoutePlan`：含 ``stops`` / ``legs`` / ``served_order_ids`` /
        ``unserved_orders``（若 CFI 未排入）。``is_feasible=True`` 表示路线
        满足全部硬约束；``False`` 表示存在未排入订单或时间窗违反。

    Notes:
        2-opt 仅在已有可行路线上做局部优化；**不能**新增订单。
        因此 ``served_order_ids`` 与 CFI 阶段完全一致；``unserved_orders``
        由 CFI 报告并写入 :attr:`RoutePlan.notes`。
    """
    seed_plan = cheapest_feasible_insertion(ctx, eligible_orders)
    optimized = constrained_two_opt(seed_plan, ctx)
    # 2-opt 的 notes 在 constrained_two_opt 内部已合并 / 透传
    return optimized


__all__ = ["unified_planner"]