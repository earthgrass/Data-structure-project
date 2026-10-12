"""LogiRoute — 电商物流配送路径规划系统。

本项目是数据结构课程设计的工程实现，分阶段开发。**所有核心数据结构与算法均手工实现**，
仅使用 Python 标准库，不依赖任何第三方图算法 / 优化库（NetworkX、NumPy、SciPy、OR-Tools 等）。

当前进度：Phase 1 — 工程初始化、配置驱动与核心数据结构。

模块说明：

* ``logiroute.core``       业务数据模型（Node / Edge / Vehicle / Courier / Order）。
* ``logiroute.graph``      有向带权图容器，邻接表作为核心存储结构。
* ``logiroute.config``     JSON 场景配置加载与校验。
* ``logiroute.algorithms`` 路径规划算法（Phase 2+ 引入，**手工实现**，禁用 ``heapq`` 替代品）。
* ``logiroute.scheduling`` 配送调度（Phase 4+ 引入）。
* ``logiroute.simulation`` 随机场景 / 动态事件（设计见 docs/architecture.md）。
* ``logiroute.api``        FastAPI 后端（Phase 6+ 引入）。
* ``logiroute.web``        前端 Dashboard 占位（前端工程独立目录管理）。
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
