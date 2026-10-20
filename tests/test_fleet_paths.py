from __future__ import annotations
from decimal import Decimal
import unittest
from unittest.mock import patch
from logiroute.core import Order, CourierStatus, VehicleStatus
from logiroute.scheduling.fleet_paths import freeze_scenario, build_closure, fingerprint_scenario, vehicle_reasons
from tests.fleet_fixtures import toy


class TestFleetPaths(unittest.TestCase):
    def test_snapshot_preserves_original_decimal_and_is_isolated(self) -> None:
        raw = toy([Order('O', 'A', Decimal('100.0000000000000000000000000000000000000001'), 0, 100)], (120,))
        snapshot = freeze_scenario(raw)
        raw.orders[0].demand = 1
        raw.graph.get_edge('W', 'A').distance = 9
        self.assertEqual(snapshot.orders['O'].demand_decimal,
                         Decimal('100.0000000000000000000000000000000000000001'))
        self.assertEqual(snapshot.bundle.graph.get_edge('W', 'A').distance, 1)
        self.assertNotEqual(snapshot.fingerprint, fingerprint_scenario(raw))

    def test_single_source_shared_table_and_unknown_self_rejected(self) -> None:
        paths = build_closure(freeze_scenario(toy()), 'distance')
        self.assertEqual(paths.dijkstra_calls, 3)
        for _ in range(10):
            self.assertEqual(paths.leg('W', 'A').distance, 1)
        self.assertEqual(paths.dijkstra_calls, 3)
        with self.assertRaises(ValueError):
            paths.leg('UNKNOWN', 'UNKNOWN')

    def test_one_way_does_not_invent_return(self) -> None:
        raw = toy([Order('O', 'A', 1, 0, 100)])
        raw.graph.remove_edge('A', 'W')
        raw.graph.remove_edge('B', 'W')
        paths = build_closure(freeze_scenario(raw), 'distance')
        self.assertIsNotNone(paths.leg('W', 'A'))
        self.assertIsNone(paths.leg('A', 'W'))

    def test_vehicle_and_courier_must_be_idle_empty_at_depot(self) -> None:
        raw = toy()
        raw.couriers[0].status = CourierStatus.DELIVERING
        raw.vehicles[0].load(1)
        raw.vehicles[0].current_node_id = 'A'
        raw.vehicles[0].status = VehicleStatus.RETURNING
        self.assertEqual(set(vehicle_reasons(freeze_scenario(raw), 'V1')),
                         {'vehicle_not_idle', 'vehicle_not_empty', 'invalid_depot', 'courier_not_idle'})

    def test_duplicate_identity_binding_and_nonfinite_time_rejected(self) -> None:
        for mutate in (lambda s: s.orders.append(s.orders[0]),
                       lambda s: s.couriers.append(s.couriers[0]),
                       lambda s: s.simulation.update(service_time=float('nan')),
                       lambda s: s.simulation.update(initial_time=True)):
            raw = toy(); mutate(raw)
            with self.assertRaises(ValueError):
                freeze_scenario(raw)

    def test_fingerprint_does_not_depend_on_input_list_order(self) -> None:
        raw = toy(capacities=(10, 20))
        before = fingerprint_scenario(raw)
        raw.orders.reverse(); raw.vehicles.reverse(); raw.couriers.reverse()
        self.assertEqual(before, fingerprint_scenario(raw))

    def test_mutation_during_quantity_clone_is_detected(self) -> None:
        from logiroute.core import Vehicle
        raw = toy()
        original = Vehicle.__init__
        def mutate(instance, *args, **kwargs):
            original(instance, *args, **kwargs)
            raw.vehicles[0].capacity = 11
        with patch.object(Vehicle, '__init__', new=mutate):
            with self.assertRaisesRegex(ValueError, 'input changed'):
                freeze_scenario(raw)
