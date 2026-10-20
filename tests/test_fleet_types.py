"""Immutable fleet DTOs keep service identity separate from node visits."""
from __future__ import annotations
from dataclasses import FrozenInstanceError
from decimal import Decimal
import json
import unittest

from logiroute.scheduling.fleet_types import (
    FleetVisit, FleetLeg, FleetService, VehicleRoutePlan, FleetScheduleResult,
    FleetValidationReport, FleetStats, UnservedOrder,
)


class TestFleetTypes(unittest.TestCase):
    def test_visit_can_hold_two_distinct_orders(self) -> None:
        visit = FleetVisit('A', ('O1', 'O2'))
        self.assertEqual(visit.order_ids, ('O1', 'O2'))
        with self.assertRaises(FrozenInstanceError):
            visit.node_id = 'B'

    def test_quantities_serialize_as_exact_strings(self) -> None:
        event = FleetService('O', 1, 0, 1, 0, 1, 2, Decimal('1e-40'))
        self.assertEqual(json.loads(json.dumps(event.to_dict()))['load_after'], '1E-40')

    def test_result_distinguishes_validity_from_completeness(self) -> None:
        for valid, complete, expected in ((True, True, 'complete'), (True, False, 'partial'),
                                          (False, False, 'invalid')):
            report = FleetValidationReport(valid, complete, ())
            result = FleetScheduleResult('x', 'distance', (), (), (), FleetStats(), report)
            self.assertEqual(result.status, expected)
            self.assertEqual(result.is_feasible, valid and complete)

    def test_missing_validation_is_not_success(self) -> None:
        result = FleetScheduleResult('x', 'cost', (), (), (), FleetStats())
        self.assertEqual(result.status, 'unverified')
        self.assertFalse(result.is_feasible)

    def test_invalid_scalars_and_mutable_collections_rejected(self) -> None:
        for bad in (float('nan'), float('inf'), -1, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                FleetLeg('W', 'A', ('W', 'A'), bad, 1, 1)
        with self.assertRaises(ValueError):
            FleetVisit('A', ['O'])
        with self.assertRaises(ValueError):
            FleetScheduleResult('x', 'travel_time', (), (), (), FleetStats())
        with self.assertRaises(ValueError):
            UnservedOrder('O', ())

    def test_idle_route_has_no_service_or_load(self) -> None:
        route = VehicleRoutePlan('V', 'D', 'W', (FleetVisit('W'), FleetVisit('W')),
                                (FleetLeg('W', 'W', ('W',), 0, 0, 0),), (),
                                Decimal(10), Decimal(0), 0, 0, 0, 0, 0)
        self.assertEqual(route.served_order_ids, ())
        self.assertEqual(route.stop_sequence, ('W', 'W'))
        self.assertEqual(route.to_dict()['capacity'], '10')
