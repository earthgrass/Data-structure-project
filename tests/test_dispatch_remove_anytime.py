"""Removal at a checkpoint keeps already loaded goods physically accountable."""
from __future__ import annotations

import unittest
from dataclasses import replace

from fastapi.testclient import TestClient
from logiroute.api import create_app
from logiroute.dispatch.session import Session, ConflictError
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.validation import validate_plan


class TestRemoveAnytime(unittest.TestCase):
    def test_loaded_order_can_be_removed_and_returned_without_graph_mutation(self) -> None:
        session = Session(make_state(42))
        session.enable_auto_replan()
        session.apply(session.prepare('distance'))
        session.depart()
        session.step()
        order_id = next(key for key, location in session.state.locations.items() if location[0] == 'vehicle')
        roads = tuple((edge.source_id, edge.target_id) for edge in session.state.graph.edges)
        session.remove_order(order_id)
        self.assertEqual(session.state.orders[order_id].status, 'cancelled')
        self.assertEqual(session.state.locations[order_id][0], 'vehicle')
        while session.running:
            session.step()
        session.process_auto_replan()
        self.assertTrue(session.plan.report.safe_to_apply, session.plan.report.violations)
        self.assertNotIn(order_id, session.plan.accepted)
        session.depart()
        while session.running:
            session.step()
        self.assertEqual(session.state.locations[order_id][0], 'returned')
        self.assertTrue(session.audit().valid, session.audit().violations)
        self.assertEqual(roads, tuple((edge.source_id, edge.target_id) for edge in session.state.graph.edges))

    def test_entered_signoff_is_not_reversed(self) -> None:
        session = Session(make_state(1))
        session.apply(session.prepare('distance'))
        session.depart()
        while session.running and not any(a and a.kind == 'deliver' for a in session.current.values()):
            session.step()
        action = next(a for a in session.current.values() if a and a.kind == 'deliver')
        with self.assertRaises(ConflictError):
            session.remove_order(action.ids[0])

    def test_remove_during_entered_load_keeps_terminal_status_and_inventory(self) -> None:
        session = Session(make_state(1))
        session.enable_auto_replan()
        session.apply(session.prepare('cost'))
        session.depart()
        action = next(a for a in session.current.values() if a and a.kind == 'load')
        order_id = action.ids[0]
        session.remove_order(order_id)
        while session.running:
            session.step()
        session.process_auto_replan()
        self.assertEqual(session.state.orders[order_id].status, 'cancelled')
        self.assertEqual(session.state.locations[order_id][0], 'vehicle')
        self.assertTrue(session.audit().valid, session.audit().violations)
        self.assertTrue(session.plan.report.safe_to_apply, session.plan.report.violations)

    def test_validator_rejects_forged_cancelled_return(self) -> None:
        session = Session(make_state(42))
        session.apply(session.prepare('distance'))
        session.depart()
        session.step()
        order_id = next(key for key, location in session.state.locations.items() if location[0]=='vehicle')
        session.remove_order(order_id)
        while session.running:
            session.step()
        proposal = session.prepare('distance')
        self.assertTrue(proposal.report.safe_to_apply)
        route = next(route for route in proposal.routes if any(a.kind=='return_cancelled' for a in route.actions))
        altered = tuple(replace(a, ids=('NONEXISTENT',)) if a.kind=='return_cancelled' else a for a in route.actions)
        routes = tuple(replace(item, actions=altered) if item.vehicle==route.vehicle else item for item in proposal.routes)
        forged = replace(proposal, routes=routes)
        self.assertFalse(validate_plan(session.state, forged).valid)

    def test_api_remove_loaded_order_replans_and_preserves_cargo(self) -> None:
        with TestClient(create_app()) as client:
            response = client.post('/api/v2/sessions', json={'seed':42,'auto_replan':True})
            self.assertEqual(response.status_code, 200, response.text)
            snapshot = response.json()
            session_id = snapshot['id']

            def command(kind: str, **fields: object) -> dict:
                nonlocal snapshot
                response = client.post(f'/api/v2/sessions/{session_id}/commands',
                                       json={'revision':snapshot['revision'],'command':kind,**fields})
                self.assertEqual(response.status_code, 200, response.text)
                snapshot = response.json()
                return snapshot

            command('plan')
            command('depart')
            command('step')
            order_id = next(order['id'] for order in snapshot['orders'] if order['location'][0]=='vehicle')
            cargo_before = next(vehicle['load'] for vehicle in snapshot['vehicles'] if order_id in vehicle['cargo'])
            command('remove', id=order_id, auto_replan=True)
            self.assertEqual(next(order for order in snapshot['orders'] if order['id']==order_id)['status'], 'cancelled')
            self.assertEqual(next(vehicle['load'] for vehicle in snapshot['vehicles'] if order_id in vehicle['cargo']), cargo_before)
            while snapshot['running']:
                command('step')
            self.assertTrue(snapshot['plan']['report']['safe_to_apply'])
            self.assertTrue(snapshot['audit']['valid'], snapshot['audit']['violations'])
            self.assertNotIn(order_id, snapshot['plan']['accepted'])


if __name__ == '__main__':
    unittest.main()
