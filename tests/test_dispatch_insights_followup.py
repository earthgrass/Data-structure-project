from __future__ import annotations

from dataclasses import replace
import unittest

from logiroute.dispatch.insights import build_impact
from logiroute.dispatch.models import Action, Plan, Route
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.session import Session


class TestDispatchInsightsFollowup(unittest.TestCase):
    def test_unused_road_version_update_does_not_report_changed_vehicle_journeys(self) -> None:
        session = Session(make_state(42))
        session.apply(session.prepare('distance'))
        old_plan = session.plan
        used = {(a.source, a.target) for route in old_plan.routes for a in route.actions if a.kind == 'drive'}
        edge = next(edge for edge in session.state.graph.edges if edge.key not in used)
        session.traffic(*edge.key, 'moderate')
        session.apply(session.prepare('distance'))
        impact = session.snapshot()['planning_insights']['impact']
        self.assertNotEqual(impact['baseline_traffic_version'], impact['traffic_version'])
        for old, new, row in zip(old_plan.routes, session.plan.routes, impact['vehicles']):
            with self.subTest(vehicle=row['vehicle']):
                self.assertEqual(tuple(replace(a, traffic_version=0) for a in old.actions),
                                 tuple(replace(a, traffic_version=0) for a in new.actions))
                self.assertEqual(row['delta'], {'distance': 0, 'cost': 0, 'travel_time': 0})
                self.assertFalse(row['changed'], 'only the evidence version changed, not this vehicle journey')

    def test_meaningful_action_changes_remain_visible(self) -> None:
        state = make_state(42)
        vehicle = next(iter(state.vehicles))
        base = state.positions[vehicle]
        original = Action(vehicle, 'drive', 1, 2, base, 'destination', ('parcel',), 3, 1, 4, 0, 1)
        route = Route(vehicle, base, base, (original,))
        before = Plan('distance', 0, 0, (), (route,), (), ())
        variations = {'vehicle': 'another', 'kind': 'wait', 'start': 0.5, 'end': 3,
                      'source': 'other-source', 'target': 'other-target', 'ids': ('other-parcel',),
                      'distance': 5, 'travel_time': 2, 'cost': 6, 'batch': 2}
        for field, value in variations.items():
            with self.subTest(field=field):
                changed = replace(original, **{field: value})
                after = replace(before, routes=(replace(route, actions=(changed,)),), revision=1)
                self.assertTrue(build_impact(state, before, after, [])['vehicles'][0]['changed'])

    def test_completion_filter_still_requires_full_traffic_evidence_identity(self) -> None:
        state = make_state(42)
        vehicle = next(iter(state.vehicles)); base = state.positions[vehicle]
        original = Action(vehicle, 'drive', 1, 2, base, 'destination', distance=3, cost=4, travel_time=1, traffic_version=1)
        route = Route(vehicle, base, base, (original,))
        before = Plan('distance', 0, 1, (), (route,), (), ())
        after = replace(before, revision=1)
        unrelated_event = {'kind': 'action', 'action': replace(original, traffic_version=0)}
        result = build_impact(state, before, after, [unrelated_event])
        self.assertEqual(result['before']['distance'], 3)
        self.assertFalse(result['vehicles'][0]['changed'])
        completed = build_impact(state, before, after, [{'kind': 'action', 'action': original}])
        self.assertEqual(completed['before']['distance'], 0)
        self.assertTrue(completed['vehicles'][0]['changed'])


if __name__ == '__main__': unittest.main()
