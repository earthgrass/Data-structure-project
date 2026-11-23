"""Critical parcels use the trunk's direct customer leg when rush permits it."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from logiroute.dispatch.admission import admit_critical
from logiroute.dispatch.session import Session
from logiroute.dispatch.studio import defaults, studio_state
from logiroute.dispatch.validation import validate_plan


class TestCriticalPriority(unittest.TestCase):
    def test_rush_critical_is_signed_by_trunk_before_hub_unloading(self) -> None:
        state = studio_state(42, defaults(), 'rush', operational=True)
        critical = {order.id for order in state.orders.values() if order.priority == 'critical'}
        self.assertTrue(critical)
        for objective in ('distance', 'cost'):
            plan = Session(state).prepare(objective)
            self.assertTrue(plan.report.valid, plan.report.violations)
            trunk = next(route for route in plan.routes if state.vehicles[route.vehicle].role == 'trunk')
            signed = [action for action in trunk.actions if action.kind == 'deliver' and action.ids[0] in critical]
            self.assertEqual({oid for action in signed for oid in action.ids}, critical)
            first_unload = min(action.start for action in trunk.actions if action.kind == 'unload')
            self.assertTrue(all(action.end <= first_unload for action in signed))

    def test_direct_trunk_beats_two_echelon_critical_signoff(self) -> None:
        state = studio_state(42, defaults(), 'rush', operational=True)
        critical_id = next(order.id for order in state.orders.values() if order.priority == 'critical')
        direct = Session(state).prepare('cost')
        legacy_state = deepcopy(state)
        legacy_state.config['direct_critical_delivery'] = False
        legacy = Session(legacy_state).prepare('cost')
        def signoff(plan):
            return next(action.end for route in plan.routes for action in route.actions
                        if action.kind == 'deliver' and critical_id in action.ids)
        self.assertLess(signoff(direct), signoff(legacy))

    def test_dynamic_critical_admission_assigns_trunk_delivery(self) -> None:
        session = Session(studio_state(42, defaults(), 'rush', operational=True))
        session.apply(session.prepare('cost'))
        destination = next(order.destination for order in session.state.orders.values() if order.priority == 'critical')
        admit_critical(session, 'NEW_CRITICAL', destination, 1, session.state.now + 2,
                       session.state.now + 12, allow_late=True)
        session.process_auto_replan()
        self.assertIn('NEW_CRITICAL', session.plan.accepted)
        self.assertTrue(session.plan.report.valid, session.plan.report.violations)
        self.assertTrue(any(action.kind == 'deliver' and 'NEW_CRITICAL' in action.ids
                            for route in session.plan.routes if session.state.vehicles[route.vehicle].role == 'trunk'
                            for action in route.actions))

    def test_in_transit_critical_is_direct_after_entered_action_finishes(self) -> None:
        session = Session(studio_state(42, defaults(), 'rush', operational=True))
        session.apply(session.prepare('cost'))
        session.depart()
        session.step()
        before = tuple(session.events)
        destination = next(order.destination for order in session.state.orders.values() if order.priority == 'critical')
        admit_critical(session, 'IN_TRANSIT_FAST', destination, 1, session.state.now + 2,
                       session.state.now + 12, allow_late=True)
        while session.running:
            session.step()
        session.process_auto_replan()
        self.assertEqual(before, tuple(session.events[:len(before)]))
        self.assertTrue(session.audit().valid, session.audit().violations)
        self.assertTrue(session.plan.report.valid, session.plan.report.violations)
        self.assertTrue(any(action.kind == 'deliver' and 'IN_TRANSIT_FAST' in action.ids
                            for route in session.plan.routes if session.state.vehicles[route.vehicle].role == 'trunk'
                            for action in route.actions))

    def test_validator_rejects_trunk_service_of_normal_order(self) -> None:
        state = studio_state(42, defaults(), 'rush', operational=True)
        plan = Session(state).prepare('cost')
        trunk = next(route for route in plan.routes if state.vehicles[route.vehicle].role == 'trunk')
        critical_action = next(action for action in trunk.actions if action.kind == 'deliver')
        normal_id = next(order.id for order in state.orders.values() if order.priority == 'normal')
        altered = tuple(replace(action, ids=(normal_id,)) if action is critical_action else action
                        for action in trunk.actions)
        routes = tuple(replace(route, actions=altered) if route.vehicle == trunk.vehicle else route
                       for route in plan.routes)
        report = validate_plan(state, replace(plan, routes=routes))
        self.assertFalse(report.valid)
        self.assertIn('customer_service', report.violations)


if __name__ == '__main__':
    unittest.main()
