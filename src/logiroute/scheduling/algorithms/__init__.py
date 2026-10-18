"""调度算法子包 —— Phase 3 自实现的算法 + Phase 5 统一调度器。

* :func:`nearest_neighbor` —— 最近邻基线（保留作回归测试）；
* :func:`cheapest_feasible_insertion` —— 可行插入（CFI）；
* :func:`constrained_two_opt` —— 受约束 2-opt 局部搜索；
* :func:`unified_planner` —— Phase 5 默认公开入口（NN / CFI + 2-opt 择优）。

公开入口（Phase 5）只接受 :func:`logiroute.scheduling.planner.plan_deliveries`
的 ``objective`` 参数；用户不再选择 NN / CFI / 2-opt 显式算法。
``ALGORITHM_NAMES`` 现包含 ``"unified"`` 作为默认算法，
``nearest_neighbor`` / ``insertion`` / ``two_opt`` 保留供回归与实验比较。
"""

from __future__ import annotations

from logiroute.scheduling.algorithms.insertion import (
    cheapest_feasible_insertion,
)
from logiroute.scheduling.algorithms.nearest_neighbor import nearest_neighbor
from logiroute.scheduling.algorithms.two_opt import constrained_two_opt
from logiroute.scheduling.algorithms.unified import unified_planner

ALGORITHM_NAMES: tuple[str, ...] = (
    "unified",
    "nearest_neighbor",
    "insertion",
    "two_opt",
)

__all__ = [
    "ALGORITHM_NAMES",
    "cheapest_feasible_insertion",
    "constrained_two_opt",
    "nearest_neighbor",
    "unified_planner",
]
