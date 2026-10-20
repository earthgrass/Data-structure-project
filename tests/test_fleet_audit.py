"""Final boundary audit: truthful status, immutable DTOs and finite export."""
from __future__ import annotations
from dataclasses import replace
import unittest
from logiroute.scheduling.fleet_types import FleetScheduleResult,FleetStats,FleetValidationReport
from logiroute.scheduling.algorithms.fleet_insertion import precedes
from tests.test_fleet_validator import witness


class TestFleetAudit(unittest.TestCase):
    def test_invalid_result_is_not_a_search_failure(self) -> None:
        result=FleetScheduleResult('x','distance',(),(),(),FleetStats(),
                                  FleetValidationReport(False,False,('bad',)))
        self.assertEqual(result.search_outcome,'invalid_result')

    def test_validation_flags_cannot_contradict_violations(self) -> None:
        with self.assertRaises(ValueError):
            FleetValidationReport(True,False,('bad',))

    def test_nested_public_records_are_immutable_and_typed(self) -> None:
        for kwargs in ({'unavailable_vehicles':(['V',('bad',)],)},
                       {'selection_trace':(['O','V',0,1,0],)},
                       {'input_fingerprint':42}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                FleetScheduleResult('x','distance',(),(),kwargs.get('unavailable_vehicles',()),
                    FleetStats(),selection_trace=kwargs.get('selection_trace',()),
                    input_fingerprint=kwargs.get('input_fingerprint',''))

    def test_global_metric_overflow_is_rejected_instead_of_exported(self) -> None:
        _,result=witness()
        route=replace(result.routes[0],total_distance=1e308)
        with self.assertRaises(ValueError):
            replace(result,routes=(route,route))

    def test_earlier_comparison_field_overrides_all_later_fields(self) -> None:
        self.assertTrue(precedes((0,100.,999.,'Z','Z',1,99,99),(1,1.,0.,'A','A',0,0,0)))
        self.assertTrue(precedes((0,1.,999.,'Z','Z',1,99,99),(0,2.,0.,'A','A',0,0,0)))
