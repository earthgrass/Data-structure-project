from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json
import unittest


class TestRealMap(unittest.TestCase):
    def test_directed_component_is_handwritten_and_deterministic(self) -> None:
        from logiroute.algorithms.osm_network import largest_component
        self.assertEqual(largest_component({'a':['b'],'b':['a','c'],'c':[],'z':[]}),['a','b'])

    def test_fixed_graph_and_seeded_unique_candidate_pool(self) -> None:
        from logiroute.dispatch.scenario import make_state
        from logiroute.dispatch.real_map import map_config
        first=make_state(42,map_config()); again=make_state(42,map_config()); other=make_state(1,map_config())
        signature=lambda s:[(e.source_id,e.target_id,e.distance,e.metadata['geometry']) for e in s.graph.edges]
        self.assertEqual(signature(first),signature(other))
        self.assertEqual(first.fingerprint(),again.fingerprint())
        destinations=[o.destination for o in first.orders.values()]
        self.assertEqual(len(destinations),len(set(destinations)))
        self.assertTrue(set(destinations)<=set(first.config['candidate_ids']))
        self.assertNotEqual(destinations,[o.destination for o in other.orders.values()])

    def test_geometry_and_source_match_actual_network(self) -> None:
        import xml.etree.ElementTree as ET
        from logiroute.algorithms.dijkstra import shortest_path
        from logiroute.dispatch.scenario import make_state
        from logiroute.dispatch.real_map import map_config
        s=make_state(42,map_config()); s.graph.validate()
        source=ET.parse(Path(__file__).resolve().parents[1]/'data/bjut/source.osm').getroot()
        ways={w.attrib['id']:w for w in source.findall('way')}
        for e in s.graph.edges:
            a=s.graph.get_node(e.source_id); b=s.graph.get_node(e.target_id)
            self.assertEqual(e.metadata['geometry'][0],[a.x,a.y])
            self.assertEqual(e.metadata['geometry'][-1],[b.x,b.y])
            self.assertTrue(e.metadata['osm_way']); self.assertGreater(e.distance,0)
            way=ways[e.metadata['osm_way']]; refs=[n.attrib['ref'] for n in way.findall('nd')]
            tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
            first=refs.index(a.metadata['osm_id']); last=refs.index(b.metadata['osm_id'])
            direction=tags.get('oneway','yes' if tags.get('junction')=='roundabout' else 'no')
            if direction in ('yes','true','1'): self.assertLess(first,last)
            elif direction=='-1': self.assertGreater(first,last)
            self.assertNotIn(tags.get('access'),('no','private'))
        for node in s.graph.nodes:
            self.assertTrue(node.metadata['osm_id'])
        for candidate in s.config['candidate_ids']:
            self.assertTrue(shortest_path(s.graph,'W1',candidate,'distance').reachable)
            self.assertTrue(shortest_path(s.graph,candidate,'W1','distance').reachable)
        self.assertEqual(s.config['map']['source'],'OpenStreetMap')

    def test_pool_add_cancel_and_actual_execution(self) -> None:
        from logiroute.dispatch.scenario import make_state
        from logiroute.dispatch.real_map import map_config
        from logiroute.dispatch.session import Session
        from logiroute.dispatch.models import Parcel
        session=Session(make_state(42,map_config()))
        junction=next(n.id for n in session.state.graph.nodes if n.metadata.get('routing_only'))
        with self.assertRaises(ValueError): session.add_order('bad',junction,1,0,2000,'normal')
        dest=session.state.config['candidate_ids'][0]
        session.add_order('same-site',dest,Decimal('0.1'),0,2000,'urgent'); session.cancel('same-site')
        self.assertEqual(session.state.orders['same-site'].status,'cancelled')
        for objective in ('distance','cost'):
            fresh=Session(make_state(42,map_config())); plan=fresh.prepare(objective)
            self.assertTrue(plan.report.complete_all,plan.report)
            fresh.apply(plan); fresh.depart()
            while fresh.running: fresh.step()
            self.assertTrue(fresh.audit().valid); self.assertTrue(fresh.audit().complete_all)

    def test_profile_does_not_change_old_default(self) -> None:
        from logiroute.dispatch.scenario import make_state
        s=make_state(42)
        self.assertEqual(len(s.graph.nodes),35)
        self.assertNotIn('candidate_ids',s.config)

    def test_api_profile_and_candidate_validation(self) -> None:
        from fastapi.testclient import TestClient
        from logiroute.api import create_app
        with TestClient(create_app()) as client:
            r=client.post('/api/v2/sessions',json={'seed':42,'profile':'bjut'})
            self.assertEqual(r.status_code,200,r.text); data=r.json()
            self.assertEqual(data['map']['source'],'OpenStreetMap')
            self.assertEqual(sum(n['type']=='customer' for n in data['nodes']),30)
            self.assertTrue(all('geometry' in e for e in data['edges']))
            self.assertEqual(client.post('/api/v2/sessions',json={'profile':'unknown'}).status_code,422)

    def test_oneway_and_access_are_not_fabricated(self) -> None:
        from logiroute.algorithms.osm_network import compile_roads
        nodes={'a':{'lon':0.,'lat':0.},'b':{'lon':1.,'lat':0.},'c':{'lon':1.,'lat':1.},'d':{'lon':0.,'lat':1.}}
        ways=[{'id':'1','nodes':['a','b','c'],'tags':{'highway':'residential','oneway':'yes'}},
              {'id':'2','nodes':['c','d','a'],'tags':{'highway':'residential','oneway':'yes'}},
              {'id':'3','nodes':['a','c'],'tags':{'highway':'residential','access':'private'}}]
        settings={'bbox':[-1,-1,2,2],'earth_radius_m':6378137,'speed_kmh':{'residential':20},'cost_per_km':2,'candidate_count':1,
                  'bases':[{'id':'W1','type':'warehouse','name':'base','lon':0,'lat':0}]}
        data=compile_roads(nodes,ways,settings)
        self.assertEqual(len(data['edges']),2)
        self.assertEqual({e['osm_way'] for e in data['edges']},{'1','2'})
        self.assertTrue(all(len(e['geometry'])==3 for e in data['edges']))
