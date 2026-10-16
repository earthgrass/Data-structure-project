"""图指纹：``PathProvider`` 缓存键的 ``graph_version`` 实现。

依据 AGENTS.md §3.7 要求，缓存键形如
``(graph_version, source, target, metric)``，其中 ``graph_version`` 由本函数提供。

**为何不用 ``sorted()`` 排序**：AGENTS.md §2.1 把 ``sorted()`` / ``heapq`` 视为
"算法核心禁表"。``graph_identity`` 不参与算法逻辑，只是元诊断指纹；
为遵守"更严标准"，本函数构造指纹元组时直接利用 ``LogisticsGraph``
**插入有序** 的内部 dict 迭代顺序，不调用任何排序工具。

指纹组成：

* ``id(graph)`` —— 进程内对象身份
* ``tuple(graph.node_ids)`` —— 节点名按插入有序快照
* ``graph.edge_count`` —— 边数（轻量 O(1) 计数）
* ``edge_part`` —— 每条边的 ``(source_id, target_id, distance, travel_time, cost, traffic)``
  完整快照，按 ``graph.node_ids`` 顺序 + ``get_out_edges(src)`` 顺序拼接

Time   : O(V + E) 迭代一次快照。
Space  : O(V + E) 元组大小。

调用方应在 ``PathProvider`` 构造时获取并冻结指纹；调度实例一次性使用，
进程内 ``id(graph)`` 已足够区分（不跨进程分享缓存）。
"""

from __future__ import annotations

from logiroute.graph.logistics_graph import LogisticsGraph


def graph_identity(graph: LogisticsGraph) -> tuple:
    """捕获 ``LogisticsGraph`` 的拓扑 + 边权指纹元组。

    Returns:
        ``(oid, node_part, edge_count, edge_part)`` 4 元组；任意分量变化即代表
        图结构或权重的修改，键值因而变化，缓存自动失效。

    Note:
        本函数纯粹用于缓存键与元诊断；**不** 调用 ``sorted()`` / ``heapq``
        等被 AGENTS.md §2.1 列为禁表的工具。
    """
    node_part: tuple[str, ...] = tuple(graph.node_ids)
    edge_count: int = graph.edge_count

    # 利用 LogisticsGraph 内部的插入有序 dict 迭代：
    #   * graph.node_ids  —— 按节点插入顺序
    #   * graph.get_out_edges(src)  —— 按 (source, target) 插入顺序
    # 不调任何排序工具，避免 §2.1 禁表。
    edge_parts: list[tuple] = []
    for src in graph.node_ids:
        for edge in graph.get_neighbors(src):
            edge_parts.append(
                (
                    edge.source_id,
                    edge.target_id,
                    edge.distance,
                    edge.travel_time,
                    edge.cost,
                    edge.traffic_status.value,
                )
            )
    edge_part: tuple = tuple(edge_parts)
    return (id(graph), node_part, edge_count, edge_part)
