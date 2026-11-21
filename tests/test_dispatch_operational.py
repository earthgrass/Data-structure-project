"""Realistic campus demonstration keeps legacy profiles and routing honest."""
from __future__ import annotations
from decimal import Decimal
import unittest


class TestDispatchOperational(unittest.TestCase):
    def test_heavy_orders_and_strict_full_coverage_for_fixed_seeds(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults
        from logiroute.dispatch.session import Session
        for seed in (0,1,42,100,2026):
            state=studio_state(seed,defaults(),'strict',operational=True)
            self.assertEqual(sum(o.demand==Decimal('20') for o in state.orders.values()),1)
            self.assertEqual(sum(o.demand==Decimal('30') for o in state.orders.values()),1)
            self.assertEqual(state.vehicles['TRUNK'].capacity,Decimal('150'))
            self.assertTrue(all(v.capacity==Decimal('50') for v in state.vehicles.values() if v.role=='delivery'))
            plan=Session(state).prepare('cost')
            self.assertTrue(plan.report.valid)
            self.assertTrue(plan.report.complete_all)
            self.assertEqual(len(plan.accepted),24)

    def test_cost_uses_fast_road_while_distance_uses_shorter_campus_road(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults
        from logiroute.algorithms.dijkstra import shortest_path
        state=studio_state(42,defaults(),'relaxed',operational=True)
        distance=shortest_path(state.graph,'W1','T_EAST','distance')
        cost=shortest_path(state.graph,'W1','T_EAST','cost')
        self.assertNotEqual(distance.path,cost.path)
        self.assertLess(distance.cross_metrics['distance'],cost.cross_metrics['distance'])
        self.assertLess(cost.cross_metrics['cost'],distance.cross_metrics['cost'])
        self.assertLess(cost.cross_metrics['travel_time'],distance.cross_metrics['travel_time'])
        service=next(e for e in state.graph.edges if e.metadata['highway']=='service')
        walking=next(e for e in state.graph.edges if e.metadata['highway']=='living_street')
        self.assertAlmostEqual(service.distance/service.travel_time*60,8)
        self.assertAlmostEqual(walking.distance/walking.travel_time*60,5)
        self.assertFalse(any(e.metadata['highway'] in ('footway','pedestrian') for e in state.graph.edges))

    def test_congestion_changes_the_cost_path(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults
        from logiroute.algorithms.dijkstra import shortest_path
        from logiroute.dispatch.traffic import Network
        state=studio_state(42,defaults(),'relaxed',operational=True)
        before=shortest_path(state.graph,'W1','T_EAST','cost')
        self.assertIn(('T_WEST','R428834798'),list(zip(before.path,before.path[1:])))
        traffic=Network(state.graph,state.config['traffic'])
        traffic.update('T_WEST','R428834798','congested')
        after=shortest_path(traffic.snapshot(),'W1','T_EAST','cost')
        self.assertNotEqual(before.path,after.path)
        self.assertTrue(after.reachable)

    def test_parameter_trial_preserves_slow_speed_and_rejects_oversize_order(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults,trial_session
        from logiroute.dispatch.session import Session
        source=Session(studio_state(42,defaults(),'relaxed',operational=True))
        original=next(e for e in source.state.graph.edges if e.metadata['highway']=='service')
        parameters=defaults();parameters['capacities']={key:('150' if key=='TRUNK' else '20') for key in parameters['capacities']}
        trial=trial_session(source,parameters)
        slow=trial.state.graph.get_edge(*original.key)
        self.assertAlmostEqual(slow.travel_time,original.travel_time)
        plan=trial.prepare('cost')
        self.assertTrue(plan.report.valid)
        self.assertFalse(plan.report.complete_all)
        self.assertTrue(any(order.demand==Decimal('30') and order.id in dict(plan.deferred) for order in trial.state.orders.values()))

    def test_api_exposes_opt_in_profile_without_changing_legacy(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            modern=client.post('/api/v2/sessions',json={'profile':'bjut-studio-operational','seed':42,'window_mode':'strict'})
            self.assertEqual(modern.status_code,200,modern.text[:200]);data=modern.json()
            self.assertIn('20',[o['demand'] for o in data['orders']])
            self.assertIn('30',[o['demand'] for o in data['orders']])
            self.assertTrue(data['studio']['model_note'])
            self.assertEqual(data['studio']['variant'],'heavy_slow_roads')
            legacy=client.post('/api/v2/sessions',json={'profile':'bjut-studio','seed':42,'window_mode':'relaxed'})
            self.assertEqual(legacy.status_code,200,legacy.text[:200])
            self.assertNotIn('30',[o['demand'] for o in legacy.json()['orders']])
            self.assertEqual(legacy.json()['studio']['variant'],'legacy')
