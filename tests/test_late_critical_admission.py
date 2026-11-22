"""Late but physically feasible dynamic critical orders retain honest signoff evidence."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import unittest
from logiroute.dispatch.admission import admit_critical, CriticalAdmissionError
from logiroute.dispatch.models import Parcel
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.session import Session
from logiroute.dispatch.validation import validate_plan


class TestLateCriticalAdmission(unittest.TestCase):
    def session(self) -> Session:
        state = make_state(42)
        first = next(iter(state.orders.values()))
        state.orders = {first.id: replace(first, demand=Decimal('40'))}
        state.locations = {first.id: ('warehouse', 'W1')}
        state.vehicles['TRUNK'] = replace(state.vehicles['TRUNK'], capacity=Decimal('40'))
        session = Session(state)
        session.enable_auto_replan()
        session.apply(session.prepare('distance'))
        return session

    def test_late_critical_is_admitted_and_actually_signed(self) -> None:
        session = self.session()
        old = next(iter(session.state.orders.values()))
        admit_critical(session, 'LATE', old.destination, 1, 0, .001, allow_late=True)
        session.process_auto_replan()
        self.assertIn('LATE', session.plan.accepted)
        self.assertIn(old.id, dict(session.plan.deferred))
        self.assertTrue(session.plan.report.valid, session.plan.report.violations)
        self.assertGreater(session._critical_admission['expected_signoff'], .001)
        self.assertGreater(session._critical_admission['lateness_minutes'], 0)
        session.depart()
        while session.running:
            session.step()
        self.assertEqual(session.state.orders['LATE'].status, 'delivered')
        self.assertTrue(session.audit().valid, session.audit().violations)

    def test_past_deadline_can_be_recorded_and_planned(self) -> None:
        state = make_state(42)
        destination = next(iter(state.orders.values())).destination
        state.orders = {}
        state.locations = {}
        state.now = 10
        session = Session(state)
        admit_critical(session, 'OVERDUE', destination, Decimal('1'), 0, 1, allow_late=True)
        session.process_auto_replan()
        self.assertIn('OVERDUE', session.plan.accepted)
        self.assertGreater(session._critical_admission['expected_signoff'], 1)

    def test_assigns_fastest_verified_delivery_vehicle(self) -> None:
        state = make_state(42)
        destination = next(iter(state.orders.values())).destination
        state.orders = {'FAST': Parcel('FAST', destination, 1, 0, .001, 'critical', allow_late=True)}
        state.locations = {'FAST': ('warehouse', state.config['warehouse_ids'][0])}
        candidates = []
        for hub in state.config['hub_ids']:
            trial = deepcopy(state)
            trial.config['hub_ids'] = [hub]
            plan = Session(trial).prepare('cost')
            if 'FAST' in plan.accepted and plan.report.valid:
                signoff = next(a.end for r in plan.routes for a in r.actions
                               if a.kind == 'deliver' and 'FAST' in a.ids)
                vehicle = next(r.vehicle for r in plan.routes for a in r.actions
                               if a.kind == 'deliver' and 'FAST' in a.ids)
                candidates.append((signoff, hub, vehicle))
        self.assertGreaterEqual(len(candidates), 2)
        plan = Session(state).prepare('cost')
        self.assertIn('FAST', plan.accepted)
        self.assertTrue(validate_plan(state, plan).valid)
        chosen_hub = dict(plan.assignments)['FAST']
        chosen_signoff = next(a.end for r in plan.routes for a in r.actions
                              if a.kind == 'deliver' and 'FAST' in a.ids)
        self.assertEqual((chosen_signoff, chosen_hub), min((end, hub) for end, hub, _ in candidates))

    def test_independent_validator_requires_explicit_late_permission(self) -> None:
        state = make_state(42)
        destination = next(iter(state.orders.values())).destination
        state.orders = {'FAST': Parcel('FAST', destination, 1, 0, .001, 'critical', allow_late=True)}
        state.locations = {'FAST': ('warehouse', state.config['warehouse_ids'][0])}
        plan = Session(state).prepare('distance')
        self.assertTrue(validate_plan(state, plan).valid)
        state.orders['FAST'] = replace(state.orders['FAST'], allow_late=False)
        report = validate_plan(state, replace(plan, fingerprint=state.fingerprint()))
        self.assertFalse(report.valid)
        self.assertIn('customer_service', report.violations)

    def test_api_late_critical_admission_and_boolean_gate(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            initial = client.post('/api/v2/sessions', json={'seed':42}).json()
            url = '/api/v2/sessions/' + initial['id']
            fields = dict(revision=initial['revision'],command='add',id='LATE',
                          destination=initial['orders'][0]['destination'],demand='1',
                          earliest=0,deadline=.001,priority='critical',protect_critical=True,
                          allow_late=True)
            bad = client.post(url+'/commands',json={**fields,'allow_late':'true'})
            self.assertEqual(bad.status_code,422)
            self.assertEqual(client.get(url).json(),initial)
            accepted = client.post(url+'/commands',json=fields)
            self.assertEqual(accepted.status_code,200,accepted.text)
            value = accepted.json()
            self.assertIn('LATE',value['plan']['accepted'])
            self.assertGreater(value['critical_admission']['lateness_minutes'],0)
            self.assertTrue(value['audit']['valid'])

    def test_physical_capacity_conflict_still_rolls_back(self) -> None:
        session = self.session()
        before = session.snapshot()
        with self.assertRaises(CriticalAdmissionError):
            admit_critical(session, 'TOO_HEAVY', next(iter(session.state.orders.values())).destination,
                           Decimal('1000'), 0, 1, allow_late=True)
        self.assertEqual(session.snapshot(), before)

    def test_downgrading_late_critical_clears_its_override(self) -> None:
        session = self.session()
        destination = next(iter(session.state.orders.values())).destination
        admit_critical(session, 'LATE', destination, 1, 0, .001, allow_late=True)
        session.priority('LATE', 'urgent')
        self.assertEqual(session.state.orders['LATE'].priority, 'urgent')
        self.assertFalse(session.state.orders['LATE'].allow_late)


if __name__ == '__main__':
    unittest.main()
