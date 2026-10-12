"""``Vehicle`` 数据模型的单元测试。"""

from __future__ import annotations

import pytest

from logiroute.core.vehicles import Vehicle


pytestmark = pytest.mark.phase1


class TestVehicleCreation:
    def test_defaults(self):
        v = Vehicle(id="V1", max_capacity=100.0)
        assert v.id == "V1"
        assert v.max_capacity == 100.0
        assert v.current_load == 0.0
        assert v.current_node_id == ""
        assert v.is_available is True
        assert v.remaining_capacity == 100.0

    def test_invalid_id_rejected(self):
        with pytest.raises(ValueError):
            Vehicle(id="", max_capacity=1.0)

    def test_negative_capacity_rejected(self):
        with pytest.raises(ValueError):
            Vehicle(id="V1", max_capacity=-1.0)

    def test_overload_at_construction_rejected(self):
        with pytest.raises(ValueError, match="exceed"):
            Vehicle(id="V1", max_capacity=10.0, current_load=20.0)


class TestVehicleLoading:
    def test_load_partial(self, make_vehicle):
        v = make_vehicle(max_capacity=100.0)
        v.load(30.0)
        assert v.current_load == 30.0
        assert v.remaining_capacity == 70.0

    def test_load_to_full_then_full_again_fails(self, make_vehicle):
        v = make_vehicle(max_capacity=10.0)
        v.load(10.0)
        with pytest.raises(ValueError):
            v.load(0.1)

    def test_unload(self, make_vehicle):
        v = make_vehicle(max_capacity=100.0, current_load=30.0)
        v.unload(10.0)
        assert v.current_load == 20.0

    def test_unload_too_much_fails(self, make_vehicle):
        v = make_vehicle(max_capacity=100.0, current_load=10.0)
        with pytest.raises(ValueError):
            v.unload(11.0)

    @pytest.mark.parametrize("amount", [-1.0, -10.0])
    def test_negative_amount_rejected(self, make_vehicle, amount):
        v = make_vehicle()
        with pytest.raises(ValueError):
            v.load(amount)
        with pytest.raises(ValueError):
            v.unload(amount)

    def test_can_load_check(self, make_vehicle):
        v = make_vehicle(max_capacity=10.0, current_load=8.0)
        assert v.can_load(2.0) is True
        assert v.can_load(2.5) is False
        assert v.can_load(-1.0) is False
        assert v.can_load("10") is False  # type: ignore[arg-type]
