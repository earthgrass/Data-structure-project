"""Compare entire scene + witnesses + routes + failure history across processes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''
from dataclasses import replace
from decimal import Decimal
import json
from logiroute.scenario_generator import load_fleet_generator_config, generate_fleet_scenario
c = load_fleet_generator_config('config/fleet_generator.json')
rows = [generate_fleet_scenario(c, seed=seed).to_dict(include_timing=False)
        for seed in (0,1,42,100,2026)]
tight = replace(c, orders_count=8,
                vehicles=tuple(replace(v,capacity=Decimal(12)) for v in c.vehicles[:2]),
                demand_choices=(Decimal(1),Decimal(2),Decimal(3)),
                window_early_slack=1,window_late_slack=0,max_attempts=6)
rows.append(generate_fleet_scenario(tight,seed=2).to_dict(include_timing=False))
print(json.dumps(rows,ensure_ascii=True,separators=(',',':'),allow_nan=False))
'''


class TestFleetGenerationProcesses(unittest.TestCase):
    def test_full_snapshots_and_actual_retry_history_across_hash_seeds(self) -> None:
        fingerprints = []
        for value in ('1', '2', '73'):
            env = dict(os.environ, PYTHONHASHSEED=value, PYTHONPATH=str(ROOT/'src'),
                       PYTHONDONTWRITEBYTECODE='1')
            completed = subprocess.run([sys.executable, '-B', '-c', CHILD],
                                       cwd=ROOT, env=env, capture_output=True, text=True,
                                       encoding='utf-8', timeout=180, check=True)
            rows = json.loads(completed.stdout)
            self.assertEqual(len(rows), 6)
            self.assertEqual(len(rows[-1]['attempts']), 3)
            for row in rows:
                self.assertTrue(all(p['validation']['valid'] and p['validation']['complete']
                                    for p in row['plans'] + row['witnesses']))
                self.assertIn('edges', row['scenario'])
            fingerprints.append(hashlib.sha256(completed.stdout.encode('utf-8')).hexdigest())
        self.assertEqual(fingerprints[0], fingerprints[1])
        self.assertEqual(fingerprints[0], fingerprints[2])
