"""受约束 2-opt 局部搜索 —— Phase 3 第三种规划策略。

依据 AGENTS.md §3.7：

* **自主实现**：受约束 2-opt，仅在已有可行路线上做单车辆配送顺序改进；
* **路径来源**：相邻 leg 全部通过 ``ctx.path_provider`` 调用 Phase 2
  Dijkstra，禁止在 2-opt 内重写第二套最短路径子例程；
* **不接受不可行种子**：调用前 ``plan_seed.is_feasible`` 必须为 True，
  否则抛 :class:`InfeasibleSeedError`；
* **方向性 / 多 metric**：图为有向、三个 metric（``distance`` /
  ``travel_time`` / ``cost``）互不一致，必须**真正重建 leg**；
  不可套用无向图
  ``Δ = d(i,j) + d(i+1,j+1) - d(i,i+1) - d(j,j+1)`` 公式 —— 那样会
  把三个 metric 偷换成同一个数，违反 §3.7 多策略对比口径。

约定
----

* ``stop_sequence`` 形如 ``(depot, s1, s2, ..., sK, depot)``，内层 K 个
  配送站（K = ``len(stop_sequence) - 2``）；
* 2-opt 反转段 ``stop_seq[i+1 : j+1]``（``1 <= i < j <= K``），
  depot 端点永不参与反转；
* 策略：first-improvement —— 发现第一个严格改善的候选立即接受并重启外层
  扫描；
* 终止：本轮扫描无任何改善 OR 达到 ``K * K`` 轮扫描上限。

不动点
------

返回值 ``RoutePlan.is_feasible`` 一定为 True（构造过程只接受可行候选）。
若种子已无可改善余地，2-opt **不**新建候选，直接以 ``plan_seed`` 为基础
重新填充 ``RoadNodeSequence / total_* / notes["iterations"]=1`` 后返回。
"""

from __future__ import annotations

from typing import Any

from logiroute.algorithms.dijkstra import PathResult
from logiroute.scheduling.feasibility import _leg_drive_time, check_feasibility
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.types import (
    DeliveryStop,
    InfeasibleSeedError,
    PlanningContext,
    RoutePlan,
)


#: 浮点比较容差；任何 ``< -_EPS`` 的差值视为严格改善。
_EPS = 1e-9


# ---------------------------------------------------------------------------
#  内部辅助
# ---------------------------------------------------------------------------


def _rebuild_stops_with_timing(
    stop_seq: tuple[str, ...],
    legs: tuple[PathResult, ...],
    ctx: PlanningContext,
) -> tuple[DeliveryStop, ...]:
    """按 ``stop_seq + legs`` 重建带时间传播的 :class:`DeliveryStop` tuple。

    传播规则（与 ``insertion.py`` / ``nearest_neighbor.py`` 保持一致）：

    * depot 出发站（``i == 0``）：
      ``arrival = service_start = service_end = ctx.initial_time``；
    * 客户站（``1 <= i <= K``）：
      ``arrival = previous.service_end + drive_time(legs[i-1])``；
      ``service_start = max(arrival, order.time_window_start)``
      （早到记入 ``waiting_time``）；
      ``service_end = service_start + ctx.service_time``。
    * depot 回归站（``i == K+1``）：
      ``arrival = previous.service_end + drive_time(legs[-1])``，
      ``service_start = service_end = arrival``，仓库无时间窗与 demand。

    订单元数据（``order_id / demand / time_window_start / time_window_end``）
    通过 ``ctx.scenario.orders`` 按节点 ID 反查；若节点无订单（例如过路的
    中转站），则按"到达即服务 + service_time 处理"。

    Args:
        stop_seq: 闭合 stop 序列（含首尾 depot）；长度 ``K+2``。
        legs: 相邻 leg 序列（来自 ``ctx.path_provider.all_pairs``）；长度 ``K+1``。
        ctx: 调度上下文。

    Returns:
        长度 ``K+2`` 的 :class:`DeliveryStop` tuple。

    Time   : O(K) 线性。
    Space  : O(K)。
    """
    # 订单元数据按 destination_id 反查（首个匹配胜出；同一节点多个订单在
    # 调用方负责的更上层去重；本函数只关心快照元数据）。
    order_by_dest: dict[str, Any] = {}
    scenario = getattr(ctx, "scenario", None)
    for order in getattr(scenario, "orders", ()) or ():
        dest = getattr(order, "destination_id", None)
        oid = getattr(order, "id", None)
        if dest is not None and oid is not None and dest not in order_by_dest:
            order_by_dest[dest] = order

    stops: list[DeliveryStop] = []
    cumulative_load = 0.0
    n = len(stop_seq)

    for i, nid in enumerate(stop_seq):
        # ---- depot 出发 ----
        if i == 0:
            stops.append(
                DeliveryStop(
                    sequence_index=0,
                    node_id=nid,
                    arrival_time=ctx.initial_time,
                    service_start=ctx.initial_time,
                    service_end=ctx.initial_time,
                    waiting_time=0.0,
                    order_id=None,
                    demand=0.0,
                    cumulative_load=0.0,
                )
            )
            continue

        prev_stop = stops[i - 1]
        drive = _leg_drive_time(legs[i - 1])
        arrival = prev_stop.service_end + drive

        # ---- depot 回归 ----
        if i == n - 1:
            stops.append(
                DeliveryStop(
                    sequence_index=i,
                    node_id=nid,
                    arrival_time=arrival,
                    service_start=arrival,
                    service_end=arrival,
                    waiting_time=0.0,
                    order_id=None,
                    demand=0.0,
                    cumulative_load=cumulative_load,
                )
            )
            continue

        # ---- 客户 / 中转站 ----
        order = order_by_dest.get(nid)
        if order is None:
            waiting = 0.0
            service_start = arrival
            service_end = service_start + ctx.service_time
            stops.append(
                DeliveryStop(
                    sequence_index=i,
                    node_id=nid,
                    arrival_time=arrival,
                    service_start=service_start,
                    service_end=service_end,
                    waiting_time=waiting,
                )
            )
            continue

        tw_start = getattr(order, "time_window_start", None)
        tw_end = getattr(order, "time_window_end", None)
        demand = float(getattr(order, "demand", 0.0) or 0.0)
        waiting = 0.0
        if tw_start is not None and arrival < tw_start:
            waiting = float(tw_start) - arrival
        service_start = arrival + waiting
        service_end = service_start + ctx.service_time
        cumulative_load += demand
        stops.append(
            DeliveryStop(
                sequence_index=i,
                node_id=nid,
                arrival_time=arrival,
                service_start=service_start,
                service_end=service_end,
                waiting_time=waiting,
                order_id=getattr(order, "id", None),
                demand=demand,
                cumulative_load=cumulative_load,
                time_window_start=tw_start,
                time_window_end=tw_end,
            )
        )

    return tuple(stops)


def _main_total(
    stops: tuple[DeliveryStop, ...],
    legs: tuple[PathResult, ...],
    objective: str,
) -> float:
    """主目标累计权重。

    Args:
        stops: 仅保留参数（与 ``_rebuild_stops_with_timing`` 同形），
            不参与函数本体计算。
        legs: 候选 / 当前路径的 leg tuple。
        objective: ``"distance"`` 或 ``"cost"``；决定 ``leg.total_weight`` 的
            语义。

    Returns:
        所有 leg 的 ``total_weight`` 之和（float）。

    Raises:
        ValueError: ``objective`` 不在白名单。

    Time   : O(K)。
    Space  : O(1)。
    """
    if objective not in ("distance", "cost"):
        raise ValueError(
            f"objective must be 'distance' or 'cost', got {objective!r}"
        )
    # ``stops`` 仅保持调用对称性（与上层构造路径如 _rebuild_stops_with_timing
    # 同时传入），自身不被读取。
    del stops
    return float(sum(leg.total_weight for leg in legs))


def _route_plan_from_state(
    stop_seq: tuple[str, ...],
    legs: tuple[PathResult, ...],
    stops: tuple[DeliveryStop, ...],
    total: float,
    iterations_done: int,
    ctx: PlanningContext,
) -> RoutePlan:
    """用最终 ``stop_seq / legs / stops`` 重新组装 :class:`RoutePlan`。

    集中处理 ``RoadNodeSequence / total_* / notes / courier_id`` 等公共字段，
    保证算法主循环与不可变组装解耦。

    Time   : O(K + L)（L 为拼接后道路节点数）。
    Space  : O(L)。
    """
    pp: PathProvider = ctx.path_provider
    road_seq = pp.road_node_sequence(stop_seq, ctx.objective)

    total_distance = sum(
        leg.cross_metrics.get("distance", leg.total_weight) for leg in legs
    )
    total_travel_time = sum(
        leg.cross_metrics.get("travel_time", leg.total_weight) for leg in legs
    )
    total_cost = sum(
        leg.cross_metrics.get("cost", leg.total_weight) for leg in legs
    )

    served: tuple[str, ...] = tuple(
        s.order_id for s in stops if s.order_id is not None
    )
    courier_obj = ctx.courier
    courier_id = getattr(courier_obj, "id", None) if courier_obj else None
    return_time = stops[-1].service_end if stops else ctx.initial_time

    return RoutePlan(
        algorithm="two_opt",
        objective=ctx.objective,
        vehicle_id=ctx.vehicle.id,
        courier_id=courier_id,
        depot_id=ctx.depot_id,
        stop_sequence=stop_seq,
        road_node_sequence=road_seq,
        legs=legs,
        stops=stops,
        total_distance=total_distance,
        total_travel_time=total_travel_time,
        total_cost=total_cost,
        main_objective_total=float(total),
        departure_time=ctx.initial_time,
        return_time=return_time,
        capacity=ctx.capacity,
        served_order_ids=served,
        is_feasible=True,
        notes={"iterations": iterations_done},
    )


# ---------------------------------------------------------------------------
#  主入口
# ---------------------------------------------------------------------------


def constrained_two_opt(
    plan_seed: RoutePlan,
    ctx: PlanningContext,
) -> RoutePlan:
    """受约束 2-opt 局部搜索（first-improvement）。

    反向 Δ 公式不适用（图为有向、三 metric 不一致），每次反转段后必须真正
    通过 ``ctx.path_provider.all_pairs`` 重建 leg，再判断是否改善。

    硬规则：传入的 ``plan_seed.is_feasible`` 必须为 ``True``；否则立即抛
    :class:`InfeasibleSeedError`，**不**调用 Dijkstra。

    Args:
        plan_seed: 上一阶段（NN / CFI）产出的可行闭合路线。
        ctx: 调度作用域上下文。

    Returns:
        新的 :class:`RoutePlan`，``is_feasible=True``，``main_objective_total``
        不大于种子；``notes["iterations"]`` 记录实际完成的扫描轮数。

    Raises:
        InfeasibleSeedError: ``plan_seed.is_feasible is False``。

    Time   : 最坏 O(K^3 · (V + E) log V) —— K^2 对 + 每次重建 leg。
    Space  : O(K) 候选缓存。
    """
    # ---- 硬规则：拒绝不可行种子 ----------------------------------------
    if not plan_seed.is_feasible:
        raise InfeasibleSeedError(
            "refusing 2-opt on infeasible seed: "
            f"plan_seed.is_feasible=False "
            f"(depot={plan_seed.depot_id!r}, "
            f"stops={len(plan_seed.stop_sequence)})"
        )

    stop_seq: tuple[str, ...] = plan_seed.stop_sequence
    K = len(stop_seq) - 2
    iter_cap = K * K

    # 0 / 1 个内层站：2-opt 无意义，直接按种子重填（保持 is_feasible=True）。
    if K < 2:
        return _route_plan_from_state(
            stop_seq=plan_seed.stop_sequence,
            legs=tuple(plan_seed.legs),
            stops=plan_seed.stops,
            total=plan_seed.main_objective_total,
            iterations_done=0,
            ctx=ctx,
        )

    pp: PathProvider = ctx.path_provider

    current_stops: tuple[DeliveryStop, ...] = plan_seed.stops
    current_legs: tuple[PathResult, ...] = tuple(plan_seed.legs)
    current_total: float = float(plan_seed.main_objective_total)
    current_stop_seq: tuple[str, ...] = stop_seq

    iterations_done = 0
    improved = True

    while improved and iterations_done < iter_cap:
        improved = False
        iterations_done += 1
        # first-improvement：i 从小到大、j 从小到大；找到首个严格改善即重启。
        for i in range(1, K):
            for j in range(i + 1, K + 1):
                candidate = (
                    current_stop_seq[: i + 1]
                    + tuple(reversed(current_stop_seq[i + 1 : j + 1]))
                    + current_stop_seq[j + 1 :]
                )
                cand_legs_list = pp.all_pairs(candidate, ctx.objective)
                # 任一腿不可达 → 候选直接否决（RoutePlan 不可构造）。
                if any(not leg.reachable for leg in cand_legs_list):
                    continue
                cand_legs: tuple[PathResult, ...] = tuple(cand_legs_list)
                cand_stops = _rebuild_stops_with_timing(
                    candidate, cand_legs, ctx
                )
                cand_report = check_feasibility(
                    cand_stops,
                    cand_legs,
                    ctx.capacity,
                    ctx.service_time,
                    ctx.initial_time,
                    ctx.depot_id,
                )
                if not cand_report.is_feasible:
                    continue
                cand_total = _main_total(cand_stops, cand_legs, ctx.objective)
                if cand_total < current_total - _EPS:
                    current_stop_seq = candidate
                    current_stops = cand_stops
                    current_legs = cand_legs
                    current_total = cand_total
                    improved = True
                    break
            if improved:
                break

    return _route_plan_from_state(
        stop_seq=current_stop_seq,
        legs=current_legs,
        stops=current_stops,
        total=current_total,
        iterations_done=iterations_done,
        ctx=ctx,
    )


__all__ = ["constrained_two_opt"]