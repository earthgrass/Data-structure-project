from __future__ import annotations
import unittest
from scripts.experiment_v2_fleet import load_settings, experiment_input, cross_process_replay
from logiroute.scheduling import plan_fleet
from logiroute.scheduling.fleet_paths import fingerprint_scenario


class TestFleetReproducibility(unittest.TestCase):
    def test_random_derived_fixture_repeats_and_modes_share_input(self) -> None:
        settings=load_settings()
        for seed in settings['seeds']:
            raw=experiment_input(settings,seed,5,2)
            before=fingerprint_scenario(raw)
            self.assertEqual(before,fingerprint_scenario(experiment_input(settings,seed,5,2)))
            for objective in ('distance','cost'):
                result=plan_fleet(raw,objective)
                self.assertTrue(result.validation.valid,result.validation.violations)
                self.assertEqual(result.input_fingerprint,before)
                self.assertEqual(fingerprint_scenario(raw),before)

    def test_five_seeds_two_objectives_three_hash_processes(self) -> None:
        evidence=cross_process_replay()
        self.assertTrue(evidence['identical'])
        self.assertEqual(len(evidence['hash_seeds']),3)
        self.assertEqual(evidence['scenarios_per_process'],10)
