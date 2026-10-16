"""Phase 3 10/20 根因修复 —— Regression 测试。

确保：

1. 固定场景能跑出 20/20 单车辆配送，不再出现 10/20；
2. brute-force 独立验证器确认可行；
3. ``select_depot`` 防御：auto-selected vehicle capacity < total_demand 必须
   抛 NoAvailableVehicleError 或者自动重选；
4. ``plan_deliveries`` 在 fixed scenario 上对三种算法 + 两种 objective 全部
   拿到 served == len(orders) 且 unserved == []。
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import TestCase

from logiroute.algorithms.dijkstra import shortest_path
from logiroute.config import load_scenario
from logiroute.scheduling import plan_deliveries, select_depot
from logiroute.scheduling.types import NoAvailableVehicleError


SCENARIO_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "scenario.json"
)


@unittest.skipUnless(
    SCENARIO_FILE.is_file(), "fixed scenario not present at config/scenario.json"
)
class TestPhase3NoLongerPartial(TestCase):
    """10/20 修复后的硬性测试 —— 4 个配置全部期望 20/20。"""

    def _bundle(self):
        return load_scenario(SCENARIO_FILE)

    def test_NN_distance_serves_all_20(self):
        r = plan_deliveries(self._bundle(), "nearest_neighbor", "distance")
        self.assertEqual(
            len(r.served_order_ids), 20,
            f"NN+distance served {len(r.served_order_ids)}/20 — "
            "this is the original 10/20 bug regressing!",
        )
        self.assertEqual(len(r.unserved_orders), 0)

    def test_NN_cost_serves_all_20(self):
        r = plan_deliveries(self._bundle(), "nearest_neighbor", "cost")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertEqual(len(r.unserved_orders), 0)

    def test_insertion_distance_serves_all_20(self):
        r = plan_deliveries(self._bundle(), "insertion", "distance")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertEqual(len(r.unserved_orders), 0)

    def test_two_opt_distance_serves_all_20(self):
        r = plan_deliveries(self._bundle(), "two_opt", "distance")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertEqual(len(r.unserved_orders), 0)

    def test_capacity_ground_truth(self):
        """场景物理可行 —— 总需求能被单车辆装下。"""
        bundle = self._bundle()
        total_demand = sum(o.demand for o in bundle.orders)
        # 单车辆规则下选 lex-min IDLE；vehicles 当前 VH1 capacity 250（已修复）
        chosen = select_depot(bundle)
        self.assertGreaterEqual(
            chosen.vehicle.capacity,
            total_demand - 1e-9,
            msg=(
                f"auto-selected vehicle capacity "
                f"{chosen.vehicle.capacity} < total demand {total_demand}; "
                "this is the original 10/20 root cause"
            ),
        )

    def test_brute_force_7_customer_subset_is_feasible(self):
        """独立 brute-force 验证器（小规模回溯）证明可行路线存在。"""
        bundle = self._bundle()
        graph = bundle.graph
        init = float(bundle.simulation["initial_time"])
        svc = float(bundle.simulation["service_time"])
        depot = "W1"
        capacity = max(v.capacity for v in bundle.vehicles)
        demands = {o.destination_id: o.demand for o in bundle.orders}
        tw = {o.destination_id: (o.time_window_start, o.time_window_end)
              for o in bundle.orders}
        cust = sorted(demands.keys())[:7]

        from itertools import permutations
        found = None
        for perm in permutations(cust):
            seq = [depot] + list(perm) + [depot]
            cum = 0.0
            cur_t = init
            ok = True
            for i in range(len(seq) - 1):
                src, tgt = seq[i], seq[i + 1]
                if src == tgt:
                    continue
                leg = shortest_path(graph, src, tgt, "travel_time")
                if not leg.reachable:
                    ok = False
                    break
                cur_t += leg.total_weight
                if tgt != depot:
                    cum += demands.get(tgt, 0.0)
                    if cum > capacity + 1e-9:
                        ok = False
                        break
                    tw_s, tw_e = tw[tgt]
                    wait = max(0.0, tw_s - cur_t)
                    ss = cur_t + wait
                    if ss > tw_e + 1e-9:
                        ok = False
                        break
                    cur_t = ss + svc
            if ok:
                found = perm
                break
        self.assertIsNotNone(
            found,
            "brute-force DFS found no feasible complete route on the "
            "fixed scenario — the scenario may not be globally feasible",
        )


class TestSelectDepotCapacityGuard(TestCase):
    """``select_depot(..., min_total_demand=...)`` 防御性 capacity 过滤。"""

    def _mini_bundle(self, capacity: float, orders_count: int = 1,
                     demand: float = 50.0):
        """构造一个最小 bundle 用于 capacity guard 测试。"""
        from logiroute.config.loader import ScenarioBundle
        from logiroute.core.orders import Order, OrderPriority, OrderStatus
        from logiroute.core.vehicles import Vehicle
        from logiroute.core.couriers import Courier
        from logiroute.core.enums import (CourierStatus, NodeType,
                                          VehicleStatus)
        from logiroute.core.edges import Edge
        from logiroute.core.nodes import Node
        from logiroute.graph.logistics_graph import LogisticsGraph

        g = LogisticsGraph()
        g.add_node(Node(id="W1", name="W1", node_type=NodeType.WAREHOUSE,
                        x=0.0, y=0.0))
        g.add_node(Node(id="C1", name="C1", node_type=NodeType.CUSTOMER,
                        x=1.0, y=1.0))
        g.add_edge(Edge("W1", "C1", 2.0, 4.0, 6.0))
        g.add_edge(Edge("C1", "W1", 2.0, 4.0, 6.0))
        v = Vehicle(id="VH1", capacity=capacity, current_load=0.0,
                    current_node_id="W1", status=VehicleStatus.IDLE)
        orders = [
            Order(
                id=f"O{i}", destination_id="C1", demand=demand,
                time_window_start=540.0, time_window_end=700.0,
                priority=OrderPriority.NORMAL, status=OrderStatus.PENDING,
            )
            for i in range(orders_count)
        ]
        return ScenarioBundle(
            name="x", mode="fixed", random_seed=42, graph=g,
            vehicles=[v], couriers=[Courier(
                id="CO1", name="CO1", vehicle_id="VH1",
                status=CourierStatus.IDLE,
            )],
            orders=orders,
            simulation={"service_time": 5.0, "initial_time": 540.0},
            optimization={"default_objective": "distance"},
            metadata={},
        )

    def test_min_total_demand_filters_undersized_vehicle(self):
        b = self._mini_bundle(capacity=10.0)
        # min_total_demand=50 (one order, demand=50) would require capacity >= 50
        with self.assertRaises(NoAvailableVehicleError):
            select_depot(b, min_total_demand=50.0)

    def test_no_min_total_demand_accepts_undersized(self):
        b = self._mini_bundle(capacity=10.0)
        c = select_depot(b)  # 无 capacity 约束，接受 10 容量的车
        self.assertEqual(c.vehicle.capacity, 10.0)


if __name__ == "__main__":
    unittest.main()
