"""Phase 5 —— FastAPI 路由集合。"""
from __future__ import annotations

from logiroute.api.routes.health import router as health_router
from logiroute.api.routes.planning import router as planning_router
from logiroute.api.routes.scenarios import router as scenarios_router

__all__ = ["health_router", "planning_router", "scenarios_router"]