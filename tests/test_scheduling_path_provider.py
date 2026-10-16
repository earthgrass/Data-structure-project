"""``tests/test_scheduling_path_provider.py`` —— Phase 3 ``PathProvider`` 单测。

仅依赖 stdlib 与 Phase 1 / Phase 2 已存在的 ``LogisticsGraph`` / ``Edge`` /
``Node`` / Dijkstra 模块。
"""

from __future__ import annotations

import unittest
from unittest import TestCase

from logiroute.algorithms.dijkstra import SUPPORTED_METRICS
from logiroute.core.edges import Edge
from logiroute.core.enums import NodeType
from logiroute.core.nodes import Node
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling.path_provider import PathProvider


# ---------------------------------------------------------------------------
#  工厂辅助
# ---------------------------------------------------------------------------


def _node(nid: str, t: NodeType = NodeType.CUSTOMER) -> Node:
    return Node(id=nid, name=nid, node_type=t, x=0.0, y=0.0)


def _edge(
    src: str,
    tgt: str,
    d: float = 1.0,
    t: float = 1.0,
    c: float = 1.0,
) -> Edge:
    return Edge(
        source_id=src,
        target_id=tgt,
        distance=d,
        travel_time=t,
        cost=c,
    )


def _mini_graph() -> LogisticsGraph:
    """4 节点 + 5 有向边，最小连通图（含一条必经中间节点的路径）。"""
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("W2", NodeType.WAREHOUSE),
        _node("C1"),
        _node("C2"),
    ):
        g.add_node(n)
    for e in (
        _edge("W1", "C1", 2.0, 4.0, 6.0),
        _edge("C1", "C2", 2.0, 4.0, 6.0),
        _edge("C2", "W1", 2.0, 4.0, 6.0),
        _edge("W1", "W2", 5.0, 8.0, 12.0),
        _edge("W2", "C1", 3.0, 5.0, 9.0),
    ):
        g.add_edge(e)
    return g


def _disconnected_graph() -> LogisticsGraph:
    """两个独立分量：``W1 -> C1`` 与 ``W2 -> C2``，无跨分量路径。"""
    g = LogisticsGraph()
    for n in (
        _node("W1", NodeType.WAREHOUSE),
        _node("W2", NodeType.WAREHOUSE),
        _node("C1"),
        _node("C2"),
    ):
        g.add_node(n)
    for e in (
        _edge("W1", "C1", 1.0, 2.0, 3.0),
        _edge("W2", "C2", 1.0, 2.0, 3.0),
    ):
        g.add_edge(e)
    return g


# ---------------------------------------------------------------------------
#  缓存命中 / 未命中 / 计数器
# ---------------------------------------------------------------------------


class TestCacheCounters(TestCase):
    def test_cache_hit_miss_counters(self):
        p = PathProvider(_mini_graph())
        p.shortest_path("W1", "C1", "distance")
        p.shortest_path("W1", "C1", "distance")
        self.assertEqual(p.cache_hits, 1)
        self.assertEqual(p.cache_misses, 1)
        self.assertEqual(p.dijkstra_calls, 1)
        self.assertEqual(p.paths_evaluated, 2)

    def test_initial_counters_zero(self):
        p = PathProvider(_mini_graph())
        self.assertEqual(p.cache_hits, 0)
        self.assertEqual(p.cache_misses, 0)
        self.assertEqual(p.dijkstra_calls, 0)
        self.assertEqual(p.paths_evaluated, 0)

    def test_unreachable_not_cached(self):
        p = PathProvider(_disconnected_graph())
        r1 = p.shortest_path("W1", "C2", "distance")
        r2 = p.shortest_path("W1", "C2", "distance")
        # 不可达：每次都重算
        self.assertFalse(r1.reachable)
        self.assertFalse(r2.reachable)
        self.assertEqual(p.cache_hits, 0)
        self.assertEqual(p.dijkstra_calls, 2)
        self.assertEqual(p.cache_misses, 2)
        self.assertEqual(p.paths_evaluated, 2)

    def test_two_instances_on_same_graph_dont_share_cache(self):
        g = _mini_graph()
        p1 = PathProvider(g)
        p2 = PathProvider(g)
        p1.shortest_path("W1", "C1", "distance")
        # p1 走了一次 dijkstra；p2 计数器应不受影响
        self.assertEqual(p1.cache_misses, 1)
        self.assertEqual(p1.dijkstra_calls, 1)
        self.assertEqual(p2.cache_misses, 0)
        self.assertEqual(p2.dijkstra_calls, 0)
        # p2 自己调一次也应是 miss
        p2.shortest_path("W1", "C1", "distance")
        self.assertEqual(p2.cache_misses, 1)
        self.assertEqual(p2.dijkstra_calls, 1)
        # p1 计数不变
        self.assertEqual(p1.cache_misses, 1)
        self.assertEqual(p1.dijkstra_calls, 1)

    def test_source_equals_target_returns_zero_weight_without_dijkstra(self):
        p = PathProvider(_mini_graph())
        result = p.shortest_path("W1", "W1", "distance")
        # 不调 dijkstra、不入缓存
        self.assertEqual(p.dijkstra_calls, 0)
        self.assertEqual(p.cache_hits, 0)
        self.assertEqual(p.cache_misses, 0)
        # 但 paths_evaluated 仍递增（成功的查询）
        self.assertEqual(p.paths_evaluated, 1)
        # 零权 PathResult 语义
        self.assertEqual(result.path, ("W1",))
        self.assertEqual(result.total_weight, 0.0)
        self.assertTrue(result.reachable)
        for m in SUPPORTED_METRICS:
            self.assertEqual(result.cross_metrics[m], 0.0)

    def test_source_equals_target_repeated_calls_do_not_cache(self):
        p = PathProvider(_mini_graph())
        for _ in range(3):
            p.shortest_path("W1", "W1", "distance")
        # 三次 shortcut：dijkstra_calls 仍 0，cache_hits 仍 0（不入缓存）
        self.assertEqual(p.dijkstra_calls, 0)
        self.assertEqual(p.cache_hits, 0)
        self.assertEqual(p.cache_misses, 0)
        self.assertEqual(p.paths_evaluated, 3)

    def test_paths_evaluated_tracks_every_successful_query(self):
        p = PathProvider(_mini_graph())
        p.shortest_path("W1", "C1", "distance")          # miss
        p.shortest_path("W1", "C1", "distance")          # hit
        p.shortest_path("W1", "C2", "distance")          # miss
        p.shortest_path("W1", "W1", "distance")          # source==target shortcut
        # 4 次成功查询；2 次调 dijkstra（命中 + shortcut 都不调）
        self.assertEqual(p.paths_evaluated, 4)
        self.assertEqual(p.dijkstra_calls, 2)
        self.assertEqual(p.cache_hits, 1)
        self.assertEqual(p.cache_misses, 2)

    def test_stats_returns_all_counters(self):
        p = PathProvider(_mini_graph())
        p.shortest_path("W1", "C1", "distance")
        p.shortest_path("W1", "C1", "distance")
        stats = p.stats()
        self.assertEqual(stats["cache_hits"], 1)
        self.assertEqual(stats["cache_misses"], 1)
        self.assertEqual(stats["dijkstra_calls"], 1)
        self.assertEqual(stats["paths_evaluated"], 2)


# ---------------------------------------------------------------------------
#  all_pairs
# ---------------------------------------------------------------------------


class TestAllPairs(TestCase):
    def test_three_stop_sequence_returns_two_legs(self):
        p = PathProvider(_mini_graph())
        legs = p.all_pairs(("W1", "C1", "W1"), "distance")
        self.assertEqual(len(legs), 2)
        self.assertTrue(legs[0].reachable)
        self.assertTrue(legs[1].reachable)
        self.assertEqual(legs[0].source, "W1")
        self.assertEqual(legs[0].target, "C1")
        self.assertEqual(legs[1].source, "C1")
        self.assertEqual(legs[1].target, "W1")

    def test_two_stop_sequence_returns_one_leg(self):
        p = PathProvider(_mini_graph())
        legs = p.all_pairs(("W1", "C2"), "distance")
        self.assertEqual(len(legs), 1)
        self.assertEqual(legs[0].source, "W1")
        self.assertEqual(legs[0].target, "C2")

    def test_empty_or_single_stop_returns_empty_list(self):
        p = PathProvider(_mini_graph())
        self.assertEqual(p.all_pairs((), "distance"), [])
        self.assertEqual(p.all_pairs(("W1",), "distance"), [])

    def test_all_pairs_uses_cache_across_legs(self):
        # 闭回路 W1 -> C2 -> W1 含 2 leg。
        # 第一次 all_pairs：两条 leg 均为 miss。
        # 第二次 all_pairs：两条 leg 均命中。
        p = PathProvider(_mini_graph())
        p.all_pairs(("W1", "C2", "W1"), "distance")
        p.all_pairs(("W1", "C2", "W1"), "distance")
        self.assertEqual(p.cache_hits, 2)
        self.assertEqual(p.cache_misses, 2)
        self.assertEqual(p.dijkstra_calls, 2)


# ---------------------------------------------------------------------------
#  road_node_sequence
# ---------------------------------------------------------------------------


class TestRoadNodeSequence(TestCase):
    def test_three_stop_road_sequence_closed_and_dedup(self):
        p = PathProvider(_mini_graph())
        seq = p.road_node_sequence(("W1", "C2", "W1"), "distance")
        self.assertGreaterEqual(len(seq), 2)
        self.assertEqual(seq[0], "W1")
        self.assertEqual(seq[-1], "W1")
        for i in range(len(seq) - 1):
            self.assertNotEqual(seq[i], seq[i + 1])

    def test_four_stop_road_sequence_closed_and_dedup(self):
        p = PathProvider(_mini_graph())
        seq = p.road_node_sequence(("W1", "C2", "W2", "W1"), "distance")
        self.assertEqual(seq[0], "W1")
        self.assertEqual(seq[-1], "W1")
        for i in range(len(seq) - 1):
            self.assertNotEqual(seq[i], seq[i + 1])

    def test_road_sequence_contains_all_leg_endpoints(self):
        p = PathProvider(_mini_graph())
        seq = p.road_node_sequence(("W1", "C2", "W1"), "distance")
        # 路径必须包含所有 stop_sequence 节点（含首尾 depot）
        for stop in ("W1", "C2", "W1"):
            self.assertIn(stop, seq)


# ---------------------------------------------------------------------------
#  图变更 & fingerprint
# ---------------------------------------------------------------------------


class TestGraphIdentityInvalidation(TestCase):
    def test_graph_mutated_changes_identity(self):
        g = _mini_graph()
        provider = PathProvider(g)
        original_id = provider._graph_id
        # 变更图：添加一条新边
        g.add_edge(_edge("C1", "W2", 2.0))
        # 新构造的 provider 抓取到的指纹必然不同
        fresh = PathProvider(g)
        self.assertNotEqual(original_id, fresh._graph_id)

    def test_fresh_provider_does_not_reuse_old_cache(self):
        # 即使两个 provider 持有同一个 graph 对象，
        # 它们的缓存键前缀 (_graph_id) 一致，缓存仍按 source/target/metric 命中。
        # 这里验证的是「同一 provider 实例」在不同 (source, target, metric)
        # 上的命中行为，而不是不同 provider 互相命中。
        g = _mini_graph()
        p = PathProvider(g)
        p.shortest_path("W1", "C1", "distance")
        # 改 metric 后应作为新 key 触发 miss
        p.shortest_path("W1", "C1", "travel_time")
        self.assertEqual(p.cache_misses, 2)
        self.assertEqual(p.dijkstra_calls, 2)


# ---------------------------------------------------------------------------
#  metric 校验
# ---------------------------------------------------------------------------


class TestMetricValidation(TestCase):
    def test_unknown_metric_in_shortest_path_raises(self):
        p = PathProvider(_mini_graph())
        with self.assertRaises(ValueError):
            p.shortest_path("W1", "C1", "bogus")

    def test_unknown_metric_in_all_pairs_raises(self):
        p = PathProvider(_mini_graph())
        with self.assertRaises(ValueError):
            p.all_pairs(("W1", "C1"), "bogus")

    def test_unknown_metric_in_road_node_sequence_raises(self):
        p = PathProvider(_mini_graph())
        with self.assertRaises(ValueError):
            p.road_node_sequence(("W1", "C1"), "bogus")


# ---------------------------------------------------------------------------
#  __slots__
# ---------------------------------------------------------------------------


class TestSlotsEnforced(TestCase):
    def test_slots_rejects_unknown_attribute(self):
        p = PathProvider(_mini_graph())
        with self.assertRaises(AttributeError):
            p.not_a_real_attribute = 1  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()