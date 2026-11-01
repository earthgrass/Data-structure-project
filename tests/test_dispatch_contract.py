"""6A: deployment config is an executable cross-reference contract."""
from __future__ import annotations
import json
from pathlib import Path
import unittest


class TestDispatchContract(unittest.TestCase):
    def test_roles_rules_and_station_bindings_are_explicit(self) -> None:
        root=Path(__file__).resolve().parents[1]
        c=json.loads((root/'config/dispatch_v2.json').read_text(encoding='utf-8'))
        self.assertEqual(c['time_window_rule'],'service_end')
        self.assertEqual(set(c['priority_weights']),{'critical','urgent','normal'})
        self.assertIsNone(c['traffic']['factors']['blocked'])
        self.assertEqual(len({v['id'] for v in c['vehicles']}),len(c['vehicles']))
        self.assertEqual(len({v['courier_id'] for v in c['vehicles']}),len(c['vehicles']))
        self.assertEqual({v['base'] for v in c['vehicles'] if v['role']=='delivery'},set(c['hub_ids']))
        self.assertTrue(all(v['base'] in c['warehouse_ids'] for v in c['vehicles'] if v['role']=='trunk'))
