"""基于动态数组与队首指针的自实现 FIFO 队列。

本模块用于支撑 ``config.loader`` 中的弱连通性 BFS 与后续阶段
（图遍历 / BFS 层序 / 事件驱动仿真）的队列需求。设计上避免依赖
``collections.deque``，原因如下：

* 课程要求核心数据结构自主实现；FIFO 队列是 BFS 的核心部件。
* ``list.pop(0)`` 头部弹出是 O(n)，不适合充当队列。
* 单一递增 ``head`` 指针在 BFS 等"短期使用、随即释放"的场景下空间
  复杂度仍为 O(n)，且实现足够简单。

本实现不试图替代通用环形队列：

* **空间回收策略**：BFS 完成后队列引用随函数栈释放；如需在长生命周期内
  复用（例如事件队列），应改用环形缓冲（Phase 5+ 仿真场景再扩展）。
* **不**保证 ``dequeue`` 后旧槽位被回收——上层应当将对象置 ``None`` 或直接
  丢弃队列引用以触发 GC。

时间复杂度
----------

* ``enqueue`` —— O(1) 摊销（动态数组均摊）
* ``dequeue`` —— O(1)
* ``is_empty`` / ``__len__`` —— O(1)
* 空间 —— O(n)，n 为当前队列中元素数
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Generic, TypeVar

T = TypeVar("T")


class EmptyQueueError(Exception):
    """对空队列执行 ``dequeue`` / ``front`` 时抛出。"""


class ArrayQueue(Generic[T]):
    """基于 ``list`` 与队首指针的 FIFO 队列。

    与 ``collections.deque`` 区别：仅暴露队列语义接口（``enqueue`` /
    ``dequeue`` / ``front``），并显式拒绝"随机访问 / 中部插入"，以保证
    课程代码与"队列"这一抽象数据类型一致。
    """

    __slots__ = ("_buf", "_head", "_len")

    def __init__(self) -> None:
        # 内部使用 list 作为底层存储；外部不应直接访问
        self._buf: list[T] = []
        self._head: int = 0
        self._len: int = 0

    # ------------------------------------------------------------------ #
    #  基本状态                                                          #
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        return self._len

    def is_empty(self) -> bool:
        return self._len == 0

    def __bool__(self) -> bool:
        return self._len > 0

    # ------------------------------------------------------------------ #
    #  入队 / 出队 / 查看队首                                            #
    # ------------------------------------------------------------------ #

    def enqueue(self, item: T) -> None:
        """在队尾追加一个元素。Time: O(1) 摊销。"""
        self._buf.append(item)
        self._len += 1

    def dequeue(self) -> T:
        """移除并返回队首元素。空队列抛 ``EmptyQueueError``。Time: O(1)。"""
        if self._len == 0:
            raise EmptyQueueError("dequeue from empty queue")
        item = self._buf[self._head]
        # 不立即清空槽位——递增 head 即可；这是经典"懒惰删除"策略，
        # 等队列整体销毁时由 GC 一并回收。
        self._head += 1
        self._len -= 1
        return item

    def front(self) -> T:
        """查看队首元素但不移除。空队列抛 ``EmptyQueueError``。Time: O(1)。"""
        if self._len == 0:
            raise EmptyQueueError("front from empty queue")
        return self._buf[self._head]

    # ------------------------------------------------------------------ #
    #  维护                                                              #
    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        """清空队列。Time: O(1)——仅重置指针。"""
        self._buf.clear()
        self._head = 0
        self._len = 0

    def compact(self) -> None:
        """主动回收已弹出元素的存储。

        适用于长生命周期队列（例如 Phase 5 事件队列）。BFS 等短期队列
        无需调用。Time: O(n)，n 为当前队列长度。
        """
        if self._head == 0:
            return
        # 删除已弹出部分
        del self._buf[: self._head]
        self._head = 0

    # ------------------------------------------------------------------ #
    #  迭代 / 调试                                                       #
    # ------------------------------------------------------------------ #

    def __iter__(self) -> Iterator[T]:
        """按队首→队尾顺序产出元素（不移除）。"""
        for i in range(self._head, self._head + self._len):
            yield self._buf[i]

    def __repr__(self) -> str:
        return f"ArrayQueue(len={self._len}, capacity={len(self._buf)})"


__all__ = ["ArrayQueue", "EmptyQueueError"]
