"""Offline real-road adapter. Original random scenario API remains unchanged."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from logiroute.core import Node,Edge
from logiroute.core.enums import NodeType
from logiroute.graph import LogisticsGraph

ROOT=Path(__file__).resolve().parents[3]


def map_config() -> dict[str,Any]:
    """Opt-in BJUT profile; all business quantities come from JSON. O(data bytes)."""
    from logiroute.dispatch.scenario import load_config
    c=load_config(); profile=json.loads((ROOT/'config/dispatch_bjut.json').read_text(encoding='utf-8'))
    c.update(profile)
    data=json.loads((ROOT/c['road_dataset']).read_text(encoding='utf-8'))
    c['candidate_ids']=data['candidate_ids']
    c['map']={**data['provenance'],'bounds':data['bounds'],'features':data['features'],'background_roads':data['background_roads'],
              'title':c['name'],'candidate_count':len(data['candidate_ids'])}
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
    return graph
