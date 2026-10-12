"""``Courier`` 数据模型的单元测试。"""

from __future__ import annotations

import pytest

from logiroute.core.couriers import Courier
from logiroute.core.enums import CourierStatus


pytestmark = pytest.mark.phase1


class TestCourierCreation:
    def test_defaults(self):
        c = Courier(id="CO1", name="张三", vehicle_id="V1")
        assert c.id == "CO1"
        assert c.name == "张三"
        assert c.vehicle_id == "V1"
        assert c.status is CourierStatus.IDLE

    @pytest.mark.parametrize("field_name", ["id", "vehicle_id"])
    def test_blank_ids_rejected(self, field_name):
        kwargs = {"id": "CO1", "name": "n", "vehicle_id": "V1"}
        kwargs[field_name] = ""
        with pytest.raises(ValueError):
            Courier(**kwargs)

    def test_blank_name_rejected(self):
        with pytest.raises(ValueError):
            Courier(id="CO1", name="", vehicle_id="V1")


class TestCourierStateTransitions:
    def test_assign_vehicle(self, make_courier):
        c = make_courier(vehicle_id="V1")
        c.assign_vehicle("V2")
        assert c.vehicle_id == "V2"

    def test_mark_delivering_from_idle(self, make_courier):
        c = make_courier()
        c.mark_delivering()
        assert c.status is CourierStatus.DELIVERING

    def test_mark_delivering_from_offline_fails(self, make_courier):
        c = make_courier(status=CourierStatus.OFFLINE)
        with pytest.raises(ValueError, match="offline"):
            c.mark_delivering()

    def test_mark_idle(self, make_courier):
        c = make_courier(status=CourierStatus.DELIVERING)
        c.mark_idle()
        assert c.status is CourierStatus.IDLE

    def test_is_dispatchable(self, make_courier):
        idle = make_courier(status=CourierStatus.IDLE)
        assert idle.is_dispatchable
        delivering = Courier(
            id="CO2", name="x", vehicle_id="V1",
            status=CourierStatus.DELIVERING,
        )
        assert delivering.is_dispatchable
        offline = Courier(
            id="CO3", name="x", vehicle_id="V1",
            status=CourierStatus.OFFLINE,
        )
        assert not offline.is_dispatchable
        resting = Courier(
            id="CO4", name="x", vehicle_id="V1",
            status=CourierStatus.RESTING,
        )
        assert not resting.is_dispatchable
