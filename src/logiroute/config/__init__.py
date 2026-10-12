"""配置管理模块。

将 JSON 场景配置加载并校验为强类型的
:class:`LogisticsGraph` / :class:`Vehicle` / :class:`Courier` / :class:`Order` 集合。

Phase 1 范围：

* 仅支持 ``mode = "fixed"`` 的固定场景。
* 验证：节点 / 边的下界指标、ID 唯一、ID 引用、权重合法、图弱连通性、
  至少存在一个仓库、订单 / 车辆 / 配送员的字段合法。
* **不**实现随机场景生成、动态仿真、路径优化计算。

仅依赖 Python 标准库；不引入第三方库。
"""

from logiroute.config.loader import (
    ConfigError,
    ScenarioBundle,
    load_scenario,
    load_scenario_from_dict,
    load_scenario_from_file,
)

__all__ = [
    "ConfigError",
    "ScenarioBundle",
    "load_scenario",
    "load_scenario_from_dict",
    "load_scenario_from_file",
]
