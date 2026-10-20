"""Handwritten priority array, identity and mutable-order consistency contracts."""
from __future__ import annotations

from dataclasses import replace
import unittest

from logiroute.core import Order, OrderPriority, OrderStatus
from logiroute.algorithms.order_queue import OrderPriorityQueue


def orders() -> list[Order]:
    return [Order("O3", "C2", 3, 0, 40), Order("O2", "C1", 8, 0, 30),
            Order("O1", "C1", 5, 0, 50, OrderPriority.URGENT)]


class TestOrderQueue(unittest.TestCase):
    def queue(self) -> OrderPriorityQueue:
        from logiroute.algorithms.order_queue import OrderPriorityQueue
        return OrderPriorityQueue()

    def test_empty(self) -> None:
        queue = self.queue()
        self.assertEqual(len(queue), 0)
        self.assertTrue(queue.is_empty())
        for method in (queue.peek_next, queue.pop_next):
            with self.assertRaises(ValueError):
                method()

    def test_single_peek_pop_preserves_object_and_status(self) -> None:
        queue = self.queue()
        item = orders()[0]
        queue.enqueue(item)
        self.assertIs(queue.peek_next(), item)
        self.assertEqual(len(queue), 1)
        self.assertIs(queue.pop_next(), item)
        self.assertEqual(item.demand, 3)
        self.assertIs(item.status, OrderStatus.PENDING)
        self.assertTrue(queue.is_empty())

    def test_late_urgent_precedes_earlier_normal(self) -> None:
        queue = self.queue()
        for item in orders():
            queue.enqueue(item)
        self.assertEqual([queue.pop_next().id for _ in range(3)], ["O1", "O2", "O3"])

    def test_deadline_and_id_ties(self) -> None:
        queue = self.queue()
        for item in (Order("B", "C", 1, 0, 10), Order("A", "C", 1, 0, 10),
                     Order("Z", "C", 1, 0, 5)):
            queue.enqueue(item)
        self.assertEqual([queue.pop_next().id for _ in range(3)], ["Z", "A", "B"])

    def test_same_destination_distinct_orders_and_demands(self) -> None:
        queue = self.queue()
        one, two = orders()[1:]
        queue.enqueue(one)
        queue.enqueue(two)
        self.assertEqual(len(queue), 2)
        self.assertEqual([queue.pop_next().demand, queue.pop_next().demand], [5, 8])

    def test_duplicate_id_rejected_atomically(self) -> None:
        queue = self.queue()
        item = orders()[0]
        queue.enqueue(item)
        with self.assertRaises(ValueError):
            queue.enqueue(replace(item, demand=9))
        self.assertEqual(len(queue), 1)
        self.assertIs(queue.peek_next(), item)

    def test_lookup_contains_remove(self) -> None:
        queue = self.queue()
        for item in orders():
            queue.enqueue(item)
        self.assertTrue(queue.contains("O2"))
        self.assertEqual(queue.get("O2").demand, 8)
        self.assertEqual(queue.remove("O2").id, "O2")
        self.assertFalse(queue.contains("O2"))
        self.assertEqual([queue.pop_next().id, queue.pop_next().id], ["O1", "O3"])

    def test_missing_lookup_and_remove(self) -> None:
        queue = self.queue()
        for method in (queue.get, queue.remove):
            with self.assertRaises(ValueError):
                method("GHOST")

    def test_every_nonpending_status_rejected(self) -> None:
        for status in OrderStatus:
            if status is OrderStatus.PENDING:
                continue
            with self.subTest(status=status):
                queue = self.queue()
                item = orders()[0]
                item.status = status
                with self.assertRaises(ValueError):
                    queue.enqueue(item)
                self.assertTrue(queue.is_empty())

    def test_invalid_head_is_not_popped_and_can_be_removed(self) -> None:
        queue = self.queue()
        urgent = orders()[2]
        queue.enqueue(orders()[0])
        queue.enqueue(urgent)
        urgent.transition_to(OrderStatus.CANCELLED)
        for method in (queue.peek_next, queue.pop_next):
            with self.assertRaises(ValueError):
                method()
        self.assertEqual(len(queue), 2)
        self.assertIs(queue.remove("O1"), urgent)
        self.assertEqual(queue.pop_next().id, "O3")

    def test_mutated_head_sort_key_rejected(self) -> None:
        for field, value in (("id", "CHANGED"), ("priority", OrderPriority.NORMAL),
                             ("time_window_end", 60)):
            with self.subTest(field=field):
                queue = self.queue()
                item = orders()[2]
                queue.enqueue(item)
                setattr(item, field, value)
                with self.assertRaises(ValueError):
                    queue.pop_next()
                self.assertIs(queue.remove("O1"), item)

    def test_remove_modify_reenqueue(self) -> None:
        queue = self.queue()
        for item in orders():
            queue.enqueue(item)
        item = queue.remove("O3")
        item.priority = OrderPriority.URGENT
        item.time_window_end = 20
        queue.enqueue(item)
        self.assertEqual(queue.peek_next().id, "O3")

    def test_insertion_order_does_not_change_output(self) -> None:
        for sequence in (orders(), list(reversed(orders())), [orders()[1], orders()[0], orders()[2]]):
            queue = self.queue()
            for item in sequence:
                queue.enqueue(item)
            self.assertEqual([queue.pop_next().id for _ in range(3)], ["O1", "O2", "O3"])

    def test_non_order_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.queue().enqueue("O1")
