from __future__ import annotations
import unittest
from logiroute.algorithms.order_queue import OrderPriorityQueue,OrderQueueError
from logiroute.core import Order,OrderPriority


class TestDynamicQueueView(unittest.TestCase):
    def test_recorded_ids_are_observable_without_dispatch_or_mutation(self) -> None:
        queue=OrderPriorityQueue()
        a=Order('a','A',1,0,100); b=Order('b','A',1,0,100,OrderPriority.URGENT)
        queue.enqueue(a); queue.enqueue(b)
        self.assertEqual(queue.snapshot_ids(),('b','a'))
        self.assertEqual(len(queue),2)
        b.id='changed'
        self.assertEqual(queue.snapshot_ids(),('b','a'))
        with self.assertRaises(OrderQueueError): queue.peek_next()
        self.assertIs(queue.remove('b'),b)
