"""Real generated roads, waits and Decimal loads, through both actual objectives."""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch
from logiroute.dynamic.config import load_dynamic_config
from logiroute.dynamic.session import DynamicSession
from logiroute.scenario_generator import load_fleet_generator_config,generate_fleet_scenario
from logiroute.scheduling.fleet_paths import fingerprint_scenario

ROOT=Path(__file__).resolve().parents[1]


class TestDynamicNetworks(unittest.TestCase):
    def test_five_seeds_both_modes_actual_metrics_and_two_waves(self) -> None:
        config=replace(load_fleet_generator_config(ROOT/'config/fleet_generator.json'),orders_count=5)
        dynamic=load_dynamic_config(ROOT/'config/dynamic_orders.json')
        for seed in (0,1,42,100,2026):
            for mode in ('distance','cost'):
                with self.subTest(seed=seed,objective=mode):
                    original=generate_fleet_scenario(config,seed=seed).scenario
                    before=fingerprint_scenario(original)
                    session=DynamicSession(original,dynamic)
                    self.assertEqual(session.replan(mode).status,'applied')
                    plan=session.snapshot().plan
                    session.depart()
                    for _ in range(300):
                        if session.step() is None: break
                        report=session.validate()
                        self.assertTrue(report.valid,report.violations)
                    else: self.fail('event program failed to terminate')
                    travel=[e for e in session.snapshot().events if e.kind=='travel']
                    self.assertAlmostEqual(sum(e.distance for e in travel),plan.total_distance)
                    self.assertAlmostEqual(sum(e.cost for e in travel),plan.total_cost)
                    self.assertAlmostEqual(sum(e.travel_time for e in travel),plan.total_travel_time)
                    actual={e.order_id:e.time for e in session.snapshot().events if e.kind=='service'}
                    expected={s.order_id:s.service_end for r in plan.routes for s in r.services}
                    self.assertEqual(actual,expected)
                    now=session.snapshot().time
                    new=session.submit_manual(original.orders[0].destination_id,Decimal('0.1'),now,now+10000)
                    self.assertEqual(session.replan(mode).status,'applied')
                    self.assertEqual([s.order_id for r in session.snapshot().plan.routes for s in r.services],[new.order_id])
                    session.depart()
                    while session.step() is not None:
                        self.assertTrue(session.validate().valid,session.validate().violations)
                    self.assertEqual(len([e for e in session.snapshot().events if e.kind=='service']),6)
                    self.assertEqual(fingerprint_scenario(original),before)

    def test_auditor_does_not_call_execution_compiler(self) -> None:
        from tests.fleet_fixtures import toy
        session=DynamicSession(toy(),load_dynamic_config(ROOT/'config/dynamic_orders.json'))
        session.replan(); session.depart()
        with patch('logiroute.dynamic.session.compile_actions',side_effect=AssertionError('not independent')):
            self.assertTrue(session.validate().valid)
