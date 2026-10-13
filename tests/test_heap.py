"""自实现索引式二叉最小堆 MinHeap 的单元测试。

所有期望顺序均由人工推算得到，**不依赖堆自身的实现进行自证**。
"""

from __future__ import annotations

import math
import unittest

from logiroute.algorithms.heap import (
    DuplicateNodeError,
    HeapError,
    InvalidPriorityError,
    MinHeap,
    UnknownNodeError,
)


# ---------------------------------------------------------------------------
#  构造 / 基本状态
# ---------------------------------------------------------------------------


class TestConstructionAndState(unittest.TestCase):
    def test_empty_heap(self) -> None:
        h = MinHeap()
        self.assertEqual(len(h), 0)
        self.assertEqual(h.size(), 0)
        self.assertTrue(h.is_empty())
        self.assertFalse(h.contains("a"))
        h.validate_heap()

    def test_single_element(self) -> None:
        h = MinHeap()
        h.push("only", 5.0)
        self.assertEqual(len(h), 1)
        self.assertFalse(h.is_empty())
        self.assertTrue(h.contains("only"))
        self.assertEqual(h.peek_min(), ("only", 5.0))
        h.validate_heap()

    def test_pop_min_on_empty_raises(self) -> None:
        h = MinHeap()
        with self.assertRaises(HeapError):
            h.pop_min()

    def test_peek_min_on_empty_raises(self) -> None:
        h = MinHeap()
        with self.assertRaises(HeapError):
            h.peek_min()


# ---------------------------------------------------------------------------
#  push / pop_min
# ---------------------------------------------------------------------------


class TestPushPop(unittest.TestCase):
    def test_push_preserves_min(self) -> None:
        h = MinHeap()
        for k, v in [("b", 2), ("a", 1), ("c", 3)]:
            h.push(k, v)
        h.validate_heap()
        self.assertEqual(h.peek_min(), ("a", 1))

    def test_ascending_push(self) -> None:
        h = MinHeap()
        for i in range(1, 8):
            h.push(f"k{i}", float(i))
        out = [h.pop_min() for _ in range(7)]
        self.assertEqual([k for k, _ in out], [f"k{i}" for i in range(1, 8)])

    def test_descending_push(self) -> None:
        h = MinHeap()
        for i in range(7, 0, -1):
            h.push(f"k{i}", float(i))
        out = [h.pop_min() for _ in range(7)]
        self.assertEqual([k for k, _ in out], [f"k{i}" for i in range(1, 8)])

    def test_random_push(self) -> None:
        import random
        rng = random.Random(42)
        items = [(f"n{i}", float(rng.randint(1, 100))) for i in range(50)]
        h = MinHeap()
        for k, v in items:
            h.push(k, v)
        out = [h.pop_min() for _ in range(len(items))]
        # 期望按 (priority, node_id) 字典序：堆在 priority 相同时按 node_id 排序
        expected = sorted(items, key=lambda x: (x[1], x[0]))
        self.assertEqual([k for k, _ in out], [k for k, _ in expected])
        h.validate_heap()

    def test_duplicate_push_rejected(self) -> None:
        h = MinHeap()
        h.push("x", 1.0)
        with self.assertRaises(DuplicateNodeError):
            h.push("x", 2.0)
        h.validate_heap()

    def test_pop_min_returns_min_each_time(self) -> None:
        h = MinHeap()
        h.push("a", 5)
        h.push("b", 3)
        h.push("c", 8)
        h.push("d", 1)
        h.push("e", 4)
        order = [h.pop_min() for _ in range(5)]
        self.assertEqual(order, [("d", 1), ("b", 3), ("e", 4), ("a", 5), ("c", 8)])


# ---------------------------------------------------------------------------
#  Tie-breaking 稳定性
# ---------------------------------------------------------------------------


class TestTieBreak(unittest.TestCase):
    def test_tie_break_by_node_id_lexicographic(self) -> None:
        h = MinHeap()
        # 三个相同 priority；按 node_id 字典序：b < c < a 错误 → a < b < c
        for nid in ("b", "c", "a"):
            h.push(nid, 1.0)
        order = [h.pop_min() for _ in range(3)]
        self.assertEqual([k for k, _ in order], ["a", "b", "c"])

    def test_stable_across_repeated_runs(self) -> None:
        """同输入多次运行结果必须一致。"""
        inputs = [("z", 5), ("y", 5), ("x", 5), ("w", 5)]
        results = []
        for _ in range(5):
            h = MinHeap()
            for k, v in inputs:
                h.push(k, v)
            results.append([h.pop_min()[0] for _ in range(4)])
        for r in results[1:]:
            self.assertEqual(r, results[0])


# ---------------------------------------------------------------------------
#  decrease_key
# ---------------------------------------------------------------------------


class TestDecreaseKey(unittest.TestCase):
    def test_decrease_key_triggers_sift_up(self) -> None:
        h = MinHeap()
        for k, v in [("a", 1), ("b", 2), ("c", 3), ("d", 4)]:
            h.push(k, v)
        # 把 d 从 4 降到 0 → 应当浮到顶
        h.decrease_key("d", 0)
        h.validate_heap()
        self.assertEqual(h.peek_min(), ("d", 0))

    def test_decrease_key_equal_value(self) -> None:
        h = MinHeap()
        h.push("a", 1)
        h.push("b", 2)
        h.decrease_key("b", 2)  # 不变，仍合法
        h.validate_heap()
        self.assertEqual(h.peek_min(), ("a", 1))

    def test_decrease_key_increase_rejected(self) -> None:
        h = MinHeap()
        h.push("a", 1)
        with self.assertRaises(HeapError):
            h.decrease_key("a", 2)

    def test_decrease_key_unknown_rejected(self) -> None:
        h = MinHeap()
        h.push("a", 1)
        with self.assertRaises(UnknownNodeError):
            h.decrease_key("ghost", 0)

    def test_decrease_key_after_pop(self) -> None:
        h = MinHeap()
        h.push("a", 1)
        h.push("b", 2)
        h.pop_min()  # 弹出 a
        with self.assertRaises(UnknownNodeError):
            h.decrease_key("a", 0)
        # b 仍然可以 decrease
        h.decrease_key("b", 0.5)
        self.assertEqual(h.peek_min(), ("b", 0.5))


# ---------------------------------------------------------------------------
#  heapify
# ---------------------------------------------------------------------------


class TestHeapify(unittest.TestCase):
    def test_heapify_random_input(self) -> None:
        import random
        rng = random.Random(7)
        items = [(f"n{i}", float(rng.randint(0, 1000))) for i in range(100)]
        h = MinHeap()
        h.heapify(items)
        h.validate_heap()
        # 期望顺序
        out = [h.pop_min() for _ in range(len(items))]
        self.assertEqual([k for k, _ in out], [k for k, _ in sorted(items, key=lambda x: x[1])])

    def test_heapify_empty(self) -> None:
        h = MinHeap()
        h.heapify([])
        self.assertTrue(h.is_empty())
        h.validate_heap()

    def test_heapify_rejects_duplicates(self) -> None:
        h = MinHeap()
        with self.assertRaises(DuplicateNodeError):
            h.heapify([("a", 1), ("a", 2)])

    def test_heapify_resets_state(self) -> None:
        h = MinHeap()
        h.push("a", 1)
        h.heapify([("x", 5), ("y", 3)])
        h.validate_heap()
        self.assertEqual(h.peek_min(), ("y", 3))
        # 旧节点 a 应当不可达
        self.assertFalse(h.contains("a"))
        self.assertTrue(h.contains("x"))


# ---------------------------------------------------------------------------
#  非法优先级
# ---------------------------------------------------------------------------


class TestInvalidPriority(unittest.TestCase):
    def test_push_nan_rejected(self) -> None:
        h = MinHeap()
        with self.assertRaises(InvalidPriorityError):
            h.push("a", float("nan"))

    def test_push_inf_rejected(self) -> None:
        h = MinHeap()
        with self.assertRaises(InvalidPriorityError):
            h.push("a", float("inf"))

    def test_push_neg_inf_rejected(self) -> None:
        h = MinHeap()
        with self.assertRaises(InvalidPriorityError):
            h.push("a", float("-inf"))

    def test_decrease_key_nan_rejected(self) -> None:
        h = MinHeap()
        h.push("a", 1)
        with self.assertRaises(InvalidPriorityError):
            h.decrease_key("a", float("nan"))

    def test_push_bool_rejected(self) -> None:
        # bool 是 int 子类，但语义上不是数值；显式拒绝
        h = MinHeap()
        with self.assertRaises(InvalidPriorityError):
            h.push("a", True)  # type: ignore[arg-type]

    def test_push_string_priority_rejected(self) -> None:
        h = MinHeap()
        with self.assertRaises(InvalidPriorityError):
            h.push("a", "1.0")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
#  大量节点下的位置映射稳定性
# ---------------------------------------------------------------------------


class TestLargeScaleConsistency(unittest.TestCase):
    def test_position_map_consistent_after_many_ops(self) -> None:
        import random
        rng = random.Random(0)
        h = MinHeap()
        # 先记录每个节点的初始 priority，再 push（保持 RNG 序列一致）
        initial: dict[str, float] = {}
        for i in range(200):
            pri = float(rng.randint(1000, 10000))
            nid = f"n{i}"
            h.push(nid, pri)
            initial[nid] = pri
        h.validate_heap()
        # 随机执行 100 次 decrease_key：必须 < 当前 priority
        ids = list(initial.keys())
        current = dict(initial)
        for _ in range(100):
            nid = rng.choice(ids)
            cur = current[nid]
            new_pri = float(rng.randint(0, max(0, int(cur) - 1)))
            h.decrease_key(nid, new_pri)
            current[nid] = new_pri
        h.validate_heap()
        # 弹出全部，断言非降序 + 堆性质
        prev_pri = -math.inf
        out = []
        while not h.is_empty():
            nid, pri = h.pop_min()
            self.assertGreaterEqual(pri, prev_pri)
            out.append((nid, pri))
            prev_pri = pri
            h.validate_heap()
        self.assertEqual(len(out), 200)


# ---------------------------------------------------------------------------
#  接口与辅助
# ---------------------------------------------------------------------------


class TestAuxiliary(unittest.TestCase):
    def test_to_sorted_list_snapshot(self) -> None:
        h = MinHeap()
        for k, v in [("a", 3), ("b", 1), ("c", 2)]:
            h.push(k, v)
        # 不修改原堆
        snapshot = h.to_sorted_list()
        self.assertEqual([k for k, _ in snapshot], ["b", "c", "a"])
        # 原堆仍可正常 pop
        self.assertEqual(h.pop_min(), ("b", 1))

    def test_repr_contains_size(self) -> None:
        h = MinHeap()
        h.push("a", 1)
        self.assertIn("size=1", repr(h))

    def test_slots_no_dynamic_attrs(self) -> None:
        h = MinHeap()
        with self.assertRaises(AttributeError):
            h.dynamic = 1  # type: ignore[attr-defined]

    def test_repeated_push_pop_balanced(self) -> None:
        """push + pop 1000 次后堆仍合法。"""
        import random
        rng = random.Random(123)
        h = MinHeap()
        for i in range(1000):
            if i % 2 == 0:
                h.push(f"n{i}", float(rng.randint(0, 100)))
            elif not h.is_empty():
                h.pop_min()
            if i % 50 == 0:
                h.validate_heap()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
