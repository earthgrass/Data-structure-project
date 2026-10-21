"""Independent tiny enumeration exposes heuristic limits instead of hiding them."""
from __future__ import annotations
import unittest
from logiroute.core import Order
from logiroute.scheduling import plan_fleet
from scripts.fleet_reference import enumerate_fleet, capacity_counterexample
from tests.fleet_fixtures import toy


class TestFleetExhaustive(unittest.TestCase):
    def test_known_tiny_optima_for_both_objectives(self) -> None:
        for raw,expected in ((toy([Order('O','A',1,0,100)]),2),
                             (toy(capacities=(1,1)),4),(toy([],(10,10)),0)):
            for objective in ('distance','cost'):
                with self.subTest(expected=expected,objective=objective):
                    exact=enumerate_fleet(raw,objective)
                    greedy=plan_fleet(raw,objective)
                    self.assertEqual(exact['best_objective'],expected)
                    self.assertTrue(greedy.is_feasible)
                    self.assertEqual(greedy.total_distance if objective=='distance' else greedy.total_cost,expected)

    def test_greedy_failure_does_not_mean_no_solution(self) -> None:
        raw=capacity_counterexample()
        for objective in ('distance','cost'):
            exact=enumerate_fleet(raw,objective)
            greedy=plan_fleet(raw,objective)
            self.assertEqual(exact['combinations_checked'],5040)
            self.assertEqual(exact['best_objective'],4)
            self.assertTrue(greedy.validation.valid)
            self.assertFalse(greedy.validation.complete)
            self.assertEqual(sum(len(route.services) for route in greedy.routes),5)
            self.assertEqual(greedy.search_outcome,'heuristic_incomplete')

    def test_reference_has_no_greedy_or_candidate_dependency(self) -> None:
        import ast,inspect
        import scripts.fleet_reference as reference
        for node in ast.walk(ast.parse(inspect.getsource(reference))):
            if isinstance(node,ast.ImportFrom):
                self.assertFalse('fleet_insertion' in (node.module or '') or
                                 'fleet_greedy' in (node.module or '') or
                                 'fleet_validator' in (node.module or ''))
