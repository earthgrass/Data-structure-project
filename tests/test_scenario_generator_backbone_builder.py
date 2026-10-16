"""``tests/test_scenario_generator_backbone_builder.py`` —— backbone builder 单测。"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import TestCase

from logiroute.config import load_scenario
from logiroute.scenario_generator.backbone_builder import build_backbone_and_orders
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.random_source import RandomSource


SCENARIO_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "scenario.json"
)


class TestBackboneBuilderBasics(TestCase):
    def test_returns_closed_backbone_with_orders(self):
        bundle = load_scenario(SCENARIO_FILE)
        cfg = GeneratorConfig(orders_count=8)  # 小一点，免得超出 capacity
        rng = RandomSource(7)
        result = build_backbone_and_orders(bundle.graph, cfg, rng)
        self.assertIsNotNone(result)
        backbone, orders = result
        # 闭环
        self.assertEqual(backbone[0], backbone[-1])
        # 中间节点数 == orders 数
        self.assertEqual(len(backbone) - 2, len(orders))
        # destination 必在 backbone 内
        for o in orders:
            self.assertIn(o.destination_id, backbone)

    def test_total_demand_within_capacity(self):
        bundle = load_scenario(SCENARIO_FILE)
        cfg = GeneratorConfig(
            orders_count=10, capacity=250.0,
            min_demand=4.0, max_demand=8.0,
        )
        rng = RandomSource(7)
        result = build_backbone_and_orders(bundle.graph, cfg, rng)
        self.assertIsNotNone(result)
        _, orders = result
        self.assertLessEqual(sum(o.demand for o in orders), 250.0 + 1e-9)

    def test_returns_none_when_capacity_too_small(self):
        bundle = load_scenario(SCENARIO_FILE)
        # 单订单 demand 上限 5 但车辆容量仅 10 —— 20 单必然超过
        cfg = GeneratorConfig(
            orders_count=20, capacity=10.0,
            min_demand=4.0, max_demand=5.0,
        )
        rng = RandomSource(7)
        result = build_backbone_and_orders(bundle.graph, cfg, rng)
        self.assertIsNone(result)

    def test_reproducible_with_seed(self):
        bundle = load_scenario(SCENARIO_FILE)
        cfg = GeneratorConfig(orders_count=5)
        a = build_backbone_and_orders(bundle.graph, cfg, RandomSource(42))
        b = build_backbone_and_orders(bundle.graph, cfg, RandomSource(42))
        self.assertEqual(a, b)

    def test_different_seeds_different_backbones(self):
        bundle = load_scenario(SCENARIO_FILE)
        cfg = GeneratorConfig(orders_count=10)
        a = build_backbone_and_orders(bundle.graph, cfg, RandomSource(1))
        b = build_backbone_and_orders(bundle.graph, cfg, RandomSource(2))
        # 至少 backbone 不同
        self.assertNotEqual(a[0], b[0])


class TestBackboneBuilderTimeWindows(TestCase):
    def test_all_orders_share_a_flat_window(self):
        """每个订单共享一个扁平宽窗口（不是 per-order 围绕 arrival 收紧）。

        原因：planner（NN / CFI / 2-opt）可能选择与 backbone 不同的访问
        顺序；只有当 window 宽到覆盖**任意**可能的 0..N 访问时间时，
        才不会因为启发式偏差漏单。

        window 公式：tw_start = initial_time - 30 ; tw_end = backbone
        沿 Phase 2 Dijkstra 的最后返回时刻 + config.window_total_extra。
        """
        from logiroute.algorithms.dijkstra import shortest_path

        bundle = load_scenario(SCENARIO_FILE)
        cfg = GeneratorConfig(orders_count=8, capacity=250.0,
                              window_total_extra=120.0)
        rng = RandomSource(7)
        result = build_backbone_and_orders(bundle.graph, cfg, rng)
        self.assertIsNotNone(result)
        backbone, orders = result
        starts = {o.time_window_start for o in orders}
        ends = {o.time_window_end for o in orders}
        self.assertEqual(len(starts), 1, "all orders should share one window_start")
        self.assertEqual(len(ends), 1, "all orders should share one window_end")

        # 自己跑 backbone 算最后返回时间（独立验证，不调 build_backbone_and_orders 内部）
        cur_t = cfg.initial_time
        for s, t in zip(backbone[:-1], backbone[1:]):
            leg = shortest_path(bundle.graph, s, t, "travel_time")
            cur_t += leg.total_weight + cfg.service_time
        expected_window_end = cur_t + cfg.window_total_extra

        self.assertAlmostEqual(
            next(iter(ends)), expected_window_end, delta=0.5,
            msg="window_end should be last_backbone_return + window_total_extra",
        )


if __name__ == "__main__":
    unittest.main()
