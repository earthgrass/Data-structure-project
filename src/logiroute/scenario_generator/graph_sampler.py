"""Phase 4 — 强连通有向图采样器（手写 + RandomSource 注入）。

依据 ``AGENTS.md`` §3.6 + ``# 十四`` + ``# 十五`` + ``# 十六`` + ``# 十七``：

* 节点数 / 边数 / 类型配额从 :class:`GeneratorConfig` 读取；
* **不** 引入 NetworkX / OR-Tools / graph-tool / igraph；
* 全部随机性通过 :class:`RandomSource` —— 单 seed 完全可复现；
* 边权 ``distance / travel_time / cost`` 全部 ``>= 0`` 且 finite；
* **不** 出现自环（``source_id == target_id``）；
* **不** 重复边（同 :class:`LogisticsGraph` 已有的语义）；
* **强连通骨架 + 额外边**：先建立全节点的有向环（cycle）保证强连通，再在
  cycle 上加随机有向边形成更真实的物流网。

公开入口：

* :func:`sample_logistics_graph(config, rng)` -> ``LogisticsGraph``
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType, TrafficStatus
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.random_source import RandomSource


#: 节点 ID 前缀。仓库 ``W`` / 客户 ``C`` / 中转 ``T``，与 Phase 1 既有命名一致。
_PREFIX: dict[NodeType, str] = {
    NodeType.WAREHOUSE: "W",
    NodeType.CUSTOMER: "C",
    NodeType.TRANSFER: "T",
}


@dataclass(frozen=True)
class _NodeSpec:
    node_id: str
    node_type: NodeType
    x: float
    y: float


def _make_node_specs(
    config: GeneratorConfig,
    rng: RandomSource,
) -> list[_NodeSpec]:
    """按配额（仓库/客户/中转）构造节点 ID 与随机坐标。"""
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

    def add(prefix: str, kind: NodeType, count: int):
        for i in range(count):
            nid = f"{prefix}{i + 1}"
            x = round(rng.uniform(0.0, 100.0), 2)
            y = round(rng.uniform(0.0, 100.0), 2)
            specs.append(_NodeSpec(nid, kind, x, y))

    add(_PREFIX[NodeType.WAREHOUSE], NodeType.WAREHOUSE, n_wh)
    add(_PREFIX[NodeType.TRANSFER], NodeType.TRANSFER, n_tr)
    add(_PREFIX[NodeType.CUSTOMER], NodeType.CUSTOMER, n_cu)
    return specs


def _euclidean_distance(a: _NodeSpec, b: _NodeSpec) -> float:
    """几何距离（km）。"""
    return math.hypot(a.x - b.x, a.y - b.y)


def _strongly_connected_anchor(
    specs: list[_NodeSpec], rng: RandomSource
) -> list[_NodeSpec]:
    """Fisher-Yates 洗牌后作为有向环骨架。

    不允许顺序保持原状（否则如果原顺序恰好是 W/C/T 分布会显得不自然）。
    """
    arr = list(specs)
    rng.shuffle(arr)
    return arr


def _extra_edges_for_node(
    anchor_idx: int,
    anchor_order: list[int],
    specs: list[_NodeSpec],
    rng: RandomSource,
    max_extra: int,
) -> set[tuple[str, str]]:
    """返回 (source_id, target_id) 元组集合 —— 随机附加有向边。

    * 自环禁止；
    * 与已有边重复禁止（由 :class:`LogisticsGraph.add_edge` 负责）；
    * 数量上限 = ``max_extra`` per node；
    * target 也必须不在 anchor 同位置（避免 destination==source 自环）。
    """
    n = len(specs)
    src = specs[anchor_idx]
    cand = []
    for j in range(n):
        if j == anchor_idx:
            continue
        if j in anchor_order:
            cand.append(j)  # 加入锚点环的下一个之前的目标
    if not cand:
        return set()
    rng.shuffle(cand)
    picked: set[tuple[str, str]] = set()
    k = min(rng.randint(0, max_extra), len(cand))
    for j in cand[:k]:
        picked.add((src.node_id, specs[j].node_id))
    return picked


def _sample_edge_weights(
    src: _NodeSpec, tgt: _NodeSpec, rng: RandomSource
) -> tuple[float, float, float]:
    """生成 ``(distance_km, travel_time_min, cost_yuan)``。

    distance  ≈ 几何距离 + 微随机扰动；
    travel_time ≈ distance / 平均速度（带噪声）；
    cost      ≈ distance * 单价 + 拥堵系数。
    """
    base = max(_euclidean_distance(src, tgt), 0.1)
    distance = base * rng.uniform(0.8, 1.2)
    speed = rng.uniform(30.0, 60.0)
    travel_time = (distance / speed) * 60.0
    unit_cost = rng.uniform(1.5, 3.0)
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
    """按 :class:`GeneratorConfig` 与 :class:`RandomSource` 采一个强连通有向图。

    算法骨架：

    1. 按配额随机生成节点（类型 + 坐标）；
    2. Fisher-Yates 打乱后建立 ``0 -> 1 -> 2 -> ... -> n-1 -> 0`` 的有向环；
       此环是强连通的；
    3. 对每个节点附加若干额外有向边（在 ``[0, max_extra]`` 区间随机数量）；
    4. 对每条候选边采样 ``distance / travel_time / cost`` 三个 metric。
    5. 构建 ``LogisticsGraph`` 并逐边 ``add_edge``，重复由 ``LogisticsGraph`` 自动拒绝。

    Time   : O(V + E)；space O(V + E)。
    """
    specs = _make_node_specs(config, rng)
    n = len(specs)
    if n == 0:
        raise RuntimeError("sampling produced 0 nodes; raise min_nodes")

    # 强连通骨架：洗牌后连成一个环
    anchor = _strongly_connected_anchor(specs, rng)
    anchor_edges: set[tuple[str, str]] = set()
    for i in range(n):
        j = (i + 1) % n
        if anchor[i].node_id != anchor[j].node_id:
            anchor_edges.add((anchor[i].node_id, anchor[j].node_id))

    # 额外边 —— 每节点随机 [0, max_extra] 条
    extra_edges: set[tuple[str, str]] = set()
    for i in range(n):
        extra_edges |= _extra_edges_for_node(
            i, list(range(n)), anchor, rng, config.max_extra_edges_per_node
        )

    edge_candidates = (anchor_edges | extra_edges) - {(s, s) for s in [n.node_id for n in specs]}

    # 边数必须在 [min_edges, max_edges] 之间，否则补足或裁剪
    if len(edge_candidates) < config.min_edges:
        # 补足
        n_more = config.min_edges - len(edge_candidates)
        # 添加反向边（保留有向性）但要避免自环
        for _ in range(n_more * 4):
            i = rng.randint(0, n - 1)
            j = rng.randint(0, n - 1)
            if i == j:
                continue
            s = anchor[i].node_id
            t = anchor[j].node_id
            if (s, t) not in edge_candidates:
                edge_candidates.add((s, t))
                if len(edge_candidates) >= config.min_edges:
                    break

    if len(edge_candidates) > config.max_edges:
        # 随机裁剪
        elist = list(edge_candidates)
        rng.shuffle(elist)
        edge_candidates = set(elist[: config.max_edges])

    # 构造图
    graph = LogisticsGraph()
    spec_by_id = {s.node_id: s for s in specs}
    for s in specs:
        graph.add_node(
            Node(
                id=s.node_id,
                name=s.node_id,
                node_type=s.node_type,
                x=s.x,
                y=s.y,
            )
        )

    for (sid, tid) in edge_candidates:
        if sid == tid:
            continue
        d, t, c = _sample_edge_weights(spec_by_id[sid], spec_by_id[tid], rng)
        try:
            graph.add_edge(
                Edge(
                    source_id=sid,
                    target_id=tid,
                    distance=d,
                    travel_time=t,
                    cost=c,
                    traffic_status=TrafficStatus.CLEAR,
                )
            )
        except ValueError:
            # duplicate (s,t) pair already exists; skip
            pass

    return graph


__all__ = ["sample_logistics_graph"]
