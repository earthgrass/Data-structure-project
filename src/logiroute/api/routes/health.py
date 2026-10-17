"""``GET /api/health`` —— 健康检查。

返回：

* ``status`` — 固定 ``"ok"``；
* ``version`` — 字符串标签（前端展示用）；
* ``objectives`` — 支持的主目标列表。

Phase 5 规格 §六 — 不再返回硬编码 test_count（避免与实际测试数量漂移）；
健康检查只证明服务可达，不证明业务正确性。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from logiroute.api.services import ALLOWED_OBJECTIVES


router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    objectives: list[str]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """健康检查端点；前端在加载时调用以确认后端可达。"""
    return HealthResponse(
        status="ok", version="phase5", objectives=list(ALLOWED_OBJECTIVES),
    )


__all__ = ["router"]