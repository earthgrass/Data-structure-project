"""Short urgent completion deadlines with scheduled service starts."""
from __future__ import annotations

import unittest

from logiroute.dispatch.session import Session
from logiroute.dispatch.studio import defaults, studio_state


class TestUrgentWindows(unittest.TestCase):
    def test_initial_urgent_deadline_and_nonzero_earliest(self) -> None:
        state = studio_state(42, defaults(), 'rush', operational=True)
        urgent = [order for order in state.orders.values() if order.priority == 'urgent']
        self.assertTrue(urgent)
        self.assertTrue(all(0 <= order.earliest - state.now < 15 for order in urgent))
        self.assertTrue(all(0 < order.deadline - order.earliest < 20 for order in urgent))
        self.assertTrue(any(order.earliest > state.now for order in urgent))
        critical = [order for order in state.orders.values() if order.priority == 'critical']
        self.assertTrue(all(0 <= order.earliest - state.now < 10 for order in critical))
        self.assertTrue(all(0 < order.deadline - order.earliest < 15 for order in critical))
        self.assertTrue(all(order.earliest < order.deadline for order in state.orders.values()))
        self.assertEqual(state.fingerprint(), studio_state(42, defaults(), 'rush', operational=True).fingerprint())

    def test_short_urgent_windows_are_reported_honestly(self) -> None:
        session = Session(studio_state(42, defaults(), 'rush', operational=True))
        plan = session.prepare('cost')
        self.assertTrue(plan.report.valid, plan.report.violations)
        session.apply(plan)
        forecast = session.snapshot()['studio']['planned_late_orders']
        services = {oid: action.end for route in plan.routes for action in route.actions
                    if action.kind == 'deliver' for oid in action.ids}
        late_urgent = {order.id for order in session.state.orders.values()
                       if order.priority == 'urgent' and services.get(order.id, 0) > order.deadline}
        self.assertEqual(late_urgent, {row['id'] for row in forecast if row['priority'] == 'urgent'})

    def test_automatic_urgent_orders_use_short_relative_windows(self) -> None:
        session = Session(studio_state(42, defaults(), 'rush', operational=True))
        session.automatic(5, 100, 'urgent')
        generated = [order for order in session.state.orders.values() if order.id.startswith(session.state.config['dynamic_prefix'])]
        self.assertEqual(len(generated), 5)
        self.assertTrue(all(0 <= order.earliest - session.state.now < 15 for order in generated))
        self.assertTrue(all(0 < order.deadline - order.earliest < 20 for order in generated))
        self.assertTrue(any(order.earliest > session.state.now for order in generated))

    def test_automatic_critical_orders_follow_short_window_limits(self) -> None:
        session = Session(studio_state(42, defaults(), 'rush', operational=True))
        session.automatic(5, 42, 'critical')
        generated = [order for order in session.state.orders.values() if order.id.startswith(session.state.config['dynamic_prefix'])]
        self.assertTrue(all(0 <= order.earliest - session.state.now < 10 for order in generated))
        self.assertTrue(all(0 < order.deadline - order.earliest < 15 for order in generated))

    def test_simulated_traffic_schedule_is_exposed_for_dashboard(self) -> None:
        session = Session(studio_state(42, defaults(), 'rush', operational=True))
        settings = session.snapshot()['settings']['simulated_traffic']
        self.assertEqual(settings['interval_seconds'], 12)
        self.assertEqual(settings['seed'], 42)

    def test_manual_rush_orders_enforce_both_bounds(self) -> None:
        session = Session(studio_state(42, defaults(), 'rush', operational=True))
        original_count = len(session.state.orders)
        destination = next(iter(session.state.orders.values())).destination
        with self.assertRaises(ValueError):
            session.add_order('TOO_LATE_START', destination, 1, session.state.now + 10,
                              session.state.now + 12, 'critical', allow_late=True)
        with self.assertRaises(ValueError):
            session.add_order('TOO_LONG', destination, 1, session.state.now + 5,
                              session.state.now + 20, 'critical', allow_late=True)
        with self.assertRaises(ValueError):
            session.add_order('URGENT_LATE_START', destination, 1, session.state.now + 15,
                              session.state.now + 16, 'urgent')
        with self.assertRaises(ValueError):
            session.add_order('URGENT_LONG', destination, 1, session.state.now + 5,
                              session.state.now + 25, 'urgent')
        self.assertEqual(len(session.state.orders), original_count)


if __name__ == '__main__':
    unittest.main()
