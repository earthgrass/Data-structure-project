"""路径规划算法模块。

Phase 2 已实现：

* ``MinHeap`` —— 自实现的索引式二叉最小堆（**禁止**使用 ``heapq``）。
* ``dijkstra`` —— 单源最短路与两点最优路径，支持三种 metric。

后续阶段：

* Phase 3 —— 多目标综合优化
* Phase 4 —— 配送顺序优化与时间窗口约束
* Phase 5 —— 动态订单插入与重规划
"""

from logiroute.algorithms.heap import (
    DuplicateNodeError,
    HeapError,
    InvalidPriorityError,
    MinHeap,
    UnknownNodeError,
)

__all__ = [
    "DuplicateNodeError",
    "HeapError",
    "InvalidPriorityError",
    "MinHeap",
    "UnknownNodeError",
    # dijkstra 模块在另一文件里，被 algorithms 包的 __init__ 选择性懒加载
    # 以避免循环依赖。下面用 getattr 提供延迟绑定。
    "dijkstra",
]


def __getattr__(name: str):
    """延迟导入 dijkstra 模块，避免循环引用。"""
    if name == "dijkstra":
        from logiroute.algorithms import dijkstra as _dijkstra
        return _dijkstra
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
