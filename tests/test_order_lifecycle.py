"""Explicit lifecycle transitions; no timers or implicit queue transitions."""
from __future__ import annotations

import unittest
from logiroute.core import Order, OrderStatus


def order() -> Order:
    return Order("O", "C", 1, 0, 10)


class TestOrderLifecycle(unittest.TestCase):
    def test_existing_values_and_default(self) -> None:
        self.assertEqual([OrderStatus.PENDING.value, OrderStatus.IN_TRANSIT.value,
                          OrderStatus.DELIVERED.value, OrderStatus.EXPIRED.value],
                         ["pending", "in_transit", "delivered", "expired"])
        self.assertIs(order().status, OrderStatus.PENDING)

    def test_full_legal_transition_table(self) -> None:
        expected = {
            "created": ("pending", "cancelled"),
            "pending": ("planned", "cancelled", "expired"),
            "planned": ("pending", "in_transit", "cancelled", "expired"),
            "in_transit": ("delivered",), "delivered": (), "cancelled": (), "expired": (),
        }
        self.assertEqual({state.value for state in OrderStatus}, set(expected))
        for source in OrderStatus:
            for target in OrderStatus:
                with self.subTest(source=source, target=target):
                    item = order()
                    item.status = source
                    if target.value in expected[source.value]:
                        item.transition_to(target)
                        self.assertIs(item.status, target)
                    else:
                        with self.assertRaises(ValueError):
                            item.transition_to(target)
                        self.assertIs(item.status, source)

    def test_plan_can_be_withdrawn_before_departure(self) -> None:
        item = order()
        item.transition_to(OrderStatus.PLANNED)
        item.transition_to(OrderStatus.PENDING)
        self.assertIs(item.status, OrderStatus.PENDING)

    def test_delivery_cannot_be_cancelled_or_withdrawn(self) -> None:
        item = order()
        item.transition_to(OrderStatus.PLANNED)
        item.transition_to(OrderStatus.IN_TRANSIT)
        for status in (OrderStatus.CANCELLED, OrderStatus.PENDING, OrderStatus.EXPIRED):
            with self.subTest(status=status), self.assertRaises(ValueError):
                item.transition_to(status)

    def test_expiry_is_explicit_and_preserves_quantities(self) -> None:
        item = order()
        item.transition_to(OrderStatus.EXPIRED)
        self.assertEqual(item.demand, 1)
        self.assertIs(item.status, OrderStatus.EXPIRED)

    def test_invalid_status_type(self) -> None:
        with self.assertRaises(ValueError):
            order().transition_to("planned")
