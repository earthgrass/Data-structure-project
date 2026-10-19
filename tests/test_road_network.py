"""V2 Phase 1: road contracts, corruption checks and hash-independent replay."""
from __future__ import annotations

from dataclasses import replace
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from logiroute.scenario_generator import GeneratorConfig, RandomSource, load_generator_config
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.road_validator import validate_road_network


SEEDS = (0, 1, 42, 100, 2026)


class TestRoadNetworkShape(unittest.TestCase):
    def graph(self, seed: int = 42, **overrides):
        config = GeneratorConfig(**overrides)
        return config, sample_logistics_graph(config, RandomSource(seed))

    def test_five_seeds_counts_ratio_and_connectivity(self) -> None:
        for seed in SEEDS:
            with self.subTest(seed=seed):
                cfg, graph = self.graph(seed)
                report = validate_road_network(graph, cfg)
                self.assertTrue(report.valid, report.violations)
                self.assertTrue(report.skeleton_complete)
                self.assertTrue(report.reachable_and_returnable)
                self.assertEqual(report.directed_edge_count,
                                 2 * report.bidirectional_road_count + report.one_way_road_count)
                self.assertEqual(report.physical_road_count,
                                 report.bidirectional_road_count + report.one_way_road_count)
                self.assertLessEqual(abs(report.bidirectional_ratio - cfg.bidirectional_ratio),
                                     0.5 / report.physical_road_count + 1e-12)

    def test_direction_ids_weights_and_independent_reverse_weights(self) -> None:
        cfg, graph = self.graph()
        roads = {}
        edge_ids = set()
        for edge in graph.get_all_edges():
            self.assertNotIn(edge.metadata['edge_id'], edge_ids)
            edge_ids.add(edge.metadata['edge_id'])
            roads.setdefault(edge.metadata['road_id'], []).append(edge)
            for value in (edge.distance, edge.travel_time, edge.cost):
                self.assertTrue(math.isfinite(value) and value >= 0)
        asymmetric = False
        for edges in roads.values():
            first = edges[0]
            if first.metadata['bidirectional']:
                self.assertEqual(len(edges), 2)
                self.assertEqual((edges[0].source_id, edges[0].target_id),
                                 (edges[1].target_id, edges[1].source_id))
                asymmetric |= edges[0].travel_time != edges[1].travel_time
            else:
                self.assertEqual(len(edges), 1)
                self.assertFalse(graph.has_edge(first.target_id, first.source_id))
        self.assertTrue(asymmetric)
        self.assertEqual(len(roads), validate_road_network(graph, cfg).physical_road_count)

    def test_stable_ids_across_replay(self) -> None:
        _, first = self.graph()
        _, second = self.graph()
        self.assertEqual(first.get_all_edges(), second.get_all_edges())

    def test_exact_physical_count(self) -> None:
        cfg, graph = self.graph(physical_road_count=80)
        report = validate_road_network(graph, cfg)
        self.assertTrue(report.valid, report.violations)
        self.assertEqual(report.physical_road_count, 80)
        self.assertEqual(report.bidirectional_road_count, 76)
        self.assertEqual(report.directed_edge_count, 156)

    def test_tight_budget_keeps_entire_tree(self) -> None:
        cfg, graph = self.graph(min_nodes=30, max_nodes=30, min_edges=58,
                                max_edges=60, physical_road_count=30)
        report = validate_road_network(graph, cfg)
        self.assertTrue(report.valid, report.violations)
        self.assertEqual(report.directed_edge_count, 59)
        self.assertEqual(report.skeleton_road_count, 29)

    def test_zero_ratio_conflicts_with_bidirectional_tree(self) -> None:
        with self.assertRaises(ValueError):
            self.graph(bidirectional_ratio=0.0)

    def test_all_bidirectional(self) -> None:
        cfg, graph = self.graph(bidirectional_ratio=1.0)
        report = validate_road_network(graph, cfg)
        self.assertTrue(report.valid, report.violations)
        self.assertEqual(report.one_way_road_count, 0)

    def test_target_rounding_is_reported(self) -> None:
        cfg, graph = self.graph(target_directed_edge_count=151)
        report = validate_road_network(graph, cfg)
        self.assertTrue(report.valid, report.violations)
        self.assertEqual(report.directed_edge_deviation, graph.edge_count - 151)
        self.assertEqual(report.directed_edge_deviation, -1)

    def test_mutated_missing_reverse_rejected(self) -> None:
        cfg, graph = self.graph()
        edge = next(e for e in graph.get_all_edges() if e.metadata['skeleton'])
        graph.remove_edge(edge.source_id, edge.target_id)
        report = validate_road_network(graph, cfg)
        self.assertFalse(report.valid)
        self.assertFalse(report.skeleton_complete)

    def test_duplicate_edge_id_rejected(self) -> None:
        cfg, graph = self.graph()
        edges = graph.get_all_edges()
        edges[1].metadata['edge_id'] = edges[0].metadata['edge_id']
        self.assertFalse(validate_road_network(graph, cfg).valid)

    def test_road_id_collision_rejected(self) -> None:
        cfg, graph = self.graph()
        edges = graph.get_all_edges()
        other = next(e for e in edges if e.metadata['road_id'] != edges[0].metadata['road_id'])
        other.metadata['road_id'] = edges[0].metadata['road_id']
        self.assertFalse(validate_road_network(graph, cfg).valid)

    def test_accidental_reverse_of_one_way_rejected(self) -> None:
        cfg, graph = self.graph()
        edge = next(e for e in graph.get_all_edges() if not e.metadata['bidirectional'])
        graph.add_edge(replace(edge, source_id=edge.target_id, target_id=edge.source_id,
                               metadata={**edge.metadata, 'edge_id': 'unexpected-reverse'}))
        self.assertFalse(validate_road_network(graph, cfg).valid)

    def test_nonfinite_and_negative_weights_rejected_independently(self) -> None:
        for field in ('distance', 'travel_time', 'cost'):
            for invalid in (float('nan'), float('inf'), -1.0):
                with self.subTest(field=field, invalid=invalid):
                    cfg, graph = self.graph()
                    setattr(graph.get_all_edges()[0], field, invalid)
                    self.assertFalse(validate_road_network(graph, cfg).valid)


class TestRoadConfiguration(unittest.TestCase):
    def test_packaged_json_loads_and_preserves_directed_budget(self) -> None:
        root = Path(__file__).resolve().parents[1]
        cfg = load_generator_config(root / 'src/logiroute/scenario_generator/road_defaults.json')
        self.assertEqual(cfg, GeneratorConfig())

    def test_custom_json_and_ambiguous_edge_count(self) -> None:
        with tempfile.TemporaryDirectory(prefix='logiroute-road-config-') as directory:
            path = Path(directory) / 'roads.json'
            path.write_text(json.dumps({'physical_road_count': 80}), encoding='utf-8')
            cfg = load_generator_config(path)
            self.assertEqual(cfg.road_quota(50), (80, 76))
            for value in ({'edge_count': 80}, [], {'max_extra_edges_per_node': 4}):
                path.write_text(json.dumps(value), encoding='utf-8')
                with self.subTest(value=value), self.assertRaises(ValueError):
                    load_generator_config(path)

    def test_conflicting_or_invalid_configs_rejected(self) -> None:
        cases = (
            {'min_edges': 100, 'max_edges': 90},
            {'max_edges': 50},
            {'physical_road_count': 20},
            {'physical_road_count': 2000},
            {'physical_road_count': 80, 'target_directed_edge_count': 155},
            {'target_directed_edge_count': 999},
            {'bidirectional_ratio': float('nan')},
            {'bidirectional_ratio': 1.01},
            {'physical_road_count': True},
            {'physical_road_count': 80.5},
            {'target_directed_edge_count': False},
            {'min_edges': 50.5},
            {'max_extra_edges_per_node': 4},
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                cfg = GeneratorConfig(**values)
                sample_logistics_graph(cfg, RandomSource(42))

    def test_directed_budget_retains_legacy_meaning(self) -> None:
        cfg = GeneratorConfig(min_edges=100, max_edges=120, max_nodes=50)
        graph = sample_logistics_graph(cfg, RandomSource(42))
        self.assertGreaterEqual(graph.edge_count, 100)
        self.assertLessEqual(graph.edge_count, 120)

    def test_geometry_parameters_reject_illegal_ranges(self) -> None:
        cases = ({'speed_range': (0, 10)}, {'unit_cost_range': (-1, 1)},
                 {'coordinate_range': (float('nan'), 100)},
                 {'distance_factor_range': (1, 0.5)}, {'minimum_distance': float('inf')})
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                GeneratorConfig(**values)

    def test_target_and_physical_counts_can_agree(self) -> None:
        cfg = GeneratorConfig(physical_road_count=80, target_directed_edge_count=156)
        report = validate_road_network(sample_logistics_graph(cfg, RandomSource(0)), cfg)
        self.assertTrue(report.valid, report.violations)
        self.assertEqual(report.directed_edge_deviation, 0)


class TestRoadCrossProcessReplay(unittest.TestCase):
    def test_five_seeds_full_scenario_identical_across_hash_seeds(self) -> None:
        script = '''
import json
from dataclasses import asdict
from logiroute.scenario_generator import generate_scenario
out = []
for seed in (0, 1, 42, 100, 2026):
    bundle, backbone = generate_scenario(seed=seed)
    out.append({'seed': seed, 'nodes': [asdict(n) for n in bundle.graph.get_all_nodes()],
                'edges': [asdict(e) for e in bundle.graph.get_all_edges()],
                'orders': [asdict(o) for o in bundle.orders],
                'vehicles': [asdict(v) for v in bundle.vehicles],
                'couriers': [asdict(c) for c in bundle.couriers],
                'simulation': bundle.simulation, 'optimization': bundle.optimization,
                'metadata': bundle.metadata, 'name': bundle.name, 'mode': bundle.mode,
                'backbone': backbone})
print(json.dumps(out, ensure_ascii=True))
'''
        outputs = []
        for hash_seed in ('1', '2', '73'):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed,
                       PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
            result = subprocess.run([sys.executable, '-B', '-c', script], env=env,
                                    capture_output=True, text=True, timeout=60, check=True)
            outputs.append(json.loads(result.stdout))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])


if __name__ == '__main__':
    unittest.main()
