"""Production generation must certify individual orders in BOTH real modes."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from logiroute.scenario_generator.fleet_config import load_fleet_generator_config
from logiroute.scenario_generator.fleet_generator import (
    FleetGenerationError, generate_fleet_scenario,
)
from logiroute.scheduling import plan_fleet
from logiroute.scheduling.fleet_paths import fingerprint_scenario
from logiroute.scheduling.fleet_validator import validate_fleet

ROOT = Path(__file__).resolve().parents[1]


class TestFleetGeneration(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_fleet_generator_config(ROOT / 'config/fleet_generator.json')

    def test_same_destination_orders_keep_separate_ids_and_services(self) -> None:
        config = replace(self.config, orders_count=35,
                         demand_choices=(Decimal('0.1'),))
        result = generate_fleet_scenario(config, seed=42)
        self.assertLess(len({o.destination_id for o in result.scenario.orders}), 35)
        expected = {o.id for o in result.scenario.orders}
        self.assertEqual(len(expected), 35)
        for answer in result.plans + result.witnesses:
            actual = [s.order_id for r in answer.routes for s in r.services]
            self.assertEqual(len(actual), 35)
            self.assertEqual(set(actual), expected)
            self.assertTrue(validate_fleet(result.scenario, answer).complete)

    def test_duplicate_vehicle_and_courier_ids_rejected(self) -> None:
        first = self.config.vehicles[0]
        for other in (first, replace(self.config.vehicles[1], courier_id=first.courier_id)):
            with self.subTest(other=other), self.assertRaises(ValueError):
                replace(self.config, vehicles=(first, other))

    def test_capacity_from_original_decimal_no_epsilon(self) -> None:
        vehicle = replace(self.config.vehicles[0], capacity=Decimal('0.3'))
        config = replace(self.config, vehicles=(vehicle,), orders_count=3,
                         demand_choices=(Decimal('0.1'),))
        result = generate_fleet_scenario(config, seed=0)
        for plan in result.plans + result.witnesses:
            self.assertEqual(plan.routes[0].initial_load, Decimal('0.3'))
        overflow = replace(config, demand_choices=(Decimal('0.10000000000000000000001'),),
                           max_attempts=2)
        with self.assertRaises(FleetGenerationError) as context:
            generate_fleet_scenario(overflow, seed=0)
        self.assertEqual(len(context.exception.attempts), 2)
        self.assertTrue(all(a.stage == 'capacity' for a in context.exception.attempts))

    def test_total_capacity_is_not_a_single_car_capacity(self) -> None:
        config = replace(self.config, vehicles=tuple(replace(v, capacity=Decimal('5'))
                         for v in self.config.vehicles), orders_count=1,
                         demand_choices=(Decimal('6'),), max_attempts=2)
        with self.assertRaises(FleetGenerationError):
            generate_fleet_scenario(config, seed=1)

    def test_both_planners_run_without_witness_hint_and_inputs_unchanged(self) -> None:
        modes = []
        def measured(bundle, objective):
            before = fingerprint_scenario(bundle)
            self.assertNotIn('assignment', bundle.metadata)
            answer = plan_fleet(bundle, objective)
            self.assertEqual(before, fingerprint_scenario(bundle))
            modes.append(objective)
            return answer
        with patch('logiroute.scenario_generator.fleet_generator.plan_fleet', side_effect=measured):
            result = generate_fleet_scenario(self.config, seed=1)
        self.assertEqual(modes, ['distance', 'cost'] * len(result.attempts))
        self.assertEqual(result.scenario_fingerprint, fingerprint_scenario(result.scenario))
        self.assertTrue(all(p.is_feasible for p in result.plans))

    def test_partial_real_plan_is_rejected_with_bounded_retry(self) -> None:
        # A valid partial answer from an independent real planner must never be certified.
        from scripts.fleet_reference import capacity_counterexample
        counter = capacity_counterexample()
        def partial(bundle, objective):
            return plan_fleet(counter, objective)
        with patch('logiroute.scenario_generator.fleet_generator.plan_fleet', side_effect=partial):
            with self.assertRaises(FleetGenerationError) as context:
                generate_fleet_scenario(replace(self.config, max_attempts=2), seed=42)
        # Wrong-source answers are invalid, so stop immediately rather than hiding a P0.
        self.assertEqual(len(context.exception.attempts), 1)
        self.assertEqual(context.exception.attempts[0].stage, 'invalid_plan')

    def test_forged_success_flag_is_independently_rejected(self) -> None:
        def forged(bundle, objective):
            result = plan_fleet(bundle, objective)
            return replace(result, routes=result.routes[:-1])
        with patch('logiroute.scenario_generator.fleet_generator.plan_fleet', side_effect=forged):
            with self.assertRaises(FleetGenerationError) as context:
                generate_fleet_scenario(self.config, seed=42)
        self.assertEqual(context.exception.attempts[0].stage, 'invalid_plan')

    def test_invalid_seed_depot_and_config_fail_explicitly(self) -> None:
        for seed in (None, True, '42'):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                generate_fleet_scenario(self.config, seed=seed)
        with self.assertRaises(ValueError):
            replace(self.config, vehicles=(replace(self.config.vehicles[0], depot_id='missing'),))
        for updates in ({'max_attempts':0}, {'orders_count':True},
                        {'window_late_slack':float('inf')}, {'demand_choices':()},
                        {'vehicles':()}, {'witness_horizon':self.config.initial_time-1}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                replace(self.config, **updates)

    def test_exact_json_load_and_unknown_keys(self) -> None:
        import tempfile
        raw = json.loads((ROOT / 'config/fleet_generator.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            text = json.dumps(raw).replace('24', '0.12345678901234567890123456789', 1)
            path.write_text(text, encoding='utf-8')
            loaded = load_fleet_generator_config(path)
            self.assertIn(Decimal('0.12345678901234567890123456789'),
                          tuple(v.capacity for v in loaded.vehicles))
            raw['unknown'] = True
            path.write_text(json.dumps(raw), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_fleet_generator_config(path)

    def test_deterministic_failure_history(self) -> None:
        config = replace(self.config, orders_count=2, demand_choices=(Decimal('1000'),),
                         max_attempts=3)
        failures = []
        for _ in range(2):
            with self.assertRaises(FleetGenerationError) as context:
                generate_fleet_scenario(config, seed=2026)
            failures.append(context.exception.to_dict(include_timing=False))
        self.assertEqual(failures[0], failures[1])
        self.assertEqual(len(failures[0]['attempts']), 3)

    def test_zero_width_window_policy_rejected_before_sampling(self) -> None:
        with self.assertRaises(ValueError):
            replace(self.config, window_early_slack=0, window_late_slack=0)

    def test_config_evidence_roundtrips_exact_quantities(self) -> None:
        import tempfile
        exact = replace(self.config, demand_choices=(Decimal('0.10000000000000000000001'),))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'roundtrip.json'
            path.write_text(json.dumps(exact.to_dict()), encoding='utf-8')
            recovered = load_fleet_generator_config(path)
        self.assertEqual(exact.fingerprint, recovered.fingerprint)

    def test_real_partial_results_retry_without_relaxing_constraints(self) -> None:
        config = replace(self.config, orders_count=8,
                         vehicles=tuple(replace(v, capacity=Decimal(12))
                                        for v in self.config.vehicles[:2]),
                         demand_choices=(Decimal(1), Decimal(2), Decimal(3)),
                         window_early_slack=1, window_late_slack=0, max_attempts=6)
        result = generate_fleet_scenario(config, seed=2)
        self.assertEqual([a.stage for a in result.attempts],
                         ['heuristic_incomplete', 'heuristic_incomplete', 'accepted'])
        self.assertEqual([tuple(n for _, _, _, n in a.outcomes) for a in result.attempts],
                         [(7, 7), (8, 7), (8, 8)])
        self.assertTrue(all(a.reasons for a in result.attempts[:-1]))
        self.assertEqual(result.config_fingerprint, config.fingerprint)
        again = generate_fleet_scenario(config, seed=2)
        self.assertEqual(result.to_dict(include_timing=False), again.to_dict(include_timing=False))
        with self.assertRaises(FleetGenerationError) as context:
            generate_fleet_scenario(replace(config, max_attempts=1), seed=2)
        self.assertEqual(context.exception.attempts[0].outcomes, result.attempts[0].outcomes)

    def test_exported_snapshot_preserves_full_graph_and_exact_loads(self) -> None:
        result = generate_fleet_scenario(self.config, seed=100)
        payload = result.to_dict(include_timing=False)
        scene = payload['scenario']
        self.assertEqual(len(scene['edges']), result.scenario.graph.edge_count)
        self.assertTrue(all('road_id' in edge['metadata'] for edge in scene['edges']))
        self.assertEqual(len(scene['orders']), self.config.orders_count)
        self.assertTrue(all(isinstance(o['demand'], str) for o in scene['orders']))
        scene['metadata']['base_seed'] = -1
        self.assertEqual(result.scenario.metadata['base_seed'], 100)

    def test_duplicate_order_ids_in_witness_cannot_be_certified(self) -> None:
        from logiroute.scenario_generator.fleet_witness import construct_candidate
        def corrupt(config, rng, seed, attempt):
            bundle, witnesses, stage, reasons = construct_candidate(config, rng, seed, attempt)
            bundle.orders[1].id = bundle.orders[0].id
            return bundle, witnesses, stage, reasons
        with patch('logiroute.scenario_generator.fleet_generator.construct_candidate', side_effect=corrupt):
            with self.assertRaises(ValueError):
                generate_fleet_scenario(self.config, seed=42)

    def test_changed_returned_scenario_cannot_export_old_certificate(self) -> None:
        result = generate_fleet_scenario(self.config, seed=42)
        result.scenario.orders[0].id = 'changed-after-generation'
        with self.assertRaises(ValueError):
            result.to_dict()

    def test_small_horizon_rejects_without_widening(self) -> None:
        # A zero-width provisional window is also an invalid config, never patched at runtime.
        with self.assertRaises(ValueError):
            replace(self.config, witness_horizon=self.config.initial_time, max_attempts=2)

    def test_unexpected_planner_error_is_not_swallowed_or_retried(self) -> None:
        with patch('logiroute.scenario_generator.fleet_generator.plan_fleet',
                   side_effect=RuntimeError('unexpected planner defect')) as planner:
            with self.assertRaisesRegex(RuntimeError, 'unexpected planner defect'):
                generate_fleet_scenario(self.config, seed=42)
        self.assertEqual(planner.call_count, 1)

    def test_both_distinct_witness_modes_are_required(self) -> None:
        from logiroute.scenario_generator.fleet_witness import construct_candidate
        def repeated(config, rng, seed, attempt):
            bundle, witnesses, stage, reasons = construct_candidate(config, rng, seed, attempt)
            return bundle, (witnesses[0], witnesses[0]), stage, reasons
        with patch('logiroute.scenario_generator.fleet_generator.construct_candidate', side_effect=repeated):
            with self.assertRaises(ValueError):
                generate_fleet_scenario(self.config, seed=42)

    def test_finite_but_too_short_horizon_preserves_rejection(self) -> None:
        config = replace(self.config, witness_horizon=self.config.initial_time+0.001, max_attempts=2)
        with self.assertRaises(FleetGenerationError) as context:
            generate_fleet_scenario(config, seed=42)
        self.assertEqual(len(context.exception.attempts), 2)
        self.assertTrue(all(a.stage == 'witness_route' for a in context.exception.attempts))


if __name__ == '__main__':
    unittest.main()
