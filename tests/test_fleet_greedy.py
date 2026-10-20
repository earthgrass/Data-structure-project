"""Fixed fleet acceptance examples; objectives share the exact same inputs."""
from __future__ import annotations
from decimal import Decimal
import unittest
from unittest.mock import patch
from logiroute.core import Order, OrderPriority, OrderStatus, CourierStatus, VehicleStatus
from logiroute.scheduling.fleet_planner import plan_fleet
from logiroute.scheduling.fleet_paths import fingerprint_scenario
from tests.fleet_fixtures import toy


class TestFleetGreedy(unittest.TestCase):
    def test_public_entry_keeps_legacy_entry_available(self) -> None:
        from logiroute.scheduling import plan_fleet as public, plan_deliveries
        self.assertIs(public,plan_fleet)
        self.assertTrue(callable(plan_deliveries))

    def check(self, raw, objective='distance'):
        before=fingerprint_scenario(raw)
        result=plan_fleet(raw,objective)
        self.assertTrue(result.validation.valid,result.validation.violations)
        self.assertEqual(before,fingerprint_scenario(raw))
        return result

    def test_one_car_one_order(self) -> None:
        r=self.check(toy([Order('O1','A',1,0,100)]))
        self.assertEqual(r.routes[0].stop_sequence,('W','A','W'))
        self.assertEqual((r.total_distance,r.total_travel_time,r.total_cost),(2,2,2))
        self.assertEqual(r.routes[0].return_time,3)
        self.assertTrue(r.is_feasible)

    def test_two_cars_one_order_stable_tie_and_idle_route(self) -> None:
        r=self.check(toy([Order('O1','A',1,0,100)],(10,10)))
        self.assertEqual(r.routes[0].served_order_ids,('O1',))
        self.assertEqual(r.routes[1].stop_sequence,('W','W'))
        self.assertEqual(r.routes[1].initial_load,Decimal(0))

    def test_global_increment_prefers_existing_route(self) -> None:
        r=self.check(toy(capacities=(10,10)))
        self.assertEqual(r.routes[0].stop_sequence,('W','B','A','W'))
        self.assertEqual(r.total_distance,3)
        self.assertEqual(r.routes[1].served_order_ids,())

    def test_urgent_then_deadline_before_increment(self) -> None:
        raw=toy([Order('O1','A',1,0,100),Order('O2','B',1,0,90),
                 Order('O3','A',1,0,200,OrderPriority.URGENT)])
        r=self.check(raw)
        self.assertEqual([x[0] for x in r.selection_trace],['O3','O2','O1'])

    def test_infeasible_urgent_does_not_block_normal(self) -> None:
        r=self.check(toy([Order('BAD','A',11,0,100,OrderPriority.URGENT),
                          Order('GOOD','B',1,0,100)]))
        self.assertEqual(r.routes[0].served_order_ids,('GOOD',))
        self.assertEqual(r.unserved_orders[0].order_id,'BAD')
        self.assertEqual(r.status,'partial')

    def test_same_site_one_visit_independent_ids_and_load(self) -> None:
        r=self.check(toy([Order('O1','A',2,0,100),Order('O2','A',3,0,100)]))
        self.assertEqual(r.routes[0].stop_sequence,('W','A','W'))
        self.assertEqual(set(r.routes[0].served_order_ids),{'O1','O2'})
        self.assertEqual(r.routes[0].initial_load,Decimal(5))
        self.assertEqual(r.routes[0].return_time,4)

    def test_exact_capacity_and_zero_demand_capacity(self) -> None:
        for capacity,demand in ((1,1),(0,0)):
            with self.subTest(capacity=capacity):
                r=self.check(toy([Order('O','A',demand,0,100)],(capacity,)))
                self.assertTrue(r.is_feasible)

    def test_demand_above_one_car_can_split_across_cars(self) -> None:
        r=self.check(toy([Order('O1','A',6,0,100),Order('O2','B',6,0,100)],(10,10)))
        self.assertEqual([route.initial_load for route in r.routes],[Decimal(6),Decimal(6)])
        self.assertEqual(r.total_distance,4)
        self.assertTrue(r.is_feasible)

    def test_every_car_capacity_rejects(self) -> None:
        r=self.check(toy([Order('O','A',11,0,100)],(10,10)))
        self.assertEqual(r.total_distance,0)
        self.assertEqual(r.unserved_orders[0].reasons,('capacity',))

    def test_outward_reachable_but_return_unreachable(self) -> None:
        raw=toy([Order('O','A',1,0,100)])
        raw.graph.remove_edge('A','W'); raw.graph.remove_edge('B','W')
        r=self.check(raw)
        self.assertEqual(r.unserved_orders[0].reasons,('return_unreachable',))

    def test_tight_window_and_completion_after_window(self) -> None:
        r=self.check(toy([Order('O','A',1,0,0.5)]))
        self.assertEqual(r.unserved_orders[0].reasons,('time_window',))
        self.assertTrue(self.check(toy([Order('O','A',1,0,1)])).is_feasible)

    def test_distance_and_cost_choose_different_vehicles(self) -> None:
        raw=toy([Order('O','A',1,0,100)],(10,10),('W','W2'))
        for source,target,distance,cost in (('W','A',1,5),('A','W',1,5),
                                            ('W2','A',2,1),('A','W2',2,1)):
            e=raw.graph.get_edge(source,target); e.distance=distance; e.cost=cost
        distance=self.check(raw,'distance'); cost=self.check(raw,'cost')
        self.assertEqual(distance.selection_trace[0][1],'V1')
        self.assertEqual(cost.selection_trace[0][1],'V2')
        self.assertEqual((distance.total_distance,distance.total_cost),(2,10))
        self.assertEqual((cost.total_distance,cost.total_cost),(4,2))

    def test_heterogeneous_capacities(self) -> None:
        r=self.check(toy([Order('O','A',2,0,100)],(1,3)))
        self.assertEqual(r.selection_trace[0][1],'V2')

    def test_own_depots_preserved(self) -> None:
        raw=toy(capacities=(1,1),homes=('W','W2'))
        for e in raw.graph.edges:
            near=(e.source_id,e.target_id) in (('W','A'),('A','W'),('W2','B'),('B','W2'))
            e.distance=e.cost=e.travel_time=1 if near else 3
        r=self.check(raw)
        self.assertEqual([route.stop_sequence for route in r.routes],[('W','A','W'),('W2','B','W2')])
        self.assertEqual(r.total_distance,4)

    def test_empty_orders(self) -> None:
        r=self.check(toy([],(10,10)))
        self.assertTrue(r.is_feasible)
        self.assertEqual(r.total_distance,0)

    def test_duplicate_input_rejected(self) -> None:
        raw=toy(); raw.orders.append(raw.orders[0])
        with self.assertRaises(ValueError): plan_fleet(raw,'distance')

    def test_nonpending_orders_reported_without_state_changes(self) -> None:
        for state in OrderStatus:
            if state is OrderStatus.PENDING: continue
            with self.subTest(state=state):
                r=self.check(toy([Order('O','A',1,0,100,status=state)]))
                self.assertEqual(r.unserved_orders[0].reasons,('order_not_pending',))

    def test_tiny_overflow_is_not_rounded_away(self) -> None:
        r=self.check(toy([Order('O1','A',100,0,100),Order('O2','A',Decimal('1e-40'),0,100)],(100,)))
        self.assertEqual(r.routes[0].served_order_ids,('O1',))
        self.assertEqual(r.unserved_orders[0].reasons,('capacity',))

    def test_unavailable_vehicle_and_no_courier_state_mutation(self) -> None:
        raw=toy(capacities=(10,10)); raw.couriers[0].status=CourierStatus.DELIVERING
        raw.vehicles[1].status=VehicleStatus.MAINTENANCE
        r=self.check(raw)
        self.assertEqual(r.routes,())
        self.assertEqual(len(r.unavailable_vehicles),2)
        self.assertTrue(all(o.reasons==('no_available_vehicle',) for o in r.unserved_orders))

    def test_input_permutations_preserve_assignments_and_routes(self) -> None:
        raw=toy(capacities=(10,10))
        a=self.check(raw)
        raw.orders.reverse(); raw.vehicles.reverse(); raw.couriers.reverse()
        b=self.check(raw)
        self.assertEqual(a.routes,b.routes)
        self.assertEqual(a.selection_trace,b.selection_trace)

    def test_rejects_time_objective_and_detects_source_mutation(self) -> None:
        with self.assertRaises(ValueError): plan_fleet(toy(),'travel_time')
        raw=toy()
        from logiroute.scheduling.fleet_planner import global_insertion
        def changed(*args):
            result=global_insertion(*args)
            raw.orders[0].demand=9
            return result
        with patch('logiroute.scheduling.fleet_planner.global_insertion',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'input changed'):
                plan_fleet(raw,'distance')
