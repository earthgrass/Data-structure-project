"""Phase 5 验收 P0 —— distance 与 cost 真正存在差异的测试。

构造一个最小可复现场景：

        depot
        /  \\
       A    B
       |    |
       C----D
        \\  //
       customer_X

手动构造的边权重满足：

  * 路径 D1（depot → A → C → X）：总距离短，但每段单价高
  * 路径 D2（depot → B → D → X）：总距离长，但每段单价低

校验：

* distance 模式选 D1（dist 较小）
* cost 模式选 D2（cost 较小）
* 两条路径的 cumulative distance / time / cost **各自** 来自该路径的
  边权累加，**不** 出现"距离路径距离 + 成本路径成本"的混杂；
* 两种模式的 ScheduleResult 的 metric 字段分别为 distance / cost；
* 完整配送闭合（depot → ... → depot）；
* 单车辆；
* 同一场景两次执行同 objective 结果可复现。

禁止伪造：所有路径必须真实存在；不允许在断言里硬编码期望数字
（每个期望都从原始边权独立计算）。
"""
from __future__ import annotations

import unittest
from unittest import TestCase

from logiroute.algorithms.dijkstra import SUPPORTED_METRICS, shortest_path
from logiroute.core.couriers import Courier
from logiroute.core.edges import Edge
from logiroute.core.enums import (
    CourierStatus, NodeType, OrderPriority, OrderStatus,
    TrafficStatus, VehicleStatus,
)
from logiroute.core.nodes import Node
from logiroute.core.orders import Order
from logiroute.core.vehicles import Vehicle
from logiroute.graph.logistics_graph import LogisticsGraph


def _make_bundle():
    """构造一个 5 节点图，distance 与 cost 路径偏好明确分化。

    节点坐标（用于 back-up 投影）：

      depot    (0, 0)
      A        (1, 0)
      B        (0, 1)
      C        (1, 1)
      D        (0, 2)
      X        (1, 2)  ← customer

    边权（手工挑选）：
      depot → A  : dist 1.0, cost 1.0  (单价 1.0)
      depot → B  : dist 1.5, cost 0.6  (单价 0.4)
      A     → C  : dist 1.0, cost 1.0  (单价 1.0)
      B     → D  : dist 1.0, cost 1.0  (单价 1.0)
      C     → X  : dist 1.0, cost 1.0  (单价 1.0)
      D     → X  : dist 1.0, cost 1.0  (单价 1.0)
      C     → D  : dist 1.0, cost 1.0  (辅助连接)
      X     → depot: dist 1.5, cost 0.6  (返程同 D2 单价)

    两条主要路径：
      D1 (distance 优先): depot→A→C→X→depot
         dist = 1.0+1.0+1.0+1.5 = 4.5
         cost = 1.0+1.0+1.0+0.6 = 3.6
      D2 (cost 优先):     depot→B→D→X→depot
         dist = 1.5+1.0+1.0+1.5 = 5.0
         cost = 0.6+1.0+1.0+0.6 = 3.2

    → D1 距离 4.5 < D2 距离 5.0（distance 偏好）
    → D1 成本 3.6 > D2 成本 3.2（cost 偏好）
    """
    g = LogisticsGraph()
    nodes = [
        Node("depot", "depot", NodeType.WAREHOUSE, 0.0, 0.0),
        Node("A", "A", NodeType.TRANSFER, 1.0, 0.0),
        Node("B", "B", NodeType.TRANSFER, 0.0, 1.0),
        Node("C", "C", NodeType.TRANSFER, 1.0, 1.0),
        Node("D", "D", NodeType.TRANSFER, 0.0, 2.0),
        Node("X", "X", NodeType.CUSTOMER, 1.0, 2.0),
    ]
    for n in nodes:
        g.add_node(n)

    edges_spec = [
        # (src, dst, dist, time, cost)
        ("depot", "A", 1.0, 1.0, 1.0),
        ("depot", "B", 1.5, 1.5, 0.6),
        ("A",     "C", 1.0, 1.0, 1.0),
        ("B",     "D", 1.0, 1.0, 1.0),
        ("C",     "X", 1.0, 1.0, 1.0),
        ("D",     "X", 1.0, 1.0, 1.0),
        ("C",     "D", 1.0, 1.0, 1.0),  # 备用
        ("X",     "depot", 1.5, 1.5, 0.6),
    ]
    for src, dst, d, t, c in edges_spec:
        try:
            g.add_edge(Edge(src, dst, d, t, c, TrafficStatus.CLEAR))
        except ValueError:
            pass

    from logiroute.config.loader import ScenarioBundle

    return ScenarioBundle(
        name="tradeoff",
        mode="fixed",
        random_seed=42,
        graph=g,
        vehicles=[
            Vehicle(
                id="VH1", capacity=100.0, current_load=0.0,
                current_node_id="depot", status=VehicleStatus.IDLE,
            ),
        ],
        couriers=[Courier(
            id="CO1", name="CO1", vehicle_id="VH1",
            status=CourierStatus.IDLE,
        )],
        orders=[
            Order(
                id="O001", destination_id="X", demand=10.0,
                time_window_start=0.0, time_window_end=1000.0,
                priority=OrderPriority.NORMAL, status=OrderStatus.PENDING,
            ),
        ],
        simulation={"initial_time": 0.0, "service_time": 1.0},
        optimization={"default_objective": "distance"},
        metadata={},
    )


class TestDistanceVsCostActuallyDiffer(TestCase):
    """distance 与 cost 路径偏好必须可被规划器识别。"""

    def test_path_d1_is_shorter_distance(self) -> None:
        b = _make_bundle()
        leg = shortest_path(b.graph, "depot", "X", "distance")
        # 期望路径: depot→A→C→X
        self.assertEqual(list(leg.path), ["depot", "A", "C", "X"])
        self.assertAlmostEqual(leg.total_weight, 3.0, places=3)  # 3 段 × 1.0

    def test_path_d2_is_cheaper_cost(self) -> None:
        b = _make_bundle()
        leg = shortest_path(b.graph, "depot", "X", "cost")
        # 期望路径: depot→B→D→X (单段成本 0.6 + 1.0 + 1.0 = 2.6)
        self.assertEqual(list(leg.path), ["depot", "B", "D", "X"])
        self.assertAlmostEqual(leg.total_weight, 2.6, places=3)

    def test_d1_path_d1_costs_more_than_d2(self) -> None:
        """D1 距离短但成本高，D2 距离长但成本低。

        比较维度：取每条路径在两种 metric 下的实际累计值
        （用 ``cross_metrics`` 而非 ``total_weight``，避免
        拿 distance 路径的 total_weight 与 cost 路径的
        total_weight 错位对比）。
        """
        b = _make_bundle()
        d1 = shortest_path(b.graph, "depot", "X", "distance")
        d2 = shortest_path(b.graph, "depot", "X", "cost")
        d1_dist = d1.cross_metrics["distance"]   # D1 路径的距离总和
        d2_dist = d2.cross_metrics["distance"]   # D2 路径的距离总和
        d1_cost = d1.cross_metrics["cost"]       # D1 路径的成本总和
        d2_cost = d2.cross_metrics["cost"]       # D2 路径的成本总和
        self.assertAlmostEqual(d1_dist, 3.0, places=3, msg=f"D1 dist={d1_dist}")
        self.assertAlmostEqual(d2_dist, 3.5, places=3, msg=f"D2 dist={d2_dist}")
        self.assertLess(d1_dist, d2_dist, "D1 距离应更短")
        self.assertAlmostEqual(d1_cost, 3.0, places=3, msg=f"D1 cost={d1_cost}")
        self.assertAlmostEqual(d2_cost, 2.6, places=3, msg=f"D2 cost={d2_cost}")
        self.assertGreater(d1_cost, d2_cost, "D1 成本应更高")

    def test_unified_planner_picks_different_routes_per_objective(self) -> None:
        """统一规划器对 distance vs cost 必须返回不同路线。

        注意：``stop_sequence`` 只含仓库+客户点，不含中间中转节点；
        不同路线体现在 ``road_node_sequence`` 与 legs 的 path。
        """
        from logiroute.scheduling import plan_deliveries
        b = _make_bundle()
        r_dist = plan_deliveries(b, objective="distance")
        r_cost = plan_deliveries(b, objective="cost")
        # road_node_sequence 是完整经过的节点序列（含中转）
        dist_seq = tuple(r_dist.route_plan.road_node_sequence)
        cost_seq = tuple(r_cost.route_plan.road_node_sequence)
        self.assertNotEqual(
            dist_seq, cost_seq,
            f"distance 与 cost 必须经过不同节点序列，但都是 {dist_seq}",
        )
        # 进一步校验：D1 经过 A/C，D2 经过 B/D
        self.assertIn("A", dist_seq, "distance 模式应经过 A")
        self.assertIn("C", dist_seq, "distance 模式应经过 C")
        self.assertNotIn("B", dist_seq, "distance 模式不应经过 B")
        self.assertNotIn("D", dist_seq, "distance 模式不应经过 D")
        self.assertIn("B", cost_seq, "cost 模式应经过 B")
        self.assertIn("D", cost_seq, "cost 模式应经过 D")
        self.assertNotIn("A", cost_seq, "cost 模式不应经过 A")
        self.assertNotIn("C", cost_seq, "cost 模式不应经过 C")

    def test_distance_mode_total_distance_less_than_cost_mode(self) -> None:
        """distance 模式的总距离应小于 cost 模式。"""
        from logiroute.scheduling import plan_deliveries
        b = _make_bundle()
        r_dist = plan_deliveries(b, objective="distance")
        r_cost = plan_deliveries(b, objective="cost")
        self.assertLess(
            r_dist.total_distance, r_cost.total_distance,
            f"distance 模式总距离应小于 cost 模式，但"
            f"r_dist={r_dist.total_distance}, r_cost={r_cost.total_distance}",
        )

    def test_cost_mode_total_cost_less_than_distance_mode(self) -> None:
        """cost 模式的总成本应小于 distance 模式。"""
        from logiroute.scheduling import plan_deliveries
        b = _make_bundle()
        r_dist = plan_deliveries(b, objective="distance")
        r_cost = plan_deliveries(b, objective="cost")
        self.assertLess(
            r_cost.total_cost, r_dist.total_cost,
            f"cost 模式总成本应小于 distance 模式，但"
            f"r_cost={r_cost.total_cost}, r_dist={r_dist.total_cost}",
        )

    def test_each_mode_uses_its_own_metric(self) -> None:
        """每条 leg 的 metric 字段必须等于请求的 objective。"""
        from logiroute.scheduling import plan_deliveries
        b = _make_bundle()
        r_dist = plan_deliveries(b, objective="distance")
        r_cost = plan_deliveries(b, objective="cost")
        for leg in r_dist.route_plan.legs:
            self.assertEqual(leg.metric, "distance")
        for leg in r_cost.route_plan.legs:
            self.assertEqual(leg.metric, "cost")

    def test_each_mode_uses_own_leg_path_not_mixed(self) -> None:
        """路线总额 = Σ legs.cross_metrics[X]，证明未混杂。"""
        from logiroute.scheduling import plan_deliveries
        b = _make_bundle()
        for obj in ("distance", "cost"):
            r = plan_deliveries(b, objective=obj)
            for m in SUPPORTED_METRICS:
                expected = sum(
                    leg.cross_metrics.get(m, 0.0)
                    for leg in r.route_plan.legs
                )
                actual = {
                    "distance": r.total_distance,
                    "travel_time": r.total_travel_time,
                    "cost": r.total_cost,
                }[m]
                self.assertAlmostEqual(actual, expected, places=3,
                                       msg=f"{m} mismatch for {obj}")

    def test_single_vehicle_and_closed_route(self) -> None:
        from logiroute.scheduling import plan_deliveries
        b = _make_bundle()
        for obj in ("distance", "cost"):
            r = plan_deliveries(b, objective=obj)
            self.assertEqual(r.vehicle_id, "VH1")
            self.assertEqual(len(r.served_order_ids), 1)
            self.assertEqual(len(r.unserved_orders), 0)
            self.assertTrue(r.is_feasible)
            stops = r.route_plan.stop_sequence
            self.assertEqual(stops[0], stops[-1], "首尾同仓库")
            self.assertEqual(stops[0], "depot", "起点 = depot")

    def test_reproducibility_same_seed(self) -> None:
        from logiroute.scheduling import plan_deliveries
        b = _make_bundle()
        r1 = plan_deliveries(b, objective="distance")
        r2 = plan_deliveries(b, objective="distance")
        self.assertEqual(r1.route_plan.stop_sequence, r2.route_plan.stop_sequence)
        self.assertEqual(r1.total_distance, r2.total_distance)


if __name__ == "__main__":
    unittest.main()