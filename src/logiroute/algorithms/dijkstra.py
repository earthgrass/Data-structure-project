"""Dijkstra 单源最短路算法 —— Phase 2 核心算法。

**禁止**使用 ``heapq`` / NetworkX / SciPy / 任何第三方 shortest_path 实现。
本模块完全基于：

* Phase 1 提供的 :class:`logiroute.graph.logistics_graph.LogisticsGraph` 邻接表
* Phase 2 自主实现的索引式二叉最小堆 :class:`logiroute.algorithms.heap.MinHeap`

核心数据结构
------------

* ``dist: dict[node_id, float]`` —— 当前从 ``source`` 到各节点的最短已知距离。
* ``prev: dict[node_id, node_id | None]`` —— 最短路径树上每个节点的前驱。
* ``settled: set[node_id]`` —— 已确定最短距离的节点。
* :class:`MinHeap` —— 待处理的 (node_id, dist) 候选集合。

算法骨架
--------

```
dist[source] = 0
其余 dist = +inf
push(source, 0) into heap
while heap not empty:
    u, du = heap.pop_min()
    if u in settled: continue     # 懒删除：可能多次入堆，只取第一次最小
    settled.add(u)
    if du > dist[u]: continue      # 该次弹出已被更新的更小值覆盖
    for edge in graph.get_neighbors(u):
        v = edge.target_id
        if v in settled: continue
        new_dist = du + edge.weight(metric)
        if new_dist < dist[v]:
            dist[v] = new_dist
            prev[v] = u
            heap.decrease_key(v, new_dist)  # 首次为 push，已存在则 decrease
```

正确性说明
----------

**贪心不变量**：当节点 ``u`` 被从堆中弹出并加入 ``settled`` 时，``dist[u]``
即 ``source → u`` 的最终最短距离。

证明概要：

1. 初始时 ``dist[source] = 0`` 显然正确，其余为 +inf；
2. 任何已确定边的非负权重保证：若 ``u`` 是堆中当前最小 dist，则任何
   经过未确定节点 ``w`` 的 ``source → u → w`` 路径至少不短于
   ``dist[u]``，因为 ``dist[u]`` 已经是堆中最小；
3. 因此 ``u`` 不可能通过任何未确定节点获得更短路径，``dist[u]`` 即
   最终最短距离，可安全移入 ``settled``。

**关于"懒删除"**：同一节点可能多次进入堆（``decrease_key`` 不可逆）。
Dijkstra 的不变量是"第一次从堆中弹出的最小值"为最终值；后续重复条目
应当被忽略（``if u in settled: continue``）。

**关于零权边**：Dijkstra 支持零权边。零权边对应"经过 ``v`` 的路径长度
等于 ``dist[u]``"，可能产生 tie-break 顺序差异；本实现按 ``MinHeap`` 的
字典序确定性规则处理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Any

from logiroute.algorithms.heap import MinHeap
from logiroute.core.enums import TrafficStatus
from logiroute.graph.logistics_graph import LogisticsGraph


SUPPORTED_METRICS = ("distance", "travel_time", "cost")


# ---------------------------------------------------------------------------
#  异常
# ---------------------------------------------------------------------------


class DijkstraError(Exception):
    """Dijkstra 计算错误。"""


class InvalidMetricError(DijkstraError):
    """``metric`` 不在支持集合内。"""


class UnknownNodeError(DijkstraError):
    """源 / 目标节点不在图中。"""


# ---------------------------------------------------------------------------
#  结果封装
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepRecord:
    """教学追踪：单轮松弛的关键事件。

    属性语义详见 :func:`dijkstra_with_trace`。
    """

    round: int                                # 轮次（从 1 开始）
    popped_node: str                          # 本轮从堆中弹出的节点
    popped_distance: float                    # 弹出时该节点的暂定距离
    settled_snapshot: tuple[str, ...]         # 本轮结束后已确定集合（按字典序）
    relaxations: tuple[dict[str, Any], ...]   # 本轮所有成功松弛的边详情


@dataclass(frozen=True)
class TraceResult:
    """Dijkstra 的完整运行轨迹（不可变快照）。"""

    source: str
    metric: str
    dist: dict[str, float]
    prev: dict[str, str | None]
    settled: tuple[str, ...]                # 节点按被确定的顺序
    steps: tuple[StepRecord, ...]
    relaxed_edges: int                      # 成功松弛的边数
    heap_pops: int                          # 堆 pop 次数（含 lazy-skip）


@dataclass(frozen=True)
class PathResult:
    """两点最优路径结果。"""

    source: str
    target: str
    metric: str
    path: tuple[str, ...]                   # 节点 ID 列表，按行驶方向；若不可达为空
    total_weight: float                     # 该 metric 下的路径总权重；不可达 = +inf
    reachable: bool
    # 同一路径在另外两个 metric 下的总权重（便于 Phase 2 末段的多策略对比）。
    cross_metrics: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
#  内部：邻接表迭代
# ---------------------------------------------------------------------------


def _weight_of(edge: Any, metric: str) -> float:
    """从 :class:`Edge` 读取指定 metric 的权重。

    优先调用 ``edge.weight(metric)``；若 Edge 不支持该方法，回退到直接属性。
    """
    w = getattr(edge, "weight", None)
    if callable(w):
        return float(w(metric))
    # 兼容 fallback（Phase 1 已有标准实现，但保留容错）
    if metric == "distance":
        return float(edge.distance)
    if metric == "travel_time":
        return float(edge.travel_time)
    if metric == "cost":
        return float(edge.cost)
    raise InvalidMetricError(f"unsupported metric: {metric!r}")


# ---------------------------------------------------------------------------
#  主体 1：单源最短路（含可选追踪）
# ---------------------------------------------------------------------------


def dijkstra_single_source(
    graph: LogisticsGraph,
    source: str,
    metric: str = "distance",
    *,
    trace: bool = False,
) -> dict[str, Any]:
    """单源最短路（Dijkstra）。

    Args:
        graph: Phase 1 提供的 ``LogisticsGraph``；仅消费，不修改。
        source: 起点节点 ID。
        metric: ``"distance"`` / ``"travel_time"`` / ``"cost"``。
        trace: 是否返回完整运行轨迹（用于教学展示）。

    Returns:
        * ``trace=False``：返回 ``dict``，键包括：
            - ``dist``  ``dict[node_id, float]``
            - ``prev``  ``dict[node_id, node_id | None]``
            - ``settled``  ``tuple[node_id, ...]``（按确定顺序）
            - ``relaxed_edges``  ``int``
        * ``trace=True``：返回 :class:`TraceResult`（包含以上全部 + steps）。

    Raises:
        InvalidMetricError: ``metric`` 不被支持。
        UnknownNodeError: ``source`` 不在图中。
    """
    if metric not in SUPPORTED_METRICS:
        raise InvalidMetricError(
            f"metric must be one of {SUPPORTED_METRICS}, got {metric!r}"
        )
    if not graph.has_node(source):
        raise UnknownNodeError(f"source node {source!r} not in graph")

    dist: dict[str, float] = {nid: inf for nid in graph.node_ids}
    prev: dict[str, str | None] = {nid: None for nid in graph.node_ids}
    settled: list[str] = []
    settled_set: set[str] = set()
    relaxed_edges = 0
    heap_pops = 0
    steps: list[StepRecord] = []

    dist[source] = 0.0
    heap: MinHeap = MinHeap()
    heap.push(source, 0.0)

    round_idx = 0
    while not heap.is_empty():
        u, du = heap.pop_min()
        heap_pops += 1
        if u in settled_set:
            # 懒删除：之前 decrease_key 留下的旧条目
            continue
        # 首次弹出最小值 = 最终距离
        settled.append(u)
        settled_set.add(u)
        round_idx += 1

        # 本轮的松弛记录
        round_relaxations: list[dict[str, Any]] = []

        for edge in graph.get_neighbors(u):
            v = edge.target_id
            if v in settled_set:
                continue
            new_dist = du + _weight_of(edge, metric)
            old_dist = dist[v]
            if new_dist < old_dist:
                dist[v] = new_dist
                prev[v] = u
                relaxed_edges += 1
                if heap.contains(v):
                    heap.decrease_key(v, new_dist)
                else:
                    heap.push(v, new_dist)
                round_relaxations.append({
                    "source": u,
                    "target": v,
                    "old_dist": old_dist,
                    "new_dist": new_dist,
                    "weight": _weight_of(edge, metric),
                })

        if trace:
            steps.append(StepRecord(
                round=round_idx,
                popped_node=u,
                popped_distance=du,
                settled_snapshot=tuple(sorted(settled_set)),
                relaxations=tuple(round_relaxations),
            ))

    if trace:
        return TraceResult(
            source=source,
            metric=metric,
            dist=dist,
            prev=prev,
            settled=tuple(settled),
            steps=tuple(steps),
            relaxed_edges=relaxed_edges,
            heap_pops=heap_pops,
        )
    return {
        "dist": dist,
        "prev": prev,
        "settled": tuple(settled),
        "relaxed_edges": relaxed_edges,
        "heap_pops": heap_pops,
    }


# ---------------------------------------------------------------------------
#  主体 2：两点最优路径
# ---------------------------------------------------------------------------


def shortest_path(
    graph: LogisticsGraph,
    source: str,
    target: str,
    metric: str = "distance",
) -> PathResult:
    """单对节点的最短路径。

    早期停止优化：当 ``target`` 被从堆中弹出时即可终止；其余未确定节点
    的 dist 仍可能为 ``+inf``（不影响本接口语义）。

    Args:
        graph: ``LogisticsGraph``，仅消费不修改。
        source: 起点。
        target: 终点。
        metric: 边权指标。

    Returns:
        :class:`PathResult`，含正向路径、总权重、是否可达，以及同一路径
        在另外两种 metric 下的总权重（用于跨策略展示）。
    """
    if metric not in SUPPORTED_METRICS:
        raise InvalidMetricError(
            f"metric must be one of {SUPPORTED_METRICS}, got {metric!r}"
        )
    if not graph.has_node(source):
        raise UnknownNodeError(f"source node {source!r} not in graph")
    if not graph.has_node(target):
        raise UnknownNodeError(f"target node {target!r} not in graph")

    if source == target:
        # 路径长度为 0；cross_metrics 也都是 0
        return PathResult(
            source=source,
            target=target,
            metric=metric,
            path=(source,),
            total_weight=0.0,
            reachable=True,
            cross_metrics={m: 0.0 for m in SUPPORTED_METRICS},
        )

    dist: dict[str, float] = {nid: inf for nid in graph.node_ids}
    prev: dict[str, str | None] = {nid: None for nid in graph.node_ids}
    settled: set[str] = set()
    dist[source] = 0.0
    heap: MinHeap = MinHeap()
    heap.push(source, 0.0)

    found = False
    while not heap.is_empty():
        u, du = heap.pop_min()
        if u in settled:
            continue
        settled.add(u)
        if u == target:
            found = True
            break
        for edge in graph.get_neighbors(u):
            v = edge.target_id
            if v in settled:
                continue
            new_dist = du + _weight_of(edge, metric)
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                if heap.contains(v):
                    heap.decrease_key(v, new_dist)
                else:
                    heap.push(v, new_dist)

    if not found or dist[target] == inf:
        return PathResult(
            source=source,
            target=target,
            metric=metric,
            path=(),
            total_weight=inf,
            reachable=False,
            cross_metrics={},
        )

    # 回溯
    path: list[str] = []
    cur: str | None = target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()

    # 同一路径在三种 metric 下的总权重（含主指标）。
    # Phase 5 规格 §3.3：``distance`` / ``travel_time`` / ``cost`` 必须
    # 都来自同一条实际选定的路径，并汇总为整条配送路线的三个指标；
    # 因此 ``cross_metrics`` 现包含主指标本身（不再跳过）。
    cross: dict[str, float] = {}
    for m in SUPPORTED_METRICS:
        total = 0.0
        for i in range(len(path) - 1):
            edge = graph.get_edge(path[i], path[i + 1])
            total += _weight_of(edge, m)
        cross[m] = total

    return PathResult(
        source=source,
        target=target,
        metric=metric,
        path=tuple(path),
        total_weight=dist[target],
        reachable=True,
        cross_metrics=cross,
    )


# ---------------------------------------------------------------------------
#  主体 3：多策略对比
# ---------------------------------------------------------------------------


def compare_metrics(
    graph: LogisticsGraph,
    source: str,
    target: str,
) -> dict[str, PathResult]:
    """对同一 (source, target) 计算三种 metric 下的最优路径。

    返回 ``{metric: PathResult}`` 字典。
    """
    results: dict[str, PathResult] = {}
    for m in SUPPORTED_METRICS:
        results[m] = shortest_path(graph, source, target, metric=m)
    return results


__all__ = [
    "SUPPORTED_METRICS",
    "DijkstraError",
    "InvalidMetricError",
    "UnknownNodeError",
    "StepRecord",
    "TraceResult",
    "PathResult",
    "dijkstra_single_source",
    "shortest_path",
    "compare_metrics",
]
