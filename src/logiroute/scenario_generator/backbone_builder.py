"""Phase 4 — Backbone Builder。

依据 ``AGENTS.md`` §3.6 + prompt ``# 二十``/``# 二十一``：

1. 选 depot（lex-min 仓库节点）；
2. 从 ``graph`` 的全部 ``CUSTOMER`` 节点中 Fisher-Yates 取 ``orders_count`` 个；
3. Fisher-Yates 洗牌得到 backbone ordering；
4. 沿 Phase 2 Dijkstra 逐段计算到达时刻 ``arrival_i``；
5. 每个订单的时间窗围绕 ``arrival_i`` 反推：
       tw_start_i = max(0, arrival_i - early_slack)
       tw_end_i   = arrival_i + late_slack + service_time
6. 每个订单 demand 在 ``[min_demand, max_demand]`` 区间随机采样；
7. priority：``urgent_fraction`` 比例置 URGENT，剩余 NORMAL；
8. **若** ``sum(demand) > capacity`` —— 拒绝 + 返回 None，调用方重新生成。

输出：
    ``(backbone: list[str], orders: list[Order])``

约束：

* 不引入任何第三方图 / 优化库；
* 总需求 ``<= capacity``（必须满足，违反则返回 ``None``）；
* backbone 必须形成闭合回路（首尾同节点）；
* 时窗**不**会偏离 backbone 太多，**不**触发 time-window miss on the backbone
  自身（Phase 2 Dijkstra travel_time 模拟）。
"""
from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Any

from logiroute.algorithms.dijkstra import shortest_path
from logiroute.config.loader import ScenarioBundle
from logiroute.core.enums import NodeType, OrderPriority, OrderStatus
from logiroute.core.orders import Order
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.random_source import RandomSource


@dataclass
class _BackboneResult:
    backbone: list[str]
    orders: list[Order]
    total_demand: float
    rejection_reason: str | None = None


def _lex_min_warehouse(graph) -> str:
    warehouses = sorted(
        n.id for n in graph.get_all_nodes()
        if n.node_type is NodeType.WAREHOUSE
    )
    if not warehouses:
        raise RuntimeError("graph has no WAREHOUSE nodes; cannot choose depot")
    return warehouses[0]


def _format_order_id(idx: int) -> str:
    """O001 / O002 / ... / O999 / O1000 ..."""
    return f"O{idx + 1:03d}"


def _sample_orders_count_customers(
    graph, k: int, rng: RandomSource
) -> list[str]:
    """Fisher-Yates 洗牌全部客户节点 ID 后取前 ``k`` 个。"""
    customer_ids = sorted(
        n.id for n in graph.get_all_nodes()
        if n.node_type is NodeType.CUSTOMER
    )
    if len(customer_ids) < k:
        raise RuntimeError(
            f"graph has only {len(customer_ids)} customers but "
            f"config requires {k} orders"
        )
    arr = list(customer_ids)
    rng.shuffle(arr)
    return arr[:k]


def _choose_backbone_ordering(
    customer_ids: list[str], rng: RandomSource
) -> list[str]:
    """对选出的 ``k`` 个客户做一次 Fisher-Yates 洗牌 —— backbone ordering。

    Backbone ordering 必须**不** 是原数组顺序（避免出现总是字典序访问）。
    """
    arr = list(customer_ids)
    rng.shuffle(arr)
    return arr


def _per_leg_drive_time(graph, src: str, tgt: str) -> float:
    """单 leg 的实际行驶时间；如果 src==tgt 返回 0。"""
    if src == tgt:
        return 0.0
    leg = shortest_path(graph, src, tgt, "travel_time")
    if not leg.reachable:
        raise RuntimeError(
            f"backbone leg {src} -> {tgt} is unreachable; "
            "graph sampler must guarantee strong connectivity"
        )
    return leg.total_weight


def build_backbone_and_orders(
    graph,
    config: GeneratorConfig,
    rng: RandomSource,
    depot_id: str | None = None,
) -> tuple[list[str], list[Order]] | None:
    """构造 backbone 序列与匹配订单列表。

    Time-window 策略：为了让任意访问顺序（NN / CFI / 2-opt）都能在单
    车辆闭环内完成，**所有订单共享一个扁平宽窗口** —— 起点
    ``initial_time - 30``，终点 = backbone 沿 Phase 2 Dijkstra 的实际返回
    时刻 + ``config.window_total_extra`` 额外余量（容纳启发式偏移 backbone
    的访问顺序）。

    Returns:
        ``(backbone, orders)`` 或 ``None``（拒绝 —— capacity 不允许）。
    """
    if depot_id is None:
        depot_id = _lex_min_warehouse(graph)

    customer_ids = _sample_orders_count_customers(
        graph, config.orders_count, rng
    )
    backbone_inner = _choose_backbone_ordering(customer_ids, rng)
    backbone = [depot_id] + backbone_inner + [depot_id]

    service_time = config.service_time
    initial_time = config.initial_time

    # 沿 backbone 计算每段 drive_time + service，累积得到最后返回时间
    cur_t = initial_time
    for s, t in zip(backbone[:-1], backbone[1:]):
        cur_t = cur_t + _per_leg_drive_time(graph, s, t)
        cur_t = cur_t + service_time
    last_return_time = cur_t

    tw_start = max(0.0, initial_time - 30.0)
    tw_end = last_return_time + config.window_total_extra
    tw_start = round(tw_start, 1)
    tw_end = round(tw_end, 1)

    # 生成 orders
    orders: list[Order] = []
    for idx, order_dest in enumerate(backbone_inner):
        demand = round(
            rng.uniform(config.min_demand, config.max_demand), 2
        )
        if rng.uniform(0.0, 1.0) < config.urgent_fraction:
            priority = OrderPriority.URGENT
        else:
            priority = OrderPriority.NORMAL
        orders.append(
            Order(
                id=_format_order_id(idx),
                destination_id=order_dest,
                demand=demand,
                time_window_start=tw_start,
                time_window_end=tw_end,
                priority=priority,
                status=OrderStatus.PENDING,
            )
        )

    total_demand = sum(o.demand for o in orders)
    if total_demand > config.capacity + 1e-9:
        return None

    return backbone, orders


__all__ = ["build_backbone_and_orders"]
