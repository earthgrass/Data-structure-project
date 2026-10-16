"""调度算法子包 —— Phase 3 自实现的三个调度构造 / 改进策略。

* :func:`nearest_neighbor` —— 最近邻基线构造；
* :func:`cheapest_feasible_insertion` —— 可行插入（CFI）；
* :func:`constrained_two_opt` —— 受约束 2-opt 局部搜索。
"""

from __future__ import annotations

ALGORITHM_NAMES: tuple[str, ...] = (
    "nearest_neighbor",
    "insertion",
    "two_opt",
)

__all__ = ["ALGORITHM_NAMES"]
