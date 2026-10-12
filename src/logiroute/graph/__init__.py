"""有向带权图容器。

阶段 1 仅实现 LogisticsGraph 基础结构（邻接表 + 邻接矩阵导出）。
后续阶段将在 ``logiroute.algorithms`` 中基于该容器实现路径规划。
"""

from logiroute.graph.logistics_graph import LogisticsGraph

__all__ = ["LogisticsGraph"]
