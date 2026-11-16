from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
import unittest


class TestOperationsStudio(unittest.TestCase):
    def test_profile_has_three_operating_hubs_and_meets_shape(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults
        s=studio_state(42,defaults(),'relaxed')
        self.assertEqual(len(s.config['hub_ids']),3)
        self.assertEqual(len(s.vehicles),4)
        self.assertGreaterEqual(len(s.graph.node_ids),30)
        self.assertGreaterEqual(sum(n.node_type.value=='warehouse' for n in s.graph.nodes),2)
        self.assertGreaterEqual(sum(n.node_type.value=='transfer' for n in s.graph.nodes),3)
        self.assertGreaterEqual(sum(n.node_type.value=='customer' for n in s.graph.nodes),15)
        self.assertGreaterEqual(len(s.graph.edges),50)
        self.assertEqual(len(s.orders),24)

    def test_trial_preserves_original_and_exact_capacity(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults,trial_session
        from logiroute.dispatch.session import Session
        a=Session(studio_state(42,defaults(),'relaxed'));before=a.state.fingerprint()
        settings=defaults();settings['capacities']={k:'0.1' for k in a.state.vehicles}
        b=trial_session(a,settings)
        self.assertEqual(before,a.state.fingerprint())
        self.assertTrue(all(v.capacity==Decimal('0.1') for v in b.state.vehicles.values()))
        self.assertFalse(b.prepare('distance').report.complete_all)
        self.assertTrue(b.prepare('distance').report.valid)
        self.assertEqual([(o.id,o.destination,o.demand,o.deadline) for o in a.state.orders.values()],[(o.id,o.destination,o.demand,o.deadline) for o in b.state.orders.values()])

    def test_cost_is_fuel_plus_time_plus_maintenance_and_not_compounded(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults,trial_session
        from logiroute.dispatch.session import Session
        c=defaults();s=studio_state(42,c,'relaxed');e=next(iter(s.graph.edges))
        expected=e.metadata['fuel_liters']*float(c['fuel_price'])+e.travel_time/60*float(c['driver_hourly'])+e.distance*float(c['maintenance_per_km'])
        self.assertAlmostEqual(e.cost,expected)
        a=Session(s);b=trial_session(a,c);again=trial_session(b,c)
        self.assertEqual([e.cost for e in b.state.graph.edges],[e.cost for e in again.state.graph.edges])

    def test_invalid_parameters_and_entered_actions_are_rejected(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults,trial_session
        from logiroute.dispatch.session import Session,ConflictError
        c=defaults();bad=deepcopy(c);bad['fuel_price']='NaN'
        with self.assertRaises(ValueError):studio_state(42,bad,'relaxed')
        bad=deepcopy(c);bad['hub_ids']=bad['hub_ids'][:2]
        with self.assertRaises(ValueError):studio_state(42,bad,'relaxed')
        a=Session(studio_state(42,c,'relaxed'));p=a.prepare('distance');a.apply(p);a.depart()
        with self.assertRaises(ConflictError):trial_session(a,c)

    def test_api_trial_is_isolated_and_revision_checked(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        from logiroute.dispatch.studio import defaults
        with TestClient(create_app()) as client:
            r=client.post('/api/v2/sessions',json={'profile':'bjut-studio','seed':42,'window_mode':'relaxed'})
            self.assertEqual(r.status_code,200,r.text);a=r.json()
            r=client.post('/api/v2/sessions/'+a['id']+'/trial',json={'revision':a['revision'],'parameters':defaults()})
            self.assertEqual(r.status_code,200,r.text);self.assertNotEqual(a['id'],r.json()['id'])
            self.assertEqual(client.get('/api/v2/sessions/'+a['id']).json()['revision'],a['revision'])
            r=client.post('/api/v2/sessions/'+a['id']+'/trial',json={'revision':a['revision']+1,'parameters':defaults()})
            self.assertEqual(r.status_code,409)

    def test_actual_overdue_unserved_order_has_penalty_without_late_signoff(self) -> None:
        from dataclasses import replace
        from logiroute.dispatch.studio import studio_state,defaults
        from logiroute.dispatch.session import Session
        s=studio_state(42,defaults(),'relaxed');key=next(iter(s.orders));s.orders[key]=replace(s.orders[key],deadline=1)
        session=Session(s);p=session.prepare('distance');self.assertIn(key,dict(p.deferred))
        session.apply(p);session.depart()
        while session.running:session.step()
        snapshot=session.snapshot();self.assertTrue(snapshot['audit']['valid'])
        self.assertEqual([o['id'] for o in snapshot['studio']['late_orders']],[key])
        self.assertGreater(snapshot['studio']['late_orders'][0]['penalty'],0)
        self.assertNotEqual(session.state.orders[key].status,'delivered')

    def test_studio_traffic_increase_triggers_verified_checkpoint_replanning(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            s=client.post('/api/v2/sessions',json={'profile':'bjut-studio','window_mode':'relaxed'}).json()
            key=s['id']
            def command(kind: str,**fields: object) -> dict:
                nonlocal s
                r=client.post('/api/v2/sessions/'+key+'/commands',json={'revision':s['revision'],'command':kind,**fields})
                self.assertEqual(r.status_code,200,r.text);s=r.json();return s
            command('plan',objective='distance');command('depart')
            edge=s['edges'][0];command('traffic',source=edge['source'],target=edge['target'],status='congested')
            self.assertIn('等待',s['studio']['auto_replan'])
            while s['running']:command('step')
            self.assertTrue(s['ready']);self.assertTrue(s['plan']['report']['valid'])
            self.assertEqual(s['plan']['traffic_version'],s['traffic_version'])
            self.assertIn('已自动',s['studio']['auto_replan'])

    def test_fuel_price_and_per_vehicle_capacity_really_change_routes(self) -> None:
        from logiroute.dispatch.studio import studio_state,defaults,trial_session
        from logiroute.dispatch.session import Session
        from logiroute.algorithms.window_calibration import route_structure
        source=Session(studio_state(42,defaults(),'relaxed'));original=source.prepare('cost')
        for change in ('fuel','capacity'):
            parameters=defaults()
            if change=='fuel':parameters['fuel_price']='30'
            else:parameters['capacities']={k:('150' if k=='TRUNK' else '20') for k in source.state.vehicles}
            plan=trial_session(source,parameters).prepare('cost')
            self.assertTrue(plan.report.valid);self.assertTrue(plan.report.complete_all)
            self.assertNotEqual(route_structure(plan),route_structure(original))
            self.assertEqual(set(plan.accepted),set(original.accepted))

    def test_studio_rejects_non_integer_seeds_like_existing_profile(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            for seed in (True,'42',42.5):
                r=client.post('/api/v2/sessions',json={'profile':'bjut-studio','seed':seed,'window_mode':'relaxed'})
                self.assertEqual(r.status_code,422,r.text[:200])
            # Failure-injection tests only the adapter's lossless error boundary.
            # It does not replace a successful generator or planner in any experiment.
            from unittest.mock import patch
            from logiroute.dispatch.time_windows import WindowGenerationError
            attempts=[{'trial':1,'reason':'controlled exhausted-window failure'}]
            with patch('logiroute.dispatch.studio.calibrate_windows',side_effect=WindowGenerationError(attempts)):
                r=client.post('/api/v2/sessions',json={'profile':'bjut-studio','seed':42})
            self.assertEqual(r.status_code,422)
            self.assertEqual(r.json()['error']['kind'],'generation_exhausted')
            self.assertEqual(r.json()['error']['attempts'],attempts)
