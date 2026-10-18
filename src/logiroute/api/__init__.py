"""Phase 5 —— LogiRoute FastAPI 应用包。

包结构：

* :mod:`logiroute.api.errors` —— 异常类型与错误响应；
* :mod:`logiroute.api.schemas` —— Pydantic 请求 / 响应模型；
* :mod:`logiroute.api.services` —— 服务端状态管理 + 调度外观；
* :mod:`logiroute.api.routes` —— 路由模块集合；
* :mod:`logiroute.api.factory` —— FastAPI 应用工厂。

Phase 5 仅承载**最小可用 Dashboard 后端**：

* ``GET /api/health``：健康检查；
* ``POST /api/scenario/random``：随机生成场景；
* ``GET /api/scenario/current``：获取当前激活的场景；
* ``POST /api/plan``：在当前场景上运行统一规划器；
* ``POST /api/compare``：在同一场景上比较最短距离与最低成本目标。

**算法核心位于调度与图算法模块**，本包**不**重新实现
Dijkstra / TSP / NN / CFI / 2-opt / 随机生成器。Web 框架（FastAPI）与
Pydantic 属于运行期依赖，**不**在课程要求的"核心算法禁表"中。
"""
from __future__ import annotations

from logiroute.api.factory import app, create_app

__all__ = ["app", "create_app"]
