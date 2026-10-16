"""``tests/test_scenario_generator.py`` — 顶层 generate_scenario + 多 seed 集成。"""
from __future__ import annotations

import unittest
from unittest import TestCase

from logiroute.scenario_generator import (
    DEFAULT_GENERATOR_CONFIG,
    GeneratorConfig,
    generate_scenario,
    validate_generated_scenario,
)
from logiroute.scheduling import plan_deliveries


class TestGeneratorSeedReproducibility(TestCase):
    def test_same_seed_same_scenario(self):
        b1, bb1 = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        b2, bb2 = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        # node_ids identical
        self.assertEqual(b1.graph.node_ids, b2.graph.node_ids)
        # orders identical (id / destination / demand / windows)
        self.assertEqual(
            [(o.id, o.destination_id, o.demand, o.time_window_start,
              o.time_window_end) for o in b1.orders],
            [(o.id, o.destination_id, o.demand, o.time_window_start,
              o.time_window_end) for o in b2.orders],
        )
        # backbone identical
        self.assertEqual(bb1, bb2)

    def test_different_seed_different_scenario(self):
        b1, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=1)
        b2, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=2)
        self.assertNotEqual(b1.graph.node_ids, b2.graph.node_ids)

    def test_five_seeds_all_feasible(self):
        """P0: 0/1/42/100/2026 五个 seed 都必须得到可行且能完成全部订单的场景。"""
        for seed in (0, 1, 42, 100, 2026):
            with self.subTest(seed=seed):
                bundle, backbone = generate_scenario(
                    DEFAULT_GENERATOR_CONFIG, seed=seed
                )
                rep = validate_generated_scenario(bundle, backbone=backbone)
                self.assertTrue(
                    rep.feasible,
                    f"seed={seed}: validation report = {rep.to_dict()}",
                )


class TestGeneratorPlannerIntegration(TestCase):
    """生成的场景必须能被 plan_deliveries 完成全部订单（P0 20/20）。

    验证：

    * ``len(result.served_order_ids) == len(bundle.orders)``
    * ``len(result.unserved_orders) == 0``
    * ``result.is_feasible is True``
    """

    def _run_for_seed(self, seed: int):
        bundle, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=seed)
        result = plan_deliveries(bundle, "insertion", "distance")
        return bundle, result

    def test_seed0_serves_all(self):
        bundle, result = self._run_for_seed(0)
        self.assertEqual(len(result.served_order_ids), len(bundle.orders))
        self.assertEqual(len(result.unserved_orders), 0)

    def test_seed1_serves_all(self):
        bundle, result = self._run_for_seed(1)
        self.assertEqual(len(result.served_order_ids), len(bundle.orders))
        self.assertEqual(len(result.unserved_orders), 0)

    def test_seed42_serves_all(self):
        bundle, result = self._run_for_seed(42)
        self.assertEqual(len(result.served_order_ids), len(bundle.orders))
        self.assertEqual(len(result.unserved_orders), 0)

    def test_seed100_serves_all(self):
        bundle, result = self._run_for_seed(100)
        self.assertEqual(len(result.served_order_ids), len(bundle.orders))
        self.assertEqual(len(result.unserved_orders), 0)

    def test_seed2026_serves_all(self):
        bundle, result = self._run_for_seed(2026)
        self.assertEqual(len(result.served_order_ids), len(bundle.orders))
        self.assertEqual(len(result.unserved_orders), 0)


class TestGeneratorSchemaCompliant(TestCase):
    """生成出的 Scenario 必须能被 Phase 1 loader 重新解析并被 Phase 3 planner 使用。"""

    def test_vehicles_at_depots(self):
        bundle, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        for v in bundle.vehicles:
            # current_node_id is one of warehouse nodes
            from logiroute.core.enums import NodeType
            self.assertIn(v.current_node_id, {
                n.id for n in bundle.graph.get_all_nodes()
                if n.node_type is NodeType.WAREHOUSE
            })

    def test_orders_targets_in_graph(self):
        bundle, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        ids = set(bundle.graph.node_ids)
        for o in bundle.orders:
            self.assertIn(o.destination_id, ids)


class TestGeneratorCustomConfig(TestCase):
    def test_smaller_order_count(self):
        cfg = GeneratorConfig(orders_count=5)
        b, _ = generate_scenario(cfg, seed=42)
        self.assertEqual(len(b.orders), 5)


if __name__ == "__main__":
    unittest.main()
