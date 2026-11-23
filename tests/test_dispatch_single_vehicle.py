"""The single vehicle profile shares the dispatch engine and has no handoffs."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import unittest

from fastapi.testclient import TestClient

from logiroute.api import create_app
from logiroute.dispatch.admission import CriticalAdmissionError, admit_critical
from logiroute.dispatch.session import Session
from logiroute.dispatch.studio import defaults, studio_state
from logiroute.dispatch.validation import validate_plan


class TestSingleVehicleDispatch(unittest.TestCase):
    def make_session(self) -> Session:
        return Session(studio_state(42, defaults(), 'rush', operational=True, single_vehicle=True))

    def test_one_route_covers_orders_and_returns_to_depot_for_both_objectives(self) -> None:
        session = self.make_session()
        (vehicle,) = session.state.vehicles.values()
        for objective in ('distance', 'cost'):
            with self.subTest(objective=objective):
                plan = session.prepare(objective)
                self.assertTrue(plan.report.complete_all, plan.report)
                (route,) = plan.routes
                self.assertEqual(route.vehicle, vehicle.id)
                self.assertEqual((route.start_node, route.end_node), (vehicle.base, vehicle.base))
                self.assertEqual((route.actions[0].kind, route.actions[-1].kind), ('load', 'finish'))
                self.assertFalse(any(action.kind == 'unload' for action in route.actions))
                delivered = [action.ids[0] for action in route.actions if action.kind == 'deliver']
                self.assertCountEqual(delivered, session.state.orders.keys())
                self.assertEqual(session.state.orders[delivered[0]].priority, 'critical')
                for action in route.actions:
                    if action.kind == 'deliver' and session.state.orders[action.ids[0]].priority == 'critical':
                        order = session.state.orders[action.ids[0]]
                        self.assertGreaterEqual(action.start, order.earliest)
                        self.assertLessEqual(action.end, order.deadline)
                        self.assertFalse(order.allow_late)

    def test_generated_critical_orders_cannot_opt_out_of_the_deadline(self) -> None:
        session = self.make_session()
        initial_orders = set(session.state.orders)
        session.automatic(1, 42, 'critical')
        (key,) = set(session.state.orders) - initial_orders
        self.assertFalse(session.state.orders[key].allow_late)

    def test_api_rejects_late_critical_atomically_even_with_a_legacy_override(self) -> None:
        with TestClient(create_app()) as client:
            initial = client.post('/api/v2/sessions', json={
                'profile':'bjut-studio-single', 'seed':42, 'auto_replan':True,
            }).json()
            endpoint = f"/api/v2/sessions/{initial['id']}/commands"
            response = client.post(endpoint, json={'revision':initial['revision'], 'command':'plan', 'objective':'cost'})
            self.assertEqual(response.status_code, 200, response.text)
            planned = response.json()
            for override in ({}, {'protect_critical':True, 'allow_late':True}):
                response = client.post(endpoint, json={
                    'revision':planned['revision'], 'command':'add', 'id':'TOO-SOON',
                    'destination':'P01', 'demand':1, 'earliest':0, 'deadline':1,
                    'priority':'critical', **override,
                })
                self.assertEqual(response.status_code, 422, response.text[:1000])
                self.assertEqual(response.json()['error']['kind'], 'critical_unavailable')
            restored = client.get(f"/api/v2/sessions/{initial['id']}").json()
            for field in ('revision', 'now', 'orders', 'plan', 'events'):
                self.assertEqual(restored[field], planned[field])

    def test_in_transit_insert_keeps_cargo_and_executes_one_vehicle_to_return(self) -> None:
        session = self.make_session()
        session.apply(session.prepare('cost'))
        session.depart()
        session.step()
        vehicle_id = next(iter(session.state.vehicles))
        self.assertEqual(session.current[vehicle_id].kind, 'drive')
        locations = dict(session.state.locations)
        destination = next(iter(session.state.orders.values())).destination
        start = session.state.now
        admit_critical(session, 'NEW', destination, Decimal('0.25'), start + 5, start + 18)
        self.assertTrue(all(session.state.locations[key] == loc for key, loc in locations.items()))
        while session.running:
            session.step()
        session.process_auto_replan()
        self.assertTrue(session.plan.report.complete_all, session.plan.report.violations)
        (route,) = session.plan.routes
        self.assertEqual(route.vehicle, vehicle_id)
        new_load = next(i for i, action in enumerate(route.actions)
                        if action.kind == 'load' and 'NEW' in action.ids)
        new_delivery = next(i for i, action in enumerate(route.actions)
                            if action.kind == 'deliver' and 'NEW' in action.ids)
        self.assertLess(new_load, new_delivery)
        self.assertGreaterEqual(route.actions[new_delivery].start, start + 5)
        self.assertLessEqual(route.actions[new_delivery].end, start + 18)
        self.assertEqual(route.actions[new_load].source, session.state.vehicles[vehicle_id].base)
        lower_deliveries = [i for i, action in enumerate(route.actions)
                            if action.kind == 'deliver'
                            and session.state.orders[action.ids[0]].priority != 'critical']
        self.assertTrue(lower_deliveries)
        self.assertLess(new_delivery, min(lower_deliveries))
        self.assertTrue(all(action.kind == 'drive' for action in route.actions[:new_load]))
        session.depart()
        while session.running:
            session.step()
        self.assertTrue(session.audit().complete_all, session.audit().violations)
        self.assertEqual(session.state.positions[vehicle_id], session.state.vehicles[vehicle_id].base)

    def test_priority_pickup_rejects_overload_without_delaying_critical_behind_old_cargo(self) -> None:
        session = self.make_session()
        session.apply(session.prepare('cost'))
        session.depart()
        session.step()
        (vehicle,) = session.state.vehicles.values()
        destination = next(iter(session.state.orders.values())).destination
        plan_before = session.plan
        fingerprint = session.state.fingerprint()
        actions_before = dict(session.current)
        with self.assertRaises(CriticalAdmissionError):
            admit_critical(session, 'FULL', destination, vehicle.capacity,
                           session.state.now, session.state.now + 14, allow_late=True)
        self.assertEqual(session.state.fingerprint(), fingerprint)
        self.assertEqual(session.current, actions_before)
        self.assertIs(session.plan, plan_before)

    def test_validator_rejects_forged_handoff(self) -> None:
        session = self.make_session()
        plan = session.prepare('cost')
        (route,) = plan.routes
        actions = list(route.actions)
        index = next(i for i, action in enumerate(actions) if action.kind == 'deliver')
        actions[index] = replace(actions[index], kind='unload')
        report = validate_plan(session.state, replace(plan, routes=(replace(route, actions=tuple(actions)),)))
        self.assertFalse(report.valid)
        self.assertIn('hub_unload', report.violations)

    def test_api_modes_and_capacity_trial_do_not_mutate_original_session(self) -> None:
        with TestClient(create_app()) as client:
            def create(profile: str) -> dict:
                response = client.post('/api/v2/sessions', json={'profile':profile, 'seed':42})
                self.assertEqual(response.status_code, 200, response.text)
                return response.json()

            single = create('bjut-studio-single')
            fleet = create('bjut-studio-operational')
            self.assertTrue(single['single_vehicle'])
            self.assertNotEqual(single['id'], fleet['id'])
            self.assertEqual(len(single['vehicles']), 1)
            self.assertGreater(len(fleet['vehicles']), 1)
            self.assertNotIn('single_vehicle', fleet)
            parameters = single['studio']['parameters']
            (vehicle,) = single['vehicles']
            parameters['capacities'][vehicle['id']] = '0.99'
            response = client.post(f"/api/v2/sessions/{single['id']}/trial",
                                   json={'revision':single['revision'], 'parameters':parameters})
            self.assertEqual(response.status_code, 200, response.text)
            trial = response.json()
            self.assertTrue(trial['single_vehicle'])
            self.assertEqual(trial['vehicles'][0]['capacity'], '0.99')
            self.assertTrue(trial['plan']['report']['valid'])
            self.assertEqual(trial['plan']['accepted'], [])
            self.assertTrue(trial['plan']['deferred'])
            original = client.get(f"/api/v2/sessions/{single['id']}").json()
            self.assertEqual(original['vehicles'][0]['capacity'], vehicle['capacity'])
            self.assertIsNone(original['plan'])
