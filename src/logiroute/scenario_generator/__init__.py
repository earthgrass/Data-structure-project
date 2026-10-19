"""Phase 4 — Random Scenario Generator / 可行优先随机场景生成器。

依据 ``AGENTS.md`` §3.6 单车辆约束 + 课程题目要求：

* **绝不** 通过"扔很多随机种子祈祷某个能跑出 20/20"来伪造可行性保证；
* **结构化** 优先：先生成强连通有向图骨架 + 一条 backbone 客户访问序列，
  所有订单共享扁平宽窗口，避免"backbone 顺序可行但 planner 走别的顺序则 miss"；
* **独立验证**：``scenario_validator.py`` 不调用 ``plan_deliveries``；
* **单一随机源**：全部随机动作走 :class:`RandomSource`，可 seed 完全复现；
* **手写 Fisher-Yates**：不调 ``random.shuffle``；
* **不** 引入第三方图算法 / 优化包。
"""

from __future__ import annotations

from logiroute.scenario_generator.backbone_builder import build_backbone_and_orders
from logiroute.scenario_generator.config_spec import (
    DEFAULT_GENERATOR_CONFIG,
    GeneratorConfig,
    GeneratorStats,
    load_generator_config,
)
from logiroute.scenario_generator.generator import generate_scenario
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.scenario_generator.road_validator import (
    RoadValidationReport, validate_road_network,
)
from logiroute.scenario_generator.validator import (
    ScenarioValidationError,
    ScenarioValidationReport,
    validate_generated_scenario,
)


__all__ = [
    "DEFAULT_GENERATOR_CONFIG",
    "GeneratorConfig",
    "GeneratorStats",
    "RandomSource",
    "ScenarioValidationError",
    "ScenarioValidationReport",
    "build_backbone_and_orders",
    "generate_scenario",
    "sample_logistics_graph",
    "validate_generated_scenario",
    "load_generator_config",
    "RoadValidationReport",
    "validate_road_network",
]
