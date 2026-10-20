"""Fleet config validates bindings and identity, never distributes orders."""
from __future__ import annotations

import copy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from logiroute.config import ConfigError, load_scenario, load_scenario_from_dict


def fleet_config() -> dict:
    data = json.loads(Path('config/scenario.json').read_text(encoding='utf-8'))
    data['vehicles'] = [
        {'id': 'V1', 'capacity': 100, 'current_load': 0, 'current_node_id': 'W1', 'status': 'idle'},
        {'id': 'V2', 'capacity': 120, 'current_load': 0, 'current_node_id': 'W2', 'status': 'idle'},
    ]
    data['couriers'] = [
        {'id': 'D1', 'name': 'D1', 'vehicle_id': 'V1', 'status': 'idle'},
        {'id': 'D2', 'name': 'D2', 'vehicle_id': 'V2', 'status': 'idle'},
    ]
    return data


class TestFleetConfiguration(unittest.TestCase):
    def test_two_vehicles_two_couriers(self) -> None:
        bundle = load_scenario_from_dict(fleet_config())
        self.assertEqual([v.capacity for v in bundle.vehicles], [100, 120])
        self.assertEqual([c.vehicle_id for c in bundle.couriers], ['V1', 'V2'])
        self.assertGreater(sum(o.demand for o in bundle.orders), 120)
        self.assertTrue(all(v.current_load == 0 for v in bundle.vehicles))

    def test_existing_single_vehicle_file_unchanged(self) -> None:
        bundle = load_scenario('config/scenario.json')
        self.assertEqual(len(bundle.vehicles), 1)
        self.assertEqual(len(bundle.couriers), 1)
        self.assertEqual(len(bundle.orders), 20)

    def test_duplicate_ids_empty_sets_and_invalid_bindings(self) -> None:
        cases = ('duplicate_vehicle', 'duplicate_courier', 'duplicate_binding',
                 'missing_binding', 'unknown_vehicle', 'unknown_node',
                 'no_vehicles', 'no_couriers', 'negative_capacity', 'overloaded')
        for case in cases:
            data = fleet_config()
            if case == 'duplicate_vehicle': data['vehicles'][1]['id'] = 'V1'
            elif case == 'duplicate_courier': data['couriers'][1]['id'] = 'D1'
            elif case == 'duplicate_binding': data['couriers'][1]['vehicle_id'] = 'V1'
            elif case == 'missing_binding': data['couriers'].pop()
            elif case == 'unknown_vehicle': data['couriers'][1]['vehicle_id'] = 'GHOST'
            elif case == 'unknown_node': data['vehicles'][1]['current_node_id'] = 'GHOST'
            elif case == 'no_vehicles': data['vehicles'] = []
            elif case == 'no_couriers': data['couriers'] = []
            elif case == 'negative_capacity': data['vehicles'][0]['capacity'] = -1
            elif case == 'overloaded': data['vehicles'][0]['current_load'] = 101
            with self.subTest(case=case), self.assertRaises(ConfigError):
                load_scenario_from_dict(data)

    def test_same_destination_different_ids_accepted(self) -> None:
        data = fleet_config()
        data['orders'][1]['destination_id'] = data['orders'][0]['destination_id']
        bundle = load_scenario_from_dict(data)
        self.assertEqual(len(bundle.orders), 20)
        self.assertNotEqual(bundle.orders[0].id, bundle.orders[1].id)

    def test_duplicate_order_id_rejected(self) -> None:
        data = fleet_config()
        data['orders'][1]['id'] = data['orders'][0]['id']
        with self.assertRaises(ConfigError):
            load_scenario_from_dict(data)

    def test_json_number_types_are_not_silently_coerced(self) -> None:
        for section, field in (('orders', 'demand'), ('vehicles', 'capacity'),
                               ('vehicles', 'current_load')):
            for value in (True, '5', None, float('nan'), float('inf')):
                data = fleet_config()
                data[section][0][field] = value
                with self.subTest(section=section, field=field, value=value):
                    with self.assertRaises(ConfigError) as caught:
                        load_scenario_from_dict(data)
                    self.assertIn(section, str(caught.exception))

    def test_raw_json_fraction_is_retained_before_legacy_float_view(self) -> None:
        data = fleet_config()
        data['orders'][0]['demand'] = '__EXACT__'
        content = json.dumps(data).replace('"__EXACT__"', '0.10000000000000000000000000001')
        with tempfile.TemporaryDirectory(prefix='logiroute-phase2-json-') as directory:
            path = Path(directory) / 'scenario.json'
            path.write_text(content, encoding='utf-8')
            bundle = load_scenario(path)
        self.assertEqual(bundle.orders[0].demand_decimal, Decimal('0.10000000000000000000000000001'))

    def test_new_and_old_status_values_round_trip(self) -> None:
        from logiroute.core import OrderStatus
        for status in OrderStatus:
            data = fleet_config()
            data['orders'][0]['status'] = status.value
            with self.subTest(status=status):
                self.assertIs(load_scenario_from_dict(data).orders[0].status, status)
