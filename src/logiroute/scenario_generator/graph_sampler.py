"""V2 Phase 1: physical roads over a protected bidirectional spanning tree."""
from __future__ import annotations

import math
from dataclasses import dataclass

from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType, TrafficStatus
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.random_source import RandomSource


@dataclass(frozen=True)
class _NodeSpec:
    node_id: str
    node_type: NodeType
    x: float
    y: float
    lng: float
    lat: float


def _make_node_specs(
    config: GeneratorConfig,
    rng: RandomSource,
) -> list[_NodeSpec]:
    """按配额（仓库/客户/中转）构造节点 ID 与随机坐标。

    坐标系统：
        * ``x`` / ``y`` —— 内部算法用抽象坐标（[0, 100]），与 Phase 1 一致；
        * ``lng`` / ``lat`` —— Phase 5 Dashboard 用的可视化坐标，落在北京 16 区
          边界框 [115.7°E, 39.5°N, 117.2°E, 40.7°N] 内，由 ``RandomSource``
          确定性采样，**不**前端重新随机。
    """
    # 在 [min, max] 区间中均匀挑一个整数
    n_total = rng.randint(config.min_nodes, config.max_nodes)

    # 至少有 min_* 个；剩余按比例分配，但保证上限不超过 n_total
    n_wh = config.min_warehouses
    n_cu = config.min_customers
    n_tr = config.min_transfers
    remaining = n_total - (n_wh + n_cu + n_tr)

    # 把剩余按 (min_warehouses, min_customers, min_transfers) 比例分摊
    # 给 warehouse / transfer / customer，避免某一方"溢出".
    # 用户配额是下限，所以先取下限，剩余按客户 → 中转 → 仓库顺序吸收。
    extra_to_customer = remaining
    # 增加上限检查：剩余再分给客户（也可以保持简单一律给客户）
    n_cu += extra_to_customer

    # 坐标范围：[0, 100]，与 Phase 1 场景规模相当（米 → km）
    specs: list[_NodeSpec] = []

    # 北京 16 区边界框（WGS84）
    BJ_LNG_MIN, BJ_LNG_MAX = config.longitude_range
    BJ_LAT_MIN, BJ_LAT_MAX = config.latitude_range

    def add(prefix: str, kind: NodeType, count: int) -> None:
        for i in range(count):
            nid = f"{prefix}{i + 1}"
            x = round(rng.uniform(*config.coordinate_range), 2)
            y = round(rng.uniform(*config.coordinate_range), 2)
            lng = round(rng.uniform(BJ_LNG_MIN, BJ_LNG_MAX), 5)
            lat = round(rng.uniform(BJ_LAT_MIN, BJ_LAT_MAX), 5)
            specs.append(_NodeSpec(nid, kind, x, y, lng, lat))

    add(config.node_prefixes["warehouse"], NodeType.WAREHOUSE, n_wh)
    add(config.node_prefixes["transfer"], NodeType.TRANSFER, n_tr)
    add(config.node_prefixes["customer"], NodeType.CUSTOMER, n_cu)
    return specs


def _euclidean_distance(a: _NodeSpec, b: _NodeSpec) -> float:
    """几何距离（km）。"""
    return math.hypot(a.x - b.x, a.y - b.y)


def _sample_edge_weights(
    src: _NodeSpec, tgt: _NodeSpec, rng: RandomSource, config: GeneratorConfig
) -> tuple[float, float, float]:
    """生成 ``(distance_km, travel_time_min, cost_yuan)``。

    distance  ≈ 几何距离 + 微随机扰动；
    travel_time ≈ distance / 平均速度（带噪声）；
    cost      ≈ distance * 单价 + 拥堵系数。
    """
    base = max(_euclidean_distance(src, tgt), config.minimum_distance)
    distance = base * rng.uniform(*config.distance_factor_range)
    speed = rng.uniform(*config.speed_range)
    travel_time = (distance / speed) * 60.0
    unit_cost = rng.uniform(*config.unit_cost_range)
    cost = distance * unit_cost
    return (
        round(distance, 3),
        round(travel_time, 3),
        round(cost, 3),
    )


def sample_logistics_graph(
    config: GeneratorConfig,
    rng: RandomSource,
) -> LogisticsGraph:
    """Build a bidirectional tree, then sample unordered pairs without replacement.

    Sets are used for membership only. All RNG consumption follows list order.
    Quotas and directed budgets are resolved before constructing any edge.
    Time O(V² + E); Space O(V² + E), including candidate pairs and validation.
    """
    specs = _make_node_specs(config, rng)
    n = len(specs)
    physical, bidirectional = config.road_quota(n)
    order = list(range(n))
    rng.shuffle(order)
    tree: list[tuple[int, int]] = []
    tree_pairs: set[tuple[int, int]] = set()
    for pos in range(1, n):
        left, right = order[pos], order[rng.randint(0, pos - 1)]
        pair = (left, right) if left < right else (right, left)
        tree.append(pair)
        tree_pairs.add(pair)
    candidates = [
        (left, right) for left in range(n) for right in range(left + 1, n)
        if (left, right) not in tree_pairs
    ]
    rng.shuffle(candidates)
    roads = tree + candidates[:physical - len(tree)]
    graph = LogisticsGraph()
    for spec in specs:
        graph.add_node(Node(
            id=spec.node_id, name=spec.node_id, node_type=spec.node_type,
            x=spec.x, y=spec.y,
            metadata={"lng": spec.lng, "lat": spec.lat,
                      "viz_source": "beijing_schematic"},
        ))
    for index, (left, right) in enumerate(roads):
        src, dst = specs[left], specs[right]
        a, b = src.node_id, dst.node_id
        if a > b:
            a, b = b, a
        road_id = f"road:{a}:{b}"
        two_way = index < bidirectional
        directions = [(src, dst), (dst, src)] if two_way else (
            [(src, dst)] if rng.randint(0, 1) == 0 else [(dst, src)]
        )
        for source, target in directions:
            distance, travel_time, cost = _sample_edge_weights(source, target, rng, config)
            graph.add_edge(Edge(
                source_id=source.node_id, target_id=target.node_id,
                distance=distance, travel_time=travel_time, cost=cost,
                traffic_status=TrafficStatus.CLEAR,
                metadata={"road_id": road_id,
                          "edge_id": f"{road_id}:{source.node_id}>{target.node_id}",
                          "bidirectional": two_way, "skeleton": index < n - 1},
            ))
    from logiroute.scenario_generator.road_validator import validate_road_network
    report = validate_road_network(graph, config)
    if not report.valid:
        raise RuntimeError(f"generated road network failed validation: {report.violations}")
    return graph


__all__ = ["sample_logistics_graph"]
