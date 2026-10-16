"""Phase 3 单车调度 —— Cheapest Feasible Insertion（可行插入构造）。

依据 AGENTS.md §3.7 自主约束：

* 算法核心：可行插入（Cheapest Feasible Insertion，CFI）—— 反复在已有可行
  路线上为剩余订单寻找"满足硬约束 + 主目标增量最小"的插入位置；
* 路径来源：所有相邻配送站点之间的有向最短路径 **必须** 调用
  :class:`logiroute.scheduling.path_provider.PathProvider.shortest_path`；
  本模块不重复实现最短路径；
* 主目标：``distance`` / ``cost`` 二选一；``travel_time`` 仅作为附加对比；
* 时间窗：``service_start <= time_window_end`` 为硬约束；早到计入等待；
* 闭合度：起止节点均必须是 :class:`PlanningContext.depot_id`；
* 不可伪造完成率：若某订单无可行插入位置 → 写入 :class:`RoutePlan.notes`
  ``['unserved_orders']``，``kind="no_feasible_insertion"``；
* 不使用 :func:`heapq` / :func:`sorted` / NumPy 等禁表工具；候选位置求
  ``argmin`` 使用手写线性扫描（与 §3.7"手写堆 / 手写排序"要求一致）。

设计要点：

* **不**依赖 :mod:`logiroute.scheduling.algorithms.nearest_neighbor` 实现
  种子构造：单订单场景下的 NN 与"depot → order → depot"两点闭回路等价，
  本模块直接构造该种子以减少跨模块耦合；
* 内部使用 :class:`_TourState` 维护"站点序列 / 腿序列 / 已服务订单"的可变
  快照，避免对 :class:`RoutePlan` 做不可变重建；
* 全部公开入口 (:func:`cheapest_feasible_insertion`) 返回不可变
  :class:`RoutePlan`；不可行订单由调用方从
  :attr:`RoutePlan.notes` ``['unserved_orders']`` 读取。

Time   : O(M · K² · ((V + E) log V))，M = 候选订单总数，K = 当前路线站数。
Space  : O(K + (V + E))。
"""

from __future__ import annotations

from collections import namedtuple
from typing import Sequence

from logiroute.algorithms.dijkstra import PathResult
from logiroute.core.enums import OrderPriority
from logiroute.core.orders import Order
from logiroute.scheduling.feasibility import _leg_drive_time, check_feasibility
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.types import (
    DeliveryStop,
    InfeasibleSeedError,
    PlanningContext,
    RoutePlan,
    Violation,
)


# ---------------------------------------------------------------------------
#  内部数据结构
# ---------------------------------------------------------------------------


#: 单个 stop 在路线中的最小信息：节点 ID + 对应订单（None 表示仓库端点）。
_StopInfo = namedtuple("_StopInfo", ["node_id", "order"])


#: 候选插入 (delta, order_id, pos) 三元组，用于 ``argmin`` 确定性比较。
#: ``delta`` 越小越好；``order_id`` ASC 作为 tie-break；``pos`` ASC 作为
#: 次级 tie-break（保证相同 delta 不同插入位置时取最小 pos）。
class _TourState:
    """CFI 主循环维护的可变路线状态。

    Notes:
        * :pyattr:`stops` / :pyattr:`legs` 长度始终满足
          ``len(stops) == len(legs) + 1``；
        * :pyattr:`stop_infos` 是"含仓库端点的命名元组列表"，其中索引 0 与
          ``K+1`` 的 ``order`` 为 ``None``，中间各索引为对应 :class:`Order`；
        * :pyattr:`served_order_ids` 由 :pyattr:`stop_infos` 派生，构造时
          一次性物化以避免重复扫描。
    """

    __slots__ = (
        "stops",
        "legs",
        "stop_sequence",
        "stop_infos",
        "served_order_ids",
    )

    def __init__(
        self,
        stops: tuple[DeliveryStop, ...],
        legs: tuple[PathResult, ...],
        stop_infos: tuple[_StopInfo, ...],
    ) -> None:
        if len(stops) != len(legs) + 1:
            raise ValueError(
                f"_TourState schema violation: len(stops)={len(stops)} "
                f"must equal len(legs)+1={len(legs) + 1}"
            )
        if len(stop_infos) != len(stops):
            raise ValueError(
                f"_TourState schema violation: len(stop_infos)="
                f"{len(stop_infos)} must equal len(stops)={len(stops)}"
            )
        node_ids = tuple(s.node_id for s in stops)
        for info, nid in zip(stop_infos, node_ids):
            if info.node_id != nid:
                raise ValueError(
                    "_TourState schema violation: stop_infos.node_id "
                    "must match stops.node_id elementwise"
                )
        self.stops: tuple[DeliveryStop, ...] = stops
        self.legs: tuple[PathResult, ...] = legs
        self.stop_sequence: tuple[str, ...] = node_ids
        self.stop_infos: tuple[_StopInfo, ...] = stop_infos
        self.served_order_ids: tuple[str, ...] = tuple(
            info.order.id
            for info in stop_infos
            if info.order is not None
        )

    def main_total_for(self, metric: str) -> float:
        """按指定 metric 累加（仅支持 distance / cost）。"""
        return _main_total(self.legs, metric)


# ---------------------------------------------------------------------------
#  工具：站点构造与传播
# ---------------------------------------------------------------------------


def _depot_start_stop(ctx: PlanningContext) -> DeliveryStop:
    """构造出发仓库的 :class:`DeliveryStop`（sequence_index=0）。"""
    return DeliveryStop(
        sequence_index=0,
        node_id=ctx.depot_id,
        arrival_time=ctx.initial_time,
        service_start=ctx.initial_time,
        service_end=ctx.initial_time,
        waiting_time=0.0,
        order_id=None,
        demand=0.0,
        cumulative_load=0.0,
        time_window_start=None,
        time_window_end=None,
    )


def _depot_end_stop(
    ctx: PlanningContext,
    seq_index: int,
    arrival_time: float,
) -> DeliveryStop:
    """构造返回仓库的 :class:`DeliveryStop`（无服务）。"""
    return DeliveryStop(
        sequence_index=seq_index,
        node_id=ctx.depot_id,
        arrival_time=arrival_time,
        service_start=arrival_time,
        service_end=arrival_time,
        waiting_time=0.0,
        order_id=None,
        demand=0.0,
        cumulative_load=0.0,
        time_window_start=None,
        time_window_end=None,
    )


def _rebuild_stops_with_timing(
    stop_infos: tuple[_StopInfo, ...],
    legs: tuple[PathResult, ...],
    ctx: PlanningContext,
) -> tuple[DeliveryStop, ...]:
    """依据 ``stop_infos`` 与 ``legs`` 重新传播各 stop 的时间字段。

    规则（与 :func:`check_feasibility` 一致）：

    * ``stops[0]`` 为出发仓库：``arrival/service_start/service_end = ctx.initial_time``；
    * ``stops[i]``（i ≥ 1）：``arrival = stops[i-1].service_end + _leg_drive_time(legs[i-1])``；
    * 若 ``stop_infos[i].order is None``（仓库端点）→ ``service_start/service_end = arrival``；
    * 否则 ``wait = max(0, tw_start - arrival)``；
      ``service_start = arrival + wait``；
      ``service_end = service_start + ctx.service_time``；
      ``cumulative_load`` 逐站累加 ``demand``。

    Time   : O(K)。
    Space  : O(K)。
    """
    if len(stop_infos) != len(legs) + 1:
        raise ValueError(
            f"len(stop_infos) ({len(stop_infos)}) must equal "
            f"len(legs) + 1 ({len(legs) + 1})"
        )

    stops: list[DeliveryStop] = []
    cum_load = 0.0
    for i, info in enumerate(stop_infos):
        if i == 0:
            stops.append(_depot_start_stop(ctx))
            continue
        leg = legs[i - 1]
        arrival = stops[i - 1].service_end + _leg_drive_time(leg)
        if info.order is None:
            stops.append(_depot_end_stop(ctx, i, arrival))
        else:
            order = info.order
            wait = max(0.0, order.time_window_start - arrival)
            service_start = arrival + wait
            service_end = service_start + ctx.service_time
            cum_load += order.demand
            stops.append(
                DeliveryStop(
                    sequence_index=i,
                    node_id=info.node_id,
                    arrival_time=arrival,
                    service_start=service_start,
                    service_end=service_end,
                    waiting_time=wait,
                    order_id=order.id,
                    demand=order.demand,
                    cumulative_load=cum_load,
                    time_window_start=order.time_window_start,
                    time_window_end=order.time_window_end,
                )
            )
    return tuple(stops)


def _main_total(legs: Sequence[PathResult], metric: str) -> float:
    """主目标累计：``sum(leg.total_weight)``。

    ``leg.total_weight`` 在 :class:`PathProvider` 中已按 ``metric`` 缓存；
    此处仅做求和，不重新计算最短路。

    Time : O(K)。
    Space: O(1)。
    """
    if metric not in ("distance", "cost"):
        raise ValueError(
            f"main objective must be 'distance' or 'cost', got {metric!r}"
        )
    return float(sum(leg.total_weight for leg in legs))


# ---------------------------------------------------------------------------
#  种子构造
# ---------------------------------------------------------------------------


def _order_first_stop_feasible(
    ctx: PlanningContext,
    order: Order,
) -> bool:
    """判断订单能否作为"depot → order → depot"单段种子。

    判定口径：

    * ``order.demand <= ctx.capacity``；
    * depot → 客户 → 仓库回程双 leg 均可达；
    * 首站 ``arrival_time <= time_window_end``（这样 ``service_start`` 落在
      窗口内，符合 AGENTS §3.7 的硬约束）。

    Time : O((V + E) log V)。
    Space: O(1)。
    """
    if order.demand > ctx.capacity + 1e-9:
        return False

    leg_out = ctx.path_provider.shortest_path(
        ctx.depot_id, order.destination_id, ctx.objective
    )
    if not leg_out.reachable:
        return False
    arrival = ctx.initial_time + _leg_drive_time(leg_out)
    if arrival > order.time_window_end + 1e-9:
        return False

    leg_back = ctx.path_provider.shortest_path(
        order.destination_id, ctx.depot_id, ctx.objective
    )
    return bool(leg_back.reachable)


def _first_feasible_seed(
    ctx: PlanningContext,
    eligible: Sequence[Order],
) -> Order | None:
    """从 ``eligible`` 中选出 CFI 的种子订单。

    规则：

    1. 仅保留 :func:`_order_first_stop_feasible` 通过的订单；
    2. URGENT 优先于 NORMAL；
    3. 同优先级按 ``order.id`` ASC tie-break。

    若无候选，返回 ``None``。手写插入排序（``M²``），避免
    :func:`sorted` / :func:`heapq` 等禁表。

    Time   : O(M · ((V + E) log V) + M²)。
    Space  : O(M)。
    """
    feasible: list[Order] = []
    for order in eligible:
        if _order_first_stop_feasible(ctx, order):
            feasible.append(order)
    if not feasible:
        return None

    priority_rank = {OrderPriority.URGENT: 0, OrderPriority.NORMAL: 1}
    # 手写插入排序
    for i in range(1, len(feasible)):
        cur_item = feasible[i]
        j = i
        while j > 0:
            prev = feasible[j - 1]
            cur_rank = priority_rank.get(cur_item.priority, 99)
            prev_rank = priority_rank.get(prev.priority, 99)
            better = (
                cur_rank < prev_rank
                or (cur_rank == prev_rank and cur_item.id < prev.id)
            )
            if not better:
                break
            feasible[j] = prev
            j -= 1
        feasible[j] = cur_item
    return feasible[0]


def _build_seed_state(
    ctx: PlanningContext,
    seed_order: Order,
) -> _TourState:
    """为单个订单构造 depot → order → depot 闭回路 :class:`_TourState`。

    Time : O((V + E) log V)。
    Space: O(K)。
    """
    stop_sequence = (ctx.depot_id, seed_order.destination_id, ctx.depot_id)
    legs = tuple(
        ctx.path_provider.shortest_path(s, t, ctx.objective)
        for s, t in zip(stop_sequence[:-1], stop_sequence[1:])
    )
    stop_infos = (
        _StopInfo(ctx.depot_id, None),
        _StopInfo(seed_order.destination_id, seed_order),
        _StopInfo(ctx.depot_id, None),
    )
    stops = _rebuild_stops_with_timing(stop_infos, legs, ctx)
    return _TourState(stops=stops, legs=legs, stop_infos=stop_infos)


def _build_empty_state(ctx: PlanningContext) -> _TourState:
    """构造空路线 ``(depot, depot)`` 的 :class:`_TourState`（0 服务）。"""
    leg = ctx.path_provider.shortest_path(
        ctx.depot_id, ctx.depot_id, ctx.objective
    )
    stop_sequence = (ctx.depot_id, ctx.depot_id)
    stop_infos = (
        _StopInfo(ctx.depot_id, None),
        _StopInfo(ctx.depot_id, None),
    )
    stops = _rebuild_stops_with_timing(stop_infos, (leg,), ctx)
    return _TourState(stops=stops, legs=(leg,), stop_infos=stop_infos)


# ---------------------------------------------------------------------------
#  候选插入评估
# ---------------------------------------------------------------------------


#: ``_try_insert`` 返回值：(new_state, delta, pos_chosen)
#: pos 用于外层 (delta, order_id, pos) tie-break（虽然内部已确定性选择），
#: 但仍保留以保留位置信息供后续扩展。
def _try_insert(
    state: _TourState,
    ctx: PlanningContext,
    candidate_order: Order,
) -> tuple[_TourState, float, int] | None:
    """对 ``candidate_order`` 在 ``state`` 的配送站间枚举插入位置，返回最佳。

    步骤：

    1. 对每个 ``pos in [1, len(state.stop_infos) - 1)``（仅配送站之间）：

       a. 构造 ``trial_infos = state.stop_infos[:pos] + [candidate_info] + state.stop_infos[pos:]``；
       b. 调 :meth:`PathProvider.shortest_path` 取新 ``legs``（缓存命中）；
       c. 任一 leg 不可达：跳过该位置；
       d. :func:`_rebuild_stops_with_timing` 重算 ``stops``；
       e. :func:`check_feasibility` 检查；
       f. 若可行 → 计算 ``delta = new_main - state.main_total``；

    2. 用手写 ``argmin``（按 ``(delta, pos)``）选最佳（同一 order 内）；
    3. 若无任何位置可行 → 返回 ``None``；
    4. 返回 ``(new_state, delta_min, pos_chosen)``。

    Time : O(K · ((V + E) log V))。
    """
    candidate_info = _StopInfo(candidate_order.destination_id, candidate_order)
    # 有效插入位置：[1, len(stop_infos))。
    # 例如 stop_infos = (depot, OU, depot)（长度 3）→ pos ∈ {1, 2}，
    # 即"在 OU 之前"与"在 OU 之后"。
    pos_upper_exclusive = len(state.stop_infos)
    current_main = state.main_total_for(ctx.objective)

    best_state: _TourState | None = None
    best_delta: float = float("inf")
    best_pos: int = -1

    for pos in range(1, pos_upper_exclusive):
        trial_infos: tuple[_StopInfo, ...] = (
            state.stop_infos[:pos]
            + (candidate_info,)
            + state.stop_infos[pos:]
        )
        trial_sequence = tuple(s.node_id for s in trial_infos)
        trial_legs = tuple(
            ctx.path_provider.shortest_path(s, t, ctx.objective)
            for s, t in zip(trial_sequence[:-1], trial_sequence[1:])
        )
        if any(not leg.reachable for leg in trial_legs):
            continue

        trial_stops = _rebuild_stops_with_timing(
            trial_infos, trial_legs, ctx
        )
        report = check_feasibility(
            stops=trial_stops,
            legs=trial_legs,
            capacity=ctx.capacity,
            service_time=ctx.service_time,
            initial_time=ctx.initial_time,
            depot_id=ctx.depot_id,
        )
        if not report.is_feasible:
            continue

        delta = _main_total(trial_legs, ctx.objective) - current_main
        # 手写 argmin: (delta ASC, pos ASC)
        if delta < best_delta or (delta == best_delta and pos < best_pos):
            best_delta = delta
            best_pos = pos
            best_state = _TourState(
                stops=trial_stops,
                legs=trial_legs,
                stop_infos=trial_infos,
            )

    if best_state is None:
        return None
    return best_state, best_delta, best_pos


# ---------------------------------------------------------------------------
#  装配 RoutePlan
# ---------------------------------------------------------------------------


def _build_route_plan(
    ctx: PlanningContext,
    state: _TourState,
    *,
    unserved_orders: tuple[Violation, ...] = (),
    algorithm_label: str = "cheapest_feasible_insertion",
) -> RoutePlan:
    """由 :class:`_TourState` 装配 :class:`RoutePlan`。

    主目标 / 行驶时间 / 距离 / 成本 均从 ``state.legs`` 的
    ``cross_metrics`` 与 ``total_weight`` 累加（与 NN 风格一致）。

    Time : O(K) leg 累计 + O(L) road sequence 拼接。
    Space: O(L)。
    """
    legs = state.legs
    total_distance = sum(
        leg.cross_metrics.get("distance", leg.total_weight) for leg in legs
    )
    total_travel_time = sum(
        leg.cross_metrics.get("travel_time", leg.total_weight) for leg in legs
    )
    total_cost = sum(
        leg.cross_metrics.get("cost", leg.total_weight) for leg in legs
    )
    if ctx.objective == "distance":
        main_total_for_check = total_distance
    else:
        main_total_for_check = total_cost

    road_sequence = ctx.path_provider.road_node_sequence(
        state.stop_sequence, ctx.objective
    )

    report = check_feasibility(
        stops=state.stops,
        legs=legs,
        capacity=ctx.capacity,
        service_time=ctx.service_time,
        initial_time=ctx.initial_time,
        depot_id=ctx.depot_id,
    )

    notes: dict[str, object] = {}
    if unserved_orders:
        notes["unserved_orders"] = tuple(
            v.to_dict() for v in unserved_orders
        )

    return RoutePlan(
        algorithm=algorithm_label,
        objective=ctx.objective,
        vehicle_id=ctx.vehicle.id,
        depot_id=ctx.depot_id,
        stop_sequence=state.stop_sequence,
        road_node_sequence=road_sequence,
        legs=legs,
        stops=state.stops,
        total_distance=total_distance,
        total_travel_time=total_travel_time,
        total_cost=total_cost,
        main_objective_total=main_total_for_check,
        departure_time=ctx.initial_time,
        return_time=state.stops[-1].arrival_time,
        capacity=ctx.capacity,
        served_order_ids=state.served_order_ids,
        is_feasible=report.is_feasible,
        courier_id=(ctx.courier.id if ctx.courier is not None else None),
        notes=notes,
    )


def _make_unserved_violation(order: Order, reason: str) -> Violation:
    """构造 ``kind="no_feasible_insertion"`` 的 :class:`Violation`。"""
    return Violation(
        order_id=order.id,
        kind="no_feasible_insertion",
        message=reason,
    )


# ---------------------------------------------------------------------------
#  公开入口
# ---------------------------------------------------------------------------


def cheapest_feasible_insertion(
    ctx: PlanningContext,
    eligible_orders: Sequence[Order],
    seed_algorithm: str = "nearest_neighbor",
) -> RoutePlan:
    """Cheapest Feasible Insertion 单车闭合调度。

    算法步骤：

    1. **空集合**：若 ``eligible_orders`` 为空 → ``(depot, depot)`` 0 服务
       空路线；``is_feasible=True``；``served_order_ids=()``。
    2. **种子构造**：从 ``eligible_orders`` 中筛选"首段可达 + demand ≤ 容量 +
       首站 time window 不迟到"的子集；按 URGENT 优先 + ``order.id`` ASC 选
       一个 ``s_seed``。若无任何合格种子 → 抛 :class:`InfeasibleSeedError`。
    3. **主循环**：当 ``remaining`` 非空且当前 plan 可行：

       a. 对每个 ``order ∈ remaining``，枚举配送站间所有插入位置
          ``pos ∈ [1, len(plan_stops) - 1)``，调 :func:`_try_insert` 求
          "delta_main 最小" 的可行 trial；
       b. 若所有 order 均无可行位置 → 把剩余全部作为
          ``kind="no_feasible_insertion"`` 的 :class:`Violation` 收集，
          并退出主循环；
       c. 否则应用最佳 trial，更新 ``state`` 与 ``remaining``。

    4. **装配** :class:`RoutePlan`（与 NN 同口径）：
       ``total_distance / total_travel_time / total_cost`` 自
       ``leg.cross_metrics`` 累加；``main_objective_total`` 对应主目标列；
       ``is_feasible = check_feasibility(...).is_feasible``。

    Args:
        ctx: 单次调度作用域上下文。
        eligible_orders: 候选订单列表（已通过订单层校验）。
        seed_algorithm: 种子算法标识；当前唯一支持 ``"nearest_neighbor"``，
            由本模块内部等价构造。其它取值 → :class:`ValueError`。

    Returns:
        :class:`RoutePlan`：单车闭合回路，含主目标累计、可行性标记与未服务
        订单（写入 ``notes['unserved_orders']`` 供上层 planner 装配）。

    Raises:
        ValueError: ``seed_algorithm`` 不在白名单内。
        InfeasibleSeedError: ``eligible_orders`` 中不存在任何能作为"首段可达
            + 容量合法 + 首站 time window 不迟到"的种子订单。

    Time   : O(M · K² · ((V + E) log V))，M = 候选订单总数，
             K = 当前路线配送站数。
    Space  : O(K + (V + E))。
    """
    if seed_algorithm != "nearest_neighbor":
        raise ValueError(
            f"unknown seed_algorithm: {seed_algorithm!r}; "
            "only 'nearest_neighbor' is currently supported"
        )

    # ---- 0. 空集合快速返回 ----------------------------------------------
    if not eligible_orders:
        empty_state = _build_empty_state(ctx)
        return _build_route_plan(ctx, empty_state)

    # ---- 1. 种子选择 -----------------------------------------------------
    seed = _first_feasible_seed(ctx, eligible_orders)
    if seed is None:
        reasons: list[str] = []
        for o in eligible_orders:
            if o.demand > ctx.capacity + 1e-9:
                reasons.append(
                    f"{o.id}: demand {o.demand} > capacity {ctx.capacity}"
                )
            else:
                leg = ctx.path_provider.shortest_path(
                    ctx.depot_id, o.destination_id, ctx.objective
                )
                if not leg.reachable:
                    reasons.append(f"{o.id}: unreachable from depot")
                else:
                    arrival = ctx.initial_time + _leg_drive_time(leg)
                    if arrival > o.time_window_end + 1e-9:
                        reasons.append(
                            f"{o.id}: arrival {arrival} > tw_end "
                            f"{o.time_window_end}"
                        )
        raise InfeasibleSeedError(
            "no feasible first order; "
            + ("; ".join(reasons) if reasons else "empty reasons")
        )

    # ---- 2. 主循环 ------------------------------------------------------
    current = _build_seed_state(ctx, seed)
    remaining: list[Order] = [
        o for o in eligible_orders if o.id != seed.id
    ]
    unserved: list[Violation] = []

    while remaining:
        # 检查当前 plan 是否仍可行；不可行即终止
        current_report = check_feasibility(
            stops=current.stops,
            legs=current.legs,
            capacity=ctx.capacity,
            service_time=ctx.service_time,
            initial_time=ctx.initial_time,
            depot_id=ctx.depot_id,
        )
        if not current_report.is_feasible:
            for o in remaining:
                unserved.append(
                    _make_unserved_violation(
                        o,
                        "current plan already infeasible",
                    )
                )
            remaining = []
            break

        # 在 remaining 中找出"全局 delta 最小"的最佳插入。
        # 手写 argmin over (order, pos)：与 NN 的最近邻候选扫描同风格，
        # 逐 order × 位置扫描，手写最小值比较，不调 sorted()/min()。
        best_state: _TourState | None = None
        best_delta: float = float("inf")
        best_order_id: str = ""
        best_pos: int = 0

        for order in remaining:
            tried = _try_insert(current, ctx, order)
            if tried is None:
                continue
            new_state, delta, pos = tried
            # 确定性比较：(delta ASC, order.id ASC, pos ASC)
            cand_key = (delta, order.id, pos)
            best_key = (best_delta, best_order_id, best_pos)
            if cand_key < best_key:
                best_state = new_state
                best_delta = delta
                best_order_id = order.id
                best_pos = pos

        if best_state is None:
            for o in remaining:
                unserved.append(
                    _make_unserved_violation(
                        o,
                        "no feasible insertion position found",
                    )
                )
            remaining = []
            break

        # 应用最佳 trial
        current = best_state
        for i, o in enumerate(remaining):
            if o.id == best_order_id:
                remaining.pop(i)
                break

    # ---- 3. 装配 RoutePlan -----------------------------------------------
    return _build_route_plan(ctx, current, unserved_orders=tuple(unserved))


__all__ = ["cheapest_feasible_insertion"]