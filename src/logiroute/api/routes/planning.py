"""``/api/plan`` / ``/api/compare`` —— 单算法与三算法比较。

* ``POST /api/plan`` —— 在当前场景上跑指定算法；
* ``POST /api/compare`` —— 在当前场景上跑全部三种算法并返回对照表。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from logiroute.api.services import ALLOWED_ALGORITHMS, ScenarioService


router = APIRouter(prefix="/api", tags=["planning"])


class PlanRequest(BaseModel):
    algorithm: str = Field(..., description="nearest_neighbor / insertion / two_opt")
    objective: str = Field(default="distance", description="distance / cost")


class CompareRequest(BaseModel):
    objective: str = Field(default="distance", description="distance / cost")
    algorithms: list[str] | None = Field(
        default=None,
        description="要比较的算法列表；None 表示默认三种全部。",
    )


def _service(request: Request) -> ScenarioService:
    svc = getattr(request.app.state, "scenario_service", None)
    if svc is None:
        raise RuntimeError("ScenarioService missing from app.state")
    return svc


@router.post("/plan")
def post_plan(body: PlanRequest, request: Request) -> dict[str, Any]:
    """在当前场景上跑指定算法；返回完整 :class:`ScheduleResult` dict。"""
    svc = _service(request)
    result = svc.plan(algorithm=body.algorithm, objective=body.objective)
    return {"result": result.to_dict()}


@router.post("/compare")
def post_compare(body: CompareRequest, request: Request) -> dict[str, Any]:
    """在同一场景上跑三种算法；返回对照 dict。"""
    svc = _service(request)
    algos = body.algorithms or list(ALLOWED_ALGORITHMS)
    results: dict[str, dict[str, Any]] = {}
    for algo in algos:
        result = svc.plan(algorithm=algo, objective=body.objective)
        results[algo] = result.to_dict()
    return {
        "objective": body.objective,
        "results": results,
    }


__all__ = ["router"]