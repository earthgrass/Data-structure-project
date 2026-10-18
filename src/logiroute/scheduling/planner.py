"""``plan_deliveries`` —— Phase 3 单车辆调度的统一入口。

职责：

* 校验 ``algorithm / objective`` 白名单；
* 自动选仓库、车辆、跟车配送员（:func:`select_depot`）；
* 在调度作用域内构造 :class:`PathProvider`，自然丢弃缓存；
* 把 NN / CFI / 2-opt 三个算法的统一输出装配为 :class:`ScheduleResult`；
* 用 ``time.monotonic()`` 度量墙钟；
* 把各算法报告的 unserved 订单 / Violation 提升到结果顶层。

拒绝多车辆（AGENTS §3.6）；不允许拆单；不可行订单如实记录。
"""

from __future__ import annotations

import time
from typing import Any

from logiroute.algorithms.dijkstra import SUPPORTED_METRICS  # noqa: F401
from logiroute.config.loader import ScenarioBundle
from logiroute.core.orders import Order
from logiroute.scheduling.algorithms import ALGORITHM_NAMES
from logiroute.scheduling.algorithms.insertion import (
    cheapest_feasible_insertion,
)
from logiroute.scheduling.algorithms.nearest_neighbor import nearest_neighbor
from logiroute.scheduling.algorithms.two_opt import constrained_two_opt
from logiroute.scheduling.algorithms.unified import unified_planner
from logiroute.scheduling.depot import select_depot
from logiroute.scheduling.feasibility import check_feasibility
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.types import (
    EmptyOrdersError,
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


#: 单一主目标白名单 —— ``travel_time`` 不允许作主目标（AGENTS §3.7）。
ALLOWED_OBJECTIVES: tuple[str, ...] = ("distance", "cost")


# ---------------------------------------------------------------------------
#  eligibility filter
# ---------------------------------------------------------------------------


def _filter_eligible(
    scenario: ScenarioBundle,
) -> tuple[list[Order], list[Violation]]:
    """剔除明显不能服务的订单，并把它们记录为 unserved violations。

    规则：

    * ``Order.destination_id`` 不在图中 → ``unreachable_leg`` 拒绝；
    * ``Order.demand`` > 车辆容量 → 越过单次容量硬约束 → ``capacity_overflow``；
    * ``Order.time_window_end <= time_window_start`` 已经由 ``Order.__post_init__``
      拦截（场景加载时已校验），此处不重复。

    Returns ``(eligible, unserved)``。
    """
    eligible: list[Order] = []
    unserved: list[Violation] = []
    known_ids = set(scenario.graph.node_ids)
    capacity = max((v.capacity for v in scenario.vehicles), default=0.0)

    for order in scenario.orders:
        if order.destination_id not in known_ids:
            unserved.append(
                Violation(
                    order_id=order.id,
                    kind="unreachable_leg",
                    message=(
                        f"destination_id={order.destination_id!r} not in graph"
                    ),
                )
            )
            continue
        if order.demand > capacity:
            unserved.append(
                Violation(
                    order_id=order.id,
                    kind="capacity_overflow",
                    message=(
                        f"order {order.id!r} demand={order.demand} "
                        f"exceeds max vehicle capacity={capacity}"
                    ),
                )
            )
            continue
        eligible.append(order)
    return eligible, unserved


def _lift_unserved_from_notes(plan: RoutePlan) -> list[Violation]:
    """从 :class:`RoutePlan.notes['unserved_orders']` 恢复 :class:`Violation` 列表。

    当前仅 :class:`cheapest_feasible_insertion` 通过该通道上报 unserved；
    其它算法调用方负责外部 unserved 装配（见 :func:`_assemble_schedule`）。
    """
    raw = plan.notes.get("unserved_orders", ())
    out: list[Violation] = []
    for item in raw:
        out.append(
            Violation(
                order_id=item.get("order_id"),
                kind=item["kind"],
                message=item["message"],
            )
        )
    return out


def _unserved_for_nn(
    plan: RoutePlan,
    eligible_orders: list[Order],
) -> list[Violation]:
    """NN 不通过 notes 通道上报 unserved —— 由 planner 计算 ``eligible − served``。"""
    served_set = set(plan.served_order_ids)
    out: list[Violation] = []
    for order in eligible_orders:
        if order.id in served_set:
            continue
        out.append(
            Violation(
                order_id=order.id,
                kind="no_feasible_next_step",
                message=(
                    f"order {order.id!r} (destination={order.destination_id!r}) "
                    "could not be reached from any chosen NN step while satisfying "
                    "capacity / time-window constraints"
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
#  counter wrapper around check_feasibility
# ---------------------------------------------------------------------------


class _FeasibilityCounter:
    """包装 ``check_feasibility`` 用于统计调用次数。"""

    __slots__ = ("count",)

    def __init__(self) -> None:
        self.count: int = 0

    def __call__(
        self,
        stops: tuple,
        legs: tuple,
        capacity: float,
        service_time: float,
        initial_time: float,
        depot_id: str,
    ):
        self.count += 1
        return check_feasibility(
            stops, legs, capacity, service_time, initial_time, depot_id
        )


# ---------------------------------------------------------------------------
#  plan_deliveries
# ---------------------------------------------------------------------------


def plan_deliveries(
    scenario: ScenarioBundle,
    algorithm: str = "unified",
    objective: str = "distance",
    depot_id: str | None = None,
    initial_time: float | None = None,
) -> ScheduleResult:
    """单车辆闭合回路规划统一入口。

    Phase 5 默认接口：``plan_deliveries(scenario, objective)``。

    Args:
        scenario: 加载完毕的 :class:`ScenarioBundle`。
        algorithm: 默认 ``"unified"``（NN / CFI 双种子 + 受约束 2-opt）；
            其它保留值 ``"nearest_neighbor"`` / ``"insertion"`` / ``"two_opt"``
            用于回归测试与实验比较，**不**作为产品公开 API。
        objective: 主目标 ``"distance"`` 或 ``"cost"``；``travel_time`` 拒绝。
        depot_id: 显式仓库；``None`` 时自动选 lex-min IDLE 车辆所在仓库。
        initial_time: 出发时刻；``None`` 时取 ``scenario.simulation["initial_time"]``。

    Returns:
        :class:`ScheduleResult` —— 含 ``RoutePlan``、未服务订单、统计、可行性标记。

    Raises:
        UnknownAlgorithmError: ``algorithm`` 不在白名单。
        InvalidObjectiveError: ``objective`` 不在 ``{"distance", "cost"}``。
        EmptyOrdersError: ``scenario.orders`` 为空。
        NoAvailableVehicleError / DepotNotFoundError: 仓库 / 车辆选择失败。
    """
    # --- 1. 参数校验 ---
    if algorithm not in ALGORITHM_NAMES:
        raise UnknownAlgorithmError(
            f"algorithm={algorithm!r} not in {ALGORITHM_NAMES}"
        )
    if objective not in ALLOWED_OBJECTIVES:
        raise InvalidObjectiveError(
            f"objective={objective!r} not in {ALLOWED_OBJECTIVES}; "
            "travel_time is reserved as comparison column only (AGENTS §3.7)"
        )
    if not scenario.orders:
        raise EmptyOrdersError("scenario.orders is empty; nothing to plan")

    # --- 2. 仓库 / 车辆 / 配送员 ---
    choice = select_depot(scenario, depot_id=depot_id)
    depot_node = choice.depot_id

    # --- 3. context 字段 ---
    service_time = float(scenario.simulation.get("service_time", 5.0))
    effective_initial_time = (
        float(initial_time)
        if initial_time is not None
        else float(scenario.simulation.get("initial_time", 0.0))
    )

    # --- 4. eligibility filter ---
    eligible_orders, pre_unserved = _filter_eligible(scenario)
    if not eligible_orders:
        # 所有订单都被预过滤拒绝 → 立刻返回"零服务"结果（仍调用一次 Dijkstra 的
        # depot->depot 零权 leg 完成 schema）。
        from logiroute.algorithms.dijkstra import PathResult

        zero_leg = PathResult(
            source=depot_node,
            target=depot_node,
            metric=objective,
            path=(depot_node,),
            total_weight=0.0,
            reachable=True,
            cross_metrics={m: 0.0 for m in SUPPORTED_METRICS},
        )
        from logiroute.scheduling.types import DeliveryStop

        depot_stop = DeliveryStop(
            sequence_index=0,
            node_id=depot_node,
            arrival_time=effective_initial_time,
            service_start=effective_initial_time,
            service_end=effective_initial_time,
            waiting_time=0.0,
        )
        empty_plan = RoutePlan(
            algorithm=algorithm,
            objective=objective,
            vehicle_id=choice.vehicle.id,
            courier_id=choice.courier.id if choice.courier else None,
            depot_id=depot_node,
            stop_sequence=(depot_node, depot_node),
            road_node_sequence=(depot_node,),
            legs=(zero_leg,),
            stops=(depot_stop, depot_stop),
            total_distance=0.0,
            total_travel_time=0.0,
            total_cost=0.0,
            main_objective_total=0.0,
            departure_time=effective_initial_time,
            return_time=effective_initial_time,
            capacity=choice.vehicle.capacity,
            served_order_ids=(),
            is_feasible=True,
        )
        return _finalize_result(
            scenario=scenario,
            algorithm=algorithm,
            objective=objective,
            plan=empty_plan,
            pre_unserved=pre_unserved,
            extra_unserved=[],
            path_provider=None,
            feasibility_counter=None,
            iterations=0,
            runtime_seconds=0.0,
        )

    # --- 4b. capacity-guard: 若已选车辆容量 < 总需求则重选 / 抛错 ---
    total_demand = sum(o.demand for o in eligible_orders)
    if total_demand > choice.vehicle.capacity + 1e-9:
        # 自动重选一次，看是否有更大容量的 IDLE 车辆可用
        try:
            choice = select_depot(
                scenario,
                depot_id=None,
                min_total_demand=total_demand,
            )
            depot_node = choice.depot_id
        except NoAvailableVehicleError:
            raise NoAvailableVehicleError(
                f"auto-selected vehicle {choice.vehicle.id!r} has capacity "
                f"{choice.vehicle.capacity} but total eligible order demand "
                f"is {total_demand} (>= capacity); no larger IDLE vehicle "
                f"at any warehouse; AGENTS §3.6 single-vehicle is infeasible "
                f"for this scenario"
            )

    # --- 5. 构造 PathProvider + PlanningContext ---
    path_provider = PathProvider(scenario.graph)
    feasibility_counter = _FeasibilityCounter()
    ctx = PlanningContext(
        scenario=scenario,
        graph=scenario.graph,
        path_provider=path_provider,
        objective=objective,
        service_time=service_time,
        initial_time=effective_initial_time,
        depot_id=depot_node,
        vehicle=choice.vehicle,
        courier=choice.courier,
        capacity=choice.vehicle.capacity,
    )

    # --- 6. 调度（带计时） ---
    t0 = time.monotonic()
    if algorithm == "unified":
        # Phase 5 默认路径：NN / CFI 双种子分别局部优化，再择优
        plan = unified_planner(ctx, eligible_orders)
        extra_unserved = _lift_unserved_from_notes(plan)
        # 2-opt 在 notes 中可能含有 iterations；CFI 不写
        iterations = int(plan.notes.get("iterations", 0))
    elif algorithm == "nearest_neighbor":
        plan = nearest_neighbor(ctx, eligible_orders)
        extra_unserved = _unserved_for_nn(plan, eligible_orders)
        iterations = 0
    elif algorithm == "insertion":
        plan = cheapest_feasible_insertion(ctx, eligible_orders)
        extra_unserved = _lift_unserved_from_notes(plan)
        iterations = 0
    elif algorithm == "two_opt":
        seed_plan = nearest_neighbor(ctx, eligible_orders)
        seed_unserved = _unserved_for_nn(seed_plan, eligible_orders)
        plan = constrained_two_opt(seed_plan, ctx)
        extra_unserved = seed_unserved  # 2-opt 不能增加订单，沿用 NN 的 unserved
        iterations = int(plan.notes.get("iterations", 0))
    else:
        # 不可能到这里 —— 参数已校验
        raise PlanningError(f"unreachable algorithm: {algorithm}")
    runtime_seconds = time.monotonic() - t0

    return _finalize_result(
        scenario=scenario,
        algorithm=algorithm,
        objective=objective,
        plan=plan,
        pre_unserved=pre_unserved,
        extra_unserved=extra_unserved,
        path_provider=path_provider,
        feasibility_counter=feasibility_counter,
        iterations=iterations,
        runtime_seconds=runtime_seconds,
    )


# ---------------------------------------------------------------------------
#  结果装配
# ---------------------------------------------------------------------------


def _finalize_result(
    *,
    scenario: ScenarioBundle,
    algorithm: str,
    objective: str,
    plan: RoutePlan,
    pre_unserved: list[Violation],
    extra_unserved: list[Violation],
    path_provider: PathProvider | None,
    feasibility_counter: _FeasibilityCounter | None,
    iterations: int,
    runtime_seconds: float,
) -> ScheduleResult:
    """统一装配 :class:`ScheduleResult`。

    包括：

    * 全局 ``is_feasible`` = ``plan.is_feasible and len(unserved) == 0``；
    * 合并非预过滤 unserved 与算法报告 unserved；
    * 计数：``cache_hits / cache_misses / dijkstra_calls / paths_evaluated`` 来自
      ``path_provider``；``feasibility_checks`` 来自 ``feasibility_counter``；
      ``iterations`` 来自 2-opt ``notes['iterations']``；``runtime_seconds`` 来自
      ``time.monotonic()`` 差。
    """
    unserved = list(pre_unserved) + list(extra_unserved)
    globally_feasible = plan.is_feasible and not unserved

    pp_stats = path_provider.stats() if path_provider is not None else {
        "cache_hits": 0,
        "cache_misses": 0,
        "dijkstra_calls": 0,
        "paths_evaluated": 0,
    }
    stats = PlanningStats(
        cache_hits=pp_stats["cache_hits"],
        cache_misses=pp_stats["cache_misses"],
        dijkstra_calls=pp_stats["dijkstra_calls"],
        paths_evaluated=pp_stats["paths_evaluated"],
        feasibility_checks=feasibility_counter.count if feasibility_counter else 0,
        iterations=iterations,
        runtime_seconds=float(runtime_seconds),
    )

    return ScheduleResult(
        scenario_name=scenario.name,
        algorithm=algorithm,
        objective=objective,
        depot_id=plan.depot_id,
        vehicle_id=plan.vehicle_id,
        courier_id=plan.courier_id,
        route_plan=plan,
        served_order_ids=plan.served_order_ids,
        unserved_orders=tuple(unserved),
        total_distance=plan.total_distance,
        total_travel_time=plan.total_travel_time,
        total_cost=plan.total_cost,
        main_objective_total=plan.main_objective_total,
        planning_stats=stats,
        is_feasible=globally_feasible,
    )


__all__ = ["plan_deliveries", "ALLOWED_OBJECTIVES"]
