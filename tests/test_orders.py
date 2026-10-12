"""``Order`` 数据模型的单元测试。"""

from __future__ import annotations

import unittest

from logiroute.core.enums import OrderPriority, OrderStatus
from logiroute.core.orders import Order


class TestOrderCreation(unittest.TestCase):
    def test_basic(self) -> None:
        o = Order(
            id="O1", destination_id="C1",
            demand=2.0,
            time_window_start=540.0, time_window_end=660.0,
        )
        self.assertIs(o.priority, OrderPriority.NORMAL)
        self.assertIs(o.status, OrderStatus.PENDING)
        self.assertAlmostEqual(o.time_window_length, 120.0)

    def test_blank_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Order(id="", destination_id="C1", demand=1.0,
                  time_window_start=0, time_window_end=10)

    def test_blank_destination_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Order(id="O1", destination_id="", demand=1.0,
                  time_window_start=0, time_window_end=10)

    def test_negative_demand_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Order(id="O1", destination_id="C1", demand=-1.0,
                  time_window_start=0, time_window_end=10)

    def test_invalid_window_end_le_start_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Order(id="O1", destination_id="C1", demand=1.0,
                  time_window_start=60, time_window_end=60)
        with self.assertRaises(ValueError):
            Order(id="O2", destination_id="C1", demand=1.0,
                  time_window_start=60, time_window_end=30)


class TestOrderWindow(unittest.TestCase):
    def test_within_window_inclusive(self) -> None:
        o = Order(id="O1", destination_id="C1", demand=1.0,
                  time_window_start=60.0, time_window_end=120.0)
        self.assertTrue(o.is_within_window(60.0))
        self.assertTrue(o.is_within_window(90.0))
        self.assertTrue(o.is_within_window(120.0))

    def test_outside_window(self) -> None:
        o = Order(id="O1", destination_id="C1", demand=1.0,
                  time_window_start=60.0, time_window_end=120.0)
        self.assertFalse(o.is_within_window(59.9))
        self.assertFalse(o.is_within_window(120.1))

    def test_priority_default_is_normal(self) -> None:
        o = Order(id="O1", destination_id="C1", demand=1.0,
                  time_window_start=0, time_window_end=10)
        self.assertIs(o.priority, OrderPriority.NORMAL)

    def test_urgent_priority(self) -> None:
        o = Order(id="O1", destination_id="C1", demand=1.0,
                  time_window_start=0, time_window_end=10,
                  priority=OrderPriority.URGENT)
        self.assertIs(o.priority, OrderPriority.URGENT)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
