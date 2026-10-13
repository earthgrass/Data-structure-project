"""Dijkstra 单源 / 两点路径算法的单元测试。

测试覆盖：

1. 基础场景（两节点 / 三节点链 / 多候选 / 同起点终点）。
2. 有向图（单向边、不可达）。
3. 边权（正整数、浮点、零权、跨数量级、非法 metric）。
4. 最小堆协同（多次 decrease_key、settled 不再更新）。
5. 路径回溯（prev 正确、不可达、循环、total_weight 一致）。
6. 三种 metric 共用同一实现并产生不同结果。
7. 教学追踪（trace）模式不改变结果。
8. 跨 metric 总权重（cross_metrics）与逐边相加一致。
9. 不修改 graph（不变量保持）。
10. 大量节点下的性能与正确性（small-scale exhaustive cross-check）。

测试中的"正确答案"通过**手工推算**或**独立穷举**（小图）得到，
**不依赖 Dijkstra 自身的结果进行自证**。
"""

from __future__ import annotations

import itertools
import unittest
from math import inf

from logiroute.algorithms.dijkstra import (
    InvalidMetricError,
    PathResult,
    TraceResult,
    UnknownNodeError,
    compare_metrics,
    dijkstra_single_source,
    shortest_path,
)
from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import LogisticsGraph


# ---------------------------------------------------------------------------
#  构造辅助
# ---------------------------------------------------------------------------


def _node(nid: str) -> Node:
    return Node(id=nid, name=nid, node_type=NodeType.CUSTOMER, x=0.0, y=0.0)


def _edge(src: str, dst: str, d: float = 1.0, t: float = 1.0, c: float = 1.0) -> Edge:
    return Edge(
        source_id=src, target_id=dst,
        distance=d, travel_time=t, cost=c,
    )


def _toy_graph() -> LogisticsGraph:
    """4 节点图：

    A→B (d=1, t=2, c=10)
    A→C (d=4, t=1, c=1)
    B→C (d=2, t=2, c=2)
    B→D (d=5, t=10, c=1)
    C→D (d=1, t=1, c=10)

    期望（人工推算）：
    - 最短距离 A→D：A→B→C→D = 1+2+1 = 4
    - 最短时间 A→D：A→C→D = 1+1 = 2
    - 最低成本 A→D：A→C→D = 1+10 = 11
    """
    g = LogisticsGraph()
    for n in ("A", "B", "C", "D"):
        g.add_node(_node(n))
    g.add_edge(_edge("A", "B", d=1, t=2, c=10))
    g.add_edge(_edge("A", "C", d=4, t=1, c=1))
    g.add_edge(_edge("B", "C", d=2, t=2, c=2))
    g.add_edge(_edge("B", "D", d=5, t=10, c=1))
    g.add_edge(_edge("C", "D", d=1, t=1, c=10))
    return g


def _exhaustive_path_cost(graph, src, tgt, metric):
    """独立穷举：枚举 src→tgt 所有简单路径，返回最小权重。
    仅用于小图（如 ≤6 节点）测试。
    """
    def walk(u, visited, acc):
        if u == tgt:
            yield acc
            return
        for e in graph.get_neighbors(u):
            v = e.target_id
            if v in visited:
                continue
            visited.add(v)
            yield from walk(v, visited, acc + _weight(e, metric))
            visited.remove(v)
    best = inf
    for total in walk(src, {src}, 0.0):
        if total < best:
            best = total
    return best


def _weight(edge, metric):
    if metric == "distance":
        return edge.distance
    if metric == "travel_time":
        return edge.travel_time
    if metric == "cost":
        return edge.cost
    raise ValueError(metric)


# ---------------------------------------------------------------------------
#  基础场景
# ---------------------------------------------------------------------------


class TestBasicScenarios(unittest.TestCase):
    def test_two_nodes_one_edge(self) -> None:
        g = LogisticsGraph()
        g.add_node(_node("A")); g.add_node(_node("B"))
        g.add_edge(_edge("A", "B", d=5))
        r = shortest_path(g, "A", "B", metric="distance")
        self.assertEqual(r.path, ("A", "B"))
        self.assertEqual(r.total_weight, 5.0)
        self.assertTrue(r.reachable)

    def test_three_node_chain(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B", d=1))
        g.add_edge(_edge("B", "C", d=2))
        r = shortest_path(g, "A", "C", metric="distance")
        self.assertEqual(r.path, ("A", "B", "C"))
        self.assertEqual(r.total_weight, 3.0)

    def test_source_equals_target(self) -> None:
        g = _toy_graph()
        r = shortest_path(g, "A", "A", metric="distance")
        self.assertEqual(r.path, ("A",))
        self.assertEqual(r.total_weight, 0.0)
        self.assertTrue(r.reachable)

    def test_multi_path_picks_cheapest(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B", d=10))
        g.add_edge(_edge("A", "C", d=1))
        g.add_edge(_edge("C", "B", d=1))
        r = shortest_path(g, "A", "B", metric="distance")
        self.assertEqual(r.path, ("A", "C", "B"))
        self.assertEqual(r.total_weight, 2.0)


# ---------------------------------------------------------------------------
#  有向图
# ---------------------------------------------------------------------------


class TestDirected(unittest.TestCase):
    def test_one_way_does_not_imply_reverse(self) -> None:
        g = LogisticsGraph()
        g.add_node(_node("A")); g.add_node(_node("B"))
        g.add_edge(_edge("A", "B", d=1))
        # A→B 存在但 B→A 不存在
        fwd = shortest_path(g, "A", "B", metric="distance")
        rev = shortest_path(g, "B", "A", metric="distance")
        self.assertTrue(fwd.reachable)
        self.assertFalse(rev.reachable)
        self.assertEqual(rev.path, ())
        self.assertEqual(rev.total_weight, inf)

    def test_unreachable_target(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C", "D"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B", d=1))
        # C, D 与 A, B 没有任何边
        r = shortest_path(g, "A", "D", metric="distance")
        self.assertFalse(r.reachable)
        self.assertEqual(r.path, ())
        self.assertEqual(r.total_weight, inf)

    def test_partial_reachability(self) -> None:
        g = _toy_graph()
        ss = dijkstra_single_source(g, "A", metric="distance")
        # D 可达
        self.assertEqual(ss["dist"]["D"], 4.0)
        # 所有节点都已 settled
        self.assertEqual(set(ss["settled"]), {"A", "B", "C", "D"})


# ---------------------------------------------------------------------------
#  边权
# ---------------------------------------------------------------------------


class TestEdgeWeights(unittest.TestCase):
    def test_integer_weights(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B", d=3))
        g.add_edge(_edge("B", "C", d=4))
        g.add_edge(_edge("A", "C", d=10))
        r = shortest_path(g, "A", "C", metric="distance")
        self.assertEqual(r.path, ("A", "B", "C"))
        self.assertEqual(r.total_weight, 7.0)

    def test_float_weights(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B", d=0.001))
        r = shortest_path(g, "A", "B", metric="distance")
        self.assertAlmostEqual(r.total_weight, 0.001)

    def test_zero_weight_edge(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B", "C"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B", d=5))
        g.add_edge(_edge("B", "C", d=0))
        r = shortest_path(g, "A", "C", metric="distance")
        self.assertEqual(r.path, ("A", "B", "C"))
        self.assertEqual(r.total_weight, 5.0)

    def test_different_scales(self) -> None:
        g = LogisticsGraph()
        for n in ("A", "B"):
            g.add_node(_node(n))
        g.add_edge(_edge("A", "B", d=1e6))
        r = shortest_path(g, "A", "B", metric="distance")
        self.assertEqual(r.total_weight, 1e6)

    def test_invalid_metric_rejected(self) -> None:
        g = _toy_graph()
        with self.assertRaises(InvalidMetricError):
            shortest_path(g, "A", "D", metric="minutes")  # type: ignore[arg-type]

    def test_invalid_source_rejected(self) -> None:
        g = _toy_graph()
        with self.assertRaises(UnknownNodeError):
            shortest_path(g, "GHOST", "D", metric="distance")

    def test_invalid_target_rejected(self) -> None:
        g = _toy_graph()
        with self.assertRaises(UnknownNodeError):
            shortest_path(g, "A", "GHOST", metric="distance")


# ---------------------------------------------------------------------------
#  三种 metric
# ---------------------------------------------------------------------------


class TestThreeMetrics(unittest.TestCase):
    def test_three_metrics_yield_different_paths(self) -> None:
        g = _toy_graph()
        results = compare_metrics(g, "A", "D")
        self.assertEqual(set(results.keys()), {"distance", "travel_time", "cost"})
        # 期望：distance → A-B-C-D；time/cost → A-C-D
        self.assertEqual(results["distance"].path, ("A", "B", "C", "D"))
        self.assertEqual(results["distance"].total_weight, 4.0)
        self.assertEqual(results["travel_time"].path, ("A", "C", "D"))
        self.assertEqual(results["travel_time"].total_weight, 2.0)
        self.assertEqual(results["cost"].path, ("A", "C", "D"))
        self.assertEqual(results["cost"].total_weight, 11.0)

    def test_path_total_weight_matches_sum(self) -> None:
        g = _toy_graph()
        for m in ("distance", "travel_time", "cost"):
            r = shortest_path(g, "A", "D", metric=m)
            # 独立累加验证
            total = 0.0
            for i in range(len(r.path) - 1):
                e = g.get_edge(r.path[i], r.path[i + 1])
                if m == "distance":
                    total += e.distance
                elif m == "travel_time":
                    total += e.travel_time
                else:
                    total += e.cost
            self.assertAlmostEqual(r.total_weight, total, places=9)

    def test_cross_metrics_consistency(self) -> None:
        g = _toy_graph()
        r = shortest_path(g, "A", "D", metric="distance")
        # cross_metrics 的"cost"应当是 A-B-C-D 这条路径上 10+2+10=22
        self.assertEqual(r.cross_metrics["cost"], 22.0)
        self.assertEqual(r.cross_metrics["travel_time"], 5.0)


# ---------------------------------------------------------------------------
#  路径回溯
# ---------------------------------------------------------------------------


class TestPathReconstruction(unittest.TestCase):
    def test_path_no_cycle(self) -> None:
        g = _toy_graph()
        r = shortest_path(g, "A", "D", metric="distance")
        self.assertEqual(len(r.path), len(set(r.path)))  # 无重复节点

    def test_path_consecutive_edges_exist(self) -> None:
        g = _toy_graph()
        r = shortest_path(g, "A", "D", metric="distance")
        for i in range(len(r.path) - 1):
            self.assertTrue(g.has_edge(r.path[i], r.path[i + 1]))

    def test_single_source_prev_chain(self) -> None:
        g = _toy_graph()
        ss = dijkstra_single_source(g, "A", metric="distance")
        # 从 prev 回溯到 A
        for tgt in ("B", "C", "D"):
            seen = set()
            cur = tgt
            while cur is not None:
                self.assertNotIn(cur, seen, msg=f"prev 链有环：{cur}")
                seen.add(cur)
                cur = ss["prev"][cur]
            self.assertIn("A", seen)

    def test_settled_ordering_matches_dist(self) -> None:
        g = _toy_graph()
        ss = dijkstra_single_source(g, "A", metric="distance")
        for i in range(len(ss["settled"]) - 1):
            u = ss["settled"][i]
            v = ss["settled"][i + 1]
            self.assertLessEqual(ss["dist"][u], ss["dist"][v])


# ---------------------------------------------------------------------------
#  Trace 模式
# ---------------------------------------------------------------------------


class TestTraceMode(unittest.TestCase):
    def test_trace_returns_trace_result(self) -> None:
        g = _toy_graph()
        tr = dijkstra_single_source(g, "A", metric="distance", trace=True)
        self.assertIsInstance(tr, TraceResult)
        self.assertEqual(tr.source, "A")
        self.assertEqual(tr.metric, "distance")
        self.assertEqual(tr.dist["D"], 4.0)
        self.assertEqual(tr.settled[-1], "D")

    def test_trace_steps_record_relaxations(self) -> None:
        g = _toy_graph()
        tr = dijkstra_single_source(g, "A", metric="distance", trace=True)
        # 至少有一次成功的松弛
        any_relax = any(len(s.relaxations) > 0 for s in tr.steps)
        self.assertTrue(any_relax)
        # step 中的 source/target 应为图中实际边
        for s in tr.steps:
            for r in s.relaxations:
                self.assertTrue(g.has_edge(r["source"], r["target"]))

    def test_trace_does_not_change_results(self) -> None:
        g = _toy_graph()
        a = dijkstra_single_source(g, "A", metric="distance", trace=False)
        b = dijkstra_single_source(g, "A", metric="distance", trace=True)
        self.assertEqual(a["dist"], b.dist)
        self.assertEqual(a["prev"], b.prev)
        self.assertEqual(a["settled"], b.settled)
        self.assertEqual(a["relaxed_edges"], b.relaxed_edges)


# ---------------------------------------------------------------------------
#  Graph 不变量保持
# ---------------------------------------------------------------------------


class TestGraphImmutability(unittest.TestCase):
    def test_dijkstra_does_not_modify_graph(self) -> None:
        g = _toy_graph()
        before_edges = g.get_all_edges()
        before_node_count = g.node_count
        before_edge_count = g.edge_count
        # 跑遍三种 metric
        for m in ("distance", "travel_time", "cost"):
            shortest_path(g, "A", "D", metric=m)
            dijkstra_single_source(g, "A", metric=m, trace=True)
        self.assertEqual(g.node_count, before_node_count)
        self.assertEqual(g.edge_count, before_edge_count)
        after_edges = g.get_all_edges()
        # 边权不应被改
        for e1, e2 in zip(before_edges, after_edges):
            self.assertEqual(e1.distance, e2.distance)
            self.assertEqual(e1.travel_time, e2.travel_time)
            self.assertEqual(e1.cost, e2.cost)


# ---------------------------------------------------------------------------
#  与独立穷举的一致性（小图）
# ---------------------------------------------------------------------------


class TestExhaustiveConsistency(unittest.TestCase):
    """对 5 节点以下的有向图，将 Dijkstra 结果与**独立穷举**的所有简单路径最小值比较。"""

    def _exhaustive_graph(self) -> LogisticsGraph:
        g = LogisticsGraph()
        for n in ("A", "B", "C", "D", "E"):
            g.add_node(_node(n))
        # 故意构造 8 条边，包含权重差异
        g.add_edge(_edge("A", "B", d=4, t=2, c=5))
        g.add_edge(_edge("A", "C", d=2, t=8, c=1))
        g.add_edge(_edge("B", "C", d=3, t=1, c=4))
        g.add_edge(_edge("B", "D", d=5, t=3, c=2))
        g.add_edge(_edge("C", "D", d=1, t=4, c=8))
        g.add_edge(_edge("C", "E", d=6, t=2, c=3))
        g.add_edge(_edge("D", "E", d=2, t=5, c=2))
        g.add_edge(_edge("A", "E", d=20, t=1, c=20))
        return g

    def test_matches_exhaustive_for_all_pairs(self) -> None:
        g = self._exhaustive_graph()
        nodes = ["A", "B", "C", "D", "E"]
        for src, tgt in itertools.permutations(nodes, 2):
            for m in ("distance", "travel_time", "cost"):
                r = shortest_path(g, src, tgt, metric=m)
                expected = _exhaustive_path_cost(g, src, tgt, m)
                if expected == inf:
                    self.assertFalse(r.reachable, msg=f"{src}→{tgt}@{m}")
                else:
                    self.assertAlmostEqual(
                        r.total_weight, expected, places=9,
                        msg=f"{src}→{tgt}@{m}: dijkstra={r.total_weight}, exh={expected}",
                    )


# ---------------------------------------------------------------------------
#  大场景（Phase 1 固定 35 节点 / 192 边）
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    __import__("pathlib").Path("config/scenario.json").is_file(),
    "scenario.json missing",
)
class TestFixedScenario(unittest.TestCase):
    """对配置驱动的固定场景做端到端验证。"""

    def test_all_pairs_reachable_in_strongly_connected(self) -> None:
        from logiroute.config import load_scenario
        b = load_scenario("config/scenario.json")
        g = b.graph
        # 任意两节点对都应可达
        for src, tgt in itertools.combinations(g.node_ids, 2):
            for m in ("distance", "travel_time", "cost"):
                r = shortest_path(g, src, tgt, metric=m)
                self.assertTrue(
                    r.reachable, msg=f"{src}→{tgt}@{m} not reachable in fixed scenario"
                )
                self.assertGreater(len(r.path), 1)

    def test_fixed_scenario_dijkstra_is_fast(self) -> None:
        from logiroute.config import load_scenario
        import time
        b = load_scenario("config/scenario.json")
        g = b.graph
        t0 = time.perf_counter()
        for src, tgt in itertools.combinations(g.node_ids, 2):
            shortest_path(g, src, tgt, metric="distance")
        elapsed = time.perf_counter() - t0
        # 35 节点 C(35,2)=595 对，期望 < 1 秒
        self.assertLess(elapsed, 1.0, msg=f"耗时 {elapsed:.3f}s")

    def test_path_edges_real_in_graph(self) -> None:
        from logiroute.config import load_scenario
        b = load_scenario("config/scenario.json")
        g = b.graph
        src, tgt = g.node_ids[0], g.node_ids[-1]
        r = shortest_path(g, src, tgt, metric="distance")
        for i in range(len(r.path) - 1):
            self.assertTrue(g.has_edge(r.path[i], r.path[i + 1]))


# ---------------------------------------------------------------------------
#  PathResult 字段
# ---------------------------------------------------------------------------


class TestPathResultFields(unittest.TestCase):
    def test_unreachable_has_empty_cross(self) -> None:
        g = LogisticsGraph()
        g.add_node(_node("A"))
        g.add_node(_node("B"))
        # 无边
        r = shortest_path(g, "A", "B", metric="distance")
        self.assertEqual(r.path, ())
        self.assertEqual(r.total_weight, inf)
        self.assertFalse(r.reachable)
        self.assertEqual(r.cross_metrics, {})

    def test_self_path_cross_metrics_zero(self) -> None:
        g = _toy_graph()
        r = shortest_path(g, "A", "A", metric="distance")
        self.assertEqual(r.cross_metrics, {"distance": 0.0, "travel_time": 0.0, "cost": 0.0})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
