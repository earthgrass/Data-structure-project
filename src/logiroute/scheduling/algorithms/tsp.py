"""单车有向 TSP：Dijkstra 距离闭包 + 有界状态搜索。

只把仓库和订单目的地放入 TSP 状态；任意两站之间允许经过完整路网的
其他节点。路径矩阵由 Phase 2 单源 Dijkstra 填充，订单访问顺序通过
手写束搜索求解。束宽有限时是启发式；未发生截断时可证明枚举了所有
满足容量/时间窗的访问顺序，不伪称所有 20 单场景都得到全局最优。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import inf

from logiroute.algorithms.dijkstra import PathResult
from logiroute.core.orders import Order
from logiroute.scheduling.feasibility import _leg_drive_time, check_feasibility
from logiroute.scheduling.types import DeliveryStop, PlanningContext, RoutePlan


@dataclass(frozen=True)
class _State:
    mask: int
    last: int
    total: float
    service_end: float
    load: float
    sequence: tuple[int, ...]


def _stable_orders(orders: list[Order]) -> list[Order]:
    """按订单 ID 手写稳定插入排序。Time O(K²)，Space O(K)。"""
    result = list(orders)
    for i in range(1, len(result)):
        item = result[i]
        j = i - 1
        while j >= 0 and result[j].id > item.id:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = item
    return result


def _distance_matrix(
    ctx: PlanningContext, orders: list[Order]
) -> list[list[PathResult]]:
    """用不超过 K+1 次单源 Dijkstra 构建 K+1 方阵。

    同节点多订单可占不同矩阵位置，但共用源节点的最短路结果。
    Time O(U·((V+E)log V + K·V) + K²)，U ≤ K+1。
    Space O(K² + U·K·V)，路径由 PathProvider 缓存。
    """
    nodes = (ctx.depot_id,) + tuple(o.destination_id for o in orders)
    unique_results: dict[str, dict[str, PathResult]] = {}
    for source in nodes:
        if source not in unique_results:
            unique_results[source] = ctx.path_provider.shortest_paths_from(
                source, nodes, ctx.objective
            )
    return [
        [unique_results[source][target] for target in nodes]
        for source in nodes
    ]


def _completion_bound(
    mask: int, last: int, matrix: list[list[PathResult]]
) -> float:
    """未访问点的有向出边下界，含当前位置与回仓。

    每个未访问站最终必须有一条出边指向另一个未访问站或仓库，
    当前位置必须先到一个未访问站；各项最小值之和是合法下界。
    Time O(K²)，Space O(1)。
    """
    k = len(matrix) - 1
    remaining: list[int] = []
    for node in range(1, k + 1):
        if not mask & (1 << (node - 1)):
            remaining.append(node)
    if not remaining:
        leg = matrix[last][0]
        return leg.total_weight if leg.reachable else inf
    first = inf
    for node in remaining:
        leg = matrix[last][node]
        if leg.reachable and leg.total_weight < first:
            first = leg.total_weight
    if first == inf:
        return inf
    bound = first
    for source in remaining:
        out = matrix[source][0]
        best = out.total_weight if out.reachable else inf
        for target in remaining:
            if target == source:
                continue
            leg = matrix[source][target]
            if leg.reachable and leg.total_weight < best:
                best = leg.total_weight
        if best == inf:
            return inf
        bound += best
    return bound


def _keep_best(
    heap: list[tuple[tuple[float, float, tuple[int, ...]], _State]],
    rank: tuple[float, float, tuple[int, ...]],
    state: _State,
    width: int,
) -> bool:
    """手写有界最大堆；返回是否因束宽丢弃了一个状态。

    最大堆根为最差状态，保留排名最小的 ``width`` 个状态。
    Time O(log width)，Space O(1) 额外空间。
    """
    entry = (rank, state)
    if len(heap) < width:
        heap.append(entry)
        i = len(heap) - 1
        while i > 0:
            parent = (i - 1) // 2
            if heap[parent][0] >= entry[0]:
                break
            heap[i] = heap[parent]
            i = parent
        heap[i] = entry
        return False
    if rank >= heap[0][0]:
        return True
    heap[0] = entry
    i = 0
    size = len(heap)
    while True:
        child = 2 * i + 1
        if child >= size:
            break
        right = child + 1
        if right < size and heap[right][0] > heap[child][0]:
            child = right
        if heap[child][0] <= entry[0]:
            break
        heap[i] = heap[child]
        i = child
    heap[i] = entry
    return True


def _make_route(
    ctx: PlanningContext,
    orders: list[Order],
    matrix: list[list[PathResult]],
    state: _State,
    *,
    width: int,
    layers: int,
    expanded: int,
    pruned: bool,
) -> RoutePlan:
    """按选中顺序重建道路段、订单身份、时间与未服务记录。

    Time O(K+L)，L 为完整道路节点数。Space O(K+L)。
    """
    indices = (0,) + state.sequence + (0,)
    stop_sequence = tuple(
        ctx.depot_id if i == 0 else orders[i - 1].destination_id
        for i in indices
    )
    legs = tuple(matrix[a][b] for a, b in zip(indices, indices[1:]))
    stops: list[DeliveryStop] = [DeliveryStop(
        sequence_index=0, node_id=ctx.depot_id,
        arrival_time=ctx.initial_time, service_start=ctx.initial_time,
        service_end=ctx.initial_time, waiting_time=0.0,
    )]
    load = 0.0
    for pos, order_index in enumerate(state.sequence, start=1):
        order = orders[order_index - 1]
        arrival = stops[-1].service_end + _leg_drive_time(legs[pos - 1])
        start = max(arrival, order.time_window_start)
        load += order.demand
        stops.append(DeliveryStop(
            sequence_index=pos, node_id=order.destination_id,
            arrival_time=arrival, service_start=start,
            service_end=start + ctx.service_time,
            waiting_time=start - arrival, order_id=order.id,
            demand=order.demand, cumulative_load=load,
            time_window_start=order.time_window_start,
            time_window_end=order.time_window_end,
        ))
    return_time = stops[-1].service_end + _leg_drive_time(legs[-1])
    stops.append(DeliveryStop(
        sequence_index=len(stops), node_id=ctx.depot_id,
        arrival_time=return_time, service_start=return_time,
        service_end=return_time, waiting_time=0.0,
        cumulative_load=load,
    ))
    report = check_feasibility(
        tuple(stops), legs, ctx.capacity, ctx.service_time,
        ctx.initial_time, ctx.depot_id,
    )
    served = set(state.sequence)
    missing = tuple(
        {
            "order_id": order.id,
            "kind": "search_budget_exhausted" if pruned else "no_feasible_next_step",
            "message": (
                "bounded TSP search did not find a full feasible tour"
                if pruned else
                "no capacity/time-window-feasible continuation was found"
            ),
        }
        for i, order in enumerate(orders, start=1)
        if i not in served
    )
    notes: dict[str, object] = {
        "iterations": layers,
        "states_expanded": expanded,
        "beam_width": width,
        "optimality_proven": not pruned and len(served) == len(orders),
    }
    if missing:
        notes["unserved_orders"] = missing
    total_distance = sum(leg.cross_metrics["distance"] for leg in legs)
    total_travel_time = sum(leg.cross_metrics["travel_time"] for leg in legs)
    total_cost = sum(leg.cross_metrics["cost"] for leg in legs)
    return RoutePlan(
        algorithm="tsp_beam", objective=ctx.objective,
        vehicle_id=ctx.vehicle.id,
        courier_id=ctx.courier.id if ctx.courier else None,
        depot_id=ctx.depot_id,
        stop_sequence=stop_sequence,
        road_node_sequence=ctx.path_provider.road_node_sequence(
            stop_sequence, ctx.objective
        ),
        legs=legs, stops=tuple(stops),
        total_distance=total_distance,
        total_travel_time=total_travel_time,
        total_cost=total_cost,
        main_objective_total=(
            total_distance if ctx.objective == "distance" else total_cost
        ),
        departure_time=ctx.initial_time, return_time=return_time,
        capacity=ctx.capacity,
        served_order_ids=tuple(orders[i - 1].id for i in state.sequence),
        is_feasible=report.is_feasible,
        notes=notes,
    )


def solve_tsp(ctx: PlanningContext, eligible_orders: list[Order]) -> RoutePlan:
    """在 Dijkstra 距离闭包上搜索单车辆闭环 TSP。

    束宽由 ``scenario.optimization['tsp_beam_width']`` 指定；未提供时
    使用订单数的平方。完整枚举未截断时为精确解，否则是有界近似解，
    输出中的 ``optimality_proven`` 明示证明状态。

    Time O(U·((V+E)log V + K·V) + K⁴·B·log B)，B 为束宽。
    Space O(K² + B·K + U·K·V)，含矩阵及路径缓存。
    """
    orders = _stable_orders(eligible_orders)
    k = len(orders)
    optimization = getattr(ctx.scenario, "optimization", {}) or {}
    width = optimization.get("tsp_beam_width", max(1, k * k))
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise ValueError("optimization.tsp_beam_width must be a positive integer")
    matrix = _distance_matrix(ctx, orders)
    initial = _State(0, 0, 0.0, ctx.initial_time, 0.0, ())
    beam = [initial]
    best_partial = initial
    best_partial_key = (0, 0.0, ())
    pruned = False
    expanded = 0
    layers = 0

    for _ in range(k):
        retained: list[tuple[tuple[float, float, tuple[int, ...]], _State]] = []
        for state in beam:
            for target in range(1, k + 1):
                bit = 1 << (target - 1)
                if state.mask & bit:
                    continue
                leg = matrix[state.last][target]
                if not leg.reachable:
                    continue
                order = orders[target - 1]
                new_load = state.load + order.demand
                if new_load > ctx.capacity + 1e-9:
                    continue
                arrival = state.service_end + _leg_drive_time(leg)
                service_start = max(arrival, order.time_window_start)
                if service_start > order.time_window_end + 1e-9:
                    continue
                mask = state.mask | bit
                bound = _completion_bound(mask, target, matrix)
                if bound == inf:
                    continue
                candidate = _State(
                    mask=mask, last=target,
                    total=state.total + leg.total_weight,
                    service_end=service_start + ctx.service_time,
                    load=new_load,
                    sequence=state.sequence + (target,),
                )
                expanded += 1
                rank = (
                    candidate.total + bound,
                    candidate.total,
                    candidate.sequence,
                )
                if _keep_best(retained, rank, candidate, width):
                    pruned = True
        if not retained:
            break
        beam = [entry[1] for entry in retained]
        layers += 1
        for state in beam:
            closing = matrix[state.last][0]
            if not closing.reachable:
                continue
            key = (-len(state.sequence), state.total + closing.total_weight, state.sequence)
            if key < best_partial_key:
                best_partial_key = key
                best_partial = state

    return _make_route(
        ctx, orders, matrix, best_partial,
        width=width, layers=layers, expanded=expanded, pruned=pruned,
    )


__all__ = ["solve_tsp"]
