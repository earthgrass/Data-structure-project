"""最近邻（Nearest-Neighbor）基线构造 —— Phase 3 调度算法之一。

依据 AGENTS.md §3.7：

* 单车辆、强制闭合（首尾均为出发仓库）；
* 所有相邻配送站点之间的最短有向路径**只**通过
  :class:`logiroute.scheduling.path_provider.PathProvider` 调用 Phase 2 Dijkstra；
* ``travel_time`` 永远走时间维度的最优路径（即便主目标是 ``distance`` /
  ``cost``），避免「把主目标所选路径错当行驶时间」的语义错位；
* ``URGENT`` 订单优先扫描，但**不**绕过容量 / 时间窗硬约束；
* ``served_order_ids`` 自然导出，``is_feasible`` 取自
  :func:`logiroute.scheduling.feasibility.check_feasibility`
  对构造出的 ``stops / legs`` 的报告 —— 算法**不**在此函数内主动抛错。

设计取舍
--------

* 维护 ``current_time``（最新 ``DeliveryStop.service_end``）与
  ``current_load``（已装载累计需求）作为局部传播状态；
* 每轮全扫描 ``remaining``，对每个候选订单依次做：
  1. 容量可行性（``current_load + demand ≤ capacity``）；
  2. 主目标路径可达性（``leg_main.reachable``）；
  3. 时间路径可达性（``leg_time.reachable``）；
  4. 时间窗硬约束（``service_start ≤ time_window_end``）；
  5. ``(total_weight, order.id, len(path))`` 三元组 ``min`` 选择最优；
* 候选全部不可行 → 记录 ``no_feasible_next_step`` 并 ``break``，剩余订单
  全部归类为「无可行下一步」。

**与 ``planner`` 模块的契约**：本函数返回的是已构造完成的 :class:`RoutePlan`；
``unserved_orders``（含 ``no_feasible_next_step`` 等 ``Violation``）由上层
``planner`` 通过 ``eligible_orders − plan.served_order_ids`` 推导后再注入
:class:`ScheduleResult`。本函数不直接产出 ``ScheduleResult``，避免边界侵入。

复杂度（V 节点 / E 边；K 入站配送站数）：
    Time   : O(K · ((V + E) log V)) — 每轮全扫描 + 每候选 1~2 次 Dijkstra
    Space  : O(K + E) — legs / stops / 道路序列 / PathProvider 缓存
"""

from __future__ import annotations

from typing import Any

from logiroute.core.enums import OrderPriority
from logiroute.core.orders import Order
from logiroute.scheduling.feasibility import (
    _leg_drive_time,
    check_feasibility,
)
from logiroute.scheduling.types import (
    DeliveryStop,
    PlanningContext,
    RoutePlan,
)


#: 优先级扫描权重；``URGENT=0`` 先扫，``NORMAL=1`` 后扫。仅决定扫描顺序，
#: 不绕过容量 / 时间窗硬约束（违反约束的 urgent 与 normal 一视同仁）。
_PRIORITY_RANK: dict[OrderPriority, int] = {
    OrderPriority.URGENT: 0,
    OrderPriority.NORMAL: 1,
}

#: 浮点容差，与 ``logiroute.scheduling.feasibility._TOL`` 同一量级。
_TOL: float = 1e-9


def nearest_neighbor(
    ctx: PlanningContext,
    eligible_orders: list[Order],
) -> RoutePlan:
    """最近邻基线构造（闭合单车辆配送回路）。

    算法骨架：

    1. 初始化 ``current_node`` / ``current_time`` / ``current_load`` 与
       首站 ``depot stop``；
    2. ``while remaining`` 全扫描，对每个候选做可达 + 容量 + 时间窗校验，
       用 ``(total_weight, order.id, len(path))`` 三元组 ``min`` 选最优；
       若 ``no best`` 则记 ``no_feasible_next_step`` 并 ``break``；
    3. 闭合：append 回归仓库 ``PathResult`` 与末尾 ``depot stop``；
    4. 调用 ``PathProvider.road_node_sequence`` 拼接完整道路序列；
    5. 累加 ``total_distance`` / ``total_cost`` / ``total_travel_time``，
       构造 :class:`RoutePlan`，``is_feasible`` 取自
       :func:`check_feasibility`。

    Args:
        ctx: 调度作用域上下文；必须含 ``path_provider`` /
            ``objective`` / ``depot_id`` / ``initial_time`` /
            ``service_time`` / ``capacity`` / ``vehicle.id``。
        eligible_orders: 当次调度可服务的订单列表。本函数**不**修改入参。

    Returns:
        :class:`RoutePlan`。已闭合、首尾均为 ``ctx.depot_id``。

    Note:
        返回的 ``RoutePlan`` 仅含「已服务订单」的快照。未服务订单的完整
        列表（含 ``Violation`` 元数据）由调用方（``planner`` 层）通过
        ``eligible_orders`` 与 ``plan.served_order_ids`` 的差集推导；
        本函数**不**为「节省字典查表时间」而偷偷把 ``unserved_orders``
        塞进 :class:`RoutePlan`（违反 ``types.RoutePlan`` schema 不变量）。

    Time   : O(K · ((V + E) log V))。
    Space  : O(K + E)。
    """
    # ---- 1. 初始化 ------------------------------------------------------- #
    current_node: str = ctx.depot_id
    current_time: float = ctx.initial_time
    current_load: float = 0.0

    # 稳定排序：(URGENT 先, 然后按 id 字典序) —— 仅决定扫描顺序，
    # 不构成「优先级绕过硬约束」的语义。
    remaining: list[Order] = sorted(
        eligible_orders,
        key=lambda o: (_PRIORITY_RANK[o.priority], o.id),
    )

    plan_stops: list[DeliveryStop] = [
        DeliveryStop(
            sequence_index=0,
            node_id=ctx.depot_id,
            arrival_time=ctx.initial_time,
            service_start=ctx.initial_time,
            service_end=ctx.initial_time,
            waiting_time=0.0,
        )
    ]
    plan_legs: list[Any] = []

    # ---- 2. 主循环 -------------------------------------------------------- #
    while remaining:
        best: Order | None = None
        best_key: tuple | None = None
        best_leg_main: Any = None
        best_leg_time: Any = None

        for order in remaining:
            # 容量硬约束；不满足即跳过（不计入 best 候选）
            if current_load + order.demand > ctx.capacity + _TOL:
                continue

            leg_main = ctx.path_provider.shortest_path(
                current_node, order.destination_id, ctx.objective
            )
            leg_time = ctx.path_provider.shortest_path(
                current_node, order.destination_id, "travel_time"
            )

            # 任何一条不可达 ⇒ 不可服务
            if (not getattr(leg_main, "reachable", False)) or (
                not getattr(leg_time, "reachable", False)
            ):
                continue

            # 到达 / 服务时间传播 —— 永远走 travel_time 维度
            drive_time = _leg_drive_time(leg_time)
            arrival = current_time + drive_time
            wait = max(0.0, order.time_window_start - arrival)
            service_start = arrival + wait
            if service_start > order.time_window_end + _TOL:
                # 晚到：超过时间窗上界，违反 AGENTS §3.7 硬约束
                continue

            # tie-break 规则
            key = (leg_main.total_weight, order.id, len(leg_main.path))
            if best_key is None or key < best_key:
                best = order
                best_key = key
                best_leg_main = leg_main
                best_leg_time = leg_time

        if best is None:
            # 剩余订单全部不可行 —— 跳出循环，由 planner 推导 unserved
            # （"no_feasible_next_step" 语义由 ``planner`` 层统一打标）
            break

        # 推进：实际进入路线
        drive_time = _leg_drive_time(best_leg_time)
        arrival = current_time + drive_time
        wait = max(0.0, best.time_window_start - arrival)
        service_start = arrival + wait
        service_end = service_start + ctx.service_time

        current_time = service_end
        current_load += best.demand

        new_stop = DeliveryStop(
            sequence_index=len(plan_stops),
            node_id=best.destination_id,
            arrival_time=arrival,
            service_start=service_start,
            service_end=service_end,
            waiting_time=wait,
            order_id=best.id,
            demand=best.demand,
            cumulative_load=current_load,
            time_window_start=best.time_window_start,
            time_window_end=best.time_window_end,
        )
        plan_stops.append(new_stop)
        plan_legs.append(best_leg_main)
        current_node = best.destination_id
        remaining.remove(best)

    # ---- 3. 闭合：append 回归仓库 ---------------------------------------- #
    return_leg = ctx.path_provider.shortest_path(
        current_node, ctx.depot_id, ctx.objective
    )
    return_drive_time = _leg_drive_time(return_leg)
    return_arrival = current_time + return_drive_time

    final_depot_stop = DeliveryStop(
        sequence_index=len(plan_stops),
        node_id=ctx.depot_id,
        arrival_time=return_arrival,
        service_start=return_arrival,
        service_end=return_arrival,
        waiting_time=0.0,
    )
    plan_stops.append(final_depot_stop)
    plan_legs.append(return_leg)

    # ---- 4. 道路序列拼接 ------------------------------------------------- #
    road_sequence: tuple[str, ...] = ctx.path_provider.road_node_sequence(
        tuple(s.node_id for s in plan_stops),
        ctx.objective,
    )

    # ---- 5. 累加 totals & 构造 RoutePlan ---------------------------------- #
    stop_sequence = tuple(s.node_id for s in plan_stops)
    served_order_ids = tuple(
        s.order_id for s in plan_stops if s.order_id is not None
    )

    # 主目标列：objective == "distance" → total_weight; objective == "cost"
    # → cross_metrics["cost"]; 另一列同理。
    total_distance: float
    total_cost: float
    if ctx.objective == "distance":
        total_distance = sum(l.total_weight for l in plan_legs)
        total_cost = sum(l.cross_metrics.get("cost", 0.0) for l in plan_legs)
    else:  # ctx.objective == "cost"
        total_distance = sum(
            l.cross_metrics.get("distance", 0.0) for l in plan_legs
        )
        total_cost = sum(l.total_weight for l in plan_legs)

    # 行驶时间口径：cross_metrics["travel_time"] —— 与规划传播保持一致
    # （避免把主目标所选路径的 total_weight 错当行驶时间）。
    total_travel_time: float = sum(
        l.cross_metrics.get("travel_time", 0.0) for l in plan_legs
    )

    main_objective_total: float = (
        total_distance if ctx.objective == "distance" else total_cost
    )

    # is_feasible 取自 check_feasibility —— 算法不主动抛错，不伪造 100%
    feasibility_report = check_feasibility(
        stops=tuple(plan_stops),
        legs=tuple(plan_legs),
        capacity=ctx.capacity,
        service_time=ctx.service_time,
        initial_time=ctx.initial_time,
        depot_id=ctx.depot_id,
    )

    return RoutePlan(
        algorithm="nearest_neighbor",
        objective=ctx.objective,
        vehicle_id=ctx.vehicle.id,
        depot_id=ctx.depot_id,
        stop_sequence=stop_sequence,
        road_node_sequence=road_sequence,
        legs=tuple(plan_legs),
        stops=tuple(plan_stops),
        total_distance=total_distance,
        total_travel_time=total_travel_time,
        total_cost=total_cost,
        main_objective_total=main_objective_total,
        departure_time=ctx.initial_time,
        return_time=current_time,
        capacity=ctx.capacity,
        served_order_ids=served_order_ids,
        is_feasible=feasibility_report.is_feasible,
    )


__all__ = ["nearest_neighbor"]
