"""``/api/scenario/*`` —— 场景生成与获取。

* ``POST /api/scenario/random`` —— 随机生成新场景，替换当前激活场景；
* ``GET  /api/scenario/current`` —— 获取当前激活场景与独立 validator 报告。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from logiroute.api.services import ScenarioService


router = APIRouter(prefix="/api/scenario", tags=["scenarios"])


class RandomScenarioRequest(BaseModel):
    """``POST /api/scenario/random`` 的请求体。"""

    seed: int = Field(
        default=42,
        description="整数 seed；同 seed + 同 config → 完全相同场景。",
    )
    orders_count: int | None = Field(
        default=None,
        ge=1,
        description="订单数；None 表示使用 GeneratorConfig 默认值。",
    )
    capacity: float | None = Field(
        default=None,
        gt=0,
        description="车辆容量；None 表示使用 GeneratorConfig 默认值。",
    )


class ScenarioResponse(BaseModel):
    """场景响应体（与 GET /api/scenario/current 一致）。"""

    scenario: dict[str, Any]
    validation: dict[str, Any]
    config_name: str


def _service(request: Request) -> ScenarioService:
    svc = getattr(request.app.state, "scenario_service", None)
    if svc is None:
        raise RuntimeError("ScenarioService missing from app.state")
    return svc


@router.post("/random", response_model=ScenarioResponse)
def post_random_scenario(
    body: RandomScenarioRequest, request: Request
) -> ScenarioResponse:
    """生成新随机场景并设为当前激活场景，返回完整场景图。"""
    svc = _service(request)
    svc.generate_random_scenario(
        seed=body.seed,
        orders_count=body.orders_count,
        capacity=body.capacity,
    )
    return ScenarioResponse(**svc.current_scenario_payload())


@router.get("/current", response_model=ScenarioResponse)
def get_current_scenario(request: Request) -> ScenarioResponse:
    """获取当前激活场景；不存在则由全局错误处理器返回 404。"""
    svc = _service(request)
    return ScenarioResponse(**svc.current_scenario_payload())


__all__ = ["router"]