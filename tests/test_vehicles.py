"""``Vehicle`` 数据模型的单元测试。"""

from __future__ import annotations

import unittest

from logiroute.core.enums import VehicleStatus
from logiroute.core.vehicles import Vehicle


class TestVehicleCreation(unittest.TestCase):
    def test_defaults(self) -> None:
        v = Vehicle(id="V1", capacity=100.0)
        self.assertEqual(v.id, "V1")
        self.assertEqual(v.capacity, 100.0)
        self.assertEqual(v.current_load, 0.0)
        self.assertEqual(v.current_node_id, "")
        self.assertIs(v.status, VehicleStatus.IDLE)
        self.assertTrue(v.is_available)
        self.assertEqual(v.remaining_capacity, 100.0)

    def test_blank_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Vehicle(id="", capacity=1.0)

    def test_negative_capacity_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Vehicle(id="V1", capacity=-1.0)

    def test_overload_at_construction_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Vehicle(id="V1", capacity=10.0, current_load=20.0)


class TestVehicleLoading(unittest.TestCase):
    def test_load_partial(self) -> None:
        v = Vehicle(id="V1", capacity=100.0)
        v.load(30.0)
        self.assertEqual(v.current_load, 30.0)
        self.assertEqual(v.remaining_capacity, 70.0)

    def test_load_to_full_then_full_again_fails(self) -> None:
        v = Vehicle(id="V1", capacity=10.0)
        v.load(10.0)
        with self.assertRaises(ValueError):
            v.load(0.1)

    def test_unload(self) -> None:
        v = Vehicle(id="V1", capacity=100.0, current_load=30.0)
        v.unload(10.0)
        self.assertEqual(v.current_load, 20.0)

    def test_unload_too_much_fails(self) -> None:
        v = Vehicle(id="V1", capacity=100.0, current_load=10.0)
        with self.assertRaises(ValueError):
            v.unload(11.0)

    def test_negative_amount_rejected(self) -> None:
        v = Vehicle(id="V1", capacity=100.0)
        with self.assertRaises(ValueError):
            v.load(-1.0)
        with self.assertRaises(ValueError):
            v.unload(-1.0)

    def test_can_load_check(self) -> None:
        v = Vehicle(id="V1", capacity=10.0, current_load=8.0)
        self.assertTrue(v.can_load(2.0))
        self.assertFalse(v.can_load(2.5))
        self.assertFalse(v.can_load(-1.0))
        self.assertFalse(v.can_load("10"))  # type: ignore[arg-type]


class TestVehicleStatus(unittest.TestCase):
    def test_mark_delivering(self) -> None:
        v = Vehicle(id="V1", capacity=10.0)
        v.mark_delivering()
        self.assertIs(v.status, VehicleStatus.DELIVERING)

    def test_mark_idle(self) -> None:
        v = Vehicle(id="V1", capacity=10.0, status=VehicleStatus.DELIVERING)
        v.mark_idle()
        self.assertIs(v.status, VehicleStatus.IDLE)

    def test_delivering_from_maintenance_rejected(self) -> None:
        v = Vehicle(id="V1", capacity=10.0, status=VehicleStatus.MAINTENANCE)
        with self.assertRaises(ValueError):
            v.mark_delivering()

    def test_invalid_status_string_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Vehicle(id="V1", capacity=10.0, status="travelling")  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
