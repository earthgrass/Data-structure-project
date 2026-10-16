"""``tests/test_scheduling_planner.py`` —— Phase 3 ``plan_deliveries`` 端到端测试。

仅依赖 stdlib + 已存在 core/graph/algorithms/scheduling 模块。
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import TestCase

from logiroute.config.loader import ScenarioBundle, load_scenario
from logiroute.core.couriers import Courier
from logiroute.core.enums import CourierStatus, NodeType, VehicleStatus
from logiroute.core.orders import Order, OrderPriority, OrderStatus
from logiroute.core.vehicles import Vehicle
from logiroute.scheduling import plan_deliveries
from logiroute.scheduling.types import (
    DepotNotFoundError,
    EmptyOrdersError,
    InvalidObjectiveError,
    NoAvailableVehicleError,
    PlanningStats,
    UnknownAlgorithmError,
)


SCENARIO_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "scenario.json"
)


# ---------------------------------------------------------------------------
#  全套单元端到端 —— 基于固定场景
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    SCENARIO_FILE.is_file(), "fixed scenario not present at config/scenario.json"
)
class TestPlannerOnFixedScenario(TestCase):
    """在固定场景上验证 plan_deliveries 端到端契约。"""

    def _bundle(self) -> ScenarioBundle:
        return load_scenario(SCENARIO_FILE)

    def test_three_algorithms_run_end_to_end(self):
        b = self._bundle()
        for algorithm in ("nearest_neighbor", "insertion", "two_opt"):
            with self.subTest(algorithm=algorithm):
                r = plan_deliveries(b, algorithm=algorithm, objective="distance")
                self.assertIsNotNone(r.route_plan)
                self.assertTrue(len(r.route_plan.stop_sequence) >= 2)
                self.assertEqual(
                    r.route_plan.stop_sequence[0],
                    r.route_plan.stop_sequence[-1],
                    msg=f"tour must close for algorithm={algorithm}",
                )
                # depot_id 与 vehicle_id 不必相等：depot 是节点，vehicle 是车辆
                self.assertEqual(r.depot_id, r.route_plan.depot_id)

    def test_route_is_closed_loop(self):
        b = self._bundle()
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        self.assertEqual(
            r.route_plan.stop_sequence[0],
            r.route_plan.stop_sequence[-1],
            "must form a closed tour from chosen depot back to same depot",
        )

    def test_objective_distance_uses_distance_column(self):
        b = self._bundle()
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        self.assertAlmostEqual(
            r.main_objective_total,
            r.total_distance,
            places=6,
            msg="main_objective_total under objective='distance' must match total_distance",
        )

    def test_objective_cost_uses_cost_column(self):
        b = self._bundle()
        r = plan_deliveries(b, "nearest_neighbor", "cost")
        self.assertAlmostEqual(
            r.main_objective_total,
            r.total_cost,
            places=6,
        )

    def test_travel_time_uses_cross_metrics_not_total_weight(self):
        b = self._bundle()
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        # total_travel_time 必须来自 cross_metrics（实际行驶时间），
        # 而不是 path 的 total_weight（distance 主目标下两者通常不同）
        legs = r.route_plan.legs
        expected = 0.0
        for leg in legs:
            cm = leg.cross_metrics or {}
            expected += float(cm.get("travel_time", leg.total_weight))
        self.assertAlmostEqual(r.total_travel_time, expected, places=6)

    def test_unknown_algorithm_raises(self):
        b = self._bundle()
        with self.assertRaises(UnknownAlgorithmError):
            plan_deliveries(b, algorithm="bogus_algo", objective="distance")

    def test_invalid_objective_raises(self):
        b = self._bundle()
        with self.assertRaises(InvalidObjectiveError):
            plan_deliveries(b, "nearest_neighbor", objective="travel_time")

    def test_planning_stats_populated(self):
        b = self._bundle()
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        self.assertIsInstance(r.planning_stats, PlanningStats)
        self.assertGreaterEqual(r.planning_stats.dijkstra_calls, 1)
        self.assertGreater(r.planning_stats.runtime_seconds, 0.0)
        self.assertGreaterEqual(r.planning_stats.paths_evaluated, 1)

    def test_two_opt_iterations_counter(self):
        b = self._bundle()
        r = plan_deliveries(b, "two_opt", "distance")
        self.assertIsInstance(r.planning_stats.iterations, int)
        self.assertGreaterEqual(r.planning_stats.iterations, 0)

    def test_result_is_json_serializable(self):
        import json

        b = self._bundle()
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        d = r.to_dict()
        # legs cross_metrics contain Python floats only; json.dumps must succeed.
        s = json.dumps(d)
        restored = json.loads(s)
        self.assertEqual(restored["scenario_name"], b.name)
        self.assertEqual(restored["algorithm"], "nearest_neighbor")
        self.assertEqual(restored["objective"], "distance")

    def test_unfeasible_orders_drive_global_is_feasible_false(self):
        # If planner cannot serve every order, is_feasible must be False at the
        # global level even when the served route itself is feasible.
        b = self._bundle()
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        # Don't assert about feasibility here — depends on time windows in scenario.
        # Instead: result.is_feasible must equal
        # (plan.is_feasible and len(unserved) == 0).
        expected = r.route_plan.is_feasible and (len(r.unserved_orders) == 0)
        self.assertEqual(r.is_feasible, expected)


# ---------------------------------------------------------------------------
#  参数校验
# ---------------------------------------------------------------------------


class TestPlannerParamValidation(TestCase):
    """不依赖场景文件的纯参数错误分支。"""

    def _minimal_bundle(self, orders=True) -> ScenarioBundle:
        """构造一个最微小的 scenario —— 1 warehouse + 1 customer + 1 order + 1 vehicle。"""
        from logiroute.core.edges import Edge
        from logiroute.core.nodes import Node
        from logiroute.graph.logistics_graph import LogisticsGraph
        from logiroute.config.loader import ScenarioBundle

        g = LogisticsGraph()
        g.add_node(Node(id="W1", name="W1", node_type=NodeType.WAREHOUSE, x=0.0, y=0.0))
        g.add_node(Node(id="C1", name="C1", node_type=NodeType.CUSTOMER, x=1.0, y=1.0))
        g.add_edge(
            Edge(
                source_id="W1", target_id="C1",
                distance=2.0, travel_time=4.0, cost=6.0,
            )
        )
        g.add_edge(
            Edge(
                source_id="C1", target_id="W1",
                distance=2.0, travel_time=4.0, cost=6.0,
            )
        )
        v = Vehicle(
            id="VH1", capacity=100.0,
            current_load=0.0, current_node_id="W1",
            status=VehicleStatus.IDLE,
        )
        c = Courier(
            id="CO1", name="CO1", vehicle_id="VH1",
            status=CourierStatus.IDLE,
        )
        order_list: list[Order] = []
        if orders:
            order_list.append(
                Order(
                    id="O1", destination_id="C1", demand=5.0,
                    time_window_start=540.0, time_window_end=700.0,
                    priority=OrderPriority.NORMAL,
                    status=OrderStatus.PENDING,
                )
            )
        return ScenarioBundle(
            name="mini",
            mode="fixed",
            random_seed=42,
            graph=g,
            vehicles=[v],
            couriers=[c],
            orders=order_list,
            simulation={"service_time": 5.0, "initial_time": 540.0},
            optimization={"default_objective": "distance"},
            metadata={},
        )

    def test_empty_orders_raises(self):
        b = self._minimal_bundle(orders=False)
        with self.assertRaises(EmptyOrdersError):
            plan_deliveries(b, "nearest_neighbor", "distance")

    def test_no_idle_vehicle_raises(self):
        from logiroute.config.loader import ScenarioBundle
        from logiroute.core.edges import Edge
        from logiroute.core.nodes import Node
        from logiroute.graph.logistics_graph import LogisticsGraph
        from logiroute.core.orders import Order

        g = LogisticsGraph()
        g.add_node(Node(id="W1", name="W1", node_type=NodeType.WAREHOUSE, x=0.0, y=0.0))
        g.add_node(Node(id="C1", name="C1", node_type=NodeType.CUSTOMER, x=1.0, y=1.0))
        g.add_edge(Edge("W1", "C1", 2.0, 4.0, 6.0))
        g.add_edge(Edge("C1", "W1", 2.0, 4.0, 6.0))
        # MAINTENANCE: not available
        v = Vehicle(id="VH1", capacity=100.0, current_load=0.0,
                    current_node_id="W1", status=VehicleStatus.MAINTENANCE)
        b = ScenarioBundle(
            name="x", mode="fixed", random_seed=42, graph=g,
            vehicles=[v], couriers=[],
            orders=[Order(
                id="O1", destination_id="C1", demand=5.0,
                time_window_start=540.0, time_window_end=700.0,
                priority=OrderPriority.NORMAL, status=OrderStatus.PENDING,
            )],
            simulation={"service_time": 5.0, "initial_time": 540.0},
            optimization={"default_objective": "distance"},
            metadata={},
        )
        with self.assertRaises(NoAvailableVehicleError):
            plan_deliveries(b, "nearest_neighbor", "distance")

    def test_depot_mismatch_raises(self):
        b = self._minimal_bundle()
        with self.assertRaises(DepotNotFoundError):
            plan_deliveries(b, "nearest_neighbor", "distance", depot_id="NOT_A_NODE")

    def test_demand_exceeds_capacity_marked_unserved(self):
        from logiroute.config.loader import ScenarioBundle
        from logiroute.core.edges import Edge
        from logiroute.core.nodes import Node
        from logiroute.graph.logistics_graph import LogisticsGraph
        from logiroute.core.orders import Order

        g = LogisticsGraph()
        g.add_node(Node(id="W1", name="W1", node_type=NodeType.WAREHOUSE, x=0.0, y=0.0))
        g.add_node(Node(id="C1", name="C1", node_type=NodeType.CUSTOMER, x=1.0, y=1.0))
        g.add_edge(Edge("W1", "C1", 2.0, 4.0, 6.0))
        g.add_edge(Edge("C1", "W1", 2.0, 4.0, 6.0))
        v = Vehicle(id="VH1", capacity=10.0, current_load=0.0,
                    current_node_id="W1", status=VehicleStatus.IDLE)
        order = Order(
            id="O1", destination_id="C1", demand=50.0,  # exceeds capacity
            time_window_start=540.0, time_window_end=700.0,
            priority=OrderPriority.NORMAL, status=OrderStatus.PENDING,
        )
        b = ScenarioBundle(
            name="x", mode="fixed", random_seed=42, graph=g,
            vehicles=[v], couriers=[],
            orders=[order],
            simulation={"service_time": 5.0, "initial_time": 540.0},
            optimization={"default_objective": "distance"},
            metadata={},
        )
        r = plan_deliveries(b, "nearest_neighbor", "distance")
        self.assertEqual(len(r.served_order_ids), 0)
        self.assertEqual(len(r.unserved_orders), 1)
        self.assertEqual(r.unserved_orders[0].kind, "capacity_overflow")
        self.assertFalse(r.is_feasible)


# ---------------------------------------------------------------------------
#  ALLOWED_OBJECTIVES 边界
# ---------------------------------------------------------------------------


class TestObjectiveAllowedSet(TestCase):
    def test_travel_time_objective_rejected(self):
        from logiroute.scheduling.planner import ALLOWED_OBJECTIVES
        self.assertNotIn("travel_time", ALLOWED_OBJECTIVES)
        self.assertIn("distance", ALLOWED_OBJECTIVES)
        self.assertIn("cost", ALLOWED_OBJECTIVES)


if __name__ == "__main__":
    unittest.main()
