"""``Courier`` 数据模型的单元测试。"""

from __future__ import annotations

import unittest

from logiroute.core.couriers import Courier
from logiroute.core.enums import CourierStatus


class TestCourierCreation(unittest.TestCase):
    def test_defaults(self) -> None:
        c = Courier(id="CO1", name="张三", vehicle_id="V1")
        self.assertEqual(c.id, "CO1")
        self.assertEqual(c.name, "张三")
        self.assertEqual(c.vehicle_id, "V1")
        self.assertIs(c.status, CourierStatus.IDLE)

    def test_blank_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Courier(id="", name="n", vehicle_id="V1")

    def test_blank_vehicle_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Courier(id="CO1", name="n", vehicle_id="")

    def test_blank_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Courier(id="CO1", name="", vehicle_id="V1")


class TestCourierStateTransitions(unittest.TestCase):
    def test_assign_vehicle(self) -> None:
        c = Courier(id="CO1", name="x", vehicle_id="V1")
        c.assign_vehicle("V2")
        self.assertEqual(c.vehicle_id, "V2")

    def test_mark_delivering_from_idle(self) -> None:
        c = Courier(id="CO1", name="x", vehicle_id="V1")
        c.mark_delivering()
        self.assertIs(c.status, CourierStatus.DELIVERING)

    def test_mark_delivering_from_offline_fails(self) -> None:
        c = Courier(id="CO1", name="x", vehicle_id="V1",
                    status=CourierStatus.OFFLINE)
        with self.assertRaises(ValueError):
            c.mark_delivering()

    def test_mark_idle(self) -> None:
        c = Courier(id="CO1", name="x", vehicle_id="V1",
                    status=CourierStatus.DELIVERING)
        c.mark_idle()
        self.assertIs(c.status, CourierStatus.IDLE)

    def test_is_dispatchable(self) -> None:
        idle = Courier(id="CO1", name="x", vehicle_id="V1")
        self.assertTrue(idle.is_dispatchable)
        delivering = Courier(id="CO2", name="x", vehicle_id="V1",
                             status=CourierStatus.DELIVERING)
        self.assertTrue(delivering.is_dispatchable)
        offline = Courier(id="CO3", name="x", vehicle_id="V1",
                          status=CourierStatus.OFFLINE)
        self.assertFalse(offline.is_dispatchable)
        resting = Courier(id="CO4", name="x", vehicle_id="V1",
                          status=CourierStatus.RESTING)
        self.assertFalse(resting.is_dispatchable)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
