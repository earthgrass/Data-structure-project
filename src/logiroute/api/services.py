"""Phase 5 —— 服务层（场景状态管理 + 调度外观）。

职责：

* 单进程持有**一个**当前激活场景（``threading.Lock`` 串行化）；
* ``/api/scenario/random`` —— 调用 Phase 4 生成器创建新场景；
* ``/api/plan`` —— 在当前场景上调用 Phase 3 ``plan_deliveries``；
* ``/api/compare`` —— 同一场景并行调用三个算法（仍走 Phase 3）；

**算法核心全部复用**：

* :mod:`logiroute.scenario_generator` —— 随机场景生成；
* :mod:`logiroute.scheduling.planner` —— 单车辆调度统一入口；
* :mod:`logiroute.scenario_generator.validator` —— 独立可行性校验。

本模块**不** 重新实现任何算法。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from logiroute.api.errors import (
    BadRequestError,
    NotFoundError,
    PlanningError,
    ScenarioGenerationError,
)
from logiroute.api.schemas import scenario_to_dict
from logiroute.config.loader import ScenarioBundle
from logiroute.scenario_generator import (
    DEFAULT_GENERATOR_CONFIG,
    GeneratorConfig,
    RandomSource,
    generate_scenario,
    validate_generated_scenario,
)
from logiroute.scheduling.planner import (
    ALLOWED_OBJECTIVES,
    plan_deliveries,
)
from logiroute.scheduling.types import ScheduleResult


ALLOWED_ALGORITHMS: tuple[str, ...] = (
    "nearest_neighbor",
    "insertion",
    "two_opt",
)


@dataclass(frozen=True)
class CurrentScenario:
    """当前激活场景的状态快照。"""

    bundle: ScenarioBundle
    backbone: list[str]
    validation: Any  # ScenarioValidationReport
    config_name: str


class ScenarioService:
    """单进程单实例的服务层（FastAPI ``app.state`` 持有）。

    线程安全：所有写操作（generate / plan）通过 ``self._lock`` 串行化。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: CurrentScenario | None = None

    # ------------------------------------------------------------------ #
    # 场景管理
    # ------------------------------------------------------------------ #

    def has_scenario(self) -> bool:
        return self._current is not None

    def get_current(self) -> CurrentScenario:
        """获取当前场景；不存在则抛 NotFoundError。"""
        if self._current is None:
            raise NotFoundError(
                "no active scenario; call POST /api/scenario/random first"
            )
        return self._current

    def generate_random_scenario(
        self,
        *,
        seed: int = 42,
        orders_count: int | None = None,
        capacity: float | None = None,
    ) -> CurrentScenario:
        """生成新场景并设为当前场景。

        参数校验：seed ∈ ℤ；orders_count / capacity 落在合理区间。
        """
        if not isinstance(seed, int):
            raise BadRequestError(
                "seed must be an integer", field="seed"
            )
        if orders_count is not None and (
            not isinstance(orders_count, int) or orders_count < 1
        ):
            raise BadRequestError(
                "orders_count must be a positive integer",
                field="orders_count",
            )
        if capacity is not None and (
            not isinstance(capacity, (int, float)) or capacity <= 0
        ):
            raise BadRequestError(
                "capacity must be a positive number", field="capacity"
            )

        overrides: dict[str, Any] = {}
        if orders_count is not None:
            overrides["orders_count"] = orders_count
        if capacity is not None:
            overrides["capacity"] = float(capacity)

        try:
            config = GeneratorConfig(**overrides) if overrides else DEFAULT_GENERATOR_CONFIG
        except (TypeError, ValueError) as exc:
            raise BadRequestError(
                f"invalid generator config: {exc}", **overrides
            ) from exc

        try:
            bundle, backbone = generate_scenario(config, seed=seed)
        except RuntimeError as exc:
            # Phase 4 generator 用 RuntimeError 表示 N 次重试仍失败
            raise ScenarioGenerationError(
                f"failed to generate a feasible scenario: {exc}",
                seed=seed,
            ) from exc

        validation = validate_generated_scenario(bundle, backbone=backbone)
        with self._lock:
            self._current = CurrentScenario(
                bundle=bundle,
                backbone=backbone,
                validation=validation,
                config_name=config.name,
            )
        return self._current

    # ------------------------------------------------------------------ #
    # 规划
    # ------------------------------------------------------------------ #

    def plan(
        self,
        algorithm: str,
        objective: str,
    ) -> ScheduleResult:
        """在当前场景上调用 :func:`plan_deliveries`。"""
        if algorithm not in ALLOWED_ALGORITHMS:
            raise BadRequestError(
                f"algorithm={algorithm!r} not in {ALLOWED_ALGORITHMS}",
                algorithm=algorithm,
            )
        if objective not in ALLOWED_OBJECTIVES:
            raise BadRequestError(
                f"objective={objective!r} not in {ALLOWED_OBJECTIVES}",
                objective=objective,
            )
        current = self.get_current()
        try:
            result = plan_deliveries(
                current.bundle, algorithm=algorithm, objective=objective
            )
        except (ValueError, RuntimeError) as exc:
            raise PlanningError(
                f"planner raised {type(exc).__name__}: {exc}",
                algorithm=algorithm,
                objective=objective,
            ) from exc
        return result

    def compare(self, objective: str) -> dict[str, ScheduleResult]:
        """同一场景上同时跑三种算法，结果聚合为字典。"""
        results: dict[str, ScheduleResult] = {}
        for algo in ALLOWED_ALGORITHMS:
            results[algo] = self.plan(algo, objective)
        return results

    # ------------------------------------------------------------------ #
    # 序列化出口
    # ------------------------------------------------------------------ #

    def current_scenario_payload(self) -> dict[str, Any]:
        current = self.get_current()
        return {
            "scenario": scenario_to_dict(current.bundle, current.backbone),
            "validation": current.validation.to_dict(),
            "config_name": current.config_name,
        }


__all__ = [
    "ALLOWED_ALGORITHMS",
    "ALLOWED_OBJECTIVES",
    "CurrentScenario",
    "ScenarioService",
]