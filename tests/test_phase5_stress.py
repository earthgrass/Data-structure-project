"""Phase 5 规格 §四 / §7 — 随机场景压力测试。

20 个不同 seed × 2 种主目标 = 40 组集成验证；每组都必须：

* served == orders（全部订单配送完成）
* unserved == 0
* is_feasible == True
* 单车辆 + 闭合回路
* 独立 validator feasible=True

任意失败立即停止并报 root cause。
"""
from __future__ import annotations

import unittest
from unittest import TestCase

from logiroute.config import load_scenario
from logiroute.scenario_generator import (
    DEFAULT_GENERATOR_CONFIG,
    generate_scenario,
    validate_generated_scenario,
)
from logiroute.scheduling import plan_deliveries

# 20 个不同 seed（覆盖确定性生成器的状态空间）
STRESS_SEEDS = (
    0, 1, 7, 13, 42, 100, 123, 256, 314, 500,
    666, 777, 888, 999, 1024, 1729, 2026, 3141, 4242, 9999,
)


class TestPhase5StressRandom(TestCase):
    """20 seed × 2 objective = 40 组；全部 served = orders + feasible + 闭合。"""

    def _run_one(self, seed: int, objective: str) -> None:
        bundle, backbone = generate_scenario(
            DEFAULT_GENERATOR_CONFIG, seed=seed,
        )
        rep = validate_generated_scenario(bundle, backbone=backbone)
        self.assertTrue(
            rep.feasible,
            f"seed={seed} validator infeasible: {rep.to_dict()}",
        )
        # 单车辆（生成器层）
        self.assertEqual(
            len(bundle.vehicles), 1,
            f"seed={seed} generated {len(bundle.vehicles)} vehicles (must be 1)",
        )
        # backbone 闭合
        self.assertGreaterEqual(len(backbone), 2)
        self.assertEqual(backbone[0], backbone[-1])

        result = plan_deliveries(bundle, objective=objective)
        self.assertTrue(
            result.is_feasible,
            f"seed={seed} objective={objective} not feasible: "
            f"served={len(result.served_order_ids)}/{len(bundle.orders)} "
            f"unserved={len(result.unserved_orders)}",
        )
        self.assertEqual(
            len(result.served_order_ids), len(bundle.orders),
            f"seed={seed} objective={objective} served != orders",
        )
        self.assertEqual(
            len(result.unserved_orders), 0,
            f"seed={seed} objective={objective} has unserved orders",
        )
        # 主目标一致
        self.assertEqual(result.objective, objective)
        # 路径 leg 的主 metric 与 objective 一致
        for leg in result.route_plan.legs:
            self.assertEqual(leg.metric, objective)
            self.assertEqual(
                leg.cross_metrics[objective], leg.total_weight,
                f"seed={seed} leg cross_metrics[{objective}] != total_weight",
            )
        # 路线总额 = legs 之和
        sum_d = sum(leg.cross_metrics.get("distance", 0.0) for leg in result.route_plan.legs)
        sum_t = sum(leg.cross_metrics.get("travel_time", 0.0) for leg in result.route_plan.legs)
        sum_c = sum(leg.cross_metrics.get("cost", 0.0) for leg in result.route_plan.legs)
        self.assertAlmostEqual(result.route_plan.total_distance, sum_d, places=3)
        self.assertAlmostEqual(result.route_plan.total_travel_time, sum_t, places=3)
        self.assertAlmostEqual(result.route_plan.total_cost, sum_c, places=3)

    def test_20_seeds_distance(self) -> None:
        for seed in STRESS_SEEDS:
            with self.subTest(seed=seed):
                self._run_one(seed, "distance")

    def test_20_seeds_cost(self) -> None:
        for seed in STRESS_SEEDS:
            with self.subTest(seed=seed):
                self._run_one(seed, "cost")


class TestPhase5StressFixedScenario(TestCase):
    """固定场景在统一规划器下也必须 20/20。"""

    def _bundle(self):
        return load_scenario("config/scenario.json")

    def test_fixed_distance_serves_all(self) -> None:
        r = plan_deliveries(self._bundle(), objective="distance")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertEqual(len(r.unserved_orders), 0)
        self.assertTrue(r.is_feasible)

    def test_fixed_cost_serves_all(self) -> None:
        r = plan_deliveries(self._bundle(), objective="cost")
        self.assertEqual(len(r.served_order_ids), 20)
        self.assertEqual(len(r.unserved_orders), 0)
        self.assertTrue(r.is_feasible)


class TestPhase5ConservativeHBound(TestCase):
    """H 保守上界必须被窗口覆盖。"""

    def test_window_covers_h_bound(self) -> None:
        for seed in STRESS_SEEDS[:5]:
            b, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=seed)
            tw_end = b.orders[0].time_window_end
            tw_start = b.orders[0].time_window_start
            self.assertGreaterEqual(
                tw_end, tw_start,
                f"seed={seed} tw_end < tw_start",
            )
            # 至少要超过 initial_time + K * 5 分钟（粗略下界）
            min_needed = b.simulation.get("initial_time", 540.0) + 50.0
            self.assertGreaterEqual(tw_end, min_needed)

    def test_scenario_reproducibility_across_seeds(self) -> None:
        """同 seed 两次生成相同场景。"""
        for seed in (0, 42, 2026):
            b1, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=seed)
            b2, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=seed)
            ids1 = sorted(b1.graph.node_ids)
            ids2 = sorted(b2.graph.node_ids)
            self.assertEqual(ids1, ids2, f"seed={seed} node_ids differ")
            self.assertEqual(b1.random_seed, b2.random_seed)


if __name__ == "__main__":
    unittest.main()