"""Soft lower-priority deadlines and hard critical completion regression tests."""
from __future__ import annotations

from dataclasses import replace
import unittest


class TestLateDelivery(unittest.TestCase):
    def test_pressure_input_is_not_filtered_to_all_on_time(self) -> None:
        from logiroute.dispatch.studio import defaults, studio_state
        from logiroute.dispatch.session import Session
        from logiroute.dispatch.validation import validate_plan
        state = studio_state(42, defaults(), 'pressure', operational=True)
        self.assertEqual(state.config['late_delivery']['hard_priorities'], ['critical'])
        self.assertEqual(len(state.orders), 24)
        for objective in ('distance', 'cost'):
            plan = Session(state).prepare(objective)
            self.assertTrue(plan.report.valid, plan.report.violations)
            self.assertTrue(plan.report.complete_all)
            self.assertTrue(validate_plan(state, plan).valid)
            services = {oid: action.end for route in plan.routes for action in route.actions
                        if action.kind == 'deliver' for oid in action.ids}
            self.assertTrue(any(services.get(oid, 0) > order.deadline
                                for oid, order in state.orders.items() if order.priority == 'normal'))
            self.assertTrue(all(services.get(oid, 0) <= order.deadline
                                for oid, order in state.orders.items() if order.priority == 'critical' and oid in services))
            self.assertTrue(all(services.get(oid, 0) <= order.deadline
                                for oid, order in state.orders.items() if order.priority == 'urgent' and oid in services))

    def test_urgent_lateness_is_worse_than_normal_lateness(self) -> None:
        from logiroute.dispatch.deadlines import fleet_lateness_score
        from logiroute.dispatch.models import Action, Parcel, Route
        orders = {'U': Parcel('U','P1',1,0,10,'urgent'),
                  'N': Parcel('N','P2',1,0,10,'normal')}
        urgent_late = (Route('V','H','H',(Action('V','deliver',9,10,'P2','P2',('N',)),
                                        Action('V','deliver',10,11,'P1','P1',('U',)))),)
        normal_late = (Route('V','H','H',(Action('V','deliver',9,10,'P1','P1',('U',)),
                                        Action('V','deliver',10,20,'P2','P2',('N',)))),)
        self.assertLess(fleet_lateness_score(normal_late, orders),
                        fleet_lateness_score(urgent_late, orders))

    def test_late_normal_signoff_executes_and_audits(self) -> None:
        from logiroute.dispatch.studio import defaults, studio_state
        from logiroute.dispatch.session import Session
        state = studio_state(42, defaults(), 'pressure', operational=True)
        session = Session(state)
        plan = session.prepare('distance')
        self.assertTrue(plan.report.valid)
        session.apply(plan)
        predicted = session.snapshot()['studio']['planned_late_orders']
        self.assertTrue(predicted)
        self.assertTrue(all(row['priority'] == 'normal' for row in predicted))
        session.depart()
        while session.running:
            session.step()
        self.assertTrue(session.audit().valid, session.audit().violations)
        actual = {oid: event['action'].end for event in session.events if event['kind'] == 'action'
                  and event['action'].kind == 'deliver' for oid in event['action'].ids}
        self.assertTrue(any(actual.get(oid, 0) > order.deadline for oid, order in session.state.orders.items()
                            if order.priority == 'normal'))
        studio = session.snapshot()['studio']
        self.assertEqual(len(studio['late_orders']), len(predicted))
        self.assertTrue(all(row['status'] == 'delivered' and row['signed_at'] > row['deadline']
                            for row in studio['late_orders']))
        self.assertGreater(studio['late_penalty_total'], 0)
        self.assertFalse(studio['planned_late_orders'])

    def test_strict_mode_still_rejects_late_normal(self) -> None:
        from logiroute.dispatch.studio import defaults, studio_state
        from logiroute.dispatch.session import Session
        state = studio_state(42, defaults(), 'relaxed', operational=True)
        key = next(k for k, order in state.orders.items() if order.priority == 'normal')
        state.orders[key] = replace(state.orders[key], deadline=state.now + 0.1)
        plan = Session(state).prepare('distance')
        self.assertNotIn(key, plan.accepted)

    def test_independent_validator_keeps_critical_deadline_hard(self) -> None:
        from logiroute.dispatch.studio import defaults, studio_state
        from logiroute.dispatch.session import Session
        from logiroute.dispatch.validation import validate_plan
        state = studio_state(42, defaults(), 'pressure', operational=True)
        plan = Session(state).prepare('distance')
        key = next(k for k, order in state.orders.items() if order.priority == 'critical')
        end = next(action.end for route in plan.routes for action in route.actions
                   if action.kind == 'deliver' and key in action.ids)
        state.orders[key] = replace(state.orders[key], deadline=end / 2)
        report = validate_plan(state, replace(plan, fingerprint=state.fingerprint()))
        self.assertFalse(report.valid)
        self.assertIn('customer_service', report.violations)

    def test_operational_api_defaults_to_pressure_without_changing_explicit_strict(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            pressure = client.post('/api/v2/sessions', json={
                'profile': 'bjut-studio-operational', 'seed': 42})
            self.assertEqual(pressure.status_code, 200, pressure.text[:200])
            self.assertEqual(pressure.json()['time_windows']['mode'], 'pressure')
            strict = client.post('/api/v2/sessions', json={
                'profile': 'bjut-studio-operational', 'seed': 42,
                'window_mode': 'strict'})
            self.assertEqual(strict.status_code, 200, strict.text[:200])
            self.assertEqual(strict.json()['time_windows']['mode'], 'strict')

    def test_pressure_critical_insertion_still_rolls_back_when_late(self) -> None:
        from logiroute.dispatch.studio import defaults, studio_state
        from logiroute.dispatch.session import Session
        from logiroute.dispatch.admission import admit_critical, CriticalAdmissionError
        state = studio_state(42, defaults(), 'pressure', operational=True)
        session = Session(state)
        session.apply(session.prepare('distance'))
        before = session.state.fingerprint()
        destination = next(iter(state.config['candidate_ids']))
        with self.assertRaises(CriticalAdmissionError):
            admit_critical(session, 'IMPOSSIBLE_CRITICAL', destination, 1, 0, 0.5)
        self.assertEqual(session.state.fingerprint(), before)
        self.assertNotIn('IMPOSSIBLE_CRITICAL', session.state.orders)

    def test_stale_road_plan_does_not_claim_current_lateness_forecast(self) -> None:
        from logiroute.dispatch.studio import defaults, studio_state
        from logiroute.dispatch.session import Session
        session = Session(studio_state(42, defaults(), 'pressure', operational=True))
        session.apply(session.prepare('distance'))
        self.assertTrue(session.snapshot()['studio']['planned_late_orders'])
        edge = next(iter(session.state.graph.edges))
        session.traffic(edge.source_id, edge.target_id, 'light')
        self.assertFalse(session.snapshot()['studio']['planned_late_orders'])
        self.assertTrue(session.snapshot()['planning_insights']['timeline']['stale'])


if __name__ == '__main__':
    unittest.main()
