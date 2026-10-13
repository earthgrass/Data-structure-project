"""索引式二叉最小堆（Indexed Binary Min Heap）。

本模块为 Phase 2 的 Dijkstra 算法提供自实现的优先队列基础。**严禁**使用
``heapq`` 等任何标准库 / 第三方优先队列。

设计要点
--------

1. **顺序存储的二叉最小堆**。底层使用 Python ``list`` 模拟完全二叉树。
   对任意下标 ``i``：

   * 父节点：``(i - 1) // 2``
   * 左孩子：``2 * i + 1``
   * 右孩子：``2 * i + 2``

2. **堆性质**：任意父节点 ``priority`` 不大于其子节点 ``priority``。

3. **索引式**：维护 ``_pos: dict[node_id, int]`` 将节点 ID 映射到其在底层
   ``list`` 中的下标，使 ``decrease_key`` 可在 O(1) 摊销时间定位元素，
   之后做 O(log n) 上浮。**Dijkstra 中的 ``decrease_key`` 是性能关键**。

4. **确定性 tie-break**：当两个节点 ``priority`` 相等时，``node_id`` 字
   典序较小者排前。多次运行相同输入得到稳定输出。

5. **拒绝非法输入**：优先级非有限数（NaN / inf）一律拒绝；``decrease_key``
   不存在的节点报错；``decrease_key`` 增大或保持原值时按文档约定行为
   处理（见方法 docstring）。

复杂度（V = 堆中元素数）
------------------------

* ``push`` —— O(log V) 摊销
* ``pop_min`` —— O(log V)
* ``peek_min`` —— O(1)
* ``decrease_key`` —— O(log V)（位置查找 O(1) + 上浮 O(log V)）
* ``contains`` —— O(1) avg
* ``is_empty`` / ``size`` —— O(1)
* ``heapify`` —— O(V)
* ``validate_heap`` —— O(V)

辅助空间：O(V)。
"""

from __future__ import annotations

import math
from typing import Any, Iterable


class HeapError(Exception):
    """堆操作的通用错误基类。"""


class DuplicateNodeError(HeapError):
    """向堆中插入已存在节点时抛出。"""


class UnknownNodeError(HeapError):
    """对堆中不存在的节点执行 ``decrease_key`` 时抛出。"""


class InvalidPriorityError(HeapError):
    """优先级为非有限数（NaN / inf）时抛出。"""


class MinHeap:
    """索引式二叉最小堆。``node_id`` 为任意可哈希对象；``priority`` 为有限实数。"""

    __slots__ = ("_heap", "_pos", "_size")

    def __init__(self) -> None:
        # 内部存储：(node_id, priority) 的 list；保持最小堆性质
        self._heap: list[tuple[Any, float]] = []
        # 位置索引：node_id -> 当前在 _heap 中的下标
        self._pos: dict[Any, int] = {}
        self._size: int = 0

    # ------------------------------------------------------------------ #
    #  基本状态                                                          #
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        return self._size

    def is_empty(self) -> bool:
        return self._size == 0

    def size(self) -> int:
        return self._size

    def contains(self, node_id: Any) -> bool:
        """O(1) avg 时间判断节点是否在堆中。"""
        return node_id in self._pos

    # ------------------------------------------------------------------ #
    #  优先级合法性                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _check_priority(value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise InvalidPriorityError(
                f"priority must be a finite number, got {type(value).__name__}"
            )
        # 拒绝 bool 后，下面可安全使用数学判等
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                raise InvalidPriorityError(
                    f"priority must be finite (no NaN/inf), got {value!r}"
                )

    # ------------------------------------------------------------------ #
    #  核心操作                                                          #
    # ------------------------------------------------------------------ #

    def push(self, node_id: Any, priority: float) -> None:
        """插入 ``(node_id, priority)``；重复节点抛 ``DuplicateNodeError``。

        Time   : O(log V) 摊销。
        """
        self._check_priority(priority)
        if node_id in self._pos:
            raise DuplicateNodeError(f"node {node_id!r} already in heap")
        self._heap.append((node_id, priority))
        self._pos[node_id] = self._size
        self._size += 1
        self._sift_up(self._size - 1)

    def pop_min(self) -> tuple[Any, float]:
        """移除并返回 ``(node_id, priority)``；空堆抛 ``HeapError``。

        Time   : O(log V)。
        """
        if self._size == 0:
            raise HeapError("pop_min from empty heap")
        top_id, top_pri = self._heap[0]
        last = self._size - 1
        if last != 0:
            # 把末尾元素移到堆顶
            self._heap[0] = self._heap[last]
            moved_id, moved_pri = self._heap[0]
            self._pos[moved_id] = 0
        # 弹出原堆顶
        del self._pos[top_id]
        self._heap.pop()
        self._size -= 1
        if self._size > 0:
            self._sift_down(0)
        return top_id, top_pri

    def peek_min(self) -> tuple[Any, float]:
        """返回堆顶元素但不移除。空堆抛 ``HeapError``。Time: O(1)。"""
        if self._size == 0:
            raise HeapError("peek_min from empty heap")
        return self._heap[0]

    def decrease_key(self, node_id: Any, new_priority: float) -> None:
        """将已存在节点的优先级降低（或保持）后上浮。

        * ``new_priority`` 严格小于旧值：正常 decrease → O(log V) 上浮。
        * ``new_priority`` 等于旧值：上浮至满足稳定顺序的位置（仍 O(log V)）。
        * ``new_priority`` 大于旧值：抛 ``HeapError``，避免破坏 Dijkstra 的
          "已确定距离不应当被更高估" 的不变量；调用方应自行决定是否需要
          改用 "delete + push" 语义。
        * 节点不在堆中：抛 ``UnknownNodeError``。
        * 非有限值：抛 ``InvalidPriorityError``。

        Time   : O(log V) —— 位置查找 O(1) + 上浮 O(log V)。
        """
        self._check_priority(new_priority)
        if node_id not in self._pos:
            raise UnknownNodeError(f"node {node_id!r} not in heap")
        idx = self._pos[node_id]
        old_id, old_pri = self._heap[idx]
        if new_priority > old_pri:
            raise HeapError(
                f"decrease_key called with larger priority "
                f"({new_priority} > {old_pri}) for node {node_id!r}"
            )
        # 重新赋值
        self._heap[idx] = (old_id, new_priority)
        if new_priority < old_pri or new_priority == old_pri:
            self._sift_up(idx)

    # ------------------------------------------------------------------ #
    #  建堆                                                              #
    # ------------------------------------------------------------------ #

    def heapify(self, items: Iterable[tuple[Any, float]]) -> None:
        """以自底向上 O(V) 方式将外部列表建为最小堆。

        输入为 ``[(node_id, priority), ...]``；不允许重复 node_id。
        调用后 ``self`` 成为新堆，旧元素全部丢弃。

        Time   : O(V)
        Space  : O(V) 新底层数组。
        """
        materialized: list[tuple[Any, float]] = list(items)
        # 校验
        seen: set[Any] = set()
        for nid, pri in materialized:
            self._check_priority(pri)
            if nid in seen:
                raise DuplicateNodeError(f"node {nid!r} appears more than once")
            seen.add(nid)
        # 替换底层
        self._heap = materialized
        self._size = len(materialized)
        self._pos = {nid: i for i, (nid, _) in enumerate(self._heap)}
        # 自底向上：对每个非叶节点下沉
        # 最后非叶节点 = (size // 2) - 1；size==0 时不入循环
        for i in range(self._size // 2 - 1, -1, -1):
            self._sift_down(i)

    # ------------------------------------------------------------------ #
    #  调试 / 校验                                                       #
    # ------------------------------------------------------------------ #

    def validate_heap(self) -> None:
        """校验：堆性质 + 位置映射 + 唯一性。失败抛 ``HeapError``。

        Time   : O(V)。
        """
        if self._size != len(self._heap):
            raise HeapError(
                f"size invariant broken: size={self._size} but len(_heap)={len(self._heap)}"
            )
        if self._size != len(self._pos):
            raise HeapError(
                f"pos map size mismatch: {len(self._pos)} entries for {self._size} nodes"
            )
        seen_ids: set[Any] = set()
        for i, (nid, pri) in enumerate(self._heap):
            if nid in seen_ids:
                raise HeapError(f"duplicate node {nid!r} at index {i}")
            seen_ids.add(nid)
            if self._pos.get(nid) != i:
                raise HeapError(
                    f"pos map stale: node {nid!r} -> {self._pos.get(nid)}, "
                    f"actual index = {i}"
                )
            # 堆性质：父 <= 子（按 (priority, node_id) 字典序）
            left = 2 * i + 1
            right = 2 * i + 2
            if left < self._size and not self._less_or_equal(i, left):
                raise HeapError(
                    f"heap property violated at index {i} vs {left}: "
                    f"{self._heap[i]} > {self._heap[left]}"
                )
            if right < self._size and not self._less_or_equal(i, right):
                raise HeapError(
                    f"heap property violated at index {i} vs {right}: "
                    f"{self._heap[i]} > {self._heap[right]}"
                )

    def to_sorted_list(self) -> list[tuple[Any, float]]:
        """返回按 ``pop_min`` 顺序排列的快照（不修改堆）。Time: O(V log V)。"""
        clone = MinHeap()
        clone.heapify([(nid, pri) for nid, pri in self._heap])
        return [clone.pop_min() for _ in range(len(clone))]

    def __iter__(self) -> Iterable[tuple[Any, float]]:
        """产出当前底层数组（不保证堆序）。"""
        return iter(list(self._heap))

    def __repr__(self) -> str:
        return f"MinHeap(size={self._size})"

    # ------------------------------------------------------------------ #
    #  内部：上浮 / 下沉                                                 #
    # ------------------------------------------------------------------ #

    def _less_or_equal(self, i: int, j: int) -> bool:
        """比较 ``_heap[i]`` 是否在排序键上不大于 ``_heap[j]``。

        排序键 = (priority, node_id)；``node_id`` 字典序保证确定性。
        """
        ni, pi = self._heap[i]
        nj, pj = self._heap[j]
        if pi != pj:
            return pi < pj
        # priority 相同时按 node_id 字典序（保证稳定）
        return str(ni) <= str(nj)

    def _sift_up(self, idx: int) -> None:
        """将下标 ``idx`` 处元素沿父链上浮至满足堆序。Time: O(log V)。"""
        h = self._heap
        while idx > 0:
            parent = (idx - 1) // 2
            if self._less_or_equal(idx, parent):
                h[idx], h[parent] = h[parent], h[idx]
                self._pos[h[idx][0]] = idx
                self._pos[h[parent][0]] = parent
                idx = parent
            else:
                break

    def _sift_down(self, idx: int) -> None:
        """将下标 ``idx`` 处元素沿子节点最小者下沉至满足堆序。Time: O(log V)。"""
        h = self._heap
        n = self._size
        while True:
            left = 2 * idx + 1
            right = 2 * idx + 2
            smallest = idx
            if left < n and self._less_or_equal(left, smallest):
                smallest = left
            if right < n and self._less_or_equal(right, smallest):
                smallest = right
            if smallest == idx:
                break
            h[idx], h[smallest] = h[smallest], h[idx]
            self._pos[h[idx][0]] = idx
            self._pos[h[smallest][0]] = smallest
            idx = smallest


__all__ = [
    "MinHeap",
    "HeapError",
    "DuplicateNodeError",
    "UnknownNodeError",
    "InvalidPriorityError",
]
