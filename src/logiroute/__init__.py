"""LogiRoute — 电商物流配送路径规划系统。

本项目是数据结构课程设计的工程实现，分阶段开发。

当前进度：Phase 1 — 工程初始化与核心数据结构。

模块说明：

* ``logiroute.core``     业务数据模型（Node / Edge / Vehicle / Courier / Order）。
* ``logiroute.graph``    有向带权图容器，邻接表作为核心存储结构。
* ``logiroute.algorithms`` 路径规划算法（Phase 2+ 引入，当前仅占位）。
* ``logiroute.dispatch`` 配送调度（Phase 2+ 引入，当前仅占位）。
* ``logiroute.config``   配置加载（Phase 2+ 引入，当前仅占位）。
* ``logiroute.api``      FastAPI 后端（Phase 2+ 引入，当前仅占位）。
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
