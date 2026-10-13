"""Phase 1 收尾阶段的回归与边界测试。

覆盖此前审计识别出的高优先级场景：

* 邻接矩阵三种 metric 与 node_order 边界（重复 / 不存在）；
* 邻接矩阵主对角线恒为 inf 的不变量；
* 邻接表 / 邻接矩阵的边权交叉一致性；
* BFS 弱连通 / DFS 强连通（双向 DFS 判定）正反例；
* Edge 字段变更后图结构不变量验证；
* 自实现 ArrayQueue 与 BFS 的协同；
* 同一配置重复加载的强一致性；
* 固定场景连通性配置驱动校验。
"""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from logiroute.config import load_scenario, load_scenario_from_dict
from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType, TrafficStatus
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.graph.queue import ArrayQueue


SCENARIO_FILE = "config/scenario.json"


def _node(nid: str, t: NodeType = NodeType.CUSTOMER) -> Node:
    return Node(id=nid, name=nid, node_type=t, x=0.0, y=0.0)


def _edge(src: str, dst: str, d: float = 1.0, t: float = 1.0, c: float = 1.0) -> Edge:
    return Edge(
        source_id=src, target_id=dst, distance=d, travel_time=t, cost=c
    )


# ---------------------------------------------------------------------------
#  邻接矩阵语义边界
# ---------------------------------------------------------------------------


class TestAdjacencyMatrixInvariants(unittest.TestCase):
    def setUp(self) -> None:
        self.g = LogisticsGraph()
        for n in ("A", "B", "C", "D"):
            self.g.add_node(_node(n))
        self.g.add_edge(_edge("A", "B", d=1.5, t=2.0, c=3.0))
        self.g.add_edge(_edge("B", "C", d=2.0, t=4.0, c=5.0))
        self.g.add_edge(_edge("C", "D", d=3.0, t=6.0, c=7.0))
        # 注意：A→D 不存在 —— 用于检测"无直接边 = inf"

    def test_main_diagonal_is_inf(self) -> None:
        for metric in ("distance", "travel_time", "cost"):
            ids, m = self.g.get_adjacency_matrix(metric=metric)
            for i, nid in enumerate(ids):
                self.assertEqual(
                    m[i][i], math.inf,
                    msg=f"主对角线应当为 inf，但 {nid}→{nid} 在 {metric} 下 = {m[i][i]}",
                )

    def test_no_self_loop_yields_inf(self) -> None:
        # Edge 构造已拒绝自环；这里验证矩阵的主对角线是按设计为 inf
        ids, m = self.g.get_adjacency_matrix(metric="distance")
        a = ids.index("A")
        self.assertEqual(m[a][a], math.inf)

    def test_no_edge_in_both_directions_simultaneously(self) -> None:
        # A→B 存在但 B→A 不存在；矩阵应非对称
        ids, m = self.g.get_adjacency_matrix(metric="distance")
        a, b = ids.index("A"), ids.index("B")
        self.assertEqual(m[a][b], 1.5)
        self.assertEqual(m[b][a], math.inf)

    def test_three_metrics_differ(self) -> None:
        _, md = self.g.get_adjacency_matrix(metric="distance")
        _, mt = self.g.get_adjacency_matrix(metric="travel_time")
        _, mc = self.g.get_adjacency_matrix(metric="cost")
        ids = self.g.node_ids
        a, b = ids.index("A"), ids.index("B")
        self.assertEqual(md[a][b], 1.5)
        self.assertEqual(mt[a][b], 2.0)
        self.assertEqual(mc[a][b], 3.0)

    def test_node_order_with_duplicates_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.g.get_adjacency_matrix(node_order=["A", "B", "A"])

    def test_node_order_with_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.g.get_adjacency_matrix(node_order=["A", "ZZZ"])

    def test_node_order_with_empty_list(self) -> None:
        ids, m = self.g.get_adjacency_matrix(node_order=[])
        self.assertEqual(ids, [])
        self.assertEqual(m, [])

    def test_unsupported_metric_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.g.get_adjacency_matrix(metric="minutes")  # type: ignore[arg-type]

    def test_matrix_is_direct_adjacency_not_shortest_path(self) -> None:
        # A→B→C 存在，但 A→C 没有直接边；矩阵的 A→C 应为 inf，
        # 而不是经过 B 的最短路 1.5+2.0=3.5
        ids, m = self.g.get_adjacency_matrix(metric="distance")
        a, c = ids.index("A"), ids.index("C")
        self.assertEqual(m[a][c], math.inf)


# ---------------------------------------------------------------------------
#  邻接表 / 邻接矩阵交叉一致性
# ---------------------------------------------------------------------------


class TestListMatrixCrossCheck(unittest.TestCase):
    def test_list_and_matrix_agree_on_weights(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C", "D"):
            g.add_node(_node(n))
        edges = [
            _edge("A", "B", d=1.0, t=2.0, c=3.0),
            _edge("A", "C", d=4.0, t=5.0, c=6.0),
            _edge("B", "D", d=7.0, t=8.0, c=9.0),
            _edge("C", "D", d=10.0, t=11.0, c=12.0),
        ]
        for e in edges:
            g.add_edge(e)

        adj = g.get_adjacency_list()
        for metric, attr in (("distance", "distance"),
                              ("travel_time", "travel_time"),
                              ("cost", "cost")):
            ids, m = g.get_adjacency_matrix(metric=metric)
            for u, neighbors in adj.items():
                i = ids.index(u)
                seen = {nbr["target"]: nbr[attr] for nbr in neighbors}
                for v_id, expected_weight in seen.items():
                    j = ids.index(v_id)
                    self.assertEqual(
                        m[i][j], expected_weight,
                        msg=f"矩阵 {u}→{v_id} 权重不一致 (metric={metric})",
                    )


# ---------------------------------------------------------------------------
#  连通性（基于 BFS + 双向 DFS）
# ---------------------------------------------------------------------------


class TestConnectivityChecks(unittest.TestCase):
    def test_weakly_connected_directed_graph(self) -> None:
        # 弱连通（有向）但不强连通
        g = LogisticsGraph()
        for n in ("A", "B", "C"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B"))
        g.add_edge(_edge("B", "C"))
        # 弱连通：BFS 双向化后 {A,B,C} 全连
        from logiroute.config.loader import _is_weakly_connected, _is_strongly_connected
        self.assertTrue(_is_weakly_connected(g, list(g.get_all_nodes())))
        # 不强连通：C 无法回到 A
        self.assertFalse(_is_strongly_connected(g, list(g.get_all_nodes())))

    def test_strongly_connected_cycle(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B"))
        g.add_edge(_edge("B", "C"))
        g.add_edge(_edge("C", "A"))
        from logiroute.config.loader import _is_strongly_connected
        self.assertTrue(_is_strongly_connected(g, list(g.get_all_nodes())))

    def test_disconnected_graph(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "X", "Y"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B"))
        g.add_edge(_edge("X", "Y"))
        from logiroute.config.loader import _is_weakly_connected
        self.assertFalse(_is_weakly_connected(g, list(g.get_all_nodes())))

    def test_bfs_uses_array_queue(self) -> None:
        # 弱连通 BFS 内部使用 ArrayQueue；此处通过构造可遍历图验证
        # 间接证据：直接调用 BFS 流程，确认其能完成遍历
        from logiroute.config.loader import _is_weakly_connected
        g = LogisticsGraph()
        for n in ("A", "B", "C", "D"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B"))
        g.add_edge(_edge("B", "C"))
        g.add_edge(_edge("C", "D"))
        self.assertTrue(_is_weakly_connected(g, list(g.get_all_nodes())))


# ---------------------------------------------------------------------------
#  Edge 字段变更对图的影响（受控接口设计）
# ---------------------------------------------------------------------------


class TestEdgeMutationImpact(unittest.TestCase):
    def test_modifying_edge_distance_propagates_to_matrix(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B"):
            g.add_node(_node(n))
        e = _edge("A", "B", d=1.0, t=2.0, c=3.0)
        g.add_edge(e)
        # 边权可调整
        e.distance = 99.0
        _, m = g.get_adjacency_matrix(metric="distance")
        ids = g.node_ids
        self.assertEqual(m[ids.index("A")][ids.index("B")], 99.0)

    def test_validate_after_endpoint_mutation_detects_inconsistency(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C"):
            g.add_node(_node(n))
        e = _edge("A", "B", d=1.0)
        g.add_edge(e)
        # 如果外部把端点改了，会破坏 _out_edges / _in_edges 的双向索引
        e.source_id = "C"  # 不应这样做
        from logiroute.graph.logistics_graph import GraphError
        with self.assertRaises(GraphError):
            g.validate()

    def test_self_loop_on_edge_constructor_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _edge("A", "A")


# ---------------------------------------------------------------------------
#  配置加载：重复加载一致性 / 非法值
# ---------------------------------------------------------------------------


class TestScenarioReloadConsistency(unittest.TestCase):
    @unittest.skipUnless(Path(SCENARIO_FILE).is_file(), "scenario.json missing")
    def test_double_load_yields_equal_graphs(self) -> None:
        b1 = load_scenario(SCENARIO_FILE)
        b2 = load_scenario(SCENARIO_FILE)
        # 节点 / 边数一致
        self.assertEqual(b1.graph.node_count, b2.graph.node_count)
        self.assertEqual(b1.graph.edge_count, b2.graph.edge_count)
        # 邻接表深度相等
        self.assertEqual(
            b1.graph.get_adjacency_list(),
            b2.graph.get_adjacency_list(),
        )
        # 邻接矩阵按 metric 全等
        for metric in ("distance", "travel_time", "cost"):
            ids1, m1 = b1.graph.get_adjacency_matrix(metric=metric)
            ids2, m2 = b2.graph.get_adjacency_matrix(metric=metric)
            self.assertEqual(ids1, ids2)
            for r1, r2 in zip(m1, m2):
                self.assertEqual(list(r1), list(r2))

    @unittest.skipUnless(Path(SCENARIO_FILE).is_file(), "scenario.json missing")
    def test_dict_reload_with_deepcopy(self) -> None:
        raw = json.loads(Path(SCENARIO_FILE).read_text(encoding="utf-8"))
        b1 = load_scenario_from_dict(copy.deepcopy(raw))
        b2 = load_scenario_from_dict(copy.deepcopy(raw))
        self.assertEqual(b1.graph.node_count, b2.graph.node_count)
        self.assertEqual(b1.graph.edge_count, b2.graph.edge_count)

    @unittest.skipUnless(Path(SCENARIO_FILE).is_file(), "scenario.json missing")
    def test_fixed_scenario_is_strongly_connected(self) -> None:
        b = load_scenario(SCENARIO_FILE)
        from logiroute.config.loader import _is_strongly_connected
        self.assertTrue(
            _is_strongly_connected(b.graph, list(b.graph.get_all_nodes()))
        )

    def test_load_rejects_negative_capacity(self) -> None:
        raw = json.loads(Path(SCENARIO_FILE).read_text(encoding="utf-8"))
        raw["vehicles"][0]["capacity"] = -1.0
        from logiroute.config import ConfigError
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(raw)

    def test_load_rejects_negative_demand(self) -> None:
        raw = json.loads(Path(SCENARIO_FILE).read_text(encoding="utf-8"))
        raw["orders"][0]["demand"] = -0.5
        from logiroute.config import ConfigError
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(raw)


# ---------------------------------------------------------------------------
#  邻接矩阵主对角线按 inf 的设计说明
# ---------------------------------------------------------------------------


class TestDiagonalPolicy(unittest.TestCase):
    """显式记录：本项目"邻接矩阵"是直接道路邻接矩阵，主对角线 = inf。

    这与"任意两点最短路距离矩阵"不同。后者在 i==j 时为 0，由
    Phase 2+ 的 all-pairs shortest path 算法另行计算。
    """

    def test_diagonal_is_inf_when_no_self_loop(self) -> None:
        g = LogisticsGraph()
        g.add_node(_node("A"))
        _, m = g.get_adjacency_matrix()
        self.assertEqual(m[0][0], math.inf)

    def test_self_loop_unreachable_in_edge_constructor(self) -> None:
        # 通过 Edge.__post_init__ 拒绝自环，因此图内不可能存在 i==i 的非 inf 项
        with self.assertRaises(ValueError):
            Edge(
                source_id="A", target_id="A",
                distance=1.0, travel_time=1.0, cost=1.0,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
