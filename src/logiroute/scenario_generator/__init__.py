"""Phase 4 — Random Scenario Generator / 可行优先随机场景生成器。

依据 ``AGENTS.md`` §3.6 单车辆约束 + 课程题目要求：

* **绝不** 通过"扔很多随机种子祈祷某个能跑出 20/20"来伪造可行性保证；
* **结构化** 优先：先生成强连通有向图骨架 + 一条 backbone 客户访问序列，
  沿 Phase 2 Dijkstra 反推每个订单的 ``time_window``；
* **独立验证**：``scenario_validator.py`` 不调用 ``plan_deliveries``；
* **单一随机源**：全部随机动作走 :class:`RandomSource`，可 seed 完全复现；
* **手写 Fisher-Yates**：不调 ``random.shuffle``；
* **不** 引入第三方图算法 / 优化包。

公开入口：

* :func:`generate_scenario(config, seed=None)` — 拉起一个完整场景；
* :data:`DEFAULT_GENERATOR_CONFIG` — 默认配置基线（被 :doc:`AGENTS`
  §3.6 固定场景最低规模约束影响）。

子模块：

* :mod:`.random_source`     — RandomSource + 手写 Fisher-Yates
* :mod:`.config_spec`       — GeneratorConfig / GeneratorStats
* :mod:`.graph_sampler`     — 强连通有向图采样
* :mod:`.backbone_builder`  — backbone 客户序列 + time_window 反推
* :mod:`.validator`         — 独立场景验证器
* :mod:`.generator`         — 顶层 generate_scenario 入口
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_GENERATOR_CONFIG",
    "GeneratorConfig",
    "GeneratorStats",
    "RandomSource",
    "ScenarioValidationError",
    "ScenarioValidationReport",
    "generate_scenario",
    "validate_generated_scenario",
]


def __getattr__(name):
    """Lazy re-exports — 子模块未完工时不阻塞包导入。"""
    if name in {"RandomSource"}:
        from logiroute.scenario_generator.random_source import RandomSource
        return RandomSource
    if name in {"DEFAULT_GENERATOR_CONFIG", "GeneratorConfig", "GeneratorStats"}:
        from logiroute.scenario_generator import config_spec as _cs
        return getattr(_cs, name)
    if name in {"ScenarioValidationError", "ScenarioValidationReport",
                "validate_generated_scenario"}:
        from logiroute.scenario_generator import validator as _v
        return getattr(_v, name)
    if name == "generate_scenario":
        from logiroute.scenario_generator.generator import generate_scenario as _g
        return _g
    raise AttributeError(f"module 'logiroute.scenario_generator' has no attribute {name!r}")
