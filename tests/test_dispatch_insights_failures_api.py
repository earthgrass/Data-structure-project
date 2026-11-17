from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient
from logiroute.api import create_app


class TestDispatchInsightsFailuresAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.context = TestClient(create_app())
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def create(self, automatic: bool) -> None:
        response = self.client.post('/api/v2/sessions', json={'seed': 42, 'auto_replan': automatic})
        self.assertEqual(response.status_code, 200, response.text)
        self.snapshot = response.json()
        self.url = '/api/v2/sessions/' + self.snapshot['id']

    def command(self, kind: str, **fields: Any) -> dict[str, Any]:
        response = self.client.post(self.url + '/commands', json={
            'revision': self.snapshot['revision'], 'command': kind, **fields})
        self.assertEqual(response.status_code, 200, response.text)
        self.snapshot = response.json()
        return self.snapshot

    def blocked_loaded_checkpoint(self) -> None:
        self.command('plan', objective='distance'); self.command('depart')
        while not any(v['current'] and v['current']['kind'] == 'drive' for v in self.snapshot['vehicles']):
            self.command('step')
        self.command('pause')
        while self.snapshot['running']: self.command('step')
        car = next(v for v in self.snapshot['vehicles'] if v['cargo'])
        for edge in [e for e in self.snapshot['edges'] if e['source'] == car['position']]:
            self.command('traffic', source=edge['source'], target=edge['target'], status='blocked')

    def rejected_manual_plan(self, objective: str) -> dict[str, Any]:
        before = self.snapshot
        response = self.client.post(self.url + '/commands', json={
            'revision': before['revision'], 'command': 'plan', 'objective': objective})
        self.assertEqual(response.status_code, 422, response.text)
        error = response.json()['error']
        self.assertEqual(error['kind'], 'unsafe_plan')
        report = error['report']
        self.assertEqual(report['revision'], before['revision'])
        self.assertEqual(report['traffic_version'], before['traffic_version'])
        self.assertEqual(report['objective'], objective)
        original = self.context.app.state.dispatch_service.sessions[before['id']]
        self.assertEqual(report['fingerprint'], original.state.fingerprint())
        self.assertFalse(report['report']['safe_to_apply'])
        self.assertTrue(report['explanations'])
        self.assertEqual({e['order_id'] for e in report['explanations']}, {oid for oid, _ in report['deferred']})
        for item in report['explanations']:
            self.assertEqual(item['scope'], 'heuristic_candidate')
            self.assertEqual(item['reason'], dict(report['deferred'])[item['order_id']])
            self.assertTrue(item['attempts'])
            self.assertTrue(item['summary'])
        # Failure diagnostics travel in the error response, not an applied plan.
        # Repeated GETs must retain all original cargo, events, versions and evidence.
        self.assertEqual(self.client.get(self.url).json(), before)
        self.assertEqual(self.client.get(self.url).json(), before)
        self.assertTrue(before['audit']['valid'])
        return report

    def test_first_manual_rejection_returns_evidence_without_committing_mutations(self) -> None:
        self.create(False)
        self.blocked_loaded_checkpoint()
        stored = self.snapshot['planning_insights']['explanations']
        self.assertEqual(stored['source'], 'applied_plan')
        self.assertFalse(stored['items'])
        report = self.rejected_manual_plan('distance')
        self.assertTrue(all(item['reason'].startswith('protected_continuation:') for item in report['explanations']))

    def test_failed_manual_retry_preserves_existing_automatic_blocked_evidence(self) -> None:
        self.create(True)
        self.blocked_loaded_checkpoint()
        stored = self.snapshot['planning_insights']['explanations']
        self.assertEqual(self.snapshot['order_control']['status'], 'blocked')
        self.assertEqual(stored['source'], 'blocked_proposal')
        self.assertTrue(stored['items'])
        self.assertFalse(stored['stale'])
        self.rejected_manual_plan('cost')
        self.assertEqual(self.client.get(self.url).json()['planning_insights']['explanations'], stored)


if __name__ == '__main__': unittest.main()
