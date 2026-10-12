"""``Edge`` 数据模型及方向性的单元测试。"""

from __future__ import annotations

import math

import pytest

from logiroute.core.edges import Edge
from logiroute.core.enums import TrafficStatus


pytestmark = pytest.mark.phase1


class TestEdgeCreation:
    def test_basic_creation(self):
        e = Edge(
            source_id="A",
            target_id="B",
            distance=1.5,
            travel_time=2.5,
            cost=0.5,
        )
        assert e.source_id == "A"
        assert e.target_id == "B"
        assert e.distance == 1.5
        assert e.travel_time == 2.5
        assert e.cost == 0.5
        assert e.traffic_status is TrafficStatus.CLEAR
        assert e.metadata == {}

    def test_zero_values_allowed(self):
        e = Edge(
            source_id="A",
            target_id="B",
            distance=0.0,
            travel_time=0.0,
            cost=0.0,
        )
        assert e.distance == 0.0


class TestEdgeValidation:
    @pytest.mark.parametrize("field_name", ["source_id", "target_id"])
    @pytest.mark.parametrize("bad_value", ["", "   "])
    def test_empty_ids_rejected(self, field_name, bad_value):
        kwargs = {
            "source_id": "A",
            "target_id": "B",
            "distance": 1.0,
            "travel_time": 1.0,
            "cost": 1.0,
        }
        kwargs[field_name] = bad_value
        with pytest.raises(ValueError):
            Edge(**kwargs)

    def test_self_loop_rejected(self):
        with pytest.raises(ValueError, match="self-loop"):
            Edge(
                source_id="A", target_id="A",
                distance=1.0, travel_time=1.0, cost=1.0,
            )

    @pytest.mark.parametrize("field_name", ["distance", "travel_time", "cost"])
    @pytest.mark.parametrize("bad_value", [-0.1, -1.0, -100.0])
    def test_negative_values_rejected(self, field_name, bad_value):
        kwargs = {
            "source_id": "A",
            "target_id": "B",
            "distance": 1.0,
            "travel_time": 1.0,
            "cost": 1.0,
        }
        kwargs[field_name] = bad_value
        with pytest.raises(ValueError):
            Edge(**kwargs)

    @pytest.mark.parametrize("field_name", ["distance", "travel_time", "cost"])
    @pytest.mark.parametrize("bad_value", [math.nan, math.inf])
    def test_non_finite_values_rejected(self, field_name, bad_value):
        kwargs = {
            "source_id": "A",
            "target_id": "B",
            "distance": 1.0,
            "travel_time": 1.0,
            "cost": 1.0,
        }
        kwargs[field_name] = bad_value
        with pytest.raises(ValueError):
            Edge(**kwargs)

    @pytest.mark.parametrize("field_name", ["distance", "travel_time", "cost"])
    def test_non_numeric_values_rejected(self, field_name):
        kwargs = {
            "source_id": "A",
            "target_id": "B",
            "distance": 1.0,
            "travel_time": 1.0,
            "cost": 1.0,
        }
        kwargs[field_name] = "1.0"  # type: ignore[assignment]
        with pytest.raises(ValueError):
            Edge(**kwargs)

    def test_invalid_traffic_status_rejected(self):
        with pytest.raises(ValueError, match="traffic_status"):
            Edge(  # type: ignore[call-arg]
                source_id="A", target_id="B",
                distance=1.0, travel_time=1.0, cost=1.0,
                traffic_status="blocked",
            )

    def test_metadata_must_be_dict(self):
        with pytest.raises(ValueError):
            Edge(  # type: ignore[call-arg]
                source_id="A", target_id="B",
                distance=1.0, travel_time=1.0, cost=1.0,
                metadata=[1, 2, 3],  # type: ignore[arg-type]
            )


class TestEdgeDirectionality:
    def test_a_to_b_is_distinct_from_b_to_a(self):
        ab = Edge(source_id="A", target_id="B",
                  distance=1.0, travel_time=2.0, cost=3.0)
        ba = Edge(source_id="B", target_id="A",
                  distance=4.0, travel_time=5.0, cost=6.0)
        assert ab.key == ("A", "B")
        assert ba.key == ("B", "A")
        assert ab.distance != ba.distance
        assert ab != ba

    def test_weight_metric_selection(self):
        e = Edge(source_id="A", target_id="B",
                 distance=1.0, travel_time=2.0, cost=3.0)
        assert e.weight("distance") == 1.0
        assert e.weight("travel_time") == 2.0
        assert e.weight("cost") == 3.0

    def test_invalid_weight_metric_raises(self):
        e = Edge(source_id="A", target_id="B",
                 distance=1.0, travel_time=2.0, cost=3.0)
        with pytest.raises(ValueError, match="unknown weight metric"):
            e.weight("time")  # type: ignore[arg-type]
