"""``LogisticsGraph`` 行为与一致性的单元测试。"""

from __future__ import annotations

import math
import unittest

from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import (
    DuplicateEdgeError,
    DuplicateNodeError,
    GraphError,
    LogisticsGraph,
    UnknownNodeError,
)


def _make_node(node_id: str, name: str = "n", t: NodeType = NodeType.CUSTOMER,
               x: float = 0.0, y: float = 0.0) -> Node:
    return Node(id=node_id, name=name, node_type=t, x=x, y=y)


def _make_edge(src: str, dst: str, distance: float = 1.0,
               travel_time: float = 1.0, cost: float = 1.0) -> Edge:
    return Edge(source_id=src, target_id=dst,
                distance=distance, travel_time=travel_time, cost=cost)


def _sample_graph() -> LogisticsGraph:
    """5 节点 / 5 边的代表性图。"""
    g = LogisticsGraph()
    for n in [
        _make_node("A", "主仓库", NodeType.WAREHOUSE, 0.0, 0.0),
        _make_node("T1", "中转A", NodeType.TRANSFER, 1.0, 1.0),
        _make_node("T2", "中转B", NodeType.TRANSFER, 1.0, -1.0),
        _make_node("C1", "客户1", NodeType.CUSTOMER, 2.0, 2.0),
        _make_node("C2", "客户2", NodeType.CUSTOMER, 2.0, -2.0),
    ]:
        g.add_node(n)
    for e in [
        _make_edge("A", "T1", 1.0, 2.0, 1.0),
        _make_edge("A", "T2", 1.0, 2.0, 1.0),
        _make_edge("T1", "C1", 1.0, 1.0, 1.0),
        _make_edge("T2", "C2", 1.0, 1.0, 1.0),
        _make_edge("T1", "C2", 2.0, 3.0, 2.0),
    ]:
        g.add_edge(e)
    return g


# ---------------------------------------------------------------------------
#  节点增删
# ---------------------------------------------------------------------------


class TestNodeOperations(unittest.TestCase):
    def test_add_node_increases_count(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        self.assertEqual(g.node_count, 1)
        self.assertTrue(g.has_node("A"))

    def test_add_duplicate_node_raises(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        with self.assertRaises(DuplicateNodeError):
            g.add_node(_make_node("A", name="alias"))

    def test_remove_node(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.remove_node("A")
        self.assertFalse(g.has_node("A"))
        self.assertTrue(g.has_node("B"))
        self.assertEqual(g.node_count, 1)

    def test_remove_unknown_node_raises(self) -> None:
        with self.assertRaises(UnknownNodeError):
            LogisticsGraph().remove_node("missing")

    def test_get_node_returns_instance(self) -> None:
        g = LogisticsGraph()
        node = _make_node("A", name="WH-A")
        g.add_node(node)
        fetched = g.get_node("A")
        self.assertIs(fetched, node)
        self.assertEqual(fetched.name, "WH-A")

    def test_try_get_node_returns_none(self) -> None:
        self.assertIsNone(LogisticsGraph().try_get_node("nope"))

    def test_add_invalid_type_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError):
            LogisticsGraph().add_node("not a node")  # type: ignore[arg-type]

    def test_nodes_property_returns_snapshot(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        snapshot = g.get_all_nodes()
        snapshot.clear()
        self.assertEqual(g.node_count, 2)

    def test_contains_operator(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        self.assertIn("A", g)
        self.assertNotIn("B", g)

    def test_get_all_edges_no_dup(self) -> None:
        g = _sample_graph()
        edges = g.get_all_edges()
        keys = {(e.source_id, e.target_id) for e in edges}
        self.assertEqual(len(keys), len(edges))


# ---------------------------------------------------------------------------
#  边增删
# ---------------------------------------------------------------------------


class TestEdgeOperations(unittest.TestCase):
    def test_add_edge_directed_only(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge(_make_edge("A", "B", distance=1.0))
        self.assertTrue(g.has_edge("A", "B"))
        self.assertFalse(g.has_edge("B", "A"))
        self.assertEqual(g.edge_count, 1)

    def test_add_edge_with_unknown_endpoint_raises(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        with self.assertRaises(UnknownNodeError):
            g.add_edge(_make_edge("A", "B"))
        with self.assertRaises(UnknownNodeError):
            g.add_edge(_make_edge("Z", "A"))

    def test_add_duplicate_edge_raises(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge(_make_edge("A", "B", distance=1.0))
        with self.assertRaises(DuplicateEdgeError):
            g.add_edge(_make_edge("A", "B", distance=2.0))

    def test_remove_edge(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge(_make_edge("A", "B", distance=1.0))
        g.remove_edge("A", "B")
        self.assertFalse(g.has_edge("A", "B"))
        self.assertEqual(g.edge_count, 0)

    def test_remove_unknown_edge_raises(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        with self.assertRaises(GraphError):
            g.remove_edge("A", "B")

    def test_get_neighbors_returns_outgoing(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_node(_make_node("C"))
        g.add_edge(_make_edge("A", "B", distance=1.0))
        g.add_edge(_make_edge("A", "C", distance=2.0))
        neighbors = g.get_neighbors("A")
        self.assertEqual({n.target_id for n in neighbors}, {"B", "C"})

    def test_get_neighbors_unknown_node_raises(self) -> None:
        with self.assertRaises(UnknownNodeError):
            LogisticsGraph().get_neighbors("nope")


# ---------------------------------------------------------------------------
#  删除节点时的边清理
# ---------------------------------------------------------------------------


class TestNodeRemovalCleanUpEdges(unittest.TestCase):
    def test_remove_node_clears_outgoing(self) -> None:
        g = _sample_graph()
        # A in sample_graph has 2 outgoing, 0 incoming
        g.remove_node("A")
        self.assertNotIn("A", g)
        self.assertEqual(g.edge_count, 3)  # 5 - 2
        g.validate()

    def test_remove_node_clears_incoming(self) -> None:
        g = _sample_graph()
        # C2 has incoming from T2 and T1
        g.remove_node("C2")
        self.assertNotIn("C2", g)
        self.assertEqual(g.edge_count, 3)
        g.validate()

    def test_remove_node_keeps_other_nodes_consistent(self) -> None:
        g = _sample_graph()
        g.remove_node("T1")
        g.validate()
        for node_id in g.node_ids:
            for in_edge in g.get_in_edges(node_id):
                self.assertTrue(g.has_edge(in_edge.source_id, node_id))

    def test_remove_isolated_node(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("ISO"))
        g.remove_node("ISO")
        self.assertEqual(g.node_count, 0)
        self.assertEqual(g.edge_count, 0)
        g.validate()


# ---------------------------------------------------------------------------
#  邻接表正确性
# ---------------------------------------------------------------------------


class TestAdjacencyListExport(unittest.TestCase):
    def test_export_shape(self) -> None:
        g = _sample_graph()
        adj = g.get_adjacency_list()
        self.assertEqual(set(adj.keys()), {"A", "T1", "T2", "C1", "C2"})
        for items in adj.values():
            for item in items:
                for k in ("target", "distance", "travel_time", "cost", "traffic_status"):
                    self.assertIn(k, item)

    def test_neighbors_sorted_by_target_id(self) -> None:
        g = LogisticsGraph()
        for node_id in ("A", "B", "C", "D"):
            g.add_node(_make_node(node_id))
        g.add_edge(_make_edge("A", "C"))
        g.add_edge(_make_edge("A", "B"))
        g.add_edge(_make_edge("A", "D"))
        adj = g.get_adjacency_list()
        self.assertEqual([item["target"] for item in adj["A"]], ["B", "C", "D"])

    def test_export_empty_node(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("ISO"))
        self.assertEqual(g.get_adjacency_list(), {"ISO": []})


# ---------------------------------------------------------------------------
#  邻接矩阵正确性
# ---------------------------------------------------------------------------


class TestAdjacencyMatrixExport(unittest.TestCase):
    def test_distance_matrix(self) -> None:
        g = _sample_graph()
        node_ids, matrix = g.get_adjacency_matrix(metric="distance")
        idx = {n: i for i, n in enumerate(node_ids)}
        a, t1, t2, c1, c2 = idx["A"], idx["T1"], idx["T2"], idx["C1"], idx["C2"]
        self.assertEqual(matrix[a][t1], 1.0)
        self.assertEqual(matrix[a][t2], 1.0)
        self.assertEqual(matrix[t1][c1], 1.0)
        self.assertEqual(matrix[t1][c2], 2.0)
        # 反向 / 自环：inf
        self.assertEqual(matrix[t1][a], math.inf)
        self.assertEqual(matrix[a][a], math.inf)

    def test_travel_time_and_cost_matrices(self) -> None:
        g = _sample_graph()
        _, m_time = g.get_adjacency_matrix(metric="travel_time")
        order = g.node_ids
        t1_idx = order.index("T1")
        c1_idx = order.index("C1")
        c2_idx = order.index("C2")
        self.assertEqual(m_time[t1_idx][c1_idx], 1.0)
        self.assertEqual(m_time[t1_idx][c2_idx], 3.0)

        _, m_cost = g.get_adjacency_matrix(metric="cost")
        self.assertEqual(m_cost[t1_idx][c1_idx], 1.0)
        self.assertEqual(m_cost[t1_idx][c2_idx], 2.0)

    def test_custom_node_order(self) -> None:
        g = _sample_graph()
        order = ["C2", "C1", "T2", "T1", "A"]
        ids, matrix = g.get_adjacency_matrix(node_order=order)
        self.assertEqual(ids, order)
        # T1->C2 weight=2 in our sample (distance metric)
        self.assertEqual(matrix[3][0], 2.0)

    def test_invalid_metric_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _sample_graph().get_adjacency_matrix(metric="time")  # type: ignore[arg-type]

    def test_unknown_node_in_order_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _sample_graph().get_adjacency_matrix(node_order=["A", "MISSING"])

    def test_empty_graph_matrix(self) -> None:
        ids, matrix = LogisticsGraph().get_adjacency_matrix()
        self.assertEqual(ids, [])
        self.assertEqual(matrix, [])


# ---------------------------------------------------------------------------
#  重复 ID、类型错误、一致性
# ---------------------------------------------------------------------------


class TestRobustnessAndConsistency(unittest.TestCase):
    def test_validation_after_random_operations(self) -> None:
        g = LogisticsGraph()
        for node_id in "ABCD":
            g.add_node(_make_node(node_id))
        g.add_edge(_make_edge("A", "C"))
        g.add_edge(_make_edge("B", "C"))
        g.add_edge(_make_edge("C", "D"))
        g.validate()
        g.remove_node("B")
        g.validate()
        # 重复边应当拒绝（图中已存在 A->C）
        try:
            g.add_edge(_make_edge("A", "C", distance=3.0))
            self.fail("should not allow duplicate edges")
        except DuplicateEdgeError:
            pass
        g.validate()

    def test_get_edge_returns_correct_instance(self) -> None:
        g = LogisticsGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        edge = _make_edge("A", "B", distance=2.5)
        g.add_edge(edge)
        self.assertIs(g.get_edge("A", "B"), edge)
        self.assertIs(g.try_get_edge("A", "B"), edge)
        self.assertIsNone(g.try_get_edge("B", "A"))

    def test_get_in_edges(self) -> None:
        g = _sample_graph()
        in_edges = g.get_in_edges("C2")
        self.assertEqual({e.source_id for e in in_edges}, {"T1", "T2"})

    def test_in_edges_consistency_after_remove_node(self) -> None:
        g = LogisticsGraph()
        for node_id in "ABCD":
            g.add_node(_make_node(node_id))
        g.add_edge(_make_edge("A", "C"))
        g.add_edge(_make_edge("B", "C"))
        g.add_edge(_make_edge("C", "D"))
        g.remove_node("C")
        self.assertEqual({e.source_id for e in g.get_in_edges("D")}, set())
        g.validate()

    def test_clear(self) -> None:
        g = _sample_graph()
        g.clear()
        self.assertEqual(g.node_count, 0)
        self.assertEqual(g.edge_count, 0)
        g.validate()

    def test_repr_contains_counts(self) -> None:
        text = repr(_sample_graph())
        self.assertIn("LogisticsGraph", text)
        self.assertIn("nodes=5", text)
        self.assertIn("edges=5", text)


# ---------------------------------------------------------------------------
#  大型配置驱动场景（连通性 + 节点/边下界）
# ---------------------------------------------------------------------------


class TestLargeScenarioShape(unittest.TestCase):
    """对 ``config/scenario.json`` 这一固定场景作形状检查。

    这些测试不属于纯单测逻辑，但属于「配置驱动初始化」必须保证的形态。
    若 ``config/scenario.json`` 不存在则自动跳过。
    """

    SCENARIO = "config/scenario.json"

    def _load_or_skip(self):
        from pathlib import Path
        from logiroute.config import ConfigError, load_scenario
        path = Path(self.SCENARIO)
        if not path.is_file():
            self.skipTest(f"{self.SCENARIO} not present")
        try:
            return load_scenario(path)
        except ConfigError as exc:
            self.fail(f"scenario.json failed validation: {exc}")

    def test_minimum_node_count(self) -> None:
        bundle = self._load_or_skip()
        self.assertGreaterEqual(bundle.graph.node_count, 30)

    def test_type_minimums(self) -> None:
        from logiroute.core.enums import NodeType
        bundle = self._load_or_skip()
        from collections import Counter
        cnt = Counter(n.node_type for n in bundle.graph.get_all_nodes())
        self.assertGreaterEqual(cnt[NodeType.WAREHOUSE], 2)
        self.assertGreaterEqual(cnt[NodeType.CUSTOMER], 15)
        self.assertGreaterEqual(cnt[NodeType.TRANSFER], 3)

    def test_minimum_edge_count(self) -> None:
        bundle = self._load_or_skip()
        self.assertGreaterEqual(bundle.graph.edge_count, 50)

    def test_internal_consistency(self) -> None:
        bundle = self._load_or_skip()
        bundle.graph.validate()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
