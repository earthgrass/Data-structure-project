"""Dijkstra 距离闭包与有界单车 TSP 的专项回归测试。"""

from __future__ import annotations

import unittest
import json
from pathlib import Path

from logiroute.config.loader import ConfigError, load_scenario_from_dict
from logiroute.algorithms.dijkstra import shortest_path
from logiroute.core.enums import NodeType
from logiroute.graph.logistics_graph import LogisticsGraph
from logiroute.scheduling.algorithms.tsp import solve_tsp
from logiroute.scheduling.path_provider import PathProvider
from tests.test_scheduling_two_opt import _ctx, _edge, _node, _order


def _graph(edges: tuple[tuple[str, str, float], ...]) -> LogisticsGraph:
    graph = LogisticsGraph()
    for node in (
        _node("W1", NodeType.WAREHOUSE),
        _node("A"), _node("B"), _node("T", NodeType.TRANSFER),
    ):
        graph.add_node(node)
    for source, target, distance in edges:
        graph.add_edge(_edge(source, target, distance, distance, distance))
    return graph


class TestTspDistanceClosure(unittest.TestCase):
    def test_matrix_uses_full_graph_and_direction(self) -> None:
        graph = _graph((
            ("W1", "T", 1.0), ("T", "A", 1.0),
            ("A", "B", 1.0), ("B", "A", 4.0),
            ("B", "W1", 1.0), ("A", "W1", 1.0),
            ("W1", "B", 5.0),
        ))
        provider = PathProvider(graph)
        from_warehouse = provider.shortest_paths_from(
            "W1", ("A", "B"), "distance"
        )
        self.assertEqual(from_warehouse["A"].path, ("W1", "T", "A"))
        self.assertEqual(from_warehouse["A"].total_weight, 2.0)
        self.assertEqual(provider.dijkstra_calls, 1)
        backward = provider.shortest_paths_from("A", ("W1",), "distance")
        self.assertEqual(backward["W1"].total_weight, 1.0)
        self.assertEqual(provider.dijkstra_calls, 2)
        self.assertNotEqual(
            from_warehouse["A"].total_weight, backward["W1"].total_weight
        )
        for metric in ("distance", "cost"):
            result = provider.shortest_paths_from("W1", ("A", "B"), metric)
            for target in ("A", "B"):
                reference = shortest_path(graph, "W1", target, metric)
                self.assertEqual(result[target].path, reference.path)
                self.assertEqual(result[target].cross_metrics, reference.cross_metrics)

    def test_small_tsp_finds_best_closed_tour(self) -> None:
        graph = _graph((
            ("W1", "A", 4.0), ("W1", "B", 1.0),
            ("A", "B", 1.0), ("B", "A", 1.0),
            ("A", "W1", 1.0), ("B", "W1", 4.0),
        ))
        orders = [_order("OA", "A"), _order("OB", "B")]
        ctx = _ctx(graph, orders=orders, initial_time=0.0, service_time=0.0)
        plan = solve_tsp(ctx, orders)
        self.assertEqual(plan.stop_sequence, ("W1", "B", "A", "W1"))
        self.assertEqual(plan.main_objective_total, 3.0)
        self.assertTrue(plan.notes["optimality_proven"])
        self.assertTrue(plan.is_feasible)

    def test_time_window_can_require_non_greedy_first_stop(self) -> None:
        graph = _graph((
            ("W1", "A", 1.0), ("W1", "B", 0.5),
            ("A", "B", 1.0), ("B", "A", 2.0),
            ("A", "W1", 1.0), ("B", "W1", 1.0),
        ))
        orders = [
            _order("OA", "A", tw_end=1.5),
            _order("OB", "B", tw_end=100.0),
        ]
        ctx = _ctx(graph, orders=orders, initial_time=0.0, service_time=0.0)
        plan = solve_tsp(ctx, orders)
        self.assertEqual(plan.stop_sequence, ("W1", "A", "B", "W1"))
        self.assertEqual(len(plan.served_order_ids), 2)

    def test_same_destination_keeps_both_order_ids(self) -> None:
        graph = _graph((("W1", "A", 1.0), ("A", "W1", 1.0)))
        orders = [_order("OA1", "A"), _order("OA2", "A")]
        ctx = _ctx(graph, orders=orders, initial_time=0.0, service_time=0.0)
        plan = solve_tsp(ctx, orders)
        self.assertEqual(plan.stop_sequence, ("W1", "A", "A", "W1"))
        self.assertCountEqual(plan.served_order_ids, ("OA1", "OA2"))
        self.assertEqual(ctx.path_provider.dijkstra_calls, 2)

    def test_impossible_window_reports_unserved(self) -> None:
        graph = _graph((
            ("W1", "A", 1.0), ("A", "W1", 1.0),
            ("W1", "B", 2.0), ("B", "W1", 1.0),
            ("A", "B", 1.0), ("B", "A", 1.0),
        ))
        orders = [
            _order("OA", "A", tw_end=100.0),
            _order("OB", "B", tw_end=0.5),
        ]
        ctx = _ctx(graph, orders=orders, initial_time=0.0, service_time=0.0)
        plan = solve_tsp(ctx, orders)
        self.assertEqual(plan.served_order_ids, ("OA",))
        self.assertEqual(plan.notes["unserved_orders"][0]["order_id"], "OB")
        self.assertFalse(plan.notes["optimality_proven"])

    def test_narrow_beam_does_not_claim_exact_optimum(self) -> None:
        graph = _graph((
            ("W1", "A", 1.0), ("A", "W1", 1.0),
            ("W1", "B", 2.0), ("B", "W1", 1.0),
            ("A", "B", 1.0), ("B", "A", 1.0),
        ))
        orders = [_order("OA", "A"), _order("OB", "B")]
        ctx = _ctx(graph, orders=orders, initial_time=0.0, service_time=0.0)
        ctx.scenario.optimization = {"tsp_beam_width": 1}
        plan = solve_tsp(ctx, orders)
        self.assertEqual(len(plan.served_order_ids), 2)
        self.assertFalse(plan.notes["optimality_proven"])

    def test_loader_rejects_invalid_beam_width(self) -> None:
        scenario = json.loads(Path("config/scenario.json").read_text(encoding="utf-8"))
        scenario["optimization"]["tsp_beam_width"] = 0
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(scenario)


if __name__ == "__main__":
    unittest.main()
