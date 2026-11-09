from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
from typing import Any
import unittest


class TestCampusDelivery(unittest.TestCase):
    def config(self) -> dict[str,Any]:
        from logiroute.dispatch.real_map import map_config
        return map_config('bjut-campus')

    def test_actual_landmarks_and_five_parallel_hubs(self) -> None:
        from logiroute.dispatch.scenario import make_state
        s=make_state(42,self.config())
        self.assertEqual(set(s.config['hub_ids']),{'T_CENTER','T_EAST','T_WEST','T_NORTH','T_SOUTH'})
        self.assertEqual(len(s.vehicles),6)
        center=s.graph.get_node('T_CENTER')
        self.assertIn('游泳馆北侧',center.name)
        self.assertGreater(center.metadata['reference_lat'],39.8757199)
        self.assertEqual(center.metadata['location_source'],'user_description')
        self.assertTrue(center.metadata['approximate'])
        for key in ('T_EAST','T_WEST','T_NORTH','T_SOUTH'):
            n=s.graph.get_node(key)
            self.assertIn('外卖柜',n.name)
            self.assertTrue(n.metadata['approximate'])
            self.assertLessEqual(n.metadata['snap_distance_m'],100)

    def test_named_campus_pool_and_source_evidence(self) -> None:
        from logiroute.dispatch.scenario import make_state
        s=make_state(42,self.config()); groups=s.config['candidate_groups']
        self.assertEqual(len(groups['campus']),22)
        self.assertEqual(len(groups['surrounding']),8)
        self.assertEqual(len(set(groups['campus']+groups['surrounding'])),30)
        for key in groups['campus']:
            n=s.graph.get_node(key)
            self.assertEqual(n.metadata['zone'],'campus')
            self.assertTrue(n.metadata['reference_osm_way'])
            self.assertLessEqual(n.metadata['snap_distance_m'],100)
        self.assertTrue(any('宿舍' in s.graph.get_node(k).name for k in groups['campus']))
        self.assertTrue(any('图书馆' in s.graph.get_node(k).name for k in groups['campus']))

    def test_region_quota_is_exact_across_five_seeds(self) -> None:
        from logiroute.dispatch.scenario import make_state
        signature=None
        for seed in (0,1,42,100,2026):
            s=make_state(seed,self.config()); again=make_state(seed,self.config())
            self.assertEqual(len(s.orders),24)
            self.assertEqual(len({o.destination for o in s.orders.values()}),24)
            self.assertEqual(sum(s.graph.get_node(o.destination).metadata['zone']=='campus' for o in s.orders.values()),20)
            self.assertEqual(s.fingerprint(),again.fingerprint())
            roads=[(e.source_id,e.target_id,e.distance,e.metadata['geometry']) for e in s.graph.edges]
            if signature is None: signature=roads
            self.assertEqual(roads,signature)

    def test_bad_quotas_are_rejected_without_silent_fallback(self) -> None:
        from logiroute.dispatch.scenario import make_state
        for quotas in ({'campus':25,'surrounding':0},{'campus':23,'surrounding':1},{'campus':True,'surrounding':23},{'unknown':24},{'campus':-1,'surrounding':25}):
            c=self.config(); c['destination_quotas']=quotas
            with self.assertRaises(ValueError): make_state(42,c)

    def test_every_candidate_returns_and_both_plans_execute(self) -> None:
        from logiroute.dispatch.scenario import make_state
        from logiroute.dispatch.session import Session
        from logiroute.algorithms.dijkstra import shortest_path
        s=make_state(42,self.config())
        for key in s.config['candidate_ids']+s.config['hub_ids']:
            self.assertTrue(shortest_path(s.graph,'W1',key,'distance').reachable)
            self.assertTrue(shortest_path(s.graph,key,'W1','distance').reachable)
        for objective in ('distance','cost'):
            session=Session(make_state(42,self.config())); plan=session.prepare(objective)
            self.assertTrue(plan.report.complete_all,plan.report)
            session.apply(plan); session.depart()
            while session.running: session.step()
            self.assertTrue(session.audit().valid); self.assertTrue(session.audit().complete_all)
            self.assertEqual(session.state.positions,{k:v.base for k,v in session.state.vehicles.items()})

    def test_same_site_dynamic_identity_and_original_profile(self) -> None:
        from logiroute.dispatch.scenario import make_state
        from logiroute.dispatch.session import Session
        from logiroute.dispatch.real_map import map_config
        s=Session(make_state(42,self.config())); original=next(iter(s.state.orders.values()))
        s.add_order('CAMPUS-EXTRA',original.destination,Decimal('0.1'),0,2000,'urgent')
        self.assertEqual(len(s.state.orders),25); s.cancel('CAMPUS-EXTRA')
        self.assertEqual(s.state.orders[original.id].status,'pending')
        old=make_state(42,map_config())
        self.assertEqual(len(old.orders),8); self.assertEqual(len(old.config['hub_ids']),3)

    def test_opt_in_api_profile(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            result=client.post('/api/v2/sessions',json={'seed':42,'profile':'bjut-campus'})
            self.assertEqual(result.status_code,200,result.text); data=result.json()
            self.assertEqual(data['map']['campus_candidate_count'],22)
            self.assertEqual(data['map']['initial_campus_orders'],20)
            self.assertEqual(len(data['orders']),24)
