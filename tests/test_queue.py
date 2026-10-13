"""自实现 FIFO 队列 ArrayQueue 的单元测试。

覆盖：FIFO 语义、空队列异常、动态扩容、``clear`` / ``compact``、
迭代顺序、类型参数、``__len__`` / ``is_empty`` / ``__bool__``。
"""

from __future__ import annotations

import unittest

from logiroute.graph.queue import ArrayQueue, EmptyQueueError


class TestBasicFifoSemantics(unittest.TestCase):
    def test_fifo_order(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        for x in (1, 2, 3, 4, 5):
            q.enqueue(x)
        out = [q.dequeue() for _ in range(5)]
        self.assertEqual(out, [1, 2, 3, 4, 5])

    def test_interleaved_enqueue_dequeue(self) -> None:
        q: ArrayQueue[str] = ArrayQueue()
        q.enqueue("a")
        q.enqueue("b")
        self.assertEqual(q.dequeue(), "a")
        q.enqueue("c")
        self.assertEqual(q.dequeue(), "b")
        self.assertEqual(q.dequeue(), "c")
        self.assertTrue(q.is_empty())

    def test_front_without_removing(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        q.enqueue(10)
        q.enqueue(20)
        self.assertEqual(q.front(), 10)
        self.assertEqual(q.front(), 10)  # 不移除
        self.assertEqual(q.dequeue(), 10)
        self.assertEqual(q.front(), 20)


class TestEmptyQueueErrors(unittest.TestCase):
    def test_dequeue_on_empty_raises(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        with self.assertRaises(EmptyQueueError):
            q.dequeue()

    def test_front_on_empty_raises(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        with self.assertRaises(EmptyQueueError):
            q.front()

    def test_dequeue_after_clear_raises(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        q.enqueue(1)
        q.clear()
        with self.assertRaises(EmptyQueueError):
            q.dequeue()


class TestStatePredicates(unittest.TestCase):
    def test_is_empty_initial(self) -> None:
        self.assertTrue(ArrayQueue().is_empty())

    def test_is_empty_after_enqueue_dequeue(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        q.enqueue(1)
        self.assertFalse(q.is_empty())
        q.dequeue()
        self.assertTrue(q.is_empty())

    def test_len_tracks_size(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        self.assertEqual(len(q), 0)
        for i in range(7):
            q.enqueue(i)
        self.assertEqual(len(q), 7)
        q.dequeue()
        q.dequeue()
        self.assertEqual(len(q), 5)

    def test_bool_conversion(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        self.assertFalse(bool(q))
        q.enqueue(0)
        self.assertTrue(bool(q))


class TestClearAndCompact(unittest.TestCase):
    def test_clear_resets(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        for i in range(10):
            q.enqueue(i)
        q.clear()
        self.assertEqual(len(q), 0)
        self.assertTrue(q.is_empty())
        # clear 后能继续使用
        q.enqueue(99)
        self.assertEqual(q.dequeue(), 99)

    def test_compact_when_no_offset_is_noop(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        for i in range(3):
            q.enqueue(i)
        q.compact()
        self.assertEqual([q.dequeue() for _ in range(3)], [0, 1, 2])

    def test_compact_reclaims_storage(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        for i in range(100):
            q.enqueue(i)
        for _ in range(95):
            q.dequeue()
        # 此时 head=95、len=5，但底层 buf 仍有 100 槽位
        self.assertEqual(len(q._buf), 100)  # type: ignore[attr-defined]
        q.compact()
        self.assertEqual(len(q._buf), 5)  # type: ignore[attr-defined]
        self.assertEqual(q._head, 0)  # type: ignore[attr-defined]
        self.assertEqual([q.dequeue() for _ in range(5)], [95, 96, 97, 98, 99])


class TestIteration(unittest.TestCase):
    def test_iter_yields_in_order_without_removing(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        for x in (3, 1, 4, 1, 5, 9, 2, 6):
            q.enqueue(x)
        snapshot = list(q)
        self.assertEqual(snapshot, [3, 1, 4, 1, 5, 9, 2, 6])
        # 迭代不应改变队列
        self.assertEqual(len(q), 8)

    def test_repr_includes_counts(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        q.enqueue(1)
        q.enqueue(2)
        text = repr(q)
        self.assertIn("ArrayQueue", text)
        self.assertIn("len=2", text)


class TestSlotEnforcement(unittest.TestCase):
    def test_no_dynamic_attributes(self) -> None:
        q: ArrayQueue[int] = ArrayQueue()
        with self.assertRaises(AttributeError):
            q.not_a_real_attr = 1  # type: ignore[attr-defined]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
