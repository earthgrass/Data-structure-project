"""Handmade witnesses and hostile replacements; no planner generates these."""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch
from logiroute.core import Order, OrderStatus
from logiroute.scheduling.fleet_types import (
    FleetVisit, FleetLeg, FleetService, VehicleRoutePlan, FleetScheduleResult,
    FleetStats, FleetValidationReport, UnservedOrder,
)
from logiroute.scheduling.fleet_validator import validate_fleet
from tests.fleet_fixtures import toy


def witness():
    raw=toy([Order('O1','A',2,0,100),Order('O2','A',3,0,100)])
    route=VehicleRoutePlan('V1','D1','W',
        (FleetVisit('W'),FleetVisit('A',('O1','O2')),FleetVisit('W')),
        (FleetLeg('W','A',('W','A'),1,1,1),FleetLeg('A','W',('A','W'),1,1,1)),
        (FleetService('O1',1,0,1,0,1,2,Decimal(3)),
         FleetService('O2',1,1,1,0,2,3,Decimal(0))),
        Decimal(10),Decimal(5),0,4,2,2,2)
    return raw,FleetScheduleResult('toy','distance',(route,),(),(),FleetStats())


class TestFleetValidator(unittest.TestCase):
    def test_handmade_same_site_witness(self) -> None:
        raw,result=witness()
        report=validate_fleet(raw,result)
        self.assertTrue(report.valid,report.violations)
        self.assertTrue(report.complete)
        self.assertFalse(report.return_deadline_checked)

    def test_does_not_call_candidate_replay(self) -> None:
        raw,result=witness()
        with patch('logiroute.scheduling.algorithms.fleet_insertion.assess_route',side_effect=AssertionError('not independent')):
            self.assertTrue(validate_fleet(raw,result).valid)

    def test_ignores_forged_success_flag(self) -> None:
        raw,result=witness()
        bad=replace(result.routes[0],return_time=0)
        result=replace(result,routes=(bad,),validation=FleetValidationReport(True,True,()))
        self.assertFalse(validate_fleet(raw,result).valid)

    def test_metric_capacity_depot_and_binding_tampering(self) -> None:
        raw,result=witness(); route=result.routes[0]
        for changes in ({'total_distance':1}, {'total_cost':1}, {'total_travel_time':1},
                        {'capacity':Decimal(11)}, {'initial_load':Decimal(4)},
                        {'depot_id':'A'}, {'courier_id':'UNKNOWN'}, {'vehicle_id':'UNKNOWN'},
                        {'return_time':5}, {'departure_time':1}):
            with self.subTest(changes=changes):
                self.assertFalse(validate_fleet(raw,replace(result,routes=(replace(route,**changes),))).valid)

    def test_service_identity_time_load_and_location_tampering(self) -> None:
        raw,result=witness(); route=result.routes[0]
        event=route.services[0]
        for changes in ({'order_id':'O2'}, {'order_id':'UNKNOWN'}, {'visit_index':0},
                        {'service_index':1}, {'arrival_time':0}, {'service_start':0},
                        {'service_end':3}, {'waiting_time':1}, {'load_after':Decimal(4)}):
            with self.subTest(changes=changes):
                bad=replace(route,services=(replace(event,**changes),route.services[1]))
                self.assertFalse(validate_fleet(raw,replace(result,routes=(bad,))).valid)
        bad=replace(route,visits=(FleetVisit('W'),FleetVisit('B',('O1','O2')),FleetVisit('W')))
        self.assertFalse(validate_fleet(raw,replace(result,routes=(bad,))).valid)

    def test_reverse_missing_and_nonoptimal_paths_rejected(self) -> None:
        raw,result=witness(); route=result.routes[0]
        for path in (('A','W'),(),('W','B','A')):
            with self.subTest(path=path):
                leg=replace(route.legs[0],path=path)
                bad=replace(route,legs=(leg,route.legs[1]))
                self.assertFalse(validate_fleet(raw,replace(result,routes=(bad,))).valid)
        raw.graph.remove_edge('W','A')
        self.assertFalse(validate_fleet(raw,result).valid)

    def test_duplicate_cross_vehicle_service_and_missing_route(self) -> None:
        raw,result=witness()
        from logiroute.core import Vehicle,Courier
        raw.vehicles.append(Vehicle('V2',10,current_node_id='W'))
        raw.couriers.append(Courier('D2','D2','V2'))
        duplicate=replace(result.routes[0],vehicle_id='V2',courier_id='D2')
        self.assertFalse(validate_fleet(raw,replace(result,routes=result.routes+(duplicate,))).valid)
        self.assertFalse(validate_fleet(raw,result).valid)

    def test_unserved_partition_unknown_overlap_and_false_reason(self) -> None:
        raw,result=witness()
        for item in (UnservedOrder('O1',('capacity',)),UnservedOrder('UNKNOWN',('capacity',))):
            self.assertFalse(validate_fleet(raw,replace(result,unserved_orders=(item,))).valid)
        empty=VehicleRoutePlan('V1','D1','W',(FleetVisit('W'),FleetVisit('W')),
            (FleetLeg('W','W',('W',),0,0,0),),(),Decimal(10),Decimal(0),0,0,0,0,0)
        partial=replace(result,routes=(empty,),unserved_orders=(UnservedOrder('O1',('capacity',)),
                                                              UnservedOrder('O2',('capacity',))))
        self.assertFalse(validate_fleet(raw,partial).valid)

    def test_real_partial_result_with_strict_capacity(self) -> None:
        raw,result=witness()
        raw.orders.append(Order('O3','A',Decimal('5.0000000000000000000000000000000000000001'),0,100))
        partial=replace(result,unserved_orders=(UnservedOrder('O3',('capacity',)),))
        report=validate_fleet(raw,partial)
        self.assertTrue(report.valid,report.violations)
        self.assertFalse(report.complete)

    def test_nonpending_assigned_order_rejected(self) -> None:
        raw,result=witness()
        raw.orders[0].status=OrderStatus.DELIVERED
        self.assertFalse(validate_fleet(raw,result).valid)

    def test_actual_path_time_cannot_be_substituted(self) -> None:
        raw,result=witness()
        raw.graph.get_edge('W','A').travel_time=20
        self.assertFalse(validate_fleet(raw,result).valid)

    def test_objective_and_fingerprint_mismatch(self) -> None:
        raw,result=witness()
        self.assertFalse(validate_fleet(raw,result,objective='cost').valid)
        self.assertFalse(validate_fleet(raw,replace(result,input_fingerprint='forged')).valid)
