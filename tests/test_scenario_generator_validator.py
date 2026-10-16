"""``tests/test_scenario_generator_validator.py`` —— validator 单测。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import TestCase

from logiroute.config import load_scenario
from logiroute.scenario_generator.validator import (
    ScenarioValidationReport,
    validate_generated_scenario,
)


SCENARIO_FILE = (
    Path(__file__).resolve().parent.parent / "config" / "scenario.json"
)


def _make_undersized_capacity_scenario() -> "object":
    """返回一个 summary: 总需求 > capacity 的小场景（用于负向测试）。"""
    from logiroute.config.loader import ScenarioBundle
    from logiroute.core.couriers import Courier
    from logiroute.core.edges import Edge
    from logiroute.core.enums import (CourierStatus, NodeType,
                                      OrderPriority, OrderStatus,
                                      TrafficStatus, VehicleStatus)
    from logiroute.core.nodes import Node
    from logiroute.core.orders import Order
    from logiroute.core.vehicles import Vehicle
    from logiroute.graph.logistics_graph import LogisticsGraph

    g = LogisticsGraph()
    for n in (
        Node("W1", "W1", NodeType.WAREHOUSE, 0, 0),
        Node("C1", "C1", NodeType.CUSTOMER, 1, 1),
    ):
        g.add_node(n)
    g.add_edge(Edge("W1", "C1", 1, 1, 1))
    g.add_edge(Edge("C1", "W1", 1, 1, 1))

    v = Vehicle(
        id="VH1", capacity=10.0, current_load=0.0,
        current_node_id="W1", status=VehicleStatus.IDLE,
    )
    c = Courier(
        id="CO1", name="CO1", vehicle_id="VH1",
        status=CourierStatus.IDLE,
    )
    order = Order(
        id="O1", destination_id="C1", demand=100.0,
        time_window_start=540.0, time_window_end=700.0,
        priority=OrderPriority.NORMAL, status=OrderStatus.PENDING,
    )
    return ScenarioBundle(
        name="undersized", mode="fixed", random_seed=42, graph=g,
        vehicles=[v], couriers=[c], orders=[order],
        simulation={"service_time": 5.0, "initial_time": 540.0},
        optimization={"default_objective": "distance"},
        metadata={},
    )


class TestValidatorBasics(TestCase):
    def test_fixed_scenario_passes_validation(self):
        bundle = load_scenario(SCENARIO_FILE)
        rep = validate_generated_scenario(bundle)
        self.assertIsInstance(rep, ScenarioValidationReport)
        # the fixed scenario has no backbone supplied, so feasibility focuses on
        # basic structural checks: capacity_ok & no missing destinations.
        self.assertTrue(rep.capacity_ok)
        self.assertEqual(rep.violations, ())

    def test_undersized_capacity_detected(self):
        b = _make_undersized_capacity_scenario()
        rep = validate_generated_scenario(b)
        self.assertFalse(rep.capacity_ok)
        self.assertTrue(any(v[0] == "capacity.total_demand" for v in rep.violations))


class TestValidatorWithBackbone(TestCase):
    def test_backbone_must_be_closed(self):
        bundle = load_scenario(SCENARIO_FILE)
        rep = validate_generated_scenario(
            bundle, backbone=["W1", "C1", "W2"]  # not closed
        )
        self.assertFalse(rep.closed_route_ok)

    def test_backbone_must_cover_all_orders(self):
        bundle = load_scenario(SCENARIO_FILE)
        # backbone that misses 5 orders
        rep = validate_generated_scenario(
            bundle,
            backbone=["W1"] + [f"C{i}" for i in range(1, 16)] + ["W1"],
        )
        self.assertFalse(rep.all_orders_covered)

    def test_backbone_with_bad_leg(self):
        bundle = load_scenario(SCENARIO_FILE)
        # Add a fake node id W999 into backbone that doesn't exist
        rep = validate_generated_scenario(
            bundle,
            backbone=["W1", "W999", "W1"],
        )
        self.assertFalse(rep.all_legs_reachable)


class TestValidatorReportToDict(TestCase):
    def test_to_dict_is_serializable(self):
        import json as _json
        bundle = load_scenario(SCENARIO_FILE)
        rep = validate_generated_scenario(bundle)
        d = rep.to_dict()
        s = _json.dumps(d)
        restored = _json.loads(s)
        self.assertEqual(restored["scenario_name"], bundle.name)


if __name__ == "__main__":
    unittest.main()
