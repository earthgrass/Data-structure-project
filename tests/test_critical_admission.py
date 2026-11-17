from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
import unittest
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.session import Session


class TestCriticalAdmission(unittest.TestCase):
    def session(self, priority: str = 'normal') -> Session:
        state = make_state(42)
        first = next(iter(state.orders.values()))
        state.orders = {first.id: replace(first, demand=Decimal('40'), priority=priority)}
        state.locations = {first.id: ('warehouse', 'W1')}
        state.vehicles['TRUNK'] = replace(state.vehicles['TRUNK'], capacity=Decimal('40'))
        session = Session(state)
        session.enable_auto_replan()
        session.apply(session.prepare('distance'))
        self.assertEqual(len(session.plan.accepted), 1)
        return session

    def test_conflicting_warehouse_order_yields_to_critical(self) -> None:
        from logiroute.dispatch.admission import admit_critical
        s = self.session(); old = next(iter(s.state.orders))
        admit_critical(s, 'NEW', s.state.orders[old].destination, Decimal('1'), 0, 2000)
        s.process_auto_replan()
        self.assertIn('NEW', s.plan.accepted)
        self.assertIn(old, dict(s.plan.deferred))
        self.assertEqual(s.state.orders[old].status, 'pending')
        self.assertTrue(s.plan.report.safe_to_apply)
        self.assertTrue(s.audit().valid)

    def test_impossible_deadline_is_atomic(self) -> None:
        from logiroute.dispatch.admission import admit_critical, CriticalAdmissionError
        s = self.session(); before = s.snapshot()
        with self.assertRaises(CriticalAdmissionError):
            admit_critical(s, 'NEW', next(iter(s.state.orders.values())).destination, 1, 0, .001)
        self.assertEqual(s.snapshot(), before)

    def test_existing_critical_cannot_be_displaced(self) -> None:
        from logiroute.dispatch.admission import admit_critical, CriticalAdmissionError
        s = self.session('critical'); before = s.snapshot()
        with self.assertRaises(CriticalAdmissionError):
            admit_critical(s, 'NEW', next(iter(s.state.orders.values())).destination, 1, 0, 2000)
        self.assertEqual(s.snapshot(), before)

    def test_entered_load_is_protected_and_failure_does_not_pause(self) -> None:
        from logiroute.dispatch.admission import admit_critical, CriticalAdmissionError
        s = self.session(); s.depart(); before = s.snapshot()
        with self.assertRaises(CriticalAdmissionError):
            admit_critical(s, 'NEW', next(iter(s.state.orders.values())).destination, 1000, 0, 2000)
        self.assertEqual(s.snapshot(), before)

    def test_nonconflicting_order_preserves_commitments(self) -> None:
        from logiroute.dispatch.admission import admit_critical
        s = self.session(); old = next(iter(s.state.orders))
        s.state.vehicles['TRUNK'] = replace(s.state.vehicles['TRUNK'], capacity=Decimal('100'))
        admit_critical(s, 'NEW', s.state.orders[old].destination, 1, 0, 2000)
        s.process_auto_replan()
        self.assertEqual(set(s.plan.accepted), {old, 'NEW'})
        self.assertEqual(s._critical_admission['displaced_order_ids'], [])

    def test_exact_completion_conflict_preempts_without_late_signoff(self) -> None:
        from logiroute.dispatch.admission import admit_critical
        s = self.session(); old = next(iter(s.state.orders))
        s.state.vehicles['TRUNK'] = replace(s.state.vehicles['TRUNK'], capacity=Decimal('100'))
        hub = s.state.orders[old].hub
        s.state.config['hub_ids'] = [hub]
        cutoff = next(a.end for r in s.plan.routes for a in r.actions if a.kind == 'deliver')
        s.state.orders[old] = replace(s.state.orders[old], deadline=cutoff)
        admit_critical(s, 'NEW', s.state.orders[old].destination, 1, 0, cutoff)
        s.process_auto_replan()
        self.assertEqual(s.plan.accepted, ('NEW',))
        self.assertTrue(s.plan.report.valid)
        s.depart()
        while s.running: s.step()
        self.assertEqual(s.state.orders['NEW'].status, 'delivered')
        self.assertEqual(s.state.orders[old].status, 'pending')
        self.assertTrue(s.audit().valid)

    def test_inflight_preview_never_advances_real_vehicle(self) -> None:
        from logiroute.dispatch.admission import admit_critical
        s = self.session(); old = next(iter(s.state.orders))
        s.depart(); entered = dict(s.current); clock = s.state.now; positions = dict(s.state.positions)
        admit_critical(s, 'NEW', s.state.orders[old].destination, 1, 0, 2000)
        for key, action in entered.items():
            if action and action.kind not in ('wait', 'finish'):
                self.assertEqual(s.current[key], action)
        self.assertEqual(s.state.now, clock)
        self.assertEqual(s.state.positions, positions)
        while s.running: s.step()
        s.process_auto_replan()
        self.assertEqual(set(s.plan.accepted), {old, 'NEW'})
        self.assertTrue(s.plan.report.safe_to_apply)

    def test_api_rejection_keeps_snapshot_and_retry_can_reuse_id(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            initial = client.post('/api/v2/sessions', json={'seed':42}).json()
            url = '/api/v2/sessions/' + initial['id']
            fields = dict(revision=initial['revision'], command='add', id='NEW',
                          destination=initial['orders'][0]['destination'], demand='1',
                          earliest=0, deadline=.001, priority='critical', protect_critical=True)
            failed = client.post(url+'/commands', json=fields)
            self.assertEqual(failed.status_code, 422, failed.text)
            self.assertEqual(failed.json()['error']['kind'], 'critical_unavailable')
            self.assertIn('建议选择更晚', failed.json()['error']['message'])
            self.assertEqual(client.get(url).json(), initial)
            fields['deadline'] = 2000
            success = client.post(url+'/commands', json=fields)
            self.assertEqual(success.status_code, 200, success.text)
            self.assertIn('NEW', success.json()['plan']['accepted'])
            self.assertTrue(success.json()['audit']['valid'])


if __name__ == '__main__': unittest.main()
