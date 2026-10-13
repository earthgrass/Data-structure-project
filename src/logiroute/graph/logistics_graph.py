"""配送网络有向带权图。

``LogisticsGraph`` 是本项目的核心数据结构。它将 ``Node`` 与 ``Edge`` 组合起来，
对外提供清晰、最小化的图操作接口。

存储结构
--------

* 邻接表（**唯一可变状态**）：

    ``_nodes``     : Dict[node_id, Node]                                 -- O(1) 节点查找
    ``_out_edges`` : Dict[source_id, Dict[target_id, Edge]]              -- 邻接表（出边）
    ``_in_edges``  : Dict[target_id, Dict[source_id, Edge]]              -- 反向邻接表（入边）

* **邻接矩阵按需导出**，不与邻接表重复维护状态。

并发边策略
----------

Phase 1 **不**支持多重边（同一对 source_id/target_id 间仅允许一条边）。
重复添加边将抛 ``ValueError``；如需修改权重，应先 ``remove_edge`` 再 ``add_edge``。

自环策略
--------

``Edge`` 在构造时即拒绝自环（``source_id == target_id``）。图层亦会再次校验。
"""

from __future__ import annotations

from typing import Any, Iterable

from logiroute.core.edges import Edge
from logiroute.core.nodes import Node


# ---------------------------------------------------------------------------
#  异常定义
# ---------------------------------------------------------------------------


class GraphError(Exception):
    """图操作的通用错误基类。"""


class DuplicateNodeError(GraphError):
    """尝试添加已存在节点 ID 时抛出。"""

    def __init__(self, node_id: str) -> None:
        super().__init__(f"node {node_id!r} already exists in the graph")
        self.node_id = node_id


class DuplicateEdgeError(GraphError):
    """尝试添加已存在 (source_id, target_id) 边时抛出。"""

    def __init__(self, source_id: str, target_id: str) -> None:
        super().__init__(
            f"edge {source_id!r} -> {target_id!r} already exists in the graph"
        )
        self.source_id = source_id
        self.target_id = target_id


class UnknownNodeError(GraphError):
    """访问不存在的节点时抛出。"""

    def __init__(self, node_id: str) -> None:
        super().__init__(f"node {node_id!r} does not exist in the graph")
        self.node_id = node_id


# 用于邻接矩阵输出「无直接边」位置的哨兵值。
# 选择 ``float('inf')`` 是图论 / 矩阵运算标准做法，便于 Dijkstra 等算法识别。
_INF = float("inf")


# ---------------------------------------------------------------------------
#  LogisticsGraph
# ---------------------------------------------------------------------------


class LogisticsGraph:
    """有向带权图：节点 + 邻接表 + （按需导出的）邻接矩阵。

    该类是后续所有路径规划算法的容器基础。本类不依赖任何第三方库，
    所有操作均基于 Python 内置 ``dict`` 手写实现。
    """

    _SUPPORTED_METRICS = ("distance", "travel_time", "cost")

    __slots__ = ("_nodes", "_out_edges", "_in_edges")

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._out_edges: dict[str, dict[str, Edge]] = {}
        self._in_edges: dict[str, dict[str, Edge]] = {}

    # ------------------------------------------------------------------ #
    #  节点操作                                                            #
    # ------------------------------------------------------------------ #

    def add_node(self, node: Node) -> None:
        """添加节点；ID 必须唯一，否则抛 ``DuplicateNodeError``。

        Time   : O(1) avg  —— dict 写入均摊常数。
        Space  : O(1) 新增。
        """
        if not isinstance(node, Node):
            raise TypeError(f"add_node requires a Node, got {type(node).__name__}")
        if node.id in self._nodes:
            raise DuplicateNodeError(node.id)
        self._nodes[node.id] = node
        self._out_edges.setdefault(node.id, {})
        self._in_edges.setdefault(node.id, {})

    def remove_node(self, node_id: str) -> None:
        """删除节点，同时原子化删除所有指向 / 来自该节点的边。

        Time   : O(deg_in + deg_out) —— 仅扫描与该节点直接相连的边。
        Space  : O(1) 仅就地修改字典。
        """
        if node_id not in self._nodes:
            raise UnknownNodeError(node_id)
        # 1) 删除作为 source 的所有出边；同时清理对端 in_edges 反向索引
        for target_id, edge in list(self._out_edges.get(node_id, {}).items()):
            self._in_edges.get(target_id, {}).pop(node_id, None)
        self._out_edges.pop(node_id, None)
        # 2) 删除作为 target 的所有入边；同时清理对端 out_edges 反向索引
        for source_id in list(self._in_edges.get(node_id, {}).keys()):
            self._out_edges.get(source_id, {}).pop(node_id, None)
        self._in_edges.pop(node_id, None)
        # 3) 最终删除节点
        self._nodes.pop(node_id, None)

    def has_node(self, node_id: str) -> bool:
        """判断节点是否存在。Time: O(1)."""
        return node_id in self._nodes

    def get_node(self, node_id: str) -> Node:
        """根据 ID 取节点；不存在时抛 ``UnknownNodeError``。

        Time   : O(1) avg.
        Space  : O(1).
        """
        if node_id not in self._nodes:
            raise UnknownNodeError(node_id)
        return self._nodes[node_id]

    def try_get_node(self, node_id: str) -> Node | None:
        """安全取节点：不存在时返回 ``None``，不抛错。Time: O(1)."""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[Node]:
        """返回图中所有节点的快照列表（按插入顺序）。

        Time   : O(V) —— V 为节点数。
        Space  : O(V) 返回新列表。
        """
        return list(self._nodes.values())

    def get_all_edges(self) -> list[Edge]:
        """返回图中所有边的快照列表（去重，每条边出现一次）。

        Time   : O(E) —— E 为边数。
        Space  : O(E) 返回新列表。
        """
        all_edges: list[Edge] = []
        for out_map in self._out_edges.values():
            all_edges.extend(out_map.values())
        return all_edges

    @property
    def nodes(self) -> list[Node]:
        """返回所有节点的快照列表。等价于 ``get_all_nodes()``。"""
        return self.get_all_nodes()

    @property
    def node_ids(self) -> list[str]:
        """返回所有节点 ID 的快照列表。Time: O(V)."""
        return list(self._nodes.keys())

    @property
    def node_count(self) -> int:
        """节点数量。Time: O(1)."""
        return len(self._nodes)

    # ------------------------------------------------------------------ #
    #  边操作                                                              #
    # ------------------------------------------------------------------ #

    def add_edge(self, edge: Edge) -> None:
        """添加一条有向边。

        校验项：

        * ``edge`` 必须是 :class:`Edge` 实例；
        * ``source_id`` / ``target_id`` 必须对应已存在节点；
        * 同对节点不允许重复边（无多边支持）。

        Time   : O(1) avg —— 单次 dict 写入。
        Space  : O(1).
        """
        if not isinstance(edge, Edge):
            raise TypeError(f"add_edge requires an Edge, got {type(edge).__name__}")
        if edge.source_id not in self._nodes:
            raise UnknownNodeError(edge.source_id)
        if edge.target_id not in self._nodes:
            raise UnknownNodeError(edge.target_id)
        if edge.target_id in self._out_edges[edge.source_id]:
            raise DuplicateEdgeError(edge.source_id, edge.target_id)
        self._out_edges[edge.source_id][edge.target_id] = edge
        self._in_edges.setdefault(edge.target_id, {})[edge.source_id] = edge

    def remove_edge(self, source_id: str, target_id: str) -> None:
        """删除一条有向边；边不存在时抛 ``GraphError``。

        Time   : O(1) avg.
        Space  : O(1).
        """
        if source_id not in self._out_edges or source_id not in self._nodes:
            raise UnknownNodeError(source_id)
        if target_id not in self._nodes:
            raise UnknownNodeError(target_id)
        out_map = self._out_edges[source_id]
        if target_id not in out_map:
            raise GraphError(f"edge {source_id!r} -> {target_id!r} does not exist")
        out_map.pop(target_id, None)
        self._in_edges.get(target_id, {}).pop(source_id, None)

    def has_edge(self, source_id: str, target_id: str) -> bool:
        """判断 (source, target) 边是否存在。Time: O(1)."""
        return (
            source_id in self._out_edges
            and target_id in self._out_edges[source_id]
        )

    def get_edge(self, source_id: str, target_id: str) -> Edge:
        """获取指定方向的边；不存在时抛错。Time: O(1) avg."""
        if source_id not in self._out_edges:
            raise GraphError(f"edge {source_id!r} -> {target_id!r} does not exist")
        edge = self._out_edges[source_id].get(target_id)
        if edge is None:
            raise GraphError(f"edge {source_id!r} -> {target_id!r} does not exist")
        return edge

    def try_get_edge(self, source_id: str, target_id: str) -> Edge | None:
        """安全取边。Time: O(1) avg."""
        if source_id not in self._out_edges:
            return None
        return self._out_edges[source_id].get(target_id)

    def get_neighbors(self, node_id: str) -> list[Edge]:
        """获取节点的**所有出边**（邻接节点对应的边集合）。

        Time   : O(deg_out) —— 仅拷贝与该节点相关的出边。
        Space  : O(deg_out).
        """
        if node_id not in self._nodes:
            raise UnknownNodeError(node_id)
        return list(self._out_edges.get(node_id, {}).values())

    def get_in_edges(self, node_id: str) -> list[Edge]:
        """获取节点的**所有入边**。

        Time   : O(deg_in).
        Space  : O(deg_in).
        """
        if node_id not in self._nodes:
            raise UnknownNodeError(node_id)
        return list(self._in_edges.get(node_id, {}).values())

    @property
    def edges(self) -> list[Edge]:
        """所有边的快照。等价于 ``get_all_edges()``。Time: O(E)."""
        return self.get_all_edges()

    @property
    def edge_count(self) -> int:
        """边的数量。Time: O(V) —— 需遍历每个节点的邻接表相加。"""
        return sum(len(m) for m in self._out_edges.values())

    # ------------------------------------------------------------------ #
    #  邻接表 / 邻接矩阵导出                                                 #
    # ------------------------------------------------------------------ #

    def get_adjacency_list(self) -> dict[str, list[dict[str, Any]]]:
        """导出邻接表为可序列化字典。

        返回结构形如::

            {
              "A": [{"target": "B", "distance": 1.0, "travel_time": 2.0,
                     "cost": 0.5, "traffic_status": "clear"}, ...],
              ...
            }

        节点的邻接列表按 ``target_id`` **字典序升序**输出，以保证序列化结果
        可复现（与插入顺序解耦，方便测试与 diff）。**该排序仅用于导出
        视图**，不参与任何路径算法；``sorted()`` 替代的代价是
        ``Σ deg(v) log deg(v)`` 的局部开销。

        Time   : O(V + E) 主干写入 + O(Σ deg(v) log deg(v)) 排序；最坏
                 O(V + E log V)（密集图退化情形）。
        Space  : O(V + E) 新建字典 / 列表。
        """
        result: dict[str, list[dict[str, Any]]] = {}
        for source_id in self.node_ids:
            out_map = self._out_edges.get(source_id, {})
            neighbors: list[dict[str, Any]] = []
            for target_id in sorted(out_map.keys()):
                edge = out_map[target_id]
                neighbors.append(
                    {
                        "target": edge.target_id,
                        "distance": edge.distance,
                        "travel_time": edge.travel_time,
                        "cost": edge.cost,
                        "traffic_status": edge.traffic_status.value,
                    }
                )
            result[source_id] = neighbors
        return result

    def get_adjacency_matrix(
        self,
        metric: str = "distance",
        *,
        node_order: Iterable[str] | None = None,
    ) -> tuple[list[str], list[list[float]]]:
        """导出邻接矩阵（**直接邻接**，不是任意两点最短路距离）。

        Args:
            metric: 权重指标，必须为 ``"distance"`` / ``"travel_time"`` / ``"cost"``。
            node_order: 可选，指定节点顺序；默认按 ``node_ids``（插入顺序）。
                传入的顺序会驱动矩阵行列对齐。

        Returns:
            ``(node_ids, matrix)``。``matrix[i][j]`` 为从 ``node_ids[i]`` 到
            ``node_ids[j]`` 的**直接边**权重；无对应边时为 ``float('inf')``。
            主对角线（``i == j``）无自环时为 ``inf``。

        Time   : O(V² + E) —— V×V 矩阵初始化 O(V²)，加上遍历邻接表填充 O(E)。
        Space  : O(V²) 新矩阵。

        Raises:
            ValueError: ``metric`` 不被支持，或 ``node_order`` 含未知节点。
        """
        if metric not in self._SUPPORTED_METRICS:
            raise ValueError(
                f"metric must be one of {self._SUPPORTED_METRICS}, got {metric!r}"
            )

        if node_order is None:
            ordered_ids = list(self._nodes.keys())
        else:
            ordered_ids = list(node_order)
            unknown = [nid for nid in ordered_ids if nid not in self._nodes]
            if unknown:
                raise ValueError(f"unknown node ids in node_order: {unknown}")
            if len(set(ordered_ids)) != len(ordered_ids):
                seen: set[str] = set()
                dups: list[str] = []
                for nid in ordered_ids:
                    if nid in seen and nid not in dups:
                        dups.append(nid)
                    seen.add(nid)
                raise ValueError(f"duplicate node ids in node_order: {dups}")

        index = {nid: i for i, nid in enumerate(ordered_ids)}
        n = len(ordered_ids)
        matrix: list[list[float]] = [
            [_INF] * n for _ in range(n)
        ]

        for source_id, out_map in self._out_edges.items():
            if source_id not in index:
                continue
            i = index[source_id]
            for target_id, edge in out_map.items():
                if target_id not in index:
                    continue
                j = index[target_id]
                matrix[i][j] = edge.weight(metric)

        return ordered_ids, matrix

    # 向后兼容别名（旧名 to_* 也可继续使用）—— 不计入 __all__，仅为降低迁移成本
    def to_adjacency_list(self) -> dict[str, list[dict[str, Any]]]:
        """``get_adjacency_list`` 的旧别名。"""
        return self.get_adjacency_list()

    def to_adjacency_matrix(self, metric: str = "distance") -> tuple[list[str], list[list[float]]]:
        """``get_adjacency_matrix`` 的旧别名。"""
        return self.get_adjacency_matrix(metric)

    # ------------------------------------------------------------------ #
    #  维护辅助                                                            #
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        """校验内部数据结构一致性；用于测试与调试。

        检查项：

        * 节点表 / 出边表 / 入边表的 key 集合一致；
        * 每条出边都对应另一端的入边；
        * 没有任何边指向不存在的节点。

        Time   : O(V + E).
        """
        node_set = set(self._nodes.keys())
        out_set = set(self._out_edges.keys())
        in_set = set(self._in_edges.keys())
        if not (node_set == out_set == in_set):
            raise GraphError(
                f"node/out/in key set mismatch: "
                f"nodes={node_set}, out={out_set}, in={in_set}"
            )
        for source_id, out_map in self._out_edges.items():
            for target_id, edge in out_map.items():
                if edge.source_id != source_id or edge.target_id != target_id:
                    raise GraphError(
                        f"edge key mismatch: ({source_id}->{target_id})"
                    )
                back = self._in_edges.get(target_id, {}).get(source_id)
                if back is not edge:
                    raise GraphError(
                        f"missing reverse entry for edge {source_id}->{target_id}"
                    )
                if target_id not in self._nodes:
                    raise GraphError(
                        f"edge points to missing node {target_id!r}"
                    )
        for target_id, in_map in self._in_edges.items():
            for source_id, edge in in_map.items():
                back = self._out_edges.get(source_id, {}).get(target_id)
                if back is not edge:
                    raise GraphError(
                        f"missing reverse entry (in-side) for {source_id}->{target_id}"
                    )

    def clear(self) -> None:
        """清空整个图。Time: O(1)."""
        self._nodes.clear()
        self._out_edges.clear()
        self._in_edges.clear()

    def __repr__(self) -> str:
        return (
            f"LogisticsGraph(nodes={self.node_count}, edges={self.edge_count})"
        )

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._nodes
