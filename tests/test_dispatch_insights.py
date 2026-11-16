from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from logiroute.dispatch.insights import build_impact
from logiroute.dispatch.models import Action, Plan, Route
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.session import Session


class TestDispatchInsights(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.initial = make_state(42)

    def session(self) -> Session:
        return Session(deepcopy(self.initial))

    def test_initial_and_first_plan_have_no_invented_comparison_or_actual_signoff(self) -> None:
        s = self.session()
        initial = s.snapshot()['planning_insights']
        self.assertIsNone(initial['impact'])
        self.assertTrue(initial['timeline']['stale'])
        self.assertTrue(all(o['expected'] is None and o['actual'] is None for o in initial['timeline']['orders']))
        s.apply(s.prepare('distance'))
        info = s.snapshot()['planning_insights']
        self.assertIsNone(info['impact'])
        self.assertFalse(info['timeline']['stale'])
        self.assertTrue(all(o['expected'] and o['actual'] is None for o in info['timeline']['orders']))

    def test_same_destination_keeps_identity_and_arrival_is_before_wait_and_service(self) -> None:
        s = self.session()
        first = next(iter(s.state.orders.values()))
        s.state.orders = {key: replace(first, id=key, earliest=1000, deadline=10000, demand=1) for key in ('A', 'B')}
        s.state.locations = {key: ('warehouse', s.state.config['warehouse_ids'][0]) for key in s.state.orders}
        s.apply(s.prepare('distance'))
        rows = s.snapshot()['planning_insights']['timeline']['orders']
        self.assertEqual([r['order_id'] for r in rows], ['A', 'B'])
        timings = [r['expected'] for r in rows]
        self.assertEqual(timings[0]['arrival'], timings[1]['arrival'])
        self.assertLess(timings[0]['arrival'], 1000)
        self.assertGreaterEqual(timings[0]['service_start'], 1000)
        self.assertNotEqual(timings[0]['signoff'], timings[1]['signoff'])

    def test_completed_prefix_excluded_and_impact_frozen_during_execution(self) -> None:
        s = self.session()
        s.apply(s.prepare('distance')); old = s.plan
        s.depart(); s.step(); s.pause()
        while s.running: s.step()
        actual_distance = sum(e['action'].distance for e in s.events if e['kind'] == 'action')
        self.assertGreater(actual_distance, 0)
        s.apply(s.prepare('cost'))
        impact = s.snapshot()['planning_insights']['impact']
        self.assertAlmostEqual(impact['before']['distance'], sum(r.total_distance for r in old.routes) - actual_distance)
        self.assertEqual(impact['comparison_basis'], 'remaining_at_checkpoint')
        self.assertEqual(impact['objective_before'], 'distance')
        self.assertEqual(impact['objective_after'], 'cost')
        self.assertAlmostEqual(impact['delta']['cost'], impact['after']['cost'] - impact['before']['cost'])
        s.depart(); s.step()
        self.assertEqual(impact, s.snapshot()['planning_insights']['impact'])

    def test_equal_end_time_without_matching_event_is_not_completed(self) -> None:
        s = self.session(); car = next(iter(s.state.vehicles)); base = s.state.positions[car]
        a = Action(car, 'drive', 0, 1, base, 'target', distance=2, cost=4, travel_time=1)
        b = replace(a, vehicle='another', distance=3)
        old = Plan('distance', 0, 0, (), (Route(car, base, base, (a, b)),), (), ())
        new = replace(old, revision=1, routes=(Route(car, base, base, (b,)),))
        s.state.now = 1
        result = build_impact(s.state, old, new, [{'kind': 'action', 'action': a}])
        self.assertEqual(result['before']['distance'], 3)
        self.assertEqual(result['after']['distance'], 3)
        self.assertEqual(result['delta']['distance'], 0)

    def test_delivery_actual_is_based_on_events_and_keeps_terminal_identity(self) -> None:
        s = self.session(); s.apply(s.prepare('distance')); s.depart()
        while s.running: s.step()
        rows = s.snapshot()['planning_insights']['timeline']['orders']
        self.assertEqual(len(rows), len(s.state.orders))
        self.assertTrue(all(r['status'] == 'delivered' and r['expected'] is None and r['actual'] for r in rows))
        ends = {oid: e['action'].end for e in s.events if e['kind'] == 'action' and e['action'].kind == 'deliver' for oid in e['action'].ids}
        for row in rows:
            self.assertEqual(row['actual']['signoff'], ends[row['order_id']])
            self.assertGreaterEqual(row['actual']['service_start'], row['actual']['arrival'])

    def test_cancelled_and_unaccepted_have_no_predicted_signoff(self) -> None:
        s = self.session(); first = next(iter(s.state.orders.values()))
        s.apply(s.prepare('distance')); s.cancel(first.id)
        s.add_order('LATE', first.destination, 1, 0, .001, 'urgent')
        s.apply(s.prepare('distance'))
        info = s.snapshot()['planning_insights']; rows = {r['order_id']: r for r in info['timeline']['orders']}
        self.assertIsNone(rows[first.id]['expected']); self.assertIsNone(rows[first.id]['actual'])
        self.assertEqual(rows[first.id]['status'], 'cancelled')
        self.assertIsNone(rows['LATE']['expected']); self.assertTrue(rows['LATE']['deferred_reason'])
        self.assertIn(first.id, info['impact']['cancelled']); self.assertIn('LATE', info['impact']['deferred'])
        s.cancel('LATE'); s.apply(s.prepare('distance'))
        impact = s.snapshot()['planning_insights']['impact']
        self.assertIn('LATE', impact['cancelled'], 'cancelling a deferred order is still an input change')
        self.assertNotIn(first.id, impact['cancelled'], 'older cancellations are not reported again')
        self.assertNotIn('LATE', impact['no_longer_planned'], 'a deferred order never had a planned service')

    def test_pause_and_legacy_input_mutations_invalidate_eta(self) -> None:
        for change in ('pause', 'add', 'traffic'):
            with self.subTest(change=change):
                s = self.session(); s.apply(s.prepare('distance'))
                if change == 'pause': s.pause()
                elif change == 'add':
                    first = next(iter(s.state.orders.values())); s.add_order('N', first.destination, 1, 0, 2000, 'normal')
                else:
                    edge = next(iter(s.state.graph.edges)); s.traffic(*edge.key, 'moderate')
                timeline = s.snapshot()['planning_insights']['timeline']
                self.assertTrue(timeline['stale']); self.assertTrue(timeline['stale_reason'])
                self.assertTrue(all(r['expected'] is None for r in timeline['orders']))

    def test_snapshot_projection_is_pure_and_traffic_baseline_is_historical(self) -> None:
        s = self.session(); s.apply(s.prepare('distance'))
        edge = next(iter(s.state.graph.edges)); s.traffic(*edge.key, 'moderate')
        s.apply(s.prepare('distance'))
        before = (s.state.fingerprint(), deepcopy(s.events), deepcopy(s.plan))
        first = s.snapshot()['planning_insights']; second = s.snapshot()['planning_insights']
        self.assertEqual(first, second)
        self.assertEqual(before, (s.state.fingerprint(), s.events, s.plan))
        self.assertTrue(first['impact']['historical_baseline'])
        self.assertNotEqual(first['impact']['baseline_traffic_version'], first['impact']['traffic_version'])

    def test_zero_completion_slack_is_legal_and_not_missing(self) -> None:
        s = self.session(); plan = s.prepare('distance')
        a = next(a for r in plan.routes for a in r.actions if a.kind == 'deliver'); oid = a.ids[0]
        s.state.orders[oid] = replace(s.state.orders[oid], deadline=a.end)
        # Preserve a valid witness route, updating its physical-input fingerprint.
        s.apply(replace(plan, fingerprint=s.state.fingerprint()))
        row = next(r for r in s.snapshot()['planning_insights']['timeline']['orders'] if r['order_id'] == oid)
        self.assertEqual(row['expected']['slack'], 0)
        self.assertEqual(row['expected']['signoff'], row['deadline'])

    def test_blocked_proposal_has_its_own_source_and_does_not_replace_valid_plan(self) -> None:
        s = self.session(); s.enable_auto_replan(); s.apply(s.prepare('distance'))
        s.depart(); s.step(); s.pause()
        while s.running: s.step()
        old = s.plan
        car = next(key for key in s.state.vehicles if any(loc == ('vehicle', key) for loc in s.state.locations.values()))
        for edge in list(s.state.graph.get_neighbors(s.state.positions[car])): s.traffic(*edge.key, 'blocked')
        s.process_auto_replan()
        info = s.snapshot()['planning_insights']
        self.assertEqual(s._order_control_status, 'blocked')
        self.assertIs(s.plan, old)
        self.assertEqual(info['explanations']['source'], 'blocked_proposal')
        self.assertFalse(info['explanations']['stale'])
        self.assertTrue(info['timeline']['stale'])
        attempt = s._last_attempt
        s.prepare('cost')
        self.assertIs(s._last_attempt, attempt, 'read-only prepare cannot replace observed diagnostic evidence')
        first = next(iter(s.state.orders.values()))
        s.add_order('AFTER_BLOCK', first.destination, 1, s.state.now, s.state.now + 2000, 'urgent')
        info = s.snapshot()['planning_insights']
        self.assertEqual(info['explanations']['source'], 'blocked_proposal')
        self.assertTrue(info['explanations']['stale'])


if __name__ == '__main__': unittest.main()
