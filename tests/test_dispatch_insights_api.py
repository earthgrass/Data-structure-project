from __future__ import annotations

import unittest
from fastapi.testclient import TestClient
from logiroute.api import create_app


class TestDispatchInsightsAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.context = TestClient(create_app())
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        response = self.client.post('/api/v2/sessions', json={'seed': 42, 'auto_replan': True})
        self.assertEqual(response.status_code, 200, response.text)
        self.snapshot = response.json()
        self.url = '/api/v2/sessions/' + self.snapshot['id']

    def command(self, kind: str, **fields: object) -> dict:
        response = self.client.post(self.url + '/commands', json={
            'revision': self.snapshot['revision'], 'command': kind, **fields,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.snapshot = response.json()
        return self.snapshot

    def test_refusal_evidence_and_timeline_share_the_applied_plan(self) -> None:
        self.assertIsNone(self.snapshot['planning_insights']['impact'])
        self.command('plan', objective='cost')
        first = self.snapshot['orders'][0]
        self.command('add', id='LATE_API', destination=first['destination'],
                     demand='0.10000000000000000000001', earliest=0,
                     deadline=0.001, priority='urgent')
        info = self.snapshot['planning_insights']
        evidence = info['explanations']
        self.assertEqual(evidence['source'], 'applied_plan')
        self.assertFalse(evidence['stale'])
        self.assertEqual(evidence['revision'], self.snapshot['plan']['revision'])
        detail = next(row for row in evidence['items'] if row['order_id'] == 'LATE_API')
        self.assertEqual(detail['scope'], 'heuristic_candidate')
        self.assertTrue(detail['attempts'])
        self.assertEqual(detail['reason'], dict(self.snapshot['plan']['deferred'])['LATE_API'])
        row = next(row for row in info['timeline']['orders'] if row['order_id'] == 'LATE_API')
        self.assertIsNone(row['expected'])
        self.assertIsNone(row['actual'])
        self.assertEqual(row['deferred_reason'], detail['reason'])
        self.assertIn('LATE_API', info['impact']['deferred'])
        self.assertTrue(self.snapshot['audit']['valid'])
        self.assertEqual(self.client.get(self.url).json(), self.snapshot)

    def test_moving_mutation_hides_old_eta_then_freezes_real_impact(self) -> None:
        self.command('plan', objective='distance')
        self.command('depart')
        while not any(v['current'] and v['current']['kind'] == 'drive'
                      for v in self.snapshot['vehicles']):
            self.command('step')
        first = self.snapshot['orders'][0]
        self.command('add', id='MOVING_API', destination=first['destination'],
                     demand='0.1', earliest=self.snapshot['now'],
                     deadline=self.snapshot['now'] + 2000, priority='urgent')
        waiting = self.snapshot['planning_insights']['timeline']
        self.assertTrue(waiting['stale'])
        self.assertTrue(all(row['expected'] is None for row in waiting['orders']))
        while self.snapshot['running']:
            self.command('step')
        impact = self.snapshot['planning_insights']['impact']
        self.assertEqual(impact['at'], self.snapshot['now'])
        self.assertEqual(impact['comparison_basis'], 'remaining_at_checkpoint')
        self.assertFalse(self.snapshot['planning_insights']['timeline']['stale'])
        for metric in ('distance', 'cost', 'travel_time'):
            self.assertAlmostEqual(impact['delta'][metric], impact['after'][metric] - impact['before'][metric])
        self.command('depart')
        self.command('step')
        self.assertEqual(self.snapshot['planning_insights']['impact'], impact)
        before = self.snapshot
        conflict = self.client.post(self.url + '/commands', json={'revision': -1, 'command': 'plan'})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(self.client.get(self.url).json(), before)

    def test_actual_signoff_requires_completed_service_and_keeps_cancelled_id(self) -> None:
        cancelled = self.snapshot['orders'][0]['id']
        self.command('cancel', id=cancelled)
        self.command('depart')
        while self.snapshot['running']:
            self.command('step')
        rows = {row['order_id']: row for row in self.snapshot['planning_insights']['timeline']['orders']}
        events = {oid: event['action'] for event in self.snapshot['events']
                  if event['kind'] == 'action' and event['action']['kind'] == 'deliver'
                  for oid in event['action']['ids']}
        self.assertEqual(len(rows), len(self.snapshot['orders']))
        self.assertEqual(rows[cancelled]['status'], 'cancelled')
        self.assertIsNone(rows[cancelled]['actual'])
        self.assertIsNone(rows[cancelled]['expected'])
        for key, action in events.items():
            self.assertEqual(rows[key]['actual']['signoff'], action['end'])
            self.assertEqual(rows[key]['actual']['service_start'], action['start'])
            self.assertEqual(rows[key]['actual']['vehicle'], action['vehicle'])
            self.assertGreaterEqual(rows[key]['actual']['slack'], 0)
        self.assertEqual(len(events), len(rows) - 1)
        self.assertTrue(self.snapshot['audit']['complete_all'])


if __name__ == '__main__':
    unittest.main()
