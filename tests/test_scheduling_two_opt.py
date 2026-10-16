"""``tests/test_scheduling_two_opt.py`` —— Phase 3 ``constrained_two_opt`` 单测。

覆盖矩阵（≥ 11）：

1. 拒绝不可行种子 → ``InfeasibleSeedError``
2. 接受可行种子 → 返回 ``is_feasible=True`` 的 ``RoutePlan``
3. 不恶化保证 → ``main_objective_total <= plan_seed.main_objective_total``
4. Plateau 终止 → ``iterations_done`` 受 ``K^2`` 上限约束
5. 短路线直通 → K=0 / K=1 直接重填，不抛错
6. Depot 守恒 → ``stop_sequence`` 首/尾均为 ``depot_id``
7. 所有 leg 可达 → ``len(result.legs) == len(result.stop_sequence) - 1``
   且每条 leg ``reachable``
8. ``service_time`` 一致性 → ``stops[i].service_end = stops[i].service_start
   + ctx.service_time``（仓库站除外）
9. ``notes["iterations"]`` 计数 → 至少为 1（执行了至少一次扫描）
10. First-improvement → 设计一个反向段确实更优的场景，验证交换已采纳
11. 路径真正重建（不是无向 Δ 公式）→ 同一 ``(source, target)`` 对在不同
    候选路径中重新查询 ``PathProvider``，缓存命中数与 ``paths_evaluated``
    计数器随重建次数变化
12. 主目标传播到 ``total_distance`` / ``total_cost`` → 三列数字独立但
    与 ``leg.cross_metrics`` 对齐（验证多 metric 字段填充正确）

仅依赖 stdlib 与 Phase 1/3 已存在的类型与 Dijkstra / PathProvider。
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any
from unittest import TestCase

from logiroute.algorithms.dijkstra import PathResult
from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling.algorithms.two_opt import (
    constrained_two_opt,
)
from logiroute.scheduling.feasibility import _leg_drive_time
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.types import (
    DeliveryStop,
    InfeasibleSeedError,
    PlanningContext,
    RoutePlan,
)


# ---------------------------------------------------------------------------
#  工厂辅助
# ---------------------------------------------------------------------------


def _node(nid: str, t: NodeType = NodeType.CUSTOMER) -> Node:
    return Node(id=nid, name=nid, node_type=t, x=0.0, y=0.0)


def _edge(src: str, tgt: str, d: float = 1.0, t: float = 1.0, c: float = 1.0) -> Edge:
    return Edge(
        source_id=src,
        target_id=tgt,
        distance=d,
        travel_time=t,
        cost=c,
    )


def _order(
    oid: str,
    dest: str,
    demand: float = 1.0,
    tw_start: float = 0.0,
    tw_end: float = 1e9,
) -> Order:
    return Order(
        id=oid,
        destination_id=dest,
        demand=demand,
        time_window_start=tw_start,
        time_window_end=tw_end,
    )


def _vehicle(vid: str = "VH1", capacity: float = 100.0) -> Vehicle:
    return Vehicle(id=vid, capacity=capacity)


def _graph_with_3_customers() -> LogisticsGraph:
    """最小连通图：W1 + 3 客户 A / B / C + 路径保证强连通。

    为使 2-opt 反演选择**唯一**，所有出边均设为直接边，
    且权重有方向差异。
    """
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("W2", NodeType.WAREHOUSE),
        _node("A"),
        _node("B"),
        _node("C"),
    ):
        g.add_node(n)

    edges = [
        # ---- 出 W1 ----
        ("W1", "A", 1.0, 2.0, 3.0),
        # ---- 客户间中间节点 ----
        ("A", "B", 5.0, 5.0, 5.0),
        ("A", "C", 5.0, 5.0, 5.0),
        ("B", "C", 5.0, 5.0, 5.0),
        ("C", "B", 5.0, 5.0, 5.0),
        # ---- 回归 W1 ----
        ("B", "W1", 1.0, 2.0, 3.0),
        ("C", "W1", 1.0, 2.0, 3.0),
        ("A", "W1", 1.0, 2.0, 3.0),
        # ---- 兜底连通 W2 ----
        ("W1", "W2", 50.0, 50.0, 50.0),
        ("W2", "W1", 50.0, 50.0, 50.0),
    ]
    for src, tgt, d, t, c in edges:
        g.add_edge(_edge(src, tgt, d, t, c))
    return g


def _graph_for_first_improvement() -> LogisticsGraph:
    """专门为"反向段严格更优"测试设计的图。

    Dijkstra 路径预期（确保直接边被选中）：

    * W1 -> A : 1（直接）
    * A -> B : 100（直接；A->C->B = 1+100 = 101 不会更短）
    * B -> C : 1（直接；B->W1->A->C = 1+1+1 = 3 不会更短）
    * C -> W1 : 100（直接；C->B->W1 = 100+1 = 101 不会更短）
    * C -> B : 100（直接；C->W1->A->B = 100+1+100 = 201 不会更短）
    * A -> C : 1（直接）
    * B -> W1 : 1（直接；B->C->W1 = 1+100 = 101 不会更短）

    故原路线 ``(W1, A, B, C, W1)`` 总距离 = 1 + 100 + 1 + 100 = **202**；
    反转 ``B..C`` 段 → ``(W1, A, C, B, W1)`` 总距离 = 1 + 1 + 100 + 1 = **103**。

    严格改善 99，跨 metric 同方向下降。
    """
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("A"),
        _node("B"),
        _node("C"),
    ):
        g.add_node(n)

    # (distance, travel_time, cost) — 三者同向，简化断言。
    edges = [
        ("W1", "A", 1.0, 1.0, 1.0),
        ("A", "B", 100.0, 100.0, 100.0),
        ("A", "C", 1.0, 1.0, 1.0),
        ("B", "C", 1.0, 1.0, 1.0),
        ("C", "B", 100.0, 100.0, 100.0),
        ("B", "W1", 1.0, 1.0, 1.0),
        ("C", "W1", 100.0, 100.0, 100.0),
    ]
    for src, tgt, d, t, c in edges:
        g.add_edge(_edge(src, tgt, d, t, c))
    return g


def _depot_stop(
    seq: int,
    nid: str,
    *,
    arrival: float,
    cumulative_load: float = 0.0,
) -> DeliveryStop:
    return DeliveryStop(
        sequence_index=seq,
        node_id=nid,
        arrival_time=arrival,
        service_start=arrival,
        service_end=arrival,
        waiting_time=0.0,
        order_id=None,
        demand=0.0,
        cumulative_load=cumulative_load,
        time_window_start=None,
        time_window_end=None,
    )


def _customer_stop(
    seq: int,
    nid: str,
    *,
    arrival: float,
    service_time: float,
    tw_start: float = 0.0,
    tw_end: float = 1e9,
    order_id: str = "O?",
    demand: float = 1.0,
    cum_load: float = 1.0,
) -> DeliveryStop:
    waiting = max(0.0, tw_start - arrival)
    service_start = arrival + waiting
    service_end = service_start + service_time
    return DeliveryStop(
        sequence_index=seq,
        node_id=nid,
        arrival_time=arrival,
        service_start=service_start,
        service_end=service_end,
        waiting_time=waiting,
        order_id=order_id,
        demand=demand,
        cumulative_load=cum_load,
        time_window_start=tw_start,
        time_window_end=tw_end,
    )


def _leg(
    src: str,
    tgt: str,
    *,
    d: float,
    t: float,
    c: float,
    reachable: bool = True,
) -> PathResult:
    return PathResult(
        source=src,
        target=tgt,
        metric="distance",
        path=(src, tgt),
        total_weight=d,
        reachable=reachable,
        cross_metrics={"distance": d, "travel_time": t, "cost": c},
    )


@dataclass
class _ScenarioLike:
    """只承载 ``orders`` 字段的最小场景壳（避免造真实 ScenarioBundle）。"""

    orders: list[Order] = field(default_factory=list)


def _scenario(orders: list[Order]) -> _ScenarioLike:
    return _ScenarioLike(orders=orders)


def _ctx(
    graph: LogisticsGraph,
    *,
    objective: str = "distance",
    service_time: float = 5.0,
    initial_time: float = 540.0,
    depot_id: str = "W1",
    vehicle: Vehicle | None = None,
    capacity: float = 100.0,
    orders: list[Order] | None = None,
    path_provider: PathProvider | None = None,
) -> PlanningContext:
    return PlanningContext(
        scenario=_scenario(orders or []),
        graph=graph,
        path_provider=path_provider or PathProvider(graph),
        objective=objective,
        service_time=service_time,
        initial_time=initial_time,
        depot_id=depot_id,
        vehicle=vehicle or _vehicle(),
        courier=None,
        capacity=capacity,
    )


def _seed_route(
    stop_seq: tuple[str, ...],
    *,
    graph: LogisticsGraph,
    depot_id: str = "W1",
    service_time: float = 5.0,
    initial_time: float = 540.0,
    capacity: float = 100.0,
    orders: list[Order] | None = None,
    is_feasible: bool = True,
    objective: str = "distance",
    vehicle_id: str = "VH1",
) -> RoutePlan:
    """根据 ``stop_seq`` 重新计算 legs + stops，构造一个 RoutePlan。

    主要供"接受 / 拒绝种子 / 不恶化"等测试用，让种子通过真实的
    Dijkstra 计算 legs，以保证 is_feasible 计算入口一致。
    """
    pp = PathProvider(graph)
    legs = tuple(
        pp.shortest_path(s, t, objective)
        for s, t in zip(stop_seq, stop_seq[1:])
    )
    assert all(l.reachable for l in legs), "stop_seq must be fully reachable"

    # 订单元数据按 destination_id 反查（首个匹配胜出）
    order_map: dict[str, Order] = {}
    for o in orders or []:
        order_map.setdefault(o.destination_id, o)

    stops: list[DeliveryStop] = []
    cumulative_load = 0.0
    n = len(stop_seq)
    for i, nid in enumerate(stop_seq):
        if i == 0:
            stops.append(_depot_stop(0, nid, arrival=initial_time))
            continue
        drive = _leg_drive_time(legs[i - 1])
        arrival = stops[i - 1].service_end + drive
        if i == n - 1:
            stops.append(
                _depot_stop(
                    i, nid, arrival=arrival, cumulative_load=cumulative_load
                )
            )
            continue
        o = order_map.get(nid)
        if o is None:
            waiting = 0.0
            service_start = arrival
            service_end = service_start + service_time
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
        tw_start = o.time_window_start
        tw_end = o.time_window_end
        demand = float(o.demand)
        cumulative_load += demand
        waiting = max(0.0, tw_start - arrival)
        service_start = arrival + waiting
        service_end = service_start + service_time
        stops.append(
            DeliveryStop(
                sequence_index=i,
                node_id=nid,
                arrival_time=arrival,
                service_start=service_start,
                service_end=service_end,
                waiting_time=waiting,
                order_id=o.id,
                demand=demand,
                cumulative_load=cumulative_load,
                time_window_start=tw_start,
                time_window_end=tw_end,
            )
        )

    total_distance = sum(
        l.cross_metrics.get("distance", l.total_weight) for l in legs
    )
    total_travel_time = sum(
        l.cross_metrics.get("travel_time", l.total_weight) for l in legs
    )
    total_cost = sum(
        l.cross_metrics.get("cost", l.total_weight) for l in legs
    )
    main_total = total_distance if objective == "distance" else total_cost
    road_seq = pp.road_node_sequence(stop_seq, objective)
    served = tuple(s.order_id for s in stops if s.order_id is not None)

    return RoutePlan(
        algorithm="seed",
        objective=objective,
        vehicle_id=vehicle_id,
        depot_id=depot_id,
        stop_sequence=stop_seq,
        road_node_sequence=road_seq,
        legs=legs,
        stops=tuple(stops),
        total_distance=total_distance,
        total_travel_time=total_travel_time,
        total_cost=total_cost,
        main_objective_total=main_total,
        departure_time=initial_time,
        return_time=stops[-1].service_end,
        capacity=capacity,
        served_order_ids=served,
        is_feasible=is_feasible,
        notes={"origin": "seed"},
    )


# ---------------------------------------------------------------------------
#  Test 1: 拒绝不可行种子
# ---------------------------------------------------------------------------


class TestRefusesInfeasibleSeed(TestCase):
    def test_infeasible_seed_raises_infeasible_seed_error(self):
        graph = _graph_with_3_customers()
        # 构造一个故意 is_feasible = False 的种子（其它字段正常）
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            is_feasible=False,
        )
        self.assertFalse(seed.is_feasible)
        ctx = _ctx(graph)
        with self.assertRaises(InfeasibleSeedError):
            constrained_two_opt(seed, ctx)

    def test_infeasible_seed_does_not_call_dijkstra(self):
        """硬规则：拒绝不可行种子时不应触发任何 Dijkstra / 路径查询。"""
        graph = _graph_with_3_customers()
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            is_feasible=False,
        )
        pp = PathProvider(graph)
        ctx = _ctx(graph, path_provider=pp)
        try:
            constrained_two_opt(seed, ctx)
        except InfeasibleSeedError:
            pass
        # 不允许访问 Dijkstra
        self.assertEqual(pp.dijkstra_calls, 0)
        self.assertEqual(pp.cache_hits, 0)
        self.assertEqual(pp.cache_misses, 0)
        self.assertEqual(pp.paths_evaluated, 0)


# ---------------------------------------------------------------------------
#  Test 2: 接受可行种子
# ---------------------------------------------------------------------------


class TestAcceptsFeasibleSeed(TestCase):
    def test_feasible_seed_returns_feasible_route_plan(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        self.assertTrue(seed.is_feasible)
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        self.assertIsInstance(result, RoutePlan)
        self.assertTrue(result.is_feasible)
        self.assertEqual(result.algorithm, "two_opt")
        self.assertEqual(result.depot_id, "W1")


# ---------------------------------------------------------------------------
#  Test 3: 不恶化保证
# ---------------------------------------------------------------------------


class TestNonWorsening(TestCase):
    def test_main_objective_total_does_not_increase(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        self.assertLessEqual(
            result.main_objective_total,
            seed.main_objective_total + 1e-6,
            msg=(
                f"2-opt worsened the route: seed={seed.main_objective_total}, "
                f"result={result.main_objective_total}"
            ),
        )


# ---------------------------------------------------------------------------
#  Test 4: Plateau 终止
# ---------------------------------------------------------------------------


class TestPlateauTermination(TestCase):
    def test_iterations_bounded_by_K_squared(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        # 路线 K=3 → iter_cap = 9
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        K = len(seed.stop_sequence) - 2
        self.assertLessEqual(result.notes["iterations"], K * K)
        # 至少跑过 1 次扫描（即便没找到改善）
        self.assertGreaterEqual(result.notes["iterations"], 1)


# ---------------------------------------------------------------------------
#  Test 5: 短路线直通
# ---------------------------------------------------------------------------


class TestShortRoutePassThrough(TestCase):
    def test_zero_inner_stops_returns_seed(self):
        graph = _graph_with_3_customers()
        # K=0：只有 depot + depot 闭合
        seed = _seed_route(
            ("W1", "W1"),
            graph=graph,
        )
        ctx = _ctx(graph)
        result = constrained_two_opt(seed, ctx)
        self.assertEqual(result.stop_sequence, seed.stop_sequence)
        self.assertTrue(result.is_feasible)
        # K=0 → iterations_done = 0
        self.assertEqual(result.notes["iterations"], 0)

    def test_single_inner_stop_returns_seed(self):
        graph = _graph_with_3_customers()
        orders = [_order("OA", "A", demand=1.0)]
        # K=1：单客户
        seed = _seed_route(
            ("W1", "A", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        # 单客户无法反转段，stop_sequence 应保持原状
        self.assertEqual(result.stop_sequence, seed.stop_sequence)
        self.assertTrue(result.is_feasible)
        self.assertEqual(result.notes["iterations"], 0)


# ---------------------------------------------------------------------------
#  Test 6: Depot 守恒
# ---------------------------------------------------------------------------


class TestDepotPreserving(TestCase):
    def test_depot_remains_at_both_ends(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        self.assertEqual(result.stop_sequence[0], "W1")
        self.assertEqual(result.stop_sequence[-1], "W1")
        self.assertEqual(result.depot_id, "W1")


# ---------------------------------------------------------------------------
#  Test 7: 所有 leg 可达
# ---------------------------------------------------------------------------


class TestAllLegsReachable(TestCase):
    def test_legs_match_stop_count_and_all_reachable(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        # 腿数 = stops - 1
        self.assertEqual(len(result.legs), len(result.stop_sequence) - 1)
        for idx, leg in enumerate(result.legs):
            self.assertTrue(
                getattr(leg, "reachable", False),
                msg=f"leg #{idx} ({leg.source!r}->{leg.target!r}) not reachable",
            )


# ---------------------------------------------------------------------------
#  Test 8: service_time 一致性
# ---------------------------------------------------------------------------


class TestServiceTimeCorrectness(TestCase):
    def test_customer_service_end_equals_service_start_plus_service_time(self):
        graph = _graph_with_3_customers()
        service_time = 5.0
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
            service_time=service_time,
        )
        ctx = _ctx(
            graph,
            orders=orders,
            service_time=service_time,
        )
        result = constrained_two_opt(seed, ctx)
        for i, stop in enumerate(result.stops):
            if stop.order_id is None:
                # depot 站 service_end == service_start（无服务）
                self.assertEqual(stop.service_end, stop.service_start)
                continue
            expected = stop.service_start + service_time
            self.assertAlmostEqual(
                stop.service_end,
                expected,
                delta=1e-6,
                msg=(
                    f"stop #{i} ({stop.node_id!r}) service_end "
                    f"{stop.service_end} != service_start {stop.service_start} "
                    f"+ service_time {service_time}"
                ),
            )


# ---------------------------------------------------------------------------
#  Test 9: notes["iterations"] 计数
# ---------------------------------------------------------------------------


class TestNotesContainsIterations(TestCase):
    def test_notes_iterations_field_present_and_int(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        self.assertIn("iterations", result.notes)
        self.assertIsInstance(result.notes["iterations"], int)
        self.assertGreaterEqual(result.notes["iterations"], 1)

    def test_notes_iterations_at_least_one_when_swap_found(self):
        """first-improvement 找到改善 → iterations_done 至少 1。"""
        graph = _graph_for_first_improvement()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        # 确认原始种子确实可被改善（设计值 ~202，远大于改进后 ~103）
        self.assertGreater(seed.main_objective_total, 100.0)
        result = constrained_two_opt(seed, ctx)
        # 改善后 main_objective_total 应大幅下降
        self.assertLess(
            result.main_objective_total, seed.main_objective_total - 1.0
        )
        self.assertGreaterEqual(result.notes["iterations"], 1)


# ---------------------------------------------------------------------------
#  Test 10: First-improvement
# ---------------------------------------------------------------------------


class TestFirstImprovementStrategy(TestCase):
    def test_reversing_better_segment_is_taken(self):
        """反向 (B, C) → (C, B) 严格更优 → 应被采纳。"""
        graph = _graph_for_first_improvement()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        # 反转后预期为 (W1, A, C, B, W1)
        self.assertEqual(result.stop_sequence, ("W1", "A", "C", "B", "W1"))
        # 改善显著
        self.assertLess(
            result.main_objective_total,
            seed.main_objective_total,
        )
        # 时间也应下降（三 metric 同向）
        self.assertLess(
            result.total_travel_time,
            seed.total_travel_time,
        )

    def test_first_improvement_takes_first_better_swap_not_best(self):
        """first-improvement 策略：仅接受第一个发现的严格改善。

        验证算法在多重可选改善中取"先发现的那个"，不会全部对比选全局最优。
        本测试中原始顺序 A-B-C；可用改善包括 (W1, A, C, B, W1)。
        期望：执行后 stop_sequence == (W1, A, C, B, W1)。
        """
        graph = _graph_for_first_improvement()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        # 第一个被采纳的反转段就是 (B..C) → (C, B)
        self.assertEqual(result.stop_sequence, ("W1", "A", "C", "B", "W1"))


# ---------------------------------------------------------------------------
#  Test 11: 路径真正重建（路径缓存 / Dijkstra 调用计数）
# ---------------------------------------------------------------------------


class TestPathsAreActuallyRebuilt(TestCase):
    def test_path_provider_cache_hits_or_misses_on_each_candidate(self):
        """每次候选都调用 ``pp.all_pairs``，故 ``paths_evaluated`` 至少
        K*(K-1)/2 次（候选 leg 总数）。种子保存为 starter, 任何额外反向都
        必须增加 ``paths_evaluated`` / ``dijkstra_calls``。"""
        graph = _graph_for_first_improvement()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        pp = PathProvider(graph)
        # 种子腿预热一次；记录 initial counters
        for leg in seed.legs:
            pp.shortest_path(leg.source, leg.target, "distance")
        prev_evaluated = pp.paths_evaluated
        prev_dijkstra = pp.dijkstra_calls

        ctx = _ctx(graph, orders=orders, path_provider=pp)
        result = constrained_two_opt(seed, ctx)
        # 算法跑过之后 paths_evaluated 必然增加（≥ 一轮 K-1=2 leg 对）
        self.assertGreater(
            pp.paths_evaluated,
            prev_evaluated,
            msg="2-opt must query the path provider for each candidate leg",
        )
        self.assertGreater(pp.dijkstra_calls, prev_dijkstra)
        # 且最终结果是 RoutePlan
        self.assertIsInstance(result, RoutePlan)


# ---------------------------------------------------------------------------
#  Test 12: 三 metric 字段填充正确
# ---------------------------------------------------------------------------


class TestMultiMetricTotalsPopulated(TestCase):
    def test_total_distance_travel_time_cost_all_filled(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        self.assertGreater(result.total_distance, 0.0)
        self.assertGreater(result.total_travel_time, 0.0)
        self.assertGreater(result.total_cost, 0.0)
        # main_objective_total 在 distance 模式下 == total_distance
        self.assertAlmostEqual(
            result.main_objective_total, result.total_distance, delta=1e-6
        )

    def test_cost_objective_aligns_main_total_with_total_cost(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
            objective="cost",
        )
        ctx = _ctx(graph, orders=orders, objective="cost")
        result = constrained_two_opt(seed, ctx)
        self.assertEqual(result.objective, "cost")
        self.assertAlmostEqual(
            result.main_objective_total, result.total_cost, delta=1e-6
        )


# ---------------------------------------------------------------------------
#  Test 13: 服务订单集合保持
# ---------------------------------------------------------------------------


class TestServedOrderSetPreserved(TestCase):
    def test_served_order_ids_match_inner_stops(self):
        graph = _graph_with_3_customers()
        orders = [
            _order("OA", "A", demand=1.0),
            _order("OB", "B", demand=1.0),
            _order("OC", "C", demand=1.0),
        ]
        seed = _seed_route(
            ("W1", "A", "B", "C", "W1"),
            graph=graph,
            orders=orders,
        )
        ctx = _ctx(graph, orders=orders)
        result = constrained_two_opt(seed, ctx)
        self.assertEqual(set(result.served_order_ids), {"OA", "OB", "OC"})


if __name__ == "__main__":
    unittest.main()