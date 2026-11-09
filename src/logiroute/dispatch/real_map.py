"""Offline real-road adapter. Original random scenario API remains unchanged."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from logiroute.core import Node,Edge
from logiroute.core.enums import NodeType
from logiroute.graph import LogisticsGraph

ROOT=Path(__file__).resolve().parents[3]


def map_config(profile: str = 'bjut') -> dict[str,Any]:
    """Opt-in BJUT profile; all business quantities come from JSON. O(data bytes)."""
    from logiroute.dispatch.scenario import load_config
    if profile not in ('bjut','bjut-campus'): raise ValueError('unknown map profile')
    filename='dispatch_bjut_campus.json' if profile=='bjut-campus' else 'dispatch_bjut.json'
    c=load_config(); c.update(json.loads((ROOT/'config'/filename).read_text(encoding='utf-8')))
    data=json.loads((ROOT/c['road_dataset']).read_text(encoding='utf-8'))
    c['candidate_ids']=data['candidate_ids']
    c['map']={**data['provenance'],'bounds':data['bounds'],'features':data['features'],'background_roads':data['background_roads'],
              'title':c['name'],'candidate_count':len(data['candidate_ids'])}
    if 'campus' in data:
        c['candidate_groups']=data['candidate_groups']
        c['map'].update(data['campus'])
        c['map'].update(campus_candidate_count=len(data['candidate_groups']['campus']),initial_campus_orders=c['destination_quotas']['campus'],initial_orders=c['orders_count'])
    return c


def load_road_graph(config: dict[str,Any]) -> LogisticsGraph:
    """Read fixed topology, geometry and roles, with no seed sampling. O(V+E+geometry)."""
    data=json.loads((ROOT/config['road_dataset']).read_text(encoding='utf-8')); graph=LogisticsGraph()
    for n in data['nodes']:
        graph.add_node(Node(n['id'],n['name'],NodeType(n['type']),n['x'],n['y'],n['metadata']))
    for e in data['edges']:
        graph.add_edge(Edge(e['source'],e['target'],e['distance'],e['travel_time'],e['cost'],metadata={k:e[k] for k in ('geometry','osm_way','name','highway')}))
    graph.validate()
    if len(config['candidate_ids'])!=len(set(config['candidate_ids'])): raise ValueError('duplicate candidate ID')
    if any(graph.get_node(k).metadata.get('routing_only') or graph.get_node(k).node_type is not NodeType.CUSTOMER for k in config['candidate_ids']): raise ValueError('invalid candidate reference')
    if 'candidate_groups' in config:
        grouped=[k for values in config['candidate_groups'].values() for k in values]
        if len(grouped)!=len(set(grouped)) or set(grouped)!=set(config['candidate_ids']): raise ValueError('invalid candidate region partition')
    return graph
