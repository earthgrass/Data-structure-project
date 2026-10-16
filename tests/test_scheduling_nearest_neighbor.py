"""``tests/test_scheduling_nearest_neighbor.py`` —— Phase 3 ``nearest_neighbor`` 单测。

覆盖矩阵（至少 12 项）：

1. 单订单 NN 闭合回路结构（3 stops / 2 legs）
2. 多订单 NN 闭合回路结构（K+1 stops / K+1 legs）
3. URGENT 优先扫描：混合 urgent/normal 时 urgent 全部先入路线
4. 不可达订单被报告为 unserved（不可达 destination → not in served_order_ids）
5. 容量溢出处理：总需求 > 容量时部分订单 unserved
6. 时间窗迟到：time_window_end < 最早可行 arrival → 该订单 unserved
7. tie-break 确定性：相同 leg_main.total_weight + order.id → 多份结果完全一致
8. ``is_feasible`` 正确：全部服务后为 True；check_feasibility 自行决定
9. ``service_end − service_start == ctx.service_time``（每个客户站都成立）
10. ``total_travel_time`` 等于 ``Σ legs.cross_metrics["travel_time"]``
11. 空 eligible_orders：1 leg（仓库→仓库短路）+ stop_sequence=(depot, depot)
12. 首尾仓库 ``order_id is None and demand == 0.0``

所有测试仅依赖 stdlib ``unittest`` 与 Phase 1/2/3 已存在类型。
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest import TestCase

from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType, OrderPriority
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling.algorithms.nearest_neighbor import nearest_neighbor
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.types import PlanningContext, Violation


# ---------------------------------------------------------------------------
#  工厂辅助
# ---------------------------------------------------------------------------


def _node(nid: str, t: NodeType = NodeType.CUSTOMER) -> Node:
    return Node(id=nid, name=nid, node_type=t, x=0.0, y=0.0)


def _edge(
    src: str,
    tgt: str,
    d: float = 1.0,
    t: float = 1.0,
    c: float = 1.0,
) -> Edge:
    return Edge(
        source_id=src,
        target_id=tgt,
        distance=d,
        travel_time=t,
        cost=c,
    )


def _tri_graph() -> LogisticsGraph:
    """4 节点 + 5 有向边的最小可连通图：``W1 -> C1 -> C2 -> W1``。

    用于最基础的 1~3 订单 NN 测试。W2 仅作为冗余节点存在。
    """
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("W2", NodeType.WAREHOUSE),
        _node("C1"),
        _node("C2"),
    ):
        g.add_node(n)
    for e in (
        _edge("W1", "C1", 2.0, 4.0, 6.0),
        _edge("C1", "C2", 2.0, 4.0, 6.0),
        _edge("C2", "W1", 2.0, 4.0, 6.0),
        _edge("W1", "W2", 5.0, 8.0, 12.0),
        _edge("W2", "C1", 3.0, 5.0, 9.0),
    ):
        g.add_edge(e)
    return g


def _disconnected_graph() -> LogisticsGraph:
    """两个独立分量：``W1 <-> C1`` 与 ``W2 <-> C2``，无跨分量路径。

    用于验证「不可达 destination 被判为不可服务」。每个分量都包含双向边，
    确保每个分量内部可形成闭合子回路；但跨分量之间不可达。
    """
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("W2", NodeType.WAREHOUSE),
        _node("C1"),
        _node("C2"),
    ):
        g.add_node(n)
    for e in (
        _edge("W1", "C1", 1.0, 2.0, 3.0),
        _edge("C1", "W1", 1.0, 2.0, 3.0),
        _edge("W2", "C2", 1.0, 2.0, 3.0),
        _edge("C2", "W2", 1.0, 2.0, 3.0),
    ):
        g.add_edge(e)
    return g


def _make_ctx(
    graph: LogisticsGraph,
    *,
    objective: str = "distance",
    service_time: float = 5.0,
    initial_time: float = 540.0,
    depot_id: str = "W1",
    capacity: float = 100.0,
    vehicle_id: str = "VH1",
) -> PlanningContext:
    """构造 ``PlanningContext`` 测试 fixture。"""
    provider = PathProvider(graph)
    vehicle = Vehicle(
        id=vehicle_id,
        capacity=capacity,
        current_load=0.0,
        current_node_id=depot_id,
    )
    return PlanningContext(
        scenario=object(),
        graph=graph,
        path_provider=provider,
        objective=objective,
        service_time=service_time,
        initial_time=initial_time,
        depot_id=depot_id,
        vehicle=vehicle,
        courier=None,
        capacity=capacity,
    )


def _make_order(
    oid: str,
    destination_id: str,
    *,
    demand: float = 5.0,
    tw_start: float = 540.0,
    tw_end: float = 720.0,
    priority: OrderPriority = OrderPriority.NORMAL,
) -> Order:
    """构造 ``Order`` 测试 fixture；默认宽时间窗规避偶发迟到。"""
    return Order(
        id=oid,
        destination_id=destination_id,
        demand=demand,
        time_window_start=tw_start,
        time_window_end=tw_end,
        priority=priority,
    )


def _plan_to_unserved(
    plan_served: tuple[str, ...],
    eligible: list[Order],
    *,
    kind: str = "no_feasible_next_step",
) -> tuple[Violation, ...]:
    """辅助：把「eligible - plan.served」映射为 ``Violation`` 元组。

    测试并不直接复现 planner 内部决策，只用「eligible 中哪些未被服务」
    作为 unserved 集合的语义代理。
    """
    served = set(plan_served)
    out: list[Violation] = []
    for o in eligible:
        if o.id in served:
            continue
        out.append(
            Violation(
                order_id=o.id,
                kind=kind,
                message=(
                    f"order {o.id!r} not served by nearest_neighbor "
                    "(planner-level derivation)"
                ),
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
#  Test 1: 单订单闭合回路结构
# ---------------------------------------------------------------------------


class TestClosedTourStructure(TestCase):
    def test_single_order_yields_depot_dst_depot(self):
        ctx = _make_ctx(_tri_graph())
        orders = [_make_order("O1", "C1", demand=5.0)]
        plan = nearest_neighbor(ctx, orders)

        self.assertEqual(plan.stop_sequence, ("W1", "C1", "W1"))
        self.assertEqual(len(plan.legs), 2)
        self.assertEqual(len(plan.stops), 3)
        self.assertEqual(plan.served_order_ids, ("O1",))
        # 闭合：route_plan.__post_init__ 已校验起止均为 depot
        self.assertEqual(plan.stop_sequence[0], ctx.depot_id)
        self.assertEqual(plan.stop_sequence[-1], ctx.depot_id)
        # 算法标记
        self.assertEqual(plan.algorithm, "nearest_neighbor")
        self.assertEqual(plan.objective, "distance")


# ---------------------------------------------------------------------------
#  Test 2: 多订单闭合回路结构
# ---------------------------------------------------------------------------


class TestMultiOrderClosedTour(TestCase):
    def test_three_orders_yields_five_stops_four_legs(self):
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order("O1", "C1", demand=2.0),
            _make_order("O2", "C2", demand=3.0),
            _make_order("O3", "C1", demand=4.0, priority=OrderPriority.URGENT),
        ]
        plan = nearest_neighbor(ctx, orders)

        # K=3 订单 → K+2 stops = 5 (depot + 3 customers + depot) → K+1 legs = 4
        self.assertEqual(len(plan.stops), 5)
        self.assertEqual(len(plan.legs), 4)
        self.assertEqual(plan.stop_sequence[0], "W1")
        self.assertEqual(plan.stop_sequence[-1], "W1")
        # 全部 served
        self.assertEqual(len(plan.served_order_ids), 3)
        self.assertEqual(set(plan.served_order_ids), {"O1", "O2", "O3"})


# ---------------------------------------------------------------------------
#  Test 3: URGENT 优先扫描
# ---------------------------------------------------------------------------


class TestUrgentScanOrder(TestCase):
    def test_all_urgent_delivered_regardless_of_position(self):
        """urgent 全部入路线（容量充足时），与 normal 一同混排。

        备注：NN 的选择键 ``(leg_main.total_weight, order.id, len(path))`` 不
        含 ``priority``；priority 仅决定**扫描**次序。所以本测试只断言
        所有 urgent 都进入 ``served_order_ids`` —— 比例合法性由 sort + 扫描 +
        容量 / 时间窗 三者一起保证。
        """
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order("O_N1", "C1", demand=1.0, priority=OrderPriority.NORMAL),
            _make_order("O_U1", "C1", demand=1.0, priority=OrderPriority.URGENT),
            _make_order("O_N2", "C2", demand=1.0, priority=OrderPriority.NORMAL),
            _make_order("O_U2", "C2", demand=1.0, priority=OrderPriority.URGENT),
            _make_order("O_N3", "C1", demand=1.0, priority=OrderPriority.NORMAL),
        ]
        plan = nearest_neighbor(ctx, orders)

        # 全部入路线（容量 100 充足，时间窗宽松）
        self.assertEqual(
            set(plan.served_order_ids), {o.id for o in orders}
        )

    def test_priority_truly_irrelevant_to_selection_when_legs_tie(self):
        """``priority`` 仅影响扫描次序。当候选 leg_main 总权相同、order.id 不
        同时，选择键由 ``order.id`` 决定 → 与 priority 无关。

        在 ``_tri_graph`` 中，W1 → C1 与 W1 → C2（经 C1）的距离不同，故不会
        完全 tie。本测试改用一个极简图：所有 order 都到同一节点 C1，使
        ``leg_main.total_weight`` 完全相等，专门验证 tie-break → order.id。
        """
        g = LogisticsGraph()
        for n in (
            _node("W1", NodeType.WAREHOUSE),
            _node("C1"),
            _node("W2", NodeType.WAREHOUSE),  # 仅用作冗余节点
        ):
            g.add_node(n)
        g.add_edge(_edge("W1", "C1", 1.0, 1.0, 1.0))
        g.add_edge(_edge("C1", "W1", 1.0, 1.0, 1.0))

        ctx = _make_ctx(g)
        orders = [
            _make_order("O_Z_URG", "C1", demand=1.0,
                        priority=OrderPriority.URGENT),
            _make_order("O_A_NORMAL", "C1", demand=1.0,
                        priority=OrderPriority.NORMAL),
        ]
        plan = nearest_neighbor(ctx, orders)

        # tie-break：leg 全相等，order.id 字典序最小者胜 → O_A_NORMAL
        first = plan.stops[1]  # index 0 = depot
        self.assertEqual(first.order_id, "O_A_NORMAL")


# ---------------------------------------------------------------------------
#  Test 4: 不可达订单被报告为 unserved
# ---------------------------------------------------------------------------


class TestUnreachableOrderUnserved(TestCase):
    def test_unreachable_destination_appears_as_unserved(self):
        # C1 是连通分量，X1 是孤立节点（无入边）→ 从 W1 不可达
        g = LogisticsGraph()
        for n in (
            _node("W1", NodeType.WAREHOUSE),
            _node("C1"),
            _node("X1"),  # 孤儿：没有任何边
        ):
            g.add_node(n)
        # 仅 W1 -> C1
        g.add_edge(_edge("W1", "C1", 1.0, 2.0, 3.0))
        # W1 的返回腿（C1 -> W1）保留闭回路
        g.add_edge(_edge("C1", "W1", 1.0, 2.0, 3.0))

        ctx = _make_ctx(g)
        orders = [
            _make_order("O_REACH", "C1", demand=5.0),
            _make_order("O_FARAWAY", "X1", demand=5.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        unserved = _plan_to_unserved(plan.served_order_ids, orders)

        # C1 应被服务，X1 不应被服务
        self.assertIn("O_REACH", plan.served_order_ids)
        self.assertNotIn("O_FARAWAY", plan.served_order_ids)

        # unserved 元组中存在 O_FARAWAY
        unserved_ids = [v.order_id for v in unserved]
        self.assertIn("O_FARAWAY", unserved_ids)
        self.assertNotIn("O_REACH", unserved_ids)

    def test_disconnected_components_unserved(self):
        """两个独立分量订单：分属不同 block 的订单全部 unserved。"""
        ctx = _make_ctx(_disconnected_graph())
        orders = [
            _make_order("O_W1_DEST", "C1", demand=5.0),  # 可达
            _make_order("O_W2_DEST", "C2", demand=5.0),  # 不可达
        ]
        plan = nearest_neighbor(ctx, orders)
        unserved = _plan_to_unserved(plan.served_order_ids, orders)

        self.assertIn("O_W1_DEST", plan.served_order_ids)
        self.assertNotIn("O_W2_DEST", plan.served_order_ids)
        unserved_ids = [v.order_id for v in unserved]
        self.assertIn("O_W2_DEST", unserved_ids)


# ---------------------------------------------------------------------------
#  Test 5: 容量溢出
# ---------------------------------------------------------------------------


class TestCapacityOverflow(TestCase):
    def test_total_demand_exceeds_capacity(self):
        ctx = _make_ctx(_tri_graph(), capacity=10.0)  # 容量 < 总需求
        orders = [
            _make_order("O1", "C1", demand=6.0),
            _make_order("O2", "C2", demand=6.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        # 至少有一个 unserved（NN 服务 C1 后 current_load=6；再加 6 > 10）
        unserved = _plan_to_unserved(plan.served_order_ids, orders)
        self.assertGreaterEqual(len(unserved), 1)
        # 累积容量字段对已服务的 stop 不应越界（≤ capacity + tol）
        for stop in plan.stops:
            self.assertLessEqual(stop.cumulative_load, 10.0 + 1e-6)


# ---------------------------------------------------------------------------
#  Test 6: 时间窗迟到
# ---------------------------------------------------------------------------


class TestTimeWindowMissUnserved(TestCase):
    def test_order_with_impossible_window_marked_unserved(self):
        # 把 O1 的时间窗上界设为「明显早于任何可行到达时间」
        # route W1 → C2 → W1 的 drive_time = 4（travel_time of edge C2->W1）
        # 中间站时间窗设为 ~545（足够），但让某个订单的 end 极小。
        ctx = _make_ctx(_tri_graph())
        # 来自 W1 的可行订单 O1: W1→C2 到达 ≈ 540 + travel_time(W1,C2)? 不存在直接边
        # → W1→C1(4)→C2(4) = 8 minutes → arrival ≈ 548
        # 如果 time_window_end=541 则肯定迟到
        orders = [
            _make_order(
                "O_LATE",
                "C2",
                demand=2.0,
                tw_start=540.0,
                tw_end=541.0,  # 极端窄窗口
            ),
            _make_order("O_OK", "C1", demand=2.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        unserved = _plan_to_unserved(plan.served_order_ids, orders)
        # O_LATE 必须 unserved
        unserved_ids = [v.order_id for v in unserved]
        self.assertIn("O_LATE", unserved_ids)


# ---------------------------------------------------------------------------
#  Test 7: tie-break 确定性
# ---------------------------------------------------------------------------


class TestTieBreakDeterminism(TestCase):
    def test_same_inputs_yield_identical_route_plan(self):
        """两个订单具有完全相同的 leg_main.total_weight（同一最短路径），

        tie-break：order.id 字典序小的优先。
        """
        g = _tri_graph()
        ctx = _make_ctx(g)
        orders = [
            _make_order("O_Z", "C1", demand=1.0),  # later id
            _make_order("O_A", "C1", demand=1.0),  # earlier id
        ]
        plan1 = nearest_neighbor(ctx, orders)
        plan2 = nearest_neighbor(ctx, list(reversed(orders)))  # reversed copy
        # 两次构造结果完全一致：stop_sequence / served / totals 均相同
        self.assertEqual(plan1.stop_sequence, plan2.stop_sequence)
        self.assertEqual(plan1.served_order_ids, plan2.served_order_ids)
        self.assertEqual(plan1.total_distance, plan2.total_distance)
        self.assertEqual(plan1.total_travel_time, plan2.total_travel_time)
        # 第一个客户站必须是 O_A（id 字典序更小）
        first_customer_stop = next(s for s in plan1.stops if s.order_id is not None)
        self.assertEqual(first_customer_stop.order_id, "O_A")


# ---------------------------------------------------------------------------
#  Test 8: is_feasible 正确性
# ---------------------------------------------------------------------------


class TestFeasibilityFlag(TestCase):
    def test_all_served_yields_feasible(self):
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order("O1", "C1", demand=2.0),
            _make_order("O2", "C2", demand=2.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        self.assertTrue(plan.is_feasible)
        self.assertEqual(len(plan.served_order_ids), 2)

    def test_feasibility_reflects_constructed_route_only(self):
        """NN 只对 *已构造* 的 stops/legs 报告可行性；unserved 不参与。

        容量 10.0 且两个 demand=6.0 订单 → 第二个会被标记为 unserved，但
        ``is_feasible`` 只刻画已构造段（每个有时间窗的 stop 都合法）。
        """
        ctx = _make_ctx(_tri_graph(), capacity=10.0)
        orders = [
            _make_order("O1", "C1", demand=6.0),
            _make_order("O2", "C2", demand=6.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        for stop in plan.stops:
            if stop.time_window_end is not None:
                self.assertLessEqual(
                    stop.service_start, stop.time_window_end + 1e-6
                )
        unserved = _plan_to_unserved(plan.served_order_ids, orders)
        self.assertGreaterEqual(len(unserved), 1)


# ---------------------------------------------------------------------------
#  Test 9: service_time 一致性
# ---------------------------------------------------------------------------


class TestServiceTimePropagation(TestCase):
    def test_each_customer_stop_has_service_end_minus_start_equal_to_ctx_service_time(
        self,
    ):
        ctx = _make_ctx(_tri_graph(), service_time=5.0)
        orders = [
            _make_order("O1", "C1", demand=1.0),
            _make_order("O2", "C2", demand=1.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        for stop in plan.stops:
            if stop.order_id is None:
                # 仓库 stop：service_start == service_end
                self.assertEqual(stop.service_start, stop.service_end)
            else:
                self.assertAlmostEqual(
                    stop.service_end - stop.service_start, 5.0, places=9
                )

    def test_service_time_propagation_with_zero_service_time(self):
        """service_time=0：每个客户站 service_start == service_end。"""
        ctx = _make_ctx(_tri_graph(), service_time=0.0)
        orders = [_make_order("O1", "C1", demand=1.0)]
        plan = nearest_neighbor(ctx, orders)
        for stop in plan.stops:
            if stop.order_id is not None:
                self.assertEqual(stop.service_start, stop.service_end)


# ---------------------------------------------------------------------------
#  Test 10: travel_time 使用 cross_metrics
# ---------------------------------------------------------------------------


class TestTravelTimeFromCrossMetrics(TestCase):
    def test_total_travel_time_uses_cross_metrics_along_chosen_path(self):
        """``distance`` 主目标下选择最短距离路径，行驶时间必须取该路径
        的 ``cross_metrics["travel_time"]`` 之和，**不**是该路径的
        ``total_weight`` 之和（否则会偷换语义为「最短时间路径」）。

        构造 ``distance`` 最优 vs. ``travel_time`` 最优分裂的图：

        * 直连 ``W1 → C1``：distance=100, travel_time=2  （距离远但快）
        * 经 ``C2``：``W1 → C2`` (dist=1, time=50) +
          ``C2 → C1`` (dist=1, time=50) → distance=2, time=100

        distance 目标下 NN 走 ``W1 → C2 → C1``；该路径的
        ``cross_metrics["travel_time"]`` 应当等于 100.0。
        """
        g = LogisticsGraph()
        for n in (
            _node("W1", NodeType.WAREHOUSE),
            _node("C1"),
            _node("C2"),
        ):
            g.add_node(n)
        g.add_edge(_edge("W1", "C1", 100.0, 2.0, 50.0))
        g.add_edge(_edge("W1", "C2", 1.0, 50.0, 1.0))
        g.add_edge(_edge("C2", "C1", 1.0, 50.0, 1.0))
        g.add_edge(_edge("C1", "W1", 2.0, 2.0, 2.0))

        ctx = _make_ctx(g, objective="distance")
        plan = nearest_neighbor(ctx, [_make_order("O1", "C1", demand=1.0)])

        # distance-optimal: W1 → C2 → C1 (total_weight = 1 + 1 = 2.0)
        self.assertEqual(plan.legs[0].total_weight, 2.0)
        self.assertEqual(plan.legs[0].path, ("W1", "C2", "C1"))
        # 该路径的 travel_time = 50 + 50 = 100
        self.assertEqual(
            plan.legs[0].cross_metrics["travel_time"], 100.0
        )

        # total_distance = Σ total_weight = 2 + 2 = 4.0
        self.assertEqual(plan.total_distance, 4.0)
        # total_travel_time = Σ cross_metrics["travel_time"] = 100 + 2 = 102
        self.assertEqual(plan.total_travel_time, 102.0)

        # 必须等于 cross_metrics 之和（口径一致）
        expected_travel = sum(
            l.cross_metrics["travel_time"] for l in plan.legs
        )
        self.assertEqual(plan.total_travel_time, expected_travel)


# ---------------------------------------------------------------------------
#  Test 11: 空 eligible_orders
# ---------------------------------------------------------------------------


class TestEmptyOrders(TestCase):
    def test_no_orders_yields_depot_to_depot_shortcut(self):
        ctx = _make_ctx(_tri_graph())
        plan = nearest_neighbor(ctx, [])

        # stop_sequence = (depot, depot)，legs = 1 条（depot→depot 短路）
        self.assertEqual(plan.stop_sequence, ("W1", "W1"))
        self.assertEqual(len(plan.legs), 1)
        self.assertEqual(len(plan.stops), 2)
        # 唯一一条 leg 是 source==target 短路
        self.assertEqual(plan.legs[0].source, "W1")
        self.assertEqual(plan.legs[0].target, "W1")
        self.assertEqual(plan.legs[0].path, ("W1",))
        self.assertEqual(plan.legs[0].total_weight, 0.0)
        self.assertTrue(plan.legs[0].reachable)
        # served 为空
        self.assertEqual(plan.served_order_ids, ())
        # 全零 totals
        self.assertEqual(plan.total_distance, 0.0)
        self.assertEqual(plan.total_travel_time, 0.0)
        self.assertEqual(plan.total_cost, 0.0)
        # 可行（空路线不违反任何约束）
        self.assertTrue(plan.is_feasible)


# ---------------------------------------------------------------------------
#  Test 12: 首尾仓库 stop 的不变量
# ---------------------------------------------------------------------------


class TestDepotStopInvariants(TestCase):
    def test_first_and_last_stops_are_depots_with_zero_demand_and_no_window(self):
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order("O1", "C1", demand=3.0),
            _make_order("O2", "C2", demand=4.0),
        ]
        plan = nearest_neighbor(ctx, orders)

        for idx in (0, -1):
            stop = plan.stops[idx]
            self.assertEqual(stop.node_id, "W1")
            self.assertIsNone(stop.order_id)
            self.assertEqual(stop.demand, 0.0)
            self.assertIsNone(stop.time_window_start)
            self.assertIsNone(stop.time_window_end)

    def test_depot_stop_zero_demand_holds_with_many_orders(self):
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order(f"O{i}", "C1" if i % 2 == 0 else "C2", demand=1.0)
            for i in range(5)
        ]
        plan = nearest_neighbor(ctx, orders)
        first, last = plan.stops[0], plan.stops[-1]
        self.assertEqual(first.order_id, None)
        self.assertEqual(last.order_id, None)
        self.assertEqual(first.demand, 0.0)
        self.assertEqual(last.demand, 0.0)


# ---------------------------------------------------------------------------
#  Test 入参 / 返回类型 + 算法元数据
# ---------------------------------------------------------------------------


class TestPlanMetadata(TestCase):
    def test_algorithm_name_matches_constant(self):
        from logiroute.scheduling.algorithms import ALGORITHM_NAMES
        ctx = _make_ctx(_tri_graph())
        orders = [_make_order("O1", "C1", demand=1.0)]
        plan = nearest_neighbor(ctx, orders)
        self.assertEqual(plan.algorithm, "nearest_neighbor")
        self.assertIn("nearest_neighbor", ALGORITHM_NAMES)

    def test_objective_cost_uses_cost_metric_for_total(self):
        ctx = _make_ctx(_tri_graph(), objective="cost")
        orders = [_make_order("O1", "C1", demand=1.0)]
        plan = nearest_neighbor(ctx, orders)

        self.assertEqual(plan.objective, "cost")
        # main_objective_total == total_cost
        self.assertEqual(plan.main_objective_total, plan.total_cost)
        # total_cost = sum(legs.total_weight)（因为 objective == cost）
        expected_cost = sum(l.total_weight for l in plan.legs)
        self.assertEqual(plan.total_cost, expected_cost)
        # total_distance = sum(legs.cross_metrics["distance"])
        expected_distance = sum(
            l.cross_metrics["distance"] for l in plan.legs
        )
        self.assertEqual(plan.total_distance, expected_distance)

    def test_legs_and_stops_lengths_match_stop_sequence(self):
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order("O1", "C1", demand=1.0),
            _make_order("O2", "C2", demand=1.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        self.assertEqual(len(plan.legs), len(plan.stops) - 1)
        self.assertEqual(len(plan.legs), len(plan.stop_sequence) - 1)

    def test_legs_cover_all_consecutive_stops(self):
        """``legs[i]`` 起止与 ``stop_sequence[i], stop_sequence[i+1]`` 一致。"""
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order("O1", "C1", demand=1.0),
            _make_order("O2", "C2", demand=1.0),
        ]
        plan = nearest_neighbor(ctx, orders)
        for i, leg in enumerate(plan.legs):
            self.assertEqual(leg.source, plan.stop_sequence[i])
            self.assertEqual(leg.target, plan.stop_sequence[i + 1])

    def test_input_eligible_orders_is_not_mutated(self):
        ctx = _make_ctx(_tri_graph())
        orders = [
            _make_order("O1", "C1", demand=1.0),
            _make_order("O2", "C2", demand=1.0),
        ]
        before_ids = [o.id for o in orders]
        _ = nearest_neighbor(ctx, orders)
        after_ids = [o.id for o in orders]
        self.assertEqual(before_ids, after_ids)


# ---------------------------------------------------------------------------
#  regression：Hash + frozen
# ---------------------------------------------------------------------------


class TestRoutePlanFrozen(TestCase):
    def test_plan_is_frozen(self):
        ctx = _make_ctx(_tri_graph())
        plan = nearest_neighbor(ctx, [_make_order("O1", "C1")])
        with self.assertRaises(Exception):
            plan.objective = "cost"  # type: ignore[misc]
        with self.assertRaises(Exception):
            plan.depot_id = "W2"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
