"""Phase 5 —— FastAPI 应用工厂。

调用方：

.. code-block:: python

    from logiroute.api import create_app
    app = create_app()

    # uvicorn 启动（dev）：
    #   uvicorn logiroute.api:app --reload --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from logiroute.api.errors import APIError
from logiroute.api.routes import (
    health_router,
    planning_router,
    scenarios_router,
)
from logiroute.api.services import ScenarioService


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """初始化 ``app.state.scenario_service``。"""
    app.state.scenario_service = ScenarioService()
    yield
    # 关闭期：单进程状态，无需持久化


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error_handler(request: Request, exc: APIError):  # noqa: ARG001
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response(),
        )


def create_app() -> FastAPI:
    """构造 FastAPI 应用实例。

    已配置：

    * CORS：允许 ``http://localhost:5172``（Vite 默认端口，5173 已被占用故改 5172）；
    * 路由：``/api/health``、``/api/scenario/*``、``/api/plan``、``/api/compare``；
    * 异常处理：``APIError`` 子类统一返回 JSON ``{"error": {...}}``；
    * ``app.state.scenario_service``：单实例 ``ScenarioService``。
    """
    app = FastAPI(
        title="LogiRoute Dashboard API",
        version="phase5",
        description=(
            "单车辆电商物流配送路径规划系统的 FastAPI 后端。"
            "算法核心全部复用 Phase 1-4 已交付模块；"
            "本包仅承载 Web 层（路由 + Pydantic + CORS）。"
        ),
        lifespan=_lifespan,
    )

    # CORS —— Vite 开发服务器（5172 / 4173 preview）；本地开发允许。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5172",
            "http://127.0.0.1:5172",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    _install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(scenarios_router)
    app.include_router(planning_router)

    return app


# 顶层 ``app`` 实例，供 ``uvicorn logiroute.api:app`` 直接使用。
app = create_app()


__all__ = ["create_app", "app"]