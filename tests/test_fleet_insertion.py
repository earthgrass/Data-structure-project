from __future__ import annotations
from decimal import Decimal
import unittest
from logiroute.core import Order
from logiroute.scheduling.fleet_paths import freeze_scenario, build_closure
from logiroute.scheduling.fleet_types import FleetVisit
from logiroute.scheduling.algorithms.fleet_insertion import assess_route, insertions, precedes, EvaluationCounters
from tests.fleet_fixtures import toy


class TestFleetInsertion(unittest.TestCase):
    def assess(self, raw, visits, objective='distance'):
        data = freeze_scenario(raw)
        return assess_route(data, build_closure(data, objective), 'V1', visits, EvaluationCounters())

    def test_same_site_independent_service_and_load(self) -> None:
        raw = toy([Order('O1', 'A', 40, 5, 100), Order('O2', 'A', 35, 0, 100),
                   Order('O3', 'B', 25, 0, 100)], (100,))
        visits = (FleetVisit('W'), FleetVisit('A', ('O1','O2')), FleetVisit('B', ('O3',)), FleetVisit('W'))
        route, errors = self.assess(raw, visits)
        self.assertEqual(errors, ())
        self.assertEqual(route.initial_load, Decimal(100))
        self.assertEqual([e.load_after for e in route.services], [Decimal(60), Decimal(25), Decimal(0)])
        self.assertEqual([e.service_start for e in route.services], [5, 6, 8])
        self.assertEqual(route.return_time, 10)
        self.assertEqual(route.total_distance, 3)

    def test_completion_after_deadline_is_allowed(self) -> None:
        route, errors = self.assess(toy([Order('O', 'A', 1, 0, 1)]),
            (FleetVisit('W'), FleetVisit('A', ('O',)), FleetVisit('W')))
        self.assertEqual(errors, ())
        self.assertEqual(route.services[0].service_end, 2)

    def test_tiny_overload_and_strict_time_boundary_rejected(self) -> None:
        raw = toy([Order('O1','A',100,0,100),Order('O2','A',Decimal('1e-40'),0,100)], (100,))
        _, errors = self.assess(raw, (FleetVisit('W'),FleetVisit('A',('O1','O2')),FleetVisit('W')))
        self.assertIn('capacity', errors)
        _, errors = self.assess(toy([Order('O','A',1,0,0.999999999999)]),
            (FleetVisit('W'),FleetVisit('A',('O',)),FleetVisit('W')))
        self.assertIn('time_window', errors)

    def test_full_replay_detects_delayed_existing_order(self) -> None:
        raw = toy([Order('O1','A',1,0,1), Order('O2','B',1,0,100)])
        _, errors = self.assess(raw, (FleetVisit('W'),FleetVisit('B',('O2',)),
                                     FleetVisit('A',('O1',)),FleetVisit('W')))
        self.assertIn('time_window', errors)

    def test_actual_main_path_time_is_used(self) -> None:
        raw=toy([Order('O','A',1,0,5)])
        raw.graph.get_edge('W','A').travel_time=10
        route, errors=self.assess(raw,(FleetVisit('W'),FleetVisit('A',('O',)),FleetVisit('W')))
        self.assertIsNone(route)
        self.assertIn('time_window', errors)

    def test_insertions_include_existing_visit_service_slots(self) -> None:
        visits=(FleetVisit('W'),FleetVisit('A',('O1',)),FleetVisit('W'))
        variants=list(insertions(visits,Order('O2','A',1,0,100)))
        self.assertEqual(len(variants),4)
        merged=[v for kind,i,j,v in variants if kind==0]
        self.assertEqual([v[1].order_ids for v in merged],[('O2','O1'),('O1','O2')])

    def test_each_comparison_field_has_approved_precedence(self) -> None:
        baseline=(1,100.,10.,'V2','O2',1,2,2)
        improvements=(0,99.,9.,'V1','O1',0,1,1)
        for index, value in enumerate(improvements):
            with self.subTest(index=index):
                candidate=list(baseline); candidate[index]=value
                self.assertTrue(precedes(tuple(candidate),baseline))
                self.assertFalse(precedes(baseline,tuple(candidate)))
        self.assertFalse(precedes(baseline,baseline))
