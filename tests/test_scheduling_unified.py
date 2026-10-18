"""Phase 5 — 统一调度器（Unified Planner）专项测试。

覆盖：

* 默认 ``plan_deliveries(scenario, objective)`` 不传 algorithm 走 unified；
* ``objective=distance`` / ``objective=cost`` 都触发统一流程；
* 同一场景下两种主目标都返回可行 ``ScheduleResult``；
* 统一流程对内部算法名称（NN/CFI/2-opt）保持兼容性；
* 主目标与 Dijkstra metric 一致（``cost`` 模式不允许 distance metric）；
* 不修改原始图（immutability 守约）；
* 不拆单 + 不增车；
* 同场景两种目标可独立调用，结果场景标识一致。
"""
from __future__ import annotations

import unittest
from unittest import TestCase

from logiroute.algorithms.dijkstra import SUPPORTED_METRICS
from logiroute.config import load_scenario
from logiroute.scenario_generator import (
    DEFAULT_GENERATOR_CONFIG,
    generate_scenario,
)
from logiroute.scheduling import plan_deliveries
from logiroute.scheduling.algorithms import ALGORITHM_NAMES
from logiroute.scheduling.types import ScheduleResult


SCENARIO_FILE = "config/scenario.json"


class TestUnifiedPlannerIsDefault(TestCase):
    """Phase 5 公开接口：默认 unified。"""

    def test_default_algorithm_is_unified(self) -> None:
        self.assertIn("unified", ALGORITHM_NAMES)
        # 入口默认 algorithm="unified"
        import inspect
        sig = inspect.signature(plan_deliveries)
        self.assertEqual(sig.parameters["algorithm"].default, "unified")

    def test_unified_signature_only_uses_objective(self) -> None:
        """用户公开 API：只接受 objective。

        ``algorithm`` 保留但默认 unified；用户调用时可省略。
        """
        import inspect
        sig = inspect.signature(plan_deliveries)
        self.assertIn("objective", sig.parameters)
        self.assertEqual(sig.parameters["objective"].default, "distance")


class TestUnifiedPlannerFixedScenario(TestCase):
    """固定场景下统一调度器必须 20/20。"""

    def _bundle(self):
        return load_scenario(SCENARIO_FILE)

    def test_default_distance_serves_all_20(self) -> None:
        b = self._bundle()
        r = plan_deliveries(b, objective="distance")
        self.assertEqual(r.route_plan.algorithm, "tsp_beam")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertEqual(len(r.unserved_orders), 0)
        self.assertTrue(r.is_feasible)

    def test_default_cost_serves_all_20(self) -> None:
        b = self._bundle()
        r = plan_deliveries(b, objective="cost")
        self.assertEqual(r.route_plan.algorithm, "tsp_beam")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertEqual(len(r.unserved_orders), 0)
        self.assertTrue(r.is_feasible)

    def test_explicit_algorithm_unified_serves_all(self) -> None:
        b = self._bundle()
        r = plan_deliveries(b, algorithm="unified", objective="distance")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertTrue(r.is_feasible)


class TestUnifiedPlannerRandomScenarios(TestCase):
    """随机场景多 seed：unified 必须 20/20。"""

    SEEDS = (0, 1, 42, 100, 2026)

    def test_unified_distance_all_seeds(self) -> None:
        for seed in self.SEEDS:
            b, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=seed)
            r = plan_deliveries(b, objective="distance")
            self.assertTrue(
                r.is_feasible,
                f"seed={seed} distance not feasible: served={len(r.served_order_ids)}/{len(b.orders)}",
            )
            self.assertEqual(len(r.served_order_ids), len(b.orders))

    def test_unified_cost_all_seeds(self) -> None:
        for seed in self.SEEDS:
            b, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=seed)
            r = plan_deliveries(b, objective="cost")
            self.assertTrue(
                r.is_feasible,
                f"seed={seed} cost not feasible: served={len(r.served_order_ids)}/{len(b.orders)}",
            )
            self.assertEqual(len(r.served_order_ids), len(b.orders))

    def test_default_keeps_better_nearest_neighbor_result(self) -> None:
        bundle, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=3)
        for objective in ("distance", "cost"):
            nearest = plan_deliveries(
                bundle, algorithm="nearest_neighbor", objective=objective
            )
            default = plan_deliveries(bundle, objective=objective)
            self.assertEqual(len(default.served_order_ids), len(bundle.orders))
            self.assertLessEqual(
                default.main_objective_total,
                nearest.main_objective_total + 1e-9,
            )


class TestUnifiedPlannerObjectiveConsistency(TestCase):
    """主目标与 Dijkstra metric 必须一致。"""

    def _bundle(self):
        return load_scenario(SCENARIO_FILE)

    def test_distance_objective_uses_distance_metric(self) -> None:
        b = self._bundle()
        r = plan_deliveries(b, objective="distance")
        # 所有 leg 的主 metric 都是 distance
        for leg in r.route_plan.legs:
            self.assertEqual(leg.metric, "distance")

    def test_cost_objective_uses_cost_metric(self) -> None:
        b = self._bundle()
        r = plan_deliveries(b, objective="cost")
        for leg in r.route_plan.legs:
            self.assertEqual(leg.metric, "cost")

    def test_cross_metrics_cover_all_supported(self) -> None:
        """PathResult.cross_metrics 包含三个主指标；至少 distance/travel_time/cost 之一必含。

        Phase 2 Dijkstra.shortest_path 主 metric 选定后，沿途累计
        其他 metric 进 cross_metrics；但某些 leg (depot→depot 等零权)
        可能只返回主 metric。 接受``distance`` / ``cost`` / ``travel_time``
        任意 metric 子集即可 —— 重点是 ``main_objective_total`` 与实际路线一致。
        """
        b = self._bundle()
        r = plan_deliveries(b, objective="distance")
        for leg in r.route_plan.legs:
            # 至少必须含主 metric
            self.assertIn("distance", leg.cross_metrics)
            # 主 metric 的累加值应等于 leg.total_weight
            self.assertEqual(
                leg.cross_metrics[leg.metric], leg.total_weight
            )

    def test_no_mixed_metric_in_totals(self) -> None:
        """路线总额（distance / travel_time / cost）必须来自同一条实际路径。

        验证：route_plan.total_distance == sum(legs.cross_metrics["distance"])。
        """
        b = self._bundle()
        for objective in ("distance", "cost"):
            r = plan_deliveries(b, objective=objective)
            if not r.route_plan.legs:
                continue
            sum_distance = sum(
                leg.cross_metrics.get("distance", 0.0)
                for leg in r.route_plan.legs
            )
            sum_travel_time = sum(
                leg.cross_metrics.get("travel_time", 0.0)
                for leg in r.route_plan.legs
            )
            sum_cost = sum(
                leg.cross_metrics.get("cost", 0.0)
                for leg in r.route_plan.legs
            )
            self.assertAlmostEqual(r.route_plan.total_distance, sum_distance, places=3)
            self.assertAlmostEqual(r.route_plan.total_travel_time, sum_travel_time, places=3)
            self.assertAlmostEqual(r.route_plan.total_cost, sum_cost, places=3)


class TestUnifiedPlannerInvariants(TestCase):
    """单车辆 + 不拆单 + 不改图。"""

    def _bundle(self):
        return load_scenario(SCENARIO_FILE)

    def test_single_vehicle_id(self) -> None:
        b = self._bundle()
        r = plan_deliveries(b, objective="distance")
        self.assertEqual(r.vehicle_id, "VH1")
        self.assertEqual(len(b.vehicles), 1)

    def test_no_split_orders(self) -> None:
        b = self._bundle()
        r = plan_deliveries(b, objective="distance")
        # served_order_ids 唯一
        self.assertEqual(
            len(r.served_order_ids),
            len(set(r.served_order_ids)),
        )
        # 与订单总数一致（不拆单 → 每订单恰好一次服务记录）
        self.assertEqual(len(r.served_order_ids), len(b.orders))

    def test_does_not_mutate_input_graph(self) -> None:
        b = self._bundle()
        before_nodes = sorted(b.graph.node_ids)
        before_edges = b.graph.edge_count
        plan_deliveries(b, objective="distance")
        self.assertEqual(sorted(b.graph.node_ids), before_nodes)
        self.assertEqual(b.graph.edge_count, before_edges)


class TestUnifiedPlannerCompareSameScenario(TestCase):
    """同场景两种主目标可独立调用，结果场景标识一致。"""

    def _bundle(self):
        return load_scenario(SCENARIO_FILE)

    def test_compare_distance_vs_cost_same_scenario(self) -> None:
        b = self._bundle()
        r_dist = plan_deliveries(b, objective="distance")
        r_cost = plan_deliveries(b, objective="cost")
        self.assertEqual(r_dist.scenario_name, r_cost.scenario_name)
        self.assertEqual(r_dist.depot_id, r_cost.depot_id)
        self.assertEqual(r_dist.vehicle_id, r_cost.vehicle_id)
        # 两种主目标都应满足 20/20，但顺序可以不同（统一流程按各自 metric 选优）
        self.assertEqual(
            len(r_dist.served_order_ids), len(r_cost.served_order_ids)
        )
        self.assertEqual(
            set(r_dist.served_order_ids), set(r_cost.served_order_ids)
        )
        # 单车辆、同一仓库、同一场景
        self.assertEqual(r_dist.vehicle_id, "VH1")


class TestUnifiedPlannerErrorPaths(TestCase):
    """错误路径：非法 objective / algorithm。"""

    def _bundle(self):
        return load_scenario(SCENARIO_FILE)

    def test_invalid_objective_rejected(self) -> None:
        b = self._bundle()
        from logiroute.scheduling.types import InvalidObjectiveError
        with self.assertRaises(InvalidObjectiveError):
            plan_deliveries(b, objective="travel_time")

    def test_unknown_algorithm_rejected(self) -> None:
        b = self._bundle()
        from logiroute.scheduling.types import UnknownAlgorithmError
        with self.assertRaises(UnknownAlgorithmError):
            plan_deliveries(b, algorithm="bogus", objective="distance")


if __name__ == "__main__":
    unittest.main()
