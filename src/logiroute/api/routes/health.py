"""``GET /api/health`` —— 健康检查。

返回：

* ``status`` — 固定 ``"ok"``；
* ``version`` — 字符串标签（前端展示用）；
* ``test_count`` — 已通过的单元测试数（写死在模块顶部，**需随 Phase
  演进而手动更新**；这是为避免给后端引入 unittest 自调用运行时成本）。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    test_count: int


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """健康检查端点；前端在加载时调用以确认后端可达。"""
    return HealthResponse(status="ok", version="phase5", test_count=442)


__all__ = ["router"]