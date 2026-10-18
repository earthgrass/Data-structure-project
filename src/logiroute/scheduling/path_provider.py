"""Phase 3 调度器专用路径缓存 —— Dijkstra 封装 + 单调度作用域缓存。

依据 AGENTS.md §3.7 要求：

* 所有相邻配送站点之间的有向最短路径必须调用 Phase 2 的 Dijkstra；
* 调度器持有**单次调度作用域内**的路径缓存，键为
  ``(graph_version, source, target, metric)``；
* 调度结束缓存自动丢弃（实例随调度对象释放），避免跨场景串味；
* ``graph_version`` 由 :func:`logiroute.scheduling.graph_identity.graph_identity`
  在构造时一次性快照；节点 / 边 / 边权变化后 ``_graph_id`` 立即不同，
  旧图所做的查询不会误命中新图的缓存键空间。

缓存策略：

* **可达查询** —— 结果写入缓存，后续查询直接命中；
* **不可达查询** —— **不**写负缓存，每次都重新调用 Dijkstra，避免某条边
  临时不可达被永久"记住"；
* **``source == target``** —— 走零权快捷路径，不入缓存（节省哈希开销）。

计数器（PUBLIC，供 :class:`logiroute.scheduling.types.PlanningStats` 读取）：

* ``cache_hits`` —— 缓存命中次数；
* ``cache_misses`` —— 缓存未命中次数；
* ``dijkstra_calls`` —— 实际调用 Dijkstra 的次数；
* ``paths_evaluated`` —— 所有 ``shortest_path`` 调用成功的总次数（含
  缓存命中 + 未命中 + ``source == target`` 快捷路径 + 不可达路径）。
"""

from __future__ import annotations

from logiroute.algorithms.dijkstra import (
    SUPPORTED_METRICS,
    PathResult,
    UnknownNodeError,
    dijkstra_single_source,
    shortest_path,
)
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling.graph_identity import graph_identity


class PathProvider:
    """Dijkstra 最短路封装 + 单调度作用域缓存。

    每个调度实例创建一个 :class:`PathProvider`；调度结束实例随之释放，
    缓存自然丢弃。**不**实现自动失效 —— 一旦图被修改，应重新构造
    :class:`PathProvider` 以获得新的 ``_graph_id``（即新的缓存键前缀）。
    """

    __slots__ = (
        "_graph",
        "_graph_id",
        "_cache",
        "cache_hits",
        "cache_misses",
        "dijkstra_calls",
        "paths_evaluated",
    )

    def __init__(self, graph: LogisticsGraph) -> None:
        """捕获图指纹，初始化空缓存与全部计数器为 0。

        Time   : O(V + E) —— ``graph_identity`` 一次性快照。
        Space  : O(V + E) —— 缓存元组大小上限。
        """
        self._graph: LogisticsGraph = graph
        self._graph_id: tuple = graph_identity(graph)
        self._cache: dict[tuple, PathResult] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.dijkstra_calls: int = 0
        self.paths_evaluated: int = 0

    # ------------------------------------------------------------------ #
    #  核心查询                                                            #
    # ------------------------------------------------------------------ #

    def shortest_path(
        self,
        source: str,
        target: str,
        metric: str,
    ) -> PathResult:
        """带缓存的最短路查询。

        行为契约：

        * ``metric`` 不在 :data:`SUPPORTED_METRICS` → 抛 :class:`ValueError`；
        * ``source == target`` → 直接返回零权 :class:`PathResult`，
          **不**入缓存，**不**调 Dijkstra；
        * 缓存命中 → 返回缓存引用，递增 ``cache_hits`` 与 ``paths_evaluated``；
        * 缓存缺失 → 调 Dijkstra，递增 ``cache_misses`` / ``dijkstra_calls``
          / ``paths_evaluated``；**仅可达**结果入缓存（不可达不写负缓存）。

        Time   : 命中 O(1)；未命中 O((V + E) log V)（Phase 2 Dijkstra）。
        Space  : O(1) 返回引用；缓存 O(K)，K = 已缓存键数。
        """
        if metric not in SUPPORTED_METRICS:
            raise ValueError(
                f"unknown metric: {metric!r}; allowed: {SUPPORTED_METRICS}"
            )

        # source == target 走零权快捷路径，不入缓存
        if source == target:
            self.paths_evaluated += 1
            return PathResult(
                source=source,
                target=target,
                metric=metric,
                path=(source,),
                total_weight=0.0,
                reachable=True,
                cross_metrics={m: 0.0 for m in SUPPORTED_METRICS},
            )

        key: tuple = (self._graph_id, source, target, metric)
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            self.paths_evaluated += 1
            return cached

        result: PathResult = shortest_path(self._graph, source, target, metric)
        self.cache_misses += 1
        self.dijkstra_calls += 1
        self.paths_evaluated += 1

        # 仅缓存可达结果；不可达不写负缓存
        if result.reachable:
            self._cache[key] = result

        return result

    # ------------------------------------------------------------------ #
    #  批量查询                                                            #
    # ------------------------------------------------------------------ #

    def all_pairs(
        self,
        stop_sequence: tuple[str, ...],
        metric: str,
    ) -> list[PathResult]:
        """对相邻 leg ``(s[i], s[i+1])`` 批量查 :meth:`shortest_path`。

        返回长度 ``len(stop_sequence) - 1`` 的 ``list``，每个元素为对应 leg 的
        :class:`PathResult`。若 ``len(stop_sequence) < 2``，返回空列表。

        Time   : 累计 O(K · (V + E) log V)，K = ``len(stop_sequence) - 1``，
                 单 leg 命中后摊到 O(1)。
        Space  : O(K)。
        """
        legs: list[PathResult] = []
        for i in range(len(stop_sequence) - 1):
            legs.append(
                self.shortest_path(
                    stop_sequence[i], stop_sequence[i + 1], metric
                )
            )
        return legs

    def shortest_paths_from(
        self,
        source: str,
        targets: tuple[str, ...],
        metric: str,
    ) -> dict[str, PathResult]:
        """一次 Dijkstra 单源运行填充多个目标的路径与三项指标。

        TSP 距离矩阵只需仓库及订单目的地作为起点，故每个不同起点最多
        运行一次 Phase 2 ``dijkstra_single_source``；沿 ``prev`` 回溯路径，
        不实现第二套最短路。可达结果写入现有调度作用域缓存。

        Time   : O((V+E)log V + T·V)，T 为目标数，回溯最坏 O(V)。
        Space  : O(V+E + T·V)，含返回的路径及缓存。
        """
        if metric not in SUPPORTED_METRICS:
            raise ValueError(f"unknown metric: {metric!r}; allowed: {SUPPORTED_METRICS}")
        if not self._graph.has_node(source):
            raise UnknownNodeError(f"source node {source!r} not in graph")
        for target in targets:
            if not self._graph.has_node(target):
                raise UnknownNodeError(f"target node {target!r} not in graph")

        results: dict[str, PathResult] = {}
        missing = False
        for target in targets:
            if source == target:
                continue
            if (self._graph_id, source, target, metric) not in self._cache:
                missing = True
                break

        single = None
        if missing:
            single = dijkstra_single_source(self._graph, source, metric)
            self.dijkstra_calls += 1
            self.cache_misses += 1

        for target in targets:
            if target in results:
                continue
            self.paths_evaluated += 1
            if source == target:
                results[target] = PathResult(
                    source=source, target=target, metric=metric,
                    path=(source,), total_weight=0.0, reachable=True,
                    cross_metrics={m: 0.0 for m in SUPPORTED_METRICS},
                )
                continue
            key = (self._graph_id, source, target, metric)
            cached = self._cache.get(key)
            if cached is not None:
                self.cache_hits += 1
                results[target] = cached
                continue
            assert single is not None
            distance = single["dist"][target]
            if distance == float("inf"):
                results[target] = PathResult(
                    source=source, target=target, metric=metric,
                    path=(), total_weight=distance, reachable=False,
                    cross_metrics={},
                )
                continue
            reverse_path: list[str] = []
            cursor: str | None = target
            while cursor is not None:
                reverse_path.append(cursor)
                cursor = single["prev"][cursor]
            reverse_path.reverse()
            cross = {m: 0.0 for m in SUPPORTED_METRICS}
            for i in range(len(reverse_path) - 1):
                edge = self._graph.get_edge(reverse_path[i], reverse_path[i + 1])
                for m in SUPPORTED_METRICS:
                    cross[m] += edge.weight(m)
            path = PathResult(
                source=source, target=target, metric=metric,
                path=tuple(reverse_path), total_weight=distance,
                reachable=True, cross_metrics=cross,
            )
            self._cache[key] = path
            results[target] = path
        return results

    def road_node_sequence(
        self,
        stop_sequence: tuple[str, ...],
        metric: str,
    ) -> tuple[str, ...]:
        """拼接所有 leg 的 ``PathResult.path``，去掉相邻重复节点。

        返回闭合完整道路序列：首尾均为 ``stop_sequence[0]``（出发仓库）。

        示例：``stop_sequence = (W1, C1, W2, W1)``，三条 leg 路径分别为
        ``(W1, C1)`` / ``(C1, W2, T1, W2)`` / ``(W2, W1)``，拼接为
        ``[W1, C1, C1, W2, T1, W2, W2, W1]``，去掉相邻重复后
        ``(W1, C1, W2, T1, W2, W1)``。

        Time   : O(L)，L = 所有 leg 路径节点总数。
        Space  : O(L)。
        """
        legs = self.all_pairs(stop_sequence, metric)
        merged: list[str] = []
        for leg in legs:
            for node in leg.path:
                # 跳过与上一节点相同的相邻重复
                if not merged or merged[-1] != node:
                    merged.append(node)
        return tuple(merged)

    # ------------------------------------------------------------------ #
    #  统计                                                                #
    # ------------------------------------------------------------------ #

    def stats(self) -> dict[str, int]:
        """返回当前计数器快照 ``dict``。

        Time   : O(1).
        Space  : O(1).
        """
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "dijkstra_calls": self.dijkstra_calls,
            "paths_evaluated": self.paths_evaluated,
        }
