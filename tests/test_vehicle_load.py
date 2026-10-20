"""Exact per-order loading, strict boundaries and immutable quantity snapshots."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, localcontext
import json
import unittest

from logiroute.core import Order, Vehicle
from logiroute.core.delivery_load import DeliveryLoadReport, DeliveryLoadState
from logiroute.core.quantities import Quantity


def shipment() -> list[Order]:
    return [Order("O1", "C12", 40, 0, 10), Order("O2", "C12", 35, 0, 10),
            Order("O3", "C18", 25, 0, 10)]


class TestVehicleLoad(unittest.TestCase):
    def check(self, capacity: Quantity, orders: list[Order]) -> DeliveryLoadReport:
        from logiroute.core.delivery_load import check_delivery_load
        return check_delivery_load(capacity, orders)

    def state(self, capacity: Quantity, orders: list[Order]) -> DeliveryLoadState:
        from logiroute.core.delivery_load import DeliveryLoadState
        return DeliveryLoadState(capacity, orders)

    def test_exact_capacity_same_site_orders(self) -> None:
        report = self.check(100, shipment())
        self.assertTrue(report.feasible)
        self.assertEqual(report.initial_load, Decimal(100))
        self.assertIsInstance(report.capacity, Decimal)

    def test_over_capacity(self) -> None:
        items = shipment()
        items[2] = replace(items[2], demand=26)
        self.assertFalse(self.check(100, items).feasible)
        with self.assertRaises(ValueError):
            self.state(100, items)

    def test_no_epsilon_overflow(self) -> None:
        item = Order("O", "C", 100.00000000000001, 0, 10)
        self.assertFalse(self.check(100, [item]).feasible)

    def test_decimal_point_one_plus_point_two(self) -> None:
        items = [Order("A", "C", 0.1, 0, 10), Order("B", "C", 0.2, 0, 10)]
        report = self.check(0.3, items)
        self.assertEqual(report.initial_load, Decimal('0.3'))
        self.assertTrue(report.feasible)

    def test_precision_cannot_hide_tiny_overflow(self) -> None:
        items = [Order("A", "C", 100, 0, 10), Order("B", "C", Decimal('1e-40'), 0, 10)]
        with localcontext() as context:
            context.prec = 6
            self.assertFalse(self.check(100, items).feasible)

    def test_direct_decimal_is_preserved(self) -> None:
        amount = Decimal('0.10000000000000000000000000001')
        item = Order("O", "C", amount, 0, 10)
        self.assertEqual(item.demand_decimal, amount)
        self.assertFalse(self.check(Decimal('0.1'), [item]).feasible)

    def test_progress_and_duplicate_delivery(self) -> None:
        state = self.state(100, shipment())
        self.assertEqual(state.initial_load, Decimal(100))
        for order_id, remaining in (("O1", 60), ("O2", 25), ("O3", 0)):
            state.deliver(order_id)
            self.assertEqual(state.current_load, Decimal(remaining))
            self.assertEqual(state.free_capacity, Decimal(100 - remaining))
        with self.assertRaises(ValueError):
            state.deliver("O1")
        self.assertEqual(state.current_load, 0)

    def test_unknown_delivery_atomic(self) -> None:
        state = self.state(100, shipment())
        with self.assertRaises(ValueError):
            state.deliver("GHOST")
        self.assertEqual(state.current_load, 100)

    def test_order_snapshot_does_not_change_after_external_demand_mutation(self) -> None:
        items = shipment()
        state = self.state(100, items)
        items[0].demand = 99
        state.deliver("O1")
        self.assertEqual(state.current_load, 60)

    def test_duplicate_ids_rejected(self) -> None:
        items = shipment()
        with self.assertRaises(ValueError):
            self.check(100, items + [replace(items[0], demand=1)])

    def test_invalid_scalars(self) -> None:
        for value in (True, '100', -1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(value, shipment())

    def test_mutated_invalid_demand_is_rejected(self) -> None:
        item = shipment()[0]
        for value in (True, '1', -1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                item.demand = value
                self.check(100, [item])

    def test_zero_demand_and_zero_capacity_compatibility(self) -> None:
        item = Order("O", "C", 0, 0, 10)
        self.assertTrue(self.check(0, [item]).feasible)
        state = self.state(0, [item])
        state.deliver("O")
        self.assertEqual(state.current_load, 0)

    def test_empty_load(self) -> None:
        state = self.state(100, [])
        self.assertEqual(state.initial_load, 0)
        self.assertEqual(state.free_capacity, 100)

    def test_json_boundary_is_decimal_strings(self) -> None:
        state = self.state(Decimal('100.0000000000000000001'), shipment())
        data = json.loads(json.dumps(state.to_dict()))
        self.assertEqual(data['capacity'], '100.0000000000000000001')
        self.assertEqual(data['current_load'], '100')

    def test_vehicle_operations_do_not_add_binary_floats(self) -> None:
        vehicle = Vehicle("V", 0.3)
        vehicle.load(0.1)
        vehicle.load(0.2)
        self.assertEqual(vehicle.current_load_decimal, Decimal('0.3'))
        self.assertFalse(vehicle.can_load(Decimal('1e-40')))
        vehicle.unload(0.1)
        self.assertEqual(vehicle.current_load_decimal, Decimal('0.2'))

    def test_vehicle_rejects_boolean_and_nonfinite_amounts(self) -> None:
        vehicle = Vehicle("V", 100)
        for amount in (True, float('inf'), float('nan'), '1'):
            with self.subTest(amount=amount):
                self.assertFalse(vehicle.can_load(amount))
                with self.assertRaises(ValueError):
                    vehicle.load(amount)

    def test_capacity_below_current_load_is_rejected_atomically(self) -> None:
        vehicle = Vehicle("V", 100, 50)
        with self.assertRaises(ValueError):
            vehicle.capacity = 49
        self.assertEqual(vehicle.capacity, 100)

    def test_precise_initial_overload_cannot_hide_in_float_view(self) -> None:
        with self.assertRaises(ValueError):
            Vehicle("V", Decimal('0.1'), Decimal('0.10000000000000000000001'))

    def test_terminal_orders_cannot_be_loaded(self) -> None:
        from logiroute.core import OrderStatus
        for status in (OrderStatus.CANCELLED, OrderStatus.EXPIRED, OrderStatus.DELIVERED):
            items = shipment()
            items[0].status = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.state(100, items)

    def test_generated_backbone_capacity_cannot_use_epsilon(self) -> None:
        from logiroute.scenario_generator import GeneratorConfig, RandomSource, sample_logistics_graph
        from logiroute.scenario_generator.backbone_builder import build_backbone_and_orders
        cfg = GeneratorConfig(orders_count=3, capacity=0.2999999999999,
                              min_demand=0.1, max_demand=0.1)
        graph = sample_logistics_graph(cfg, RandomSource(42))
        self.assertIsNone(build_backbone_and_orders(graph, cfg, RandomSource(42)))

    def test_nonzero_exact_cargo_cannot_look_available_after_float_underflow(self) -> None:
        vehicle = Vehicle('V', 1, Decimal('1e-400'))
        self.assertFalse(vehicle.is_available)
