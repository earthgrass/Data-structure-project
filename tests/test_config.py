"""配置加载器的单元测试。

完全使用 ``unittest`` 标准库。
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from logiroute.config import (
    ConfigError,
    ScenarioBundle,
    load_scenario,
    load_scenario_from_dict,
)
from logiroute.config.loader import ScenarioLimits


SCENARIO_FILE = "config/scenario.json"


def _scenario_dict() -> dict:
    p = Path(SCENARIO_FILE)
    if not p.is_file():
        raise unittest.SkipTest(f"{SCENARIO_FILE} not present")
    return json.loads(p.read_text(encoding="utf-8"))


class TestLoadHappyPath(unittest.TestCase):
    def test_load_real_scenario_file(self) -> None:
        p = Path(SCENARIO_FILE)
        if not p.is_file():
            self.skipTest(f"{SCENARIO_FILE} not present")
        bundle = load_scenario(p)
        self.assertIsInstance(bundle, ScenarioBundle)
        self.assertEqual(bundle.name, "logiroute.standard.35")
        self.assertEqual(bundle.mode, "fixed")
        self.assertEqual(bundle.random_seed, 42)
        self.assertEqual(bundle.graph.node_count, 35)
        self.assertEqual(len(bundle.vehicles), 4)
        self.assertEqual(len(bundle.couriers), 4)
        self.assertEqual(len(bundle.orders), 20)
        self.assertEqual(bundle.optimization["default_objective"], "distance")
        bundle.graph.validate()

    def test_load_from_dict(self) -> None:
        data = _scenario_dict()
        bundle = load_scenario_from_dict(copy.deepcopy(data))
        self.assertEqual(bundle.graph.node_count, 35)

    def test_bundle_exposes_strongly_typed_objects(self) -> None:
        p = Path(SCENARIO_FILE)
        if not p.is_file():
            self.skipTest(f"{SCENARIO_FILE} not present")
        bundle = load_scenario(p)
        for v in bundle.vehicles:
            self.assertGreater(v.capacity, 0)
            self.assertGreaterEqual(v.current_load, 0)
            self.assertLessEqual(v.current_load, v.capacity)
        for c in bundle.couriers:
            self.assertTrue(c.vehicle_id)
        for o in bundle.orders:
            self.assertLess(o.time_window_start, o.time_window_end)


class TestValidationErrors(unittest.TestCase):
    def _base(self) -> dict:
        try:
            return _scenario_dict()
        except unittest.SkipTest:
            self.skipTest("scenario.json missing")
            raise

    def test_missing_scenario_section(self) -> None:
        data = self._base()
        del data["scenario"]
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_wrong_mode(self) -> None:
        data = self._base()
        data["scenario"]["mode"] = "random"
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_node_too_few(self) -> None:
        data = self._base()
        nodes = data["network"]["nodes"]
        # 切到仅剩 25 个节点
        data["network"]["nodes"] = nodes[:25]
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_warehouse_too_few(self) -> None:
        data = self._base()
        # 删除一个仓库节点；任何引用其的边也清理
        nodes = data["network"]["nodes"]
        whs = [n for n in nodes if n["type"] == "warehouse"]
        data["network"]["nodes"] = [n for n in nodes if n["id"] != whs[0]["id"]]
        data["network"]["edges"] = [
            e for e in data["network"]["edges"]
            if e["source"] != whs[0]["id"] and e["target"] != whs[0]["id"]
        ]
        # 同时移除引用该仓库的车辆
        data["vehicles"] = [
            v for v in data["vehicles"] if v.get("current_node_id") != whs[0]["id"]
        ]
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_edge_too_few(self) -> None:
        data = self._base()
        data["network"]["edges"] = data["network"]["edges"][:10]
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_edge_weight_negative_distance(self) -> None:
        data = self._base()
        data["network"]["edges"][0]["distance"] = -1.0
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_edge_to_unknown_node(self) -> None:
        data = self._base()
        data["network"]["edges"][0]["target"] = "ZZZ"
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_invalid_traffic_status(self) -> None:
        data = self._base()
        data["network"]["edges"][0]["traffic_status"] = "detour"
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_self_loop_via_target_equals_source(self) -> None:
        data = self._base()
        # 制造 source == target 边
        e = data["network"]["edges"][0]
        e["target"] = e["source"]
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_duplicate_node_id(self) -> None:
        data = self._base()
        data["network"]["nodes"].append(dict(data["network"]["nodes"][0]))
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_order_to_unknown_node(self) -> None:
        data = self._base()
        data["orders"][0]["destination_id"] = "GHOST"
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_courier_to_unknown_vehicle(self) -> None:
        data = self._base()
        data["couriers"][0]["vehicle_id"] = "NOPE"
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_invalid_window(self) -> None:
        data = self._base()
        o = data["orders"][0]
        o["time_window_end"] = o["time_window_start"]
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_optimization_invalid_default(self) -> None:
        data = self._base()
        data["optimization"]["default_objective"] = "minutes"
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_network_undirected_rejected(self) -> None:
        data = self._base()
        data["network"]["directed"] = False
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)


class TestPathMissing(unittest.TestCase):
    def test_missing_file(self) -> None:
        with self.assertRaises(ConfigError):
            load_scenario("/tmp/does_not_exist_xyz.json")


class TestLimitsDefaults(unittest.TestCase):
    def test_scenario_limits_have_course_minimums(self) -> None:
        limits = ScenarioLimits()
        self.assertGreaterEqual(limits.min_nodes, 30)
        self.assertGreaterEqual(limits.min_warehouses, 2)
        self.assertGreaterEqual(limits.min_customers, 15)
        self.assertGreaterEqual(limits.min_transfers, 3)
        self.assertGreaterEqual(limits.min_edges, 50)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
