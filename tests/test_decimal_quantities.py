"""Exact arithmetic across ambient Decimal contexts and model compatibility views."""
from __future__ import annotations

from decimal import Decimal, localcontext
import json
from dataclasses import asdict
import unittest

from logiroute.core import Order, Vehicle
from logiroute.core.quantities import decimal_quantity, exact_difference, exact_sum


class TestDecimalQuantities(unittest.TestCase):
    def test_conversion_of_original_individual_scalars(self) -> None:
        self.assertEqual(exact_sum([decimal_quantity(0.1), decimal_quantity(0.2)]), Decimal('0.3'))

    def test_rejects_bool_strings_nonfinite_negative(self) -> None:
        for value in (True, '0.1', -1, float('inf'), float('nan'), Decimal('NaN')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decimal_quantity(value)

    def test_empty_and_zero(self) -> None:
        self.assertEqual(exact_sum([]), Decimal(0))
        self.assertEqual(exact_difference(Decimal(0), Decimal(0)), Decimal(0))

    def test_exact_total_and_difference_at_low_ambient_precision(self) -> None:
        with localcontext() as context:
            context.prec = 3
            full = exact_sum((Decimal(100), Decimal('1e-40')))
            self.assertGreater(full, Decimal(100))
            self.assertEqual(exact_difference(full, Decimal(100)), Decimal('1e-40'))

    def test_legacy_asdict_remains_serializable(self) -> None:
        item = Order('O', 'C', Decimal('0.100000000000000000001'), 0, 10)
        vehicle = Vehicle('V', Decimal('0.300000000000000000001'))
        self.assertEqual(item.demand_decimal, Decimal('0.100000000000000000001'))
        self.assertEqual(vehicle.capacity_decimal, Decimal('0.300000000000000000001'))
        json.dumps(asdict(item))
        json.dumps(asdict(vehicle))

    def test_demand_assignment_updates_exact_source(self) -> None:
        item = Order('O', 'C', 1, 0, 10)
        item.demand = Decimal('1.0000000000000000000001')
        self.assertEqual(item.demand_decimal, Decimal('1.0000000000000000000001'))

    def test_invalid_demand_assignment_is_atomic(self) -> None:
        item = Order('O', 'C', 1, 0, 10)
        with self.assertRaises(ValueError):
            item.demand = True
        self.assertEqual(item.demand_decimal, Decimal(1))

    def test_vehicle_addition_and_subtraction_stay_decimal(self) -> None:
        vehicle = Vehicle('V', 0.3)
        vehicle.load(0.1)
        vehicle.load(0.2)
        self.assertEqual(vehicle.current_load_decimal, Decimal('0.3'))
        vehicle.unload(0.1)
        self.assertEqual(vehicle.current_load_decimal, Decimal('0.2'))
