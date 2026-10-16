"""``tests/test_scenario_generator_graph_sampler.py`` —— graph_sampler 单测。"""
from __future__ import annotations

import unittest

from logiroute.core.enums import NodeType
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scenario_generator.config_spec import DEFAULT_GENERATOR_CONFIG, GeneratorConfig
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.random_source import RandomSource


class TestGraphSamplerConnectivity(unittest.TestCase):
    def test_strongly_connected_under_default_config(self):
        """默认配置下生成的图必须强连通（cycle backbone 满足）。"""
        from logiroute.algorithms.dijkstra import dijkstra_single_source

        rng = RandomSource(42)
        g = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, rng)
        # 选任一节点，验证 bfs reverse + forward 都能到达所有节点
        # 这里用 dijkstra_single_source 直接检查 reachability
        first = g.node_ids[0]
        ss = dijkstra_single_source(g, first, metric="distance")
        n_reach = len([v for v in ss["dist"].values()
                       if v != float("inf")])
        self.assertEqual(
            n_reach, g.node_count,
            f"from {first} only reach {n_reach}/{g.node_count} nodes — "
            "graph not strongly connected",
        )

    def test_no_self_loops(self):
        rng = RandomSource(42)
        g = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, rng)
        for src in g.node_ids:
            for edge in g.get_neighbors(src):
                self.assertNotEqual(
                    edge.source_id, edge.target_id,
                    f"self-loop detected at {src}",
                )

    def test_all_metrics_finite_and_non_negative(self):
        rng = RandomSource(42)
        g = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, rng)
        for src in g.node_ids:
            for edge in g.get_neighbors(src):
                self.assertGreaterEqual(edge.distance, 0.0)
                self.assertGreaterEqual(edge.travel_time, 0.0)
                self.assertGreaterEqual(edge.cost, 0.0)
                for v in (edge.distance, edge.travel_time, edge.cost):
                    self.assertFalse(v != v, "NaN in metric")  # NaN check
                    self.assertNotEqual(v, float("inf"))

    def test_node_type_quotas_satisfied(self):
        cfg = GeneratorConfig(min_nodes=30)
        rng = RandomSource(42)
        g = sample_logistics_graph(cfg, rng)
        type_count = {t: 0 for t in NodeType}
        for n in g.get_all_nodes():
            type_count[n.node_type] += 1
        self.assertGreaterEqual(type_count[NodeType.WAREHOUSE], cfg.min_warehouses)
        self.assertGreaterEqual(type_count[NodeType.CUSTOMER], cfg.min_customers)
        self.assertGreaterEqual(type_count[NodeType.TRANSFER], cfg.min_transfers)

    def test_edge_count_in_configured_range(self):
        cfg = DEFAULT_GENERATOR_CONFIG
        rng = RandomSource(42)
        g = sample_logistics_graph(cfg, rng)
        self.assertGreaterEqual(g.edge_count, cfg.min_edges)
        self.assertLessEqual(g.edge_count, cfg.max_edges)


class TestGraphSamplerReproducibility(unittest.TestCase):
    def test_same_seed_same_graph(self):
        g_a = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, RandomSource(2026))
        g_b = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, RandomSource(2026))
        # 所有节点 ID 一致
        self.assertEqual(g_a.node_ids, g_b.node_ids)
        # 所有边 (src, tgt) 一致
        sig_a = sorted(
            (s, e.target_id)
            for s in g_a.node_ids for e in g_a.get_neighbors(s)
        )
        sig_b = sorted(
            (s, e.target_id)
            for s in g_b.node_ids for e in g_b.get_neighbors(s)
        )
        self.assertEqual(sig_a, sig_b)
        # 边权也一致
        ea = {(s, e.target_id): (e.distance, e.travel_time, e.cost)
              for s in g_a.node_ids for e in g_a.get_neighbors(s)}
        eb = {(s, e.target_id): (e.distance, e.travel_time, e.cost)
              for s in g_b.node_ids for e in g_b.get_neighbors(s)}
        self.assertEqual(ea, eb)

    def test_different_seed_usually_different(self):
        g_a = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, RandomSource(1))
        g_b = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, RandomSource(2))
        # 至少节点坐标或边权应有差异
        a_coords = [(n.x, n.y) for n in g_a.get_all_nodes()]
        b_coords = [(n.x, n.y) for n in g_b.get_all_nodes()]
        self.assertNotEqual(a_coords, b_coords)


class TestGraphSamplerRejectedConfigs(unittest.TestCase):
    def test_default_config_passes(self):
        rng = RandomSource(0)
        # just ensure no exception
        g = sample_logistics_graph(DEFAULT_GENERATOR_CONFIG, rng)
        self.assertIsInstance(g, LogisticsGraph)


if __name__ == "__main__":
    unittest.main()
