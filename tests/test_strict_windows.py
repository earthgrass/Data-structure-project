from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import unittest


class TestStrictWindows(unittest.TestCase):
    def test_service_deadline_forces_different_route_without_priority_changes(self) -> None:
        from logiroute.core import Node,Edge
        from logiroute.core.enums import NodeType
        from logiroute.graph import LogisticsGraph
        from logiroute.dispatch.algorithms import Paths,build_route
        from logiroute.dispatch.models import Job,VehicleSpec
        g=LogisticsGraph()
        for key,kind in [('D',NodeType.TRANSFER),('A',NodeType.CUSTOMER),('B',NodeType.CUSTOMER)]:g.add_node(Node(key,key,kind,0,0))
        for a,b,d in [('D','A',1),('A','D',1),('A','B',1),('B','D',1),('D','B',6),('B','A',5)]:g.add_edge(Edge(a,b,d,d,d))
        car=VehicleSpec('V','C','delivery','D',Decimal(10))
        a=Job('A','A','deliver',('OA',),Decimal(1),'normal',0,100,4)
        b=Job('B','B','deliver',('OB',),Decimal(1),'normal',0,100,0)
        wide,failed=build_route(Paths(g),car,[a,b],0);self.assertFalse(failed)
        strict,failed=build_route(Paths(g),car,[a,replace(b,deadline=2)],0);self.assertFalse(failed)
        sequence=lambda r:[x.ids[0] for x in r.actions if x.kind=='deliver']
        self.assertEqual(sequence(wide),['OA','OB']);self.assertEqual(sequence(strict),['OB','OA'])
        self.assertGreater(strict.total_distance,wide.total_distance)
        self.assertEqual(next(x.end for x in strict.actions if x.ids==('OB',)),2)
        partial,failed=build_route(Paths(g),car,[a,replace(b,deadline=1)],0)
        self.assertEqual(sequence(partial),['OA']);self.assertEqual(failed['B'],'completion_deadline')
        waiting,failed=build_route(Paths(g),car,[replace(a,earliest=20,deadline=30),replace(b,deadline=2)],0)
        self.assertFalse(failed)
        self.assertEqual(next(x.end for x in waiting.actions if x.ids==('OA',)),24)
        self.assertTrue(any(x.kind=='wait' and x.target=='A' and x.end==20 for x in waiting.actions))
        _,failed=build_route(Paths(g),car,[replace(a,earliest=20,deadline=23),replace(b,deadline=2)],0)
        self.assertEqual(failed['A'],'completion_deadline')

    def test_strict_campus_changes_routes_and_baseline_really_violates_deadlines(self) -> None:
        from logiroute.dispatch.real_map import map_config
        from logiroute.dispatch.scenario import make_state
        from logiroute.dispatch.time_windows import calibrate_windows,load_window_policy
        from logiroute.dispatch.planner import plan_dispatch
        from logiroute.dispatch.validation import validate_plan
        c=map_config('bjut-campus'); original=make_state(42,c); strict=calibrate_windows(original,load_window_policy(c),'strict')
        self.assertEqual(original.orders['O1'].deadline,2000)
        for key,o in original.orders.items():
            changed=strict.orders[key]
            self.assertEqual((o.id,o.destination,o.demand,o.priority),(changed.id,changed.destination,changed.demand,changed.priority))
            self.assertLess(changed.deadline-changed.earliest,30)
        evidence=strict.config['window_evidence']
        self.assertTrue(evidence['changed_vehicles']);self.assertTrue(evidence['baseline_late_orders'])
        self.assertGreaterEqual(len(evidence['attempts']),1)
        baseline=plan_dispatch(original)
        replay=validate_plan(strict,replace(baseline,fingerprint=strict.fingerprint()))
        self.assertFalse(replay.valid);self.assertIn('customer_service',replay.violations)
        for mode in ('distance','cost'):
            self.assertTrue(plan_dispatch(strict,mode).report.complete_all)

    def test_modes_are_fair_and_seed_reproducible(self) -> None:
        from logiroute.dispatch.real_map import map_config
        from logiroute.dispatch.generation import generate_state
        c=map_config('bjut-campus')
        a,_=generate_state(42,c,window_mode='strict');b,_=generate_state(42,c,window_mode='relaxed');again,_=generate_state(42,c,window_mode='strict')
        self.assertEqual(a.fingerprint(),again.fingerprint())
        self.assertEqual(a.positions,b.positions);self.assertEqual(a.vehicles,b.vehicles)
        self.assertEqual([(o.id,o.destination,o.demand,o.priority) for o in a.orders.values()],[(o.id,o.destination,o.demand,o.priority) for o in b.orders.values()])
        self.assertEqual([(e.source_id,e.target_id,e.distance,e.travel_time,e.cost) for e in a.graph.edges],[(e.source_id,e.target_id,e.distance,e.travel_time,e.cost) for e in b.graph.edges])
        self.assertTrue(all(o.deadline==2000 for o in b.orders.values()))

    def test_exact_deadlines_execute_and_tampering_is_rejected(self) -> None:
        from logiroute.dispatch.real_map import map_config
        from logiroute.dispatch.generation import generate_state
        from logiroute.dispatch.session import Session
        from logiroute.dispatch.validation import validate_plan
        state,_=generate_state(42,map_config('bjut-campus'),window_mode='strict')
        session=Session(state);p=session.prepare('distance')
        service=next(a for r in p.routes for a in r.actions if a.kind=='deliver')
        malformed=deepcopy(state); oid=service.ids[0]; malformed.orders[oid]=replace(malformed.orders[oid],deadline=service.end-0.0001)
        self.assertFalse(validate_plan(malformed,replace(p,fingerprint=malformed.fingerprint())).valid)
        session.apply(p);session.depart()
        while session.running:session.step()
        self.assertTrue(session.audit().valid);self.assertTrue(session.audit().complete_all)
        for e in session.events:
            a=e.get('action')
            if a and a.kind=='deliver':self.assertLessEqual(a.end,state.orders[a.ids[0]].deadline)

    def test_conflicting_window_generation_rejects_without_soft_fallback(self) -> None:
        from logiroute.dispatch.real_map import map_config
        from logiroute.dispatch.scenario import make_state
        from logiroute.dispatch.time_windows import calibrate_windows,load_window_policy,WindowGenerationError
        c=map_config('bjut-campus');policy=load_window_policy(c);policy['deadline_advance_minutes']=2000
        with self.assertRaises(WindowGenerationError) as caught:calibrate_windows(make_state(42,c),policy,'strict')
        self.assertTrue(caught.exception.attempts)
        # Appointment construction must intersect, never widen, configured bounds.
        c['timing']['window_start']=30
        bounded=calibrate_windows(make_state(42,c),load_window_policy(c),'strict')
        self.assertTrue(all(o.earliest>=30 for o in bounded.orders.values()))

    def test_api_defaults_strict_and_explicit_relaxed_remains_available(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            r=client.post('/api/v2/sessions',json={'seed':42,'profile':'bjut-campus'})
            self.assertEqual(r.status_code,200,r.text);s=r.json()
            self.assertEqual(s['time_windows']['mode'],'strict');self.assertTrue(s['time_windows']['changed_vehicles'])
            self.assertEqual(s['settings']['automatic_window_width'],20)
            self.assertLess(max(o['deadline'] for o in s['orders']),90)
            r=client.post('/api/v2/sessions',json={'seed':42,'profile':'bjut-campus','window_mode':'relaxed'})
            self.assertEqual(r.status_code,200,r.text)
            self.assertTrue(all(o['deadline']==2000 for o in r.json()['orders']))
            self.assertEqual(client.post('/api/v2/sessions',json={'profile':'bjut-campus','window_mode':'unknown'}).status_code,422)
