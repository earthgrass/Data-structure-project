"""``Order`` 数据模型的单元测试。"""

from __future__ import annotations

import pytest

from logiroute.core.enums import OrderPriority, OrderStatus
from logiroute.core.orders import Order


pytestmark = pytest.mark.phase1


class TestOrderCreation:
    def test_basic(self):
        o = Order(
            id="O1", destination_node_id="C1",
            demand=2.0,
            time_window_start=540.0, time_window_end=660.0,
        )
        assert o.priority is OrderPriority.NORMAL
        assert o.status is OrderStatus.PENDING
        assert o.time_window_length == pytest.approx(120.0)

    def test_blank_id_rejected(self):
        with pytest.raises(ValueError):
            Order(id="", destination_node_id="C1", demand=1.0,
                  time_window_start=0, time_window_end=10)

    def test_blank_destination_rejected(self):
        with pytest.raises(ValueError):
            Order(id="O1", destination_node_id="", demand=1.0,
                  time_window_start=0, time_window_end=10)

    def test_negative_demand_rejected(self):
        with pytest.raises(ValueError):
            Order(id="O1", destination_node_id="C1", demand=-1.0,
                  time_window_start=0, time_window_end=10)

    def test_invalid_window_end_le_start_rejected(self):
        with pytest.raises(ValueError, match="time_window_end"):
            Order(id="O1", destination_node_id="C1", demand=1.0,
                  time_window_start=60, time_window_end=60)
        with pytest.raises(ValueError):
            Order(id="O2", destination_node_id="C1", demand=1.0,
                  time_window_start=60, time_window_end=30)


class TestOrderWindow:
    def test_within_window_inclusive(self, make_order):
        o = make_order(time_window_start=60.0, time_window_end=120.0)
        assert o.is_within_window(60.0) is True
        assert o.is_within_window(90.0) is True
        assert o.is_within_window(120.0) is True

    def test_outside_window(self, make_order):
        o = make_order(time_window_start=60.0, time_window_end=120.0)
        assert o.is_within_window(59.9) is False
        assert o.is_within_window(120.1) is False

    def test_priority_default(self, make_order):
        o = make_order()
        assert o.priority is OrderPriority.NORMAL

    def test_urgent_priority(self, make_order):
        o = make_order(priority=OrderPriority.URGENT)
        assert o.priority is OrderPriority.URGENT
