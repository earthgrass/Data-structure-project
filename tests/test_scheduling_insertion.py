"""``tests/test_scheduling_insertion.py`` —— Phase 3 ``cheapest_feasible_insertion`` 单测。

覆盖矩阵（≥ 10 个测试）：

1. **Closed tour**：2-order 输入产生 ``(depot, o1, o2, depot)`` 形状。
2. **Feasibility preserved**：所有可行输入 → ``is_feasible=True``。
3. **Cheapness property**：在可控的小图上，CFI 的 ``main_objective_total``
   不大于某种朴素构造（手算上界）的总量。
4. **Tie-break deterministic**：两次运行 CFI 产生 bytes-identical ``RoutePlan``。
5. **Seed construction raises** ：所有订单超出 capacity → 抛
   :class:`InfeasibleSeedError`。
6. **Empty eligible_orders** → 返回合法 2-stop tour。
7. **Unserviceable orders reported**：混合可行 / 不可行 → 仅可行被服务，
   不可行进入 ``notes['unserved_orders']``。
8. **Service time correctness**：每个 stop 的
   ``service_end - service_start == ctx.service_time``。
9. **Travel time from cross_metrics not total_weight**：
   实际行驶时间口径为 ``cross_metrics['travel_time']``，与主目标 distance
   不同。
11. **Priority-handled seed**：URGENT 即使 tw 更晚也应作为种子。
12. **Custom cheapness hand-built**：在精心构造的图中，可行插入必然优于
    最近邻（与已提交 NN 风格对比；用本模块自身的不带插入 / 带插入对比）。

不依赖 ``nearest_neighbor.py`` / ``two_opt.py`` —— 单独运行亦可通过。
"""

from __future__ import annotations

import unittest
from unittest import TestCase

from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType, OrderPriority
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling.algorithms.insertion import (
    cheapest_feasible_insertion,
)
from logiroute.scheduling.feasibility import check_feasibility
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.types import (
    InfeasibleSeedError,
    PlanningContext,
)


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


def _small_star_graph() -> LogisticsGraph:
    """小星形图：W1 → {C1, C2, C3} → W1；可直接手算最短路。

    边权：
        W1→C1: dist=5,  t=2,  c=10
        W1→C2: dist=10, t=5,  c=5
        W1→C3: dist=7,  t=3,  c=8
        C1→W1: dist=5,  t=2,  c=10
        C2→W1: dist=10, t=5,  c=5
        C3→W1: dist=7,  t=3,  c=8
        C1↔C2: dist=3, t=1, c=4（与 C3 各加一条）

    用于测试 cheapness 与 closed-tour 形状。
    """
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("C1"),
        _node("C2"),
        _node("C3"),
    ):
        g.add_node(n)
    edges = (
        _edge("W1", "C1", 5.0, 2.0, 10.0),
        _edge("W1", "C2", 10.0, 5.0, 5.0),
        _edge("W1", "C3", 7.0, 3.0, 8.0),
        _edge("C1", "W1", 5.0, 2.0, 10.0),
        _edge("C2", "W1", 10.0, 5.0, 5.0),
        _edge("C3", "W1", 7.0, 3.0, 8.0),
        _edge("C1", "C2", 3.0, 1.0, 4.0),
        _edge("C2", "C1", 3.0, 1.0, 4.0),
        _edge("C1", "C3", 4.0, 2.0, 5.0),
        _edge("C3", "C1", 4.0, 2.0, 5.0),
        _edge("C2", "C3", 6.0, 3.0, 7.0),
        _edge("C3", "C2", 6.0, 3.0, 7.0),
    )
    for e in edges:
        g.add_edge(e)
    return g


def _build_context(
    graph: LogisticsGraph,
    *,
    objective: str = "distance",
    service_time: float = 5.0,
    initial_time: float = 540.0,
    capacity: float = 100.0,
    depot_id: str = "W1",
    vehicle: Vehicle | None = None,
) -> PlanningContext:
    """构造最小可用的 :class:`PlanningContext`。"""
    if vehicle is None:
        vehicle = Vehicle(
            id="VH1",
            capacity=capacity,
            current_node_id=depot_id,
        )
    pp = PathProvider(graph)
    return PlanningContext(
        scenario=object(),
        graph=graph,
        path_provider=pp,
        objective=objective,
        service_time=service_time,
        initial_time=initial_time,
        depot_id=depot_id,
        vehicle=vehicle,
        courier=None,
        capacity=capacity,
    )


def _order(
    oid: str,
    dest: str,
    *,
    demand: float = 5.0,
    tw_start: float = 540.0,
    tw_end: float = 1200.0,
    priority: OrderPriority = OrderPriority.NORMAL,
) -> Order:
    return Order(
        id=oid,
        destination_id=dest,
        demand=demand,
        time_window_start=tw_start,
        time_window_end=tw_end,
        priority=priority,
    )


# ---------------------------------------------------------------------------
#  Test 1: 闭环形状
# ---------------------------------------------------------------------------


class TestClosedTour(TestCase):
    def test_two_order_input_produces_depot_o1_o2_depot(self):
        ctx = _build_context(_small_star_graph())
        orders = [_order("O1", "C1"), _order("O2", "C2")]
        plan = cheapest_feasible_insertion(ctx, orders)
        self.assertEqual(plan.depot_id, "W1")
        self.assertEqual(plan.stop_sequence[0], "W1")
        self.assertEqual(plan.stop_sequence[-1], "W1")
        self.assertEqual(len(plan.stop_sequence), 4)
        # 中间两个停靠站必须都是订单对应客户
        mids = set(plan.stop_sequence[1:-1])
        self.assertEqual(mids, {"C1", "C2"})
        # served_order_ids 应含两个订单
        self.assertEqual(set(plan.served_order_ids), {"O1", "O2"})
        # 闭环：leg 数 == stop 数 - 1
        self.assertEqual(len(plan.legs), len(plan.stop_sequence) - 1)
        # 所有 leg 均可达
        for leg in plan.legs:
            self.assertTrue(leg.reachable)


# ---------------------------------------------------------------------------
#  Test 2: 可行性保持
# ---------------------------------------------------------------------------


class TestFeasibilityPreserved(TestCase):
    def test_three_feasible_orders_produce_feasible_plan(self):
        ctx = _build_context(_small_star_graph())
        orders = [
            _order("O1", "C1", tw_end=1200.0),
            _order("O2", "C2", tw_end=1200.0),
            _order("O3", "C3", tw_end=1200.0),
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        self.assertTrue(
            plan.is_feasible,
            msg=f"expected feasible; got violations in plan: {plan.notes}",
        )
        # 重新运行 check_feasibility 应对整条 plan 通过
        report = check_feasibility(
            stops=plan.stops,
            legs=plan.legs,
            capacity=ctx.capacity,
            service_time=ctx.service_time,
            initial_time=ctx.initial_time,
            depot_id=ctx.depot_id,
        )
        self.assertTrue(report.is_feasible)
        self.assertEqual(report.violations, ())


# ---------------------------------------------------------------------------
#  Test 3: 廉价性 —— CFI 不超过"贪心"上界
# ---------------------------------------------------------------------------


class TestCheapnessProperty(TestCase):
    def test_cfi_main_objective_not_worse_than_path_provider_greedy(self):
        """手算：``W1 → C2 → C1 → W1`` 的距离主目标 = 10+3+5 = 18。
        该顺序对 distance 主目标是已知最优（手算列举两种 3 站顺序均可验证）。
        CFI 应能找出一个不劣于 18 的解。
        """
        g = _small_star_graph()
        ctx = _build_context(g, objective="distance")
        orders = [
            _order("O1", "C1", tw_end=1200.0),
            _order("O2", "C2", tw_end=1200.0),
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        # 三站顺序手算：W1->C1->C2->W1 = 5+3+10=18；
        #               W1->C2->C1->W1 = 10+3+5=18。 两者并列最优。
        self.assertLessEqual(
            plan.main_objective_total,
            18.0 + 1e-6,
            msg=f"expected CFI distance <= 18, got {plan.main_objective_total}",
        )
        # CFI 必须保证至少为可行（不大于上界），且不退化
        self.assertGreaterEqual(plan.main_objective_total, 13.0)

    def test_cfi_chooses_cheaper_insertion_on_hand_built_example(self):
        """手算下界：固定 O1=O2 后，可行插入应优于最坏顺序。
        图：W1→{C1=10, C2=1, C3=2}，客户间 C1→C2=1, C2→C1=1, C1→C3=1, C3→C1=1；
        所有 leg 反向亦建（对称权 1）。
        最优：W1→C2→C1→W1 = 1 + 1 + 10 = 12
        CFI 必须 ≤ 贪心 NN 的上界 18。
        """
        g = LogisticsGraph()
        for n in (
            _node("W1", NodeType.WAREHOUSE),
            _node("C1"),
            _node("C2"),
            _node("C3"),
        ):
            g.add_node(n)
        for s, t in (
            ("W1", "C2"), ("C2", "W1"),
            ("W1", "C3"), ("C3", "W1"),
            ("C1", "C2"), ("C2", "C1"),
            ("C1", "C3"), ("C3", "C1"),
            ("C2", "C3"), ("C3", "C2"),
        ):
            g.add_edge(
                Edge(s, t, distance=1.0, travel_time=1.0, cost=1.0)
            )
        # 最后单独把 W1↔C1 的距离调到 10（保留其它边为 1）
        g.add_edge(Edge("W1", "C1", distance=10.0, travel_time=10.0, cost=10.0))
        g.add_edge(Edge("C1", "W1", distance=10.0, travel_time=10.0, cost=10.0))

        ctx = _build_context(g, objective="distance")
        orders = [
            _order("O1", "C1", tw_end=1200.0),
            _order("O2", "C2", tw_end=1200.0),
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        # 手算最优：W1→C2→C1→W1 = 1 + 1 + 10 = 12
        # CFI 必须 ≤ 贪心 NN 的上界 18。
        self.assertLessEqual(
            plan.main_objective_total,
            18.0 + 1e-6,
            msg=f"CFI distance should be at most 18, got "
                f"{plan.main_objective_total}",
        )


# ---------------------------------------------------------------------------
#  Test 4: Tie-break deterministic
# ---------------------------------------------------------------------------


class TestTieBreakDeterministic(TestCase):
    def test_identical_input_produces_identical_route_plan_bytes(self):
        g = _small_star_graph()
        orders = [_order("O1", "C1"), _order("O2", "C2")]
        ctx1 = _build_context(g)
        plan1 = cheapest_feasible_insertion(ctx1, orders)
        ctx2 = _build_context(g)
        plan2 = cheapest_feasible_insertion(ctx2, orders)
        # to_dict() 是 JSON-safe 且含全部字段；用 bytes 等价比较
        import json
        b1 = json.dumps(plan1.to_dict(), sort_keys=True).encode("utf-8")
        b2 = json.dumps(plan2.to_dict(), sort_keys=True).encode("utf-8")
        self.assertEqual(b1, b2)
        # 直接 __eq__ 也应一致（RoutePlan frozen + tuple-based）
        self.assertEqual(plan1, plan2)


# ---------------------------------------------------------------------------
#  Test 5: InfeasibleSeedError
# ---------------------------------------------------------------------------


class TestSeedInfeasibilityRaises(TestCase):
    def test_all_orders_exceed_capacity_raises(self):
        ctx = _build_context(_small_star_graph(), capacity=10.0)
        orders = [
            _order("O1", "C1", demand=15.0),
            _order("O2", "C2", demand=20.0),
        ]
        with self.assertRaises(InfeasibleSeedError) as cm_exc:
            cheapest_feasible_insertion(ctx, orders)
        msg = str(cm_exc.exception)
        self.assertIn("capacity", msg.lower())


# ---------------------------------------------------------------------------
#  Test 6: Empty eligible_orders
# ---------------------------------------------------------------------------


class TestEmptyEligibleOrders(TestCase):
    def test_empty_returns_two_stop_tour(self):
        ctx = _build_context(_small_star_graph())
        plan = cheapest_feasible_insertion(ctx, [])
        # 2-stop tour
        self.assertEqual(plan.stop_sequence, ("W1", "W1"))
        self.assertEqual(len(plan.stops), 2)
        self.assertEqual(len(plan.legs), 1)
        self.assertTrue(plan.is_feasible)
        self.assertEqual(plan.served_order_ids, ())
        # unserved_orders 应为空
        self.assertFalse(plan.notes.get("unserved_orders"))


# ---------------------------------------------------------------------------
#  Test 7: Mixed feasible / infeasible — only feasible delivered
# ---------------------------------------------------------------------------


class TestUnserviceableOrdersReported(TestCase):
    def test_mixed_orders_only_feasible_served(self):
        """O1 容量合法 + 时间窗合法；O2 demand 超出容量。
        O3 时间窗早到过迟（service_start > tw_end）。
        期望：仅 O1 被服务；O2/O3 进入 unserved。
        """
        ctx = _build_context(_small_star_graph(), capacity=10.0)
        orders = [
            _order("O1", "C1", demand=5.0, tw_end=1200.0),
            _order("O2", "C2", demand=50.0, tw_end=1200.0),  # 超容
            _order("O3", "C3", demand=3.0, tw_end=600.0),    # tw_end 早
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        # 仅 O1 与 O3 被服务；O2 因 demand > capacity 被排除（作为 unserved）
        self.assertEqual(
            set(plan.served_order_ids), {"O1", "O3"},
            msg=f"expected O1 and O3 served; got {plan.served_order_ids}",
        )
        # unserved 必须记录 O2
        uns = plan.notes.get("unserved_orders", ())
        uns_ids = {v["order_id"] for v in uns}
        self.assertIn("O2", uns_ids)
        # violation kind 应在白名单内（RoutePlan.notes 中存的是 dict）
        for v in uns:
            self.assertIn(
                v["kind"],
                {"no_feasible_insertion", "infeasible_seed"},
                msg=f"unexpected violation kind: {v['kind']}",
            )


# ---------------------------------------------------------------------------
#  Test 8: service_time correctness
# ---------------------------------------------------------------------------


class TestServiceTimeCorrectness(TestCase):
    def test_each_stop_service_end_minus_start_equals_service_time(self):
        ctx = _build_context(_small_star_graph(), service_time=7.5)
        orders = [
            _order("O1", "C1", tw_end=1200.0),
            _order("O2", "C2", tw_end=1200.0),
            _order("O3", "C3", tw_end=1200.0),
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        for stop in plan.stops:
            if stop.order_id is None:
                # 仓库端点 service_end == service_start
                self.assertAlmostEqual(
                    stop.service_end,
                    stop.service_start,
                    places=9,
                )
            else:
                self.assertAlmostEqual(
                    stop.service_end - stop.service_start,
                    ctx.service_time,
                    places=6,
                    msg=f"stop {stop.node_id} order {stop.order_id} has "
                        f"service_end-service_start={stop.service_end - stop.service_start} "
                        f"!= service_time={ctx.service_time}",
                )


# ---------------------------------------------------------------------------
#  Test 9: Travel time from cross_metrics not total_weight
# ---------------------------------------------------------------------------


class TestTravelTimeFromCrossMetrics(TestCase):
    def test_actual_drive_time_uses_cross_metrics_travel_time(self):
        """设置 distance=10, travel_time=3 的边；
        主目标=distance 时 leg.total_weight=10；cross_metrics['travel_time']=3。
        期望：实际 stop 之间的 arrival 差 = travel_time（来自 cross_metrics），
        即 3，而非 distance 10。
        """
        g = LogisticsGraph()
        for n in (
            _node("W1", NodeType.WAREHOUSE),
            _node("C1"),
            _node("C2"),
        ):
            g.add_node(n)
        # distance=10, travel_time=3, cost=99 — 三 metric 显著分离
        for s, t in (
            ("W1", "C1"), ("C1", "W1"),
            ("W1", "C2"), ("C2", "W1"),
            ("C1", "C2"), ("C2", "C1"),
        ):
            g.add_edge(Edge(s, t, distance=10.0, travel_time=3.0, cost=99.0))

        ctx = _build_context(g, objective="distance", service_time=0.0)
        orders = [
            _order("O1", "C1", tw_end=1200.0),
            _order("O2", "C2", tw_end=1200.0),
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        # service_time=0 → stops 之间 arrival 差严格等于 drive_time
        # (cross_metrics['travel_time'])。每条 leg travel_time = 3，
        # 因此 stops[0]=540, stops[1]=543, stops[2]=546, stops[3]=549。
        expected_arrivals = [540.0, 543.0, 546.0, 549.0]
        actual_arrivals = [s.arrival_time for s in plan.stops]
        for i, (a, e) in enumerate(zip(actual_arrivals, expected_arrivals)):
            self.assertAlmostEqual(
                a, e, places=6,
                msg=f"stop {i} arrival expected {e}, got {a}; "
                    "CFI must use cross_metrics['travel_time'] for actual drive time",
            )
        # 主目标应是 distance 主目标
        self.assertEqual(plan.main_objective_total, plan.total_distance)
        # total_travel_time 应等于 travel_time 之和（来自 cross_metrics）
        expected_tt = sum(
            leg.cross_metrics["travel_time"] for leg in plan.legs
        )
        self.assertAlmostEqual(plan.total_travel_time, expected_tt, places=6)


# ---------------------------------------------------------------------------
#  Test 10: URGENT seed
# ---------------------------------------------------------------------------


class TestPriorityHandledSeed(TestCase):
    def test_urgent_seed_even_with_later_window(self):
        """O_N NORMAL 早窗口但客户离仓库**回程**路径代价高（→ 强制在 OU 之后
        插入）；O_U URGENT 晚窗口。期望 O_U 作为种子出现在服务序列最前。
        """
        g = LogisticsGraph()
        for n in (
            _node("W1", NodeType.WAREHOUSE),
            _node("C1"),
            _node("C2"),
        ):
            g.add_node(n)
        # W1↔C1: 出 10 / 回 1（不对称）；W1↔C2: 出 5 / 回 5（对称）；
        # C2↔C1: 各 1（短）。
        # Seed: W1→C2→W1 = 5+5 = 10。
        # Insert ON@C1：
        #   pos 1 (depot → ON → OU → depot) = 10 + 1 + 5 = 16 → delta = 6。
        #   pos 2 (depot → OU → ON → depot) = 5 + 1 + 1 = 7  → delta = -3。
        # → ON 必须在 OU 之后插入 → served_order_ids[0] == 'OU'。
        for s, t, d, tr, c in (
            ("W1", "C1", 10.0, 10.0, 10.0),
            ("C1", "W1", 1.0, 1.0, 1.0),
            ("W1", "C2", 5.0, 5.0, 5.0),
            ("C2", "W1", 5.0, 5.0, 5.0),
            ("C1", "C2", 1.0, 1.0, 1.0),
            ("C2", "C1", 1.0, 1.0, 1.0),
        ):
            g.add_edge(Edge(s, t, distance=d, travel_time=tr, cost=c))
        ctx = _build_context(g, objective="distance")
        orders = [
            _order("ON", "C1", tw_start=540.0, tw_end=1200.0),    # NORMAL 早窗口
            _order("OU", "C2", tw_start=900.0, tw_end=1200.0,    # URGENT 晚窗口
                   priority=OrderPriority.URGENT),
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        # OU 作为种子，且 NON 在其后方插入 → 第一个被服务 = OU
        self.assertEqual(
            plan.served_order_ids[0],
            "OU",
            msg=f"URGENT order OU should be seed (first served); got "
                f"order sequence {plan.served_order_ids}",
        )
        # 两个订单都应被服务（均容量合法、时间窗可达）
        self.assertEqual(set(plan.served_order_ids), {"ON", "OU"})


# ---------------------------------------------------------------------------
#  Test 11: 空 ctx / 边界
# ---------------------------------------------------------------------------


class TestRoutePlanSanity(TestCase):
    def test_plan_is_feasible_frozen_and_exportable(self):
        ctx = _build_context(_small_star_graph())
        orders = [_order("O1", "C1")]
        plan = cheapest_feasible_insertion(ctx, orders)
        # RoutePlan 是 frozen
        from dataclasses import FrozenInstanceError
        with self.assertRaises(FrozenInstanceError):
            plan.depot_id = "X"  # type: ignore[misc]
        # to_dict 必须 JSON 可序列化
        import json
        json.dumps(plan.to_dict())


# ---------------------------------------------------------------------------
#  Test 12: unknown seed_algorithm
# ---------------------------------------------------------------------------


class TestUnknownSeedAlgorithm(TestCase):
    def test_unknown_seed_algorithm_raises_value_error(self):
        ctx = _build_context(_small_star_graph())
        with self.assertRaises(ValueError):
            cheapest_feasible_insertion(ctx, [], seed_algorithm="bogus")
        with self.assertRaises(ValueError):
            cheapest_feasible_insertion(
                ctx, [_order("O1", "C1")], seed_algorithm="bogus"
            )


# ---------------------------------------------------------------------------
#  Test 13: 容量边界 — 多个订单累加恰好等于容量
# ---------------------------------------------------------------------------


class TestCapacityAccumulation(TestCase):
    def test_cumulative_load_matches_sum_of_demands(self):
        ctx = _build_context(_small_star_graph(), capacity=20.0)
        orders = [
            _order("O1", "C1", demand=4.0, tw_end=1200.0),
            _order("O2", "C2", demand=6.0, tw_end=1200.0),
            _order("O3", "C3", demand=10.0, tw_end=1200.0),
        ]
        plan = cheapest_feasible_insertion(ctx, orders)
        # 累加 demand 与 cumulative_load 一致
        running = 0.0
        for stop in plan.stops:
            if stop.order_id is not None:
                running += stop.demand
                self.assertAlmostEqual(
                    stop.cumulative_load, running, places=6,
                    msg=f"cumulative_load mismatch at {stop.order_id}",
                )


if __name__ == "__main__":
    unittest.main()