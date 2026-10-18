"""``/api/plan`` / ``/api/compare`` —— Phase 5 统一调度接口。

* ``POST /api/plan`` —— 在当前场景上跑统一规划器（用户只选 ``objective``）；
* ``POST /api/compare`` —— 在同一场景快照上同时跑 distance 与 cost。

Phase 5 规格 §3.1 / §五：

* 用户公开 API **不**再传入 algorithm；统一规划器内部运行
  ``Dijkstra 距离矩阵 + 有向 TSP``；
* ``algorithm`` 字段保留作向后兼容；传入时记录 deprecation warning 并被
  强制忽略（生产流程仍走 unified）；
* 比较接口不再比较三算法，仅比较 distance vs cost 两种主目标。
"""
from __future__ import annotations

import warnings
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from logiroute.api.services import (
    ALLOWED_OBJECTIVES,
    DEFAULT_ALGORITHM,
    ScenarioService,
)


router = APIRouter(prefix="/api", tags=["planning"])


class PlanRequest(BaseModel):
    """``POST /api/plan`` 请求体。

    Phase 5 默认只接受 ``objective``；``algorithm`` 保留作向后兼容但被忽略。
    """

    objective: str = Field(
        default="distance",
        description="主目标：distance / cost；travel_time 拒绝",
    )
    algorithm: str | None = Field(
        default=None,
        description=(
            "DEPRECATED —— 已废弃。用户公开 API 不再传入算法名称；"
            "统一规划器内部使用 Dijkstra 距离矩阵 + TSP 搜索。传任何值都会被忽略。"
        ),
    )


class CompareRequest(BaseModel):
    """``POST /api/compare`` 请求体。

    比较两种主目标（distance / cost）；不再比较三种调度算法。
    """

    distance: bool = Field(
        default=True,
        description="是否运行最短距离模式（默认 True）",
    )
    cost: bool = Field(
        default=True,
        description="是否运行最低成本模式（默认 True）",
    )


def _service(request: Request) -> ScenarioService:
    svc = getattr(request.app.state, "scenario_service", None)
    if svc is None:
        raise RuntimeError("ScenarioService missing from app.state")
    return svc


@router.post("/plan")
def post_plan(body: PlanRequest, request: Request) -> dict[str, Any]:
    """在当前场景上跑统一规划器（用户只选主目标）。"""
    svc = _service(request)
    # 弃用字段警告（即使传值也不影响生产流程）
    if body.algorithm is not None:
        warnings.warn(
            "POST /api/plan 'algorithm' field is deprecated and ignored; "
            "use 'objective' only. Unified planner runs Dijkstra + TSP search.",
            DeprecationWarning,
            stacklevel=2,
        )
    if body.objective not in ALLOWED_OBJECTIVES:
        from logiroute.api.errors import BadRequestError
        raise BadRequestError(
            f"objective={body.objective!r} not in {ALLOWED_OBJECTIVES}",
            field="objective",
        )
    result = svc.plan(algorithm=DEFAULT_ALGORITHM, objective=body.objective)
    return {
        "objective": body.objective,
        "result": result.to_dict(),
    }


@router.post("/compare")
def post_compare(body: CompareRequest, request: Request) -> dict[str, Any]:
    """在同一场景快照上跑两种主目标（distance + cost）。"""
    svc = _service(request)
    objectives: list[str] = []
    if body.distance:
        objectives.append("distance")
    if body.cost:
        objectives.append("cost")
    if not objectives:
        from logiroute.api.errors import BadRequestError
        raise BadRequestError(
            "at least one of {distance, cost} must be true",
        )
    results: dict[str, dict[str, Any]] = {}
    for obj in objectives:
        r = svc.plan(algorithm=DEFAULT_ALGORITHM, objective=obj)
        results[obj] = r.to_dict()
    return {
        "objectives": objectives,
        "results": results,
    }


__all__ = ["router"]
