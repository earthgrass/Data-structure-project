"""``LogisticsGraph`` 行为与一致性的单元测试。"""

from __future__ import annotations

import math

import pytest

from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType, TrafficStatus
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import (
    DuplicateEdgeError,
    DuplicateNodeError,
    GraphError,
    LogisticsGraph,
    UnknownNodeError,
)


pytestmark = pytest.mark.phase1


# ---------------------------------------------------------------------------
#  节点增删
# ---------------------------------------------------------------------------


class TestNodeOperations:
    def test_add_node_increases_count(self, make_graph, make_node):
        g = make_graph()
        g.add_node(make_node("A"))
        assert g.node_count == 1
        assert g.has_node("A")

    def test_add_duplicate_node_raises(self, make_graph, make_node):
        g = make_graph()
        g.add_node(make_node("A"))
        with pytest.raises(DuplicateNodeError):
            g.add_node(make_node("A", name="alias"))

    def test_remove_node(self, make_graph, make_node):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        g.remove_node("A")
        assert not g.has_node("A")
        assert g.has_node("B")
        assert g.node_count == 1

    def test_remove_unknown_node_raises(self, make_graph):
        with pytest.raises(UnknownNodeError):
            make_graph().remove_node("missing")

    def test_get_node_returns_instance(self, make_graph, make_node):
        g = make_graph()
        node = make_node("A", name="WH-A")
        g.add_node(node)
        fetched = g.get_node("A")
        assert fetched is node
        assert fetched.name == "WH-A"

    def test_try_get_node_returns_none(self, make_graph):
        assert make_graph().try_get_node("nope") is None

    def test_add_invalid_type_raises_typeerror(self, make_graph):
        with pytest.raises(TypeError):
            make_graph().add_node("not a node")  # type: ignore[arg-type]

    def test_nodes_property_returns_snapshot(self, make_graph, make_node):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        nodes = g.nodes
        nodes.clear()
        # Snapshot semantics: graph not affected
        assert g.node_count == 2

    def test_contains_operator(self, make_graph, make_node):
        g = make_graph()
        g.add_node(make_node("A"))
        assert "A" in g
        assert "B" not in g


# ---------------------------------------------------------------------------
#  边增删
# ---------------------------------------------------------------------------


class TestEdgeOperations:
    def test_add_edge_directed_only(self, make_graph, make_node, make_edge):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        g.add_edge(make_edge("A", "B", distance=1.0))
        assert g.has_edge("A", "B") is True
        assert g.has_edge("B", "A") is False
        assert g.edge_count == 1

    def test_add_edge_with_unknown_endpoint_raises(
        self, make_graph, make_node, make_edge
    ):
        g = make_graph()
        g.add_node(make_node("A"))
        with pytest.raises(UnknownNodeError):
            g.add_edge(make_edge("A", "B"))
        with pytest.raises(UnknownNodeError):
            g.add_edge(make_edge("Z", "A"))

    def test_add_duplicate_edge_raises(self, make_graph, make_node, make_edge):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        g.add_edge(make_edge("A", "B", distance=1.0))
        with pytest.raises(DuplicateEdgeError):
            g.add_edge(make_edge("A", "B", distance=2.0))

    def test_remove_edge(self, make_graph, make_node, make_edge):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        g.add_edge(make_edge("A", "B", distance=1.0))
        g.remove_edge("A", "B")
        assert g.has_edge("A", "B") is False
        assert g.edge_count == 0

    def test_remove_unknown_edge_raises(self, make_graph, make_node, make_edge):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        with pytest.raises(GraphError):
            g.remove_edge("A", "B")

    def test_get_neighbors(self, make_graph, make_node, make_edge):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        g.add_node(make_node("C"))
        g.add_edge(make_edge("A", "B", distance=1.0))
        g.add_edge(make_edge("A", "C", distance=2.0))
        neighbors = g.get_neighbors("A")
        assert {n.target_id for n in neighbors} == {"B", "C"}

    def test_get_neighbors_unknown_node_raises(self, make_graph):
        with pytest.raises(UnknownNodeError):
            make_graph().get_neighbors("nope")

    def test_edges_property_uniqueness(self, sample_graph):
        # 重复获取 edges 应仍代表同一对象，避免无意复制
        first = sample_graph.edges
        # 集合中不应出现重复边
        keys = {(e.source_id, e.target_id) for e in first}
        assert len(keys) == len(first)
        # 添加一条边不会引发相邻边集合突增
        sample_graph.add_edge(Edge("C1", "C2",
                                  distance=1.0, travel_time=1.0, cost=1.0))
        assert sample_graph.edge_count == len(sample_graph.edges)


# ---------------------------------------------------------------------------
#  删除节点时的边清理
# ---------------------------------------------------------------------------


class TestNodeRemovalCleanUpEdges:
    def test_remove_node_clears_outgoing(self, sample_graph):
        # A 在 sample_graph 中具有 2 条出边（A->T1, A->T2），无入边
        sample_graph.remove_node("A")
        assert "A" not in sample_graph
        # 仅剔除 A 的两条出边，剩余 5 - 2 = 3 条
        assert sample_graph.edge_count == 3

    def test_remove_node_clears_incoming(self, sample_graph):
        # C2 收到 T2->C2 与 T1->C2 两条入边
        sample_graph.remove_node("C2")
        assert "C2" not in sample_graph
        # 删除 C2 后，应只剩 A->T1, A->T2, T1->C1
        assert sample_graph.edge_count == 3

    def test_remove_node_keeps_other_nodes_consistent(self, sample_graph):
        sample_graph.remove_node("T1")
        # T1 删除后其作为 source 的边不在，其作为 target 的入边被清理
        sample_graph.validate()
        # 验证反向索引依然一致
        for node_id in sample_graph.node_ids:
            for in_edge in sample_graph.get_in_edges(node_id):
                assert sample_graph.has_edge(in_edge.source_id, node_id)

    def test_remove_isolated_node(self, make_graph, make_node):
        g = make_graph()
        g.add_node(make_node("ISO"))
        g.remove_node("ISO")
        assert g.node_count == 0
        assert g.edge_count == 0
        g.validate()


# ---------------------------------------------------------------------------
#  邻接表正确性
# ---------------------------------------------------------------------------


class TestAdjacencyListExport:
    def test_export_shape(self, sample_graph):
        adj = sample_graph.to_adjacency_list()
        assert set(adj.keys()) == {"A", "T1", "T2", "C1", "C2"}
        for src, items in adj.items():
            for item in items:
                assert "target" in item
                assert "distance" in item
                assert "travel_time" in item
                assert "cost" in item
                assert "traffic_status" in item

    def test_export_neighbors_sorted_by_target_id(self, make_graph, make_node, make_edge):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        g.add_node(make_node("C"))
        g.add_node(make_node("D"))
        # 添加顺序：A->C, A->B, A->D
        g.add_edge(make_edge("A", "C"))
        g.add_edge(make_edge("A", "B"))
        g.add_edge(make_edge("A", "D"))
        adj = g.to_adjacency_list()
        targets = [item["target"] for item in adj["A"]]
        assert targets == ["B", "C", "D"]

    def test_export_empty_node(self, make_graph, make_node):
        g = make_graph()
        g.add_node(make_node("ISO"))
        adj = g.to_adjacency_list()
        assert adj == {"ISO": []}


# ---------------------------------------------------------------------------
#  邻接矩阵正确性
# ---------------------------------------------------------------------------


class TestAdjacencyMatrixExport:
    def test_distance_matrix(self, sample_graph):
        node_ids, matrix = sample_graph.to_adjacency_matrix(metric="distance")
        # A -> T1: distance=1
        a = node_ids.index("A")
        t1 = node_ids.index("T1")
        t2 = node_ids.index("T2")
        c2 = node_ids.index("C2")
        c1 = node_ids.index("C1")
        assert matrix[a][t1] == 1.0
        assert matrix[a][t2] == 1.0
        assert matrix[t1][c1] == 1.0
        assert matrix[t1][c2] == 2.0
        # 反向不存在则为 inf
        assert matrix[t1][a] == math.inf
        # 自环不存在则为 inf（无论节点本身有什么设置）
        assert matrix[a][a] == math.inf

    def test_travel_time_and_cost_matrices(self, sample_graph):
        _, m_time = sample_graph.to_adjacency_matrix(metric="travel_time")
        # T1->C1 travel_time=1
        a, t1, c1, t2, c2 = range(5)
        # 在没有指定 node_order 时，行列顺序为插入顺序
        order = sample_graph.node_ids
        t1_idx = order.index("T1")
        c1_idx = order.index("C1")
        assert m_time[t1_idx][c1_idx] == 1.0
        assert m_time[t1_idx][order.index("C2")] == 3.0

        _, m_cost = sample_graph.to_adjacency_matrix(metric="cost")
        assert m_cost[t1_idx][c1_idx] == 1.0
        assert m_cost[t1_idx][order.index("C2")] == 2.0

    def test_custom_node_order(self, sample_graph):
        order = ["C2", "C1", "T2", "T1", "A"]
        ids, matrix = sample_graph.to_adjacency_matrix(node_order=order)
        assert ids == order
        # 在该顺序下：T1(下标 3) -> C2(下标 0) weight=2
        assert matrix[3][0] == 2.0

    def test_invalid_metric_rejected(self, sample_graph):
        with pytest.raises(ValueError, match="metric"):
            sample_graph.to_adjacency_matrix(metric="time")  # type: ignore[arg-type]

    def test_unknown_node_in_order_rejected(self, sample_graph):
        with pytest.raises(ValueError, match="unknown node ids"):
            sample_graph.to_adjacency_matrix(node_order=["A", "MISSING"])

    def test_empty_graph_matrix(self, make_graph):
        ids, matrix = make_graph().to_adjacency_matrix()
        assert ids == []
        assert matrix == []

    def test_matrix_is_serializable_structure(self, sample_graph):
        import json
        _, matrix = sample_graph.to_adjacency_matrix()
        # 替换 inf 后必须是有限数才能 JSON 化
        cleaned = [
            [0.0 if (math.isinf(v) or math.isnan(v)) else v for v in row]
            for row in matrix
        ]
        json.dumps(cleaned)  # 不抛错即视为结构良好


# ---------------------------------------------------------------------------
#  重复 ID、类型错误、一致性
# ---------------------------------------------------------------------------


class TestRobustnessAndConsistency:
    def test_validation_after_random_operations(self, make_graph, make_node, make_edge):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        g.add_node(make_node("C"))
        g.add_edge(make_edge("A", "B", distance=1.0))
        g.add_edge(make_edge("B", "C", distance=1.0))
        g.add_edge(make_edge("C", "A", distance=1.0))
        g.validate()
        g.remove_node("B")
        g.validate()
        g.add_edge(make_edge("A", "C", distance=2.0))
        g.validate()

    def test_get_edge_returns_correct_instance(
        self, make_graph, make_node, make_edge
    ):
        g = make_graph()
        g.add_node(make_node("A"))
        g.add_node(make_node("B"))
        edge = make_edge("A", "B", distance=2.5)
        g.add_edge(edge)
        assert g.get_edge("A", "B") is edge
        assert g.try_get_edge("A", "B") is edge
        assert g.try_get_edge("B", "A") is None

    def test_get_in_edges(self, sample_graph):
        c2_in = sample_graph.get_in_edges("C2")
        sources = {e.source_id for e in c2_in}
        assert sources == {"T1", "T2"}

    def test_in_edges_consistency_after_remove_node(
        self, make_graph, make_node, make_edge
    ):
        g = make_graph()
        for i in "ABCD":
            g.add_node(make_node(i))
        g.add_edge(make_edge("A", "C"))
        g.add_edge(make_edge("B", "C"))
        g.add_edge(make_edge("C", "D"))
        g.remove_node("C")
        # C 已删除，其旧入边不再可见
        assert {e.source_id for e in g.get_in_edges("D")} == set()
        g.validate()

    def test_clear(self, sample_graph):
        sample_graph.clear()
        assert sample_graph.node_count == 0
        assert sample_graph.edge_count == 0
        sample_graph.validate()

    def test_repr_contains_counts(self, sample_graph):
        text = repr(sample_graph)
        assert "LogisticsGraph" in text
        assert "nodes=5" in text
        assert "edges=5" in text
