from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from logiroute.dynamic.config import load_dynamic_config

ROOT=Path(__file__).resolve().parents[1]


class TestDynamicConfig(unittest.TestCase):
    def test_json_original_quantities_and_roundtrip_are_exact(self) -> None:
        raw=(ROOT/'config/dynamic_orders.json').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json'
            path.write_text(raw.replace('0.1','0.10000000000000000000001',1),encoding='utf-8')
            config=load_dynamic_config(path)
            self.assertEqual(config.automatic.demand_choices[0],Decimal('0.10000000000000000000001'))
            path.write_text(json.dumps(config.to_dict()),encoding='utf-8')
            self.assertEqual(load_dynamic_config(path).fingerprint,config.fingerprint)

    def test_invalid_ranges_identifiers_and_unknown_fields(self) -> None:
        config=load_dynamic_config(ROOT/'config/dynamic_orders.json')
        for values in ({'demand_choices':()}, {'urgent_fraction':True},
                       {'window_width_range':(0,1)}, {'window_delay_range':(2,1)},
                       {'destination_ids':('A','A')}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(config.automatic,**values)
        for values in ({'name':''},{'default_objective':'travel_time'},{'order_id_prefix':''}):
            with self.subTest(values=values),self.assertRaises(ValueError): replace(config,**values)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json'; raw=config.to_dict(); raw['unknown']=1
            path.write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaises(ValueError): load_dynamic_config(path)
