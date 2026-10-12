"""``Edge`` 数据模型及方向性的单元测试。"""

from __future__ import annotations

import math
import unittest

from logiroute.core.edges import Edge
from logiroute.core.enums import TrafficStatus


class TestEdgeCreation(unittest.TestCase):
    def test_basic_creation(self) -> None:
        e = Edge(
            source_id="A",
            target_id="B",
            distance=1.5,
            travel_time=2.5,
            cost=0.5,
        )
        self.assertEqual(e.source_id, "A")
        self.assertEqual(e.target_id, "B")
        self.assertEqual(e.distance, 1.5)
        self.assertEqual(e.travel_time, 2.5)
        self.assertEqual(e.cost, 0.5)
        self.assertIs(e.traffic_status, TrafficStatus.CLEAR)
        self.assertEqual(e.metadata, {})

    def test_zero_values_allowed(self) -> None:
        e = Edge(source_id="A", target_id="B", distance=0.0, travel_time=0.0, cost=0.0)
        self.assertEqual(e.distance, 0.0)


class TestEdgeValidation(unittest.TestCase):
    def _kwargs(self, **overrides):
        base = {
            "source_id": "A", "target_id": "B",
            "distance": 1.0, "travel_time": 1.0, "cost": 1.0,
        }
        base.update(overrides)
        return base

    def test_blank_source_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(source_id=""))

    def test_blank_target_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(target_id=""))

    def test_self_loop_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(source_id="A", target_id="A",
                 distance=1.0, travel_time=1.0, cost=1.0)

    def test_negative_distance_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(distance=-0.1))

    def test_negative_travel_time_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(travel_time=-1.0))

    def test_negative_cost_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(cost=-100.0))

    def test_nan_distance_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(distance=math.nan))

    def test_inf_cost_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(cost=math.inf))

    def test_string_value_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(**self._kwargs(distance="1.0"))  # type: ignore[arg-type]

    def test_invalid_traffic_status_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Edge(source_id="A", target_id="B",
                 distance=1.0, travel_time=1.0, cost=1.0,
                 traffic_status="blocked")  # type: ignore[arg-type]

    def test_metadata_must_be_dict(self) -> None:
        with self.assertRaises(ValueError):
            Edge(source_id="A", target_id="B",
                 distance=1.0, travel_time=1.0, cost=1.0,
                 metadata=[1, 2, 3])  # type: ignore[arg-type]


class TestEdgeDirectionality(unittest.TestCase):
    def test_a_to_b_distinct_from_b_to_a(self) -> None:
        ab = Edge(source_id="A", target_id="B",
                  distance=1.0, travel_time=2.0, cost=3.0)
        ba = Edge(source_id="B", target_id="A",
                  distance=4.0, travel_time=5.0, cost=6.0)
        self.assertEqual(ab.key, ("A", "B"))
        self.assertEqual(ba.key, ("B", "A"))
        self.assertNotEqual(ab.distance, ba.distance)
        self.assertNotEqual(ab, ba)

    def test_weight_metric_selection(self) -> None:
        e = Edge(source_id="A", target_id="B",
                 distance=1.0, travel_time=2.0, cost=3.0)
        self.assertEqual(e.weight("distance"), 1.0)
        self.assertEqual(e.weight("travel_time"), 2.0)
        self.assertEqual(e.weight("cost"), 3.0)

    def test_invalid_weight_metric(self) -> None:
        e = Edge(source_id="A", target_id="B",
                 distance=1.0, travel_time=2.0, cost=3.0)
        with self.assertRaises(ValueError):
            e.weight("time")  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
