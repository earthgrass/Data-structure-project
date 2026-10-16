"""Phase 4 — Random Scenario Generator 综合回归测试。

P0 gate（与 ``# 二十八`` / ``# 二十九`` 一致）：

* A. 单车辆（``len(result.vehicle_id) == 1`` 在 ScheduleResult 上下文中）
* B. 全订单（5 seeds × 3 算法 = 15 配置均得到 served=20, unserved=0）
* C. 闭环（``route[0] == route[-1] == depot_id``）
* D. 不拆单
* E. 容量（``total demand <= vehicle capacity``）
* F. 时间窗（``service_start <= window_end`` 是 planner 默认规则，由
       宽窗与 check_feasibility 共同保证）
* G. 可达性（所有 backbone legs reachable）
* H. seed 完全可复现（signatures identical）

单元 vs 集成：

* 单元测试（不需要 Phase 4 生成器）：手写 Fisher-Yates / 手写 ≥40
  配置校验 / 时间窗反推等；
* 集成测试：5 seeds × 3 算法 跑通 plan_deliveries。
"""
from __future__ import annotations

import json
import unittest
from unittest import TestCase

from logiroute.scenario_generator import (
    DEFAULT_GENERATOR_CONFIG,
    GeneratorConfig,
    generate_scenario,
    validate_generated_scenario,
)
from logiroute.scheduling import plan_deliveries


SEEDS = (0, 1, 42, 100, 2026)
ALGORITHMS = ("nearest_neighbor", "insertion", "two_opt")


def _bundle_signature(bundle) -> str:
    return json.dumps(
        {
            "name": bundle.name,
            "mode": bundle.mode,
            "seed": bundle.random_seed,
            "node_ids": bundle.graph.node_ids,
            "orders": [
                {"id": o.id, "dest": o.destination_id,
                 "demand": o.demand, "tws": o.time_window_start,
                 "twe": o.time_window_end}
                for o in bundle.orders
            ],
            "n_edges": bundle.graph.edge_count,
        },
        sort_keys=True,
        default=str,
    )


class TestPhase4P0Gates(TestCase):
    """P0 验收：5 seeds × 3 algorithms 全部 20/20。"""

    def _check_seed(self, seed: int):
        bundle, backbone = generate_scenario(
            DEFAULT_GENERATOR_CONFIG, seed=seed
        )
        rep = validate_generated_scenario(bundle, backbone=backbone)
        self.assertTrue(
            rep.feasible,
            f"seed={seed} validation failed: {rep.to_dict()}",
        )
        # E. capacity
        self.assertLessEqual(
            rep.total_demand, rep.capacity + 1e-9,
            f"seed={seed} total_demand {rep.total_demand} > capacity {rep.capacity}",
        )
        # G. backbone legs reachable
        self.assertTrue(rep.all_legs_reachable)
        # C. closed tour
        self.assertTrue(rep.closed_route_ok)
        # B. all algorithms serve all
        for algo in ALGORITHMS:
            with self.subTest(algo=algo, seed=seed):
                result = plan_deliveries(bundle, algo, "distance")
                self.assertEqual(
                    len(result.served_order_ids), len(bundle.orders),
                    f"seed={seed} algo={algo} only served "
                    f"{len(result.served_order_ids)}/{len(bundle.orders)}",
                )
                self.assertEqual(len(result.unserved_orders), 0)
                self.assertTrue(result.is_feasible)

    def test_seed0(self): self._check_seed(0)
    def test_seed1(self): self._check_seed(1)
    def test_seed42(self): self._check_seed(42)
    def test_seed100(self): self._check_seed(100)
    def test_seed2026(self): self._check_seed(2026)


class TestPhase4SeedReproducibility(TestCase):
    """H. seed 完全可复现：同 seed 两次产生字节签名相同。"""

    def test_byte_identical_signature(self):
        a, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        b, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        self.assertEqual(_bundle_signature(a), _bundle_signature(b))

    def test_distinct_seeds_diverge(self):
        sigs = set()
        for s in SEEDS:
            b, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=s)
            sigs.add(tuple(b.graph.node_ids))
        self.assertGreaterEqual(
            len(sigs), 3,
            "expected at least 3 distinct node_id sets across 5 seeds",
        )


class TestPhase4SingleVehicle(TestCase):
    """A. 单车辆 + D. 不拆单。"""

    def test_one_vehicle_id(self):
        bundle, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        # 4 vehicles 在场景中；但 planner 真实只用一辆
        result = plan_deliveries(bundle, "insertion", "distance")
        # ScheduleResult 应该有明确的单一 vehicle_id
        self.assertIn(result.vehicle_id, {v.id for v in bundle.vehicles})

    def test_no_split_orders(self):
        bundle, backbone = generate_scenario(
            DEFAULT_GENERATOR_CONFIG, seed=42
        )
        result = plan_deliveries(bundle, "nearest_neighbor", "distance")
        # 每个 served_order_id 唯一出现在 served 列表
        self.assertEqual(
            len(result.served_order_ids),
            len(set(result.served_order_ids)),
        )


class TestPhase4DefaultConfig(TestCase):
    """默认配置 = 与 AGENTS §3.6 兼容基线。"""

    def test_default_quota(self):
        b, _ = generate_scenario(DEFAULT_GENERATOR_CONFIG, seed=42)
        from logiroute.core.enums import NodeType
        counts = {t: 0 for t in NodeType}
        for n in b.graph.get_all_nodes():
            counts[n.node_type] += 1
        self.assertGreaterEqual(counts[NodeType.WAREHOUSE],
                                DEFAULT_GENERATOR_CONFIG.min_warehouses)
        self.assertGreaterEqual(counts[NodeType.CUSTOMER],
                                DEFAULT_GENERATOR_CONFIG.min_customers)
        self.assertGreaterEqual(counts[NodeType.TRANSFER],
                                DEFAULT_GENERATOR_CONFIG.min_transfers)
        self.assertGreaterEqual(b.graph.node_count,
                                DEFAULT_GENERATOR_CONFIG.min_nodes)
        self.assertGreaterEqual(b.graph.edge_count,
                                DEFAULT_GENERATOR_CONFIG.min_edges)


if __name__ == "__main__":
    unittest.main()
