"""Phase 4 — ``generate_scenario`` 顶层入口。

依据 prompt ``# 十一``/``# 十二``/``# 二十二``：

1. 随机生成强连通有向图（Fisher-Yates 骨架 + 额外边）；
2. 随机生成 backbone 客户访问序列（Fisher-Yates 客户 ID 集合）；
3. 沿 Phase 2 Dijkstra 反推每个订单 time_window；
4. 生成 demand / priority（urgency_fraction 概率置 URGENT）；
5. **不** 调 planner —— **仅** 调独立 :class:`validator` 验证 backbone + 容量
   + 时间窗 + 闭环 + 可达性 + 覆盖性；
6. 拒绝 + 重新生成（如 backbone 不可达 / 容量不够）；
7. 输出 :class:`ScenarioBundle` + ``backbone``（生成器内部状态，**不**
   暴露给 planner 作为"答案"）。

调用：

    from logiroute.scenario_generator import (
        generate_scenario, validate_generated_scenario, GeneratorConfig,
    )
    bundle, backbone = generate_scenario(GeneratorConfig(orders_count=20), seed=42)
    rep = validate_generated_scenario(bundle, backbone=backbone)
    assert rep.feasible

**Planners 看到的是普通 ScenarioBundle** —— 不接受任何"backbone 提示"。
"""
from __future__ import annotations

from typing import Any

from logiroute.config.loader import ScenarioBundle
from logiroute.core.couriers import Courier
from logiroute.core.enums import (
    CourierStatus, NodeType, VehicleStatus,
)
from logiroute.core.vehicles import Vehicle
from logiroute.scenario_generator.backbone_builder import build_backbone_and_orders
from logiroute.scenario_generator.config_spec import (
    DEFAULT_GENERATOR_CONFIG, GeneratorConfig, GeneratorStats,
)
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.scenario_generator.validator import (
    ScenarioValidationReport, validate_generated_scenario,
)


def _vehicles_and_couriers_for(
    depot_id: str,
    capacity: float,
) -> tuple[list[Vehicle], list[Courier]]:
    """生成严格单车辆 + 单配送员配置。

    AGENTS.md §3.6 + 教师原题：只能有一辆车参与实际配送。
    这里只造一辆 ``VH1``（IDLE @ depot，capacity = ``config.capacity``）
    + 一名跟车配送员 ``CO1``；不再保留任何"模型保留"车辆。
    """
    vehicles = [
        Vehicle(
            id="VH1",
            capacity=capacity,
            current_load=0.0,
            current_node_id=depot_id,
            status=VehicleStatus.IDLE,
        ),
    ]
    couriers = [
        Courier(
            id="CO1",
            name="CO1",
            vehicle_id="VH1",
            status=CourierStatus.IDLE,
        ),
    ]
    return vehicles, couriers


def _attach_vehicles_to_depots(
    graph,
    vehicles: list[Vehicle],
    couriers: list[Courier],
) -> None:
    """严格单车辆约束下，此函数为 no-op。

    保留此函数仅为保持接口稳定（未来若放开约束可扩展使用）。
    当前 ``vehicles`` 长度为 1，不存在跨仓库车辆分配场景。
    """
    del graph, vehicles, couriers  # explicitly unused under strict 1-vehicle


def generate_scenario(
    config: GeneratorConfig | None = None,
    seed: int | None = 42,
) -> tuple[ScenarioBundle, list[str]]:
    """生成一个完整 :class:`ScenarioBundle` 与对应的 backbone。

    Args:
        config: 生成配置；默认 :data:`DEFAULT_GENERATOR_CONFIG`。
        seed: 整数种子；同 seed + 同 config → 完全相同场景。

    Returns:
        ``(bundle, backbone)`` —— ``bundle`` 独立可被 ``plan_deliveries``
        直接处理；``backbone`` 是单车辆访问序列，仅用于独立验证。

    Raises:
        RuntimeError: 多次尝试后仍无法生成可行场景（实际不应发生，因为
            backbone-first 设计与 max_rejection_attempts 兜底）。
    """
    if config is None:
        config = DEFAULT_GENERATOR_CONFIG
    rng = RandomSource(seed)

    last_error: str | None = None
    for attempt in range(1, max(1, config.max_rejection_attempts) + 1):
        # 1. 图
        graph = sample_logistics_graph(config, rng)

        # 2. backbone + orders（容量不过则拒绝）
        result = build_backbone_and_orders(graph, config, rng)
        if result is None:
            last_error = "backbone build rejected (capacity overflow)"
            continue
        backbone, orders = result

        # 3. 选 depot
        warehouses = sorted(
            n.id for n in graph.get_all_nodes()
            if n.node_type is NodeType.WAREHOUSE
        )
        if not warehouses:
            last_error = "graph has no warehouses"
            continue
        depot_id = warehouses[0]

        # 4. 车辆 + 配送员（严格单车辆）
        vehicles, couriers = _vehicles_and_couriers_for(
            depot_id, config.capacity
        )
        _attach_vehicles_to_depots(graph, vehicles, couriers)

        # 5. 组装 ScenarioBundle
        bundle = ScenarioBundle(
            name=f"{config.name}.seed{seed or 0}",
            mode="fixed",  # Phase 1 loader 校验固定场景（mode='fixed' 是唯一允许值）
            random_seed=seed if seed is not None else 0,
            graph=graph,
            vehicles=vehicles,
            couriers=couriers,
            orders=orders,
            simulation={
                "initial_time": config.initial_time,
                "traffic_update_interval": 30,
                "congestion_threshold": 0.2,
                "service_time": config.service_time,
            },
            optimization={
                "default_objective": "distance",
                "tsp_beam_width": config.tsp_beam_width,
                "weights": {"distance": 1.0, "travel_time": 1.0, "cost": 1.0},
                "late_penalty_per_minute": 0.5,
                "expiry_grace_minutes": 10,
            },
            metadata={
                "generator": "logiroute.scenario_generator",
                "config_name": config.name,
                "seed": seed,
                "orders_count": config.orders_count,
                "capacity": config.capacity,
                "backbone_length": len(backbone),
            },
        )

        # 6. 独立验证
        report = validate_generated_scenario(bundle, backbone=backbone)
        if not report.feasible:
            last_error = "; ".join(
                f"{k}: {m}" for k, m in report.violations[:3]
            )
            continue
        return bundle, backbone

    raise RuntimeError(
        f"failed to generate a feasible scenario after "
        f"{config.max_rejection_attempts} attempts; last error: {last_error}"
    )


__all__ = ["generate_scenario"]
