"""Read-only provenance, direction, geometry and quota audit of frozen data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from logiroute.dispatch.real_map import map_config,load_road_graph
from logiroute.dispatch.scenario import make_state


def main() -> None:
    """Time O(seeds*(V+E+sampling)); preserve sources and old evidence."""
    root=Path(__file__).resolve().parents[1];target=root/'docs/experiments/phase7-map.json'
    if target.exists():raise ValueError('existing evidence preserved')
    c=map_config('bjut-campus');g=load_road_graph(c);g.validate()
    for e in g.edges:
        a,b=g.get_node(e.source_id),g.get_node(e.target_id);line=e.metadata['geometry']
        assert line[0]==[a.x,a.y] and line[-1]==[b.x,b.y],e.key
    road=lambda graph:hashlib.sha256(json.dumps([(e.source_id,e.target_id,e.distance,e.travel_time,e.cost,e.metadata['geometry']) for e in graph.edges],separators=(',',':')).encode()).hexdigest()
    fingerprint=road(g);rows=[]
    for seed in (0,1,42,100,2026):
        s=make_state(seed,c);assert road(s.graph)==fingerprint
        counts={zone:sum(o.destination in ids for o in s.orders.values()) for zone,ids in c['candidate_groups'].items()}
        assert counts==c['destination_quotas'];rows.append({'seed':seed,'quotas':counts,'roads_fingerprint':fingerprint})
    places=[{'id':n.id,'name':n.name,**n.metadata} for n in g.nodes if not n.metadata.get('routing_only')]
    data={'nodes':len(g.node_ids),'directed_edges':len(list(g.edges)),'without_reverse':sum(not g.has_edge(e.target_id,e.source_id) for e in g.edges),
          'geometry_endpoints_all_match':True,'provenance':{k:v for k,v in c['map'].items() if k not in ('features','background_roads','outline')},'places':places,'runs':rows,
          'files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'data/bjut/source.osm',root/'data/bjut/network.json',root/'data/bjut/campus-network.json',root/'data/bjut/campus-config.json')}}
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(data['nodes'],data['directed_edges'],data['without_reverse'],'direction/geometry/quotas verified')


if __name__=='__main__':main()
