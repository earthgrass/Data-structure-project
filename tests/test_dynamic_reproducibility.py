from __future__ import annotations
import unittest
from scripts.experiment_v2_dynamic import cross_process_replay


class TestDynamicProcesses(unittest.TestCase):
    def test_full_event_state_and_rollback_histories_across_three_hash_processes(self) -> None:
        report=cross_process_replay()
        self.assertTrue(report['identical'])
        self.assertEqual(report['hash_seeds'],['1','2','73'])
        self.assertEqual(len(set(report['sha256'])),1)
