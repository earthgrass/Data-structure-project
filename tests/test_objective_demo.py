from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import unittest


class TestObjectiveDemo(unittest.TestCase):
    def test_same_input_tradeoff_and_independent_small_reference(self) -> None:
        from logiroute.dispatch.controlled_demo import objective_demo
        r=objective_demo()
        a,b=r['runs']
        self.assertEqual(a['input_fingerprint'],b['input_fingerprint'])
        self.assertLess(a['distance'],b['distance'])
        self.assertGreater(a['cost'],b['cost'])
        self.assertTrue(all(x['audit']['valid'] and x['audit']['complete_all'] for x in r['runs']))
        self.assertEqual(a['distance'],r['reference']['minimum_distance'])
        self.assertEqual(b['cost'],r['reference']['minimum_cost'])
        self.assertEqual(r['reference']['enumerated_closed_routes'],4)

    def test_original_deadline_and_same_site_individual_ids(self) -> None:
        from logiroute.dispatch.controlled_demo import demo_state
        from logiroute.dispatch.models import Parcel
        from logiroute.dispatch.session import Session
        s=demo_state();a=next(iter(s.orders.values()))
        s.orders[a.id]=replace(a,earliest=30,deadline=32)
        s.orders['SAME']=Parcel('SAME',a.destination,Decimal('0.1'),30,34)
        s.locations['SAME']=s.locations[a.id]
        p=Session(s).prepare('distance')
        self.assertTrue(p.report.complete_all,p.deferred)
        ends={k:x.end for r in p.routes for x in r.actions if x.kind=='deliver' for k in x.ids}
        self.assertEqual(ends[a.id],32);self.assertEqual(ends['SAME'],34)
        self.assertTrue(any(x.kind=='wait' for r in p.routes for x in r.actions))

    def test_impossible_window_preserves_identity(self) -> None:
        from logiroute.dispatch.controlled_demo import demo_state
        from logiroute.dispatch.session import Session
        s=demo_state();key=next(iter(s.orders));s.orders[key]=replace(s.orders[key],deadline=1)
        p=Session(s).prepare('distance')
        self.assertTrue(p.report.valid);self.assertFalse(p.report.complete_all)
        self.assertIn(key,dict(p.deferred));self.assertEqual(len(s.orders),1)

    def test_stale_traffic_plan_cannot_apply(self) -> None:
        from logiroute.dispatch.controlled_demo import demo_state
        from logiroute.dispatch.session import Session,ConflictError
        session=Session(demo_state());p=session.prepare('distance')
        road=next(a for r in p.routes for a in r.actions if a.kind=='drive')
        session.traffic(road.source,road.target,'congested')
        with self.assertRaises(ConflictError):session.apply(p)

    def test_demo_endpoint_is_isolated_from_sessions(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            r=client.get('/api/v2/experiments/objective-demo')
            self.assertEqual(r.status_code,200,r.text)
            self.assertTrue(r.json()['simulated_costs'])
            self.assertEqual(client.app.state.dispatch_service.sessions,{})
