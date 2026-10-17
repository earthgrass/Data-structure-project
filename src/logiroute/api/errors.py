"""Phase 5 —— FastAPI 应用的自定义异常与错误响应。

设计：

* API 层异常统一从 :class:`APIError` 派生；
* HTTP 状态码在 :func:`http_status_for` 中集中映射；
* 错误响应体固定形如 ``{"error": {"kind": "...", "message": "..."}}``，
  便于前端统一处理。
"""
from __future__ import annotations

from typing import Any


class APIError(Exception):
    """API 层异常的基类。所有 API 抛出的异常必须继承此类。"""

    kind: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details)

    def to_response(self) -> dict[str, Any]:
        """转换为对外 JSON 错误体。"""
        body: dict[str, Any] = {
            "error": {"kind": self.kind, "message": self.message}
        }
        if self.details:
            body["error"]["details"] = self.details
        return body


class BadRequestError(APIError):
    kind = "bad_request"
    status_code = 400


class NotFoundError(APIError):
    kind = "not_found"
    status_code = 404


class ConflictError(APIError):
    kind = "conflict"
    status_code = 409


class ScenarioGenerationError(APIError):
    kind = "scenario_generation_failed"
    status_code = 500


class PlanningError(APIError):
    kind = "planning_failed"
    status_code = 500


__all__ = [
    "APIError",
    "BadRequestError",
    "ConflictError",
    "NotFoundError",
    "PlanningError",
    "ScenarioGenerationError",
]