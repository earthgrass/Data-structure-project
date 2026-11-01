"""Same coordinates/orders, genuine random-vs-local graph and dual-objective runs."""
from __future__ import annotations
from copy import deepcopy
import json
import math
from pathlib import Path
from time import perf_counter
from logiroute.dispatch.scenario import load_config,make_state
from logiroute.dispatch.session import Session
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.road_validator import validate_road_network


def main() -> None:
    target=Path(__file__).resolve().parents[1]/'docs/experiments/local-roads-results.json'
    if target.exists(): raise ValueError('existing raw evidence is preserved')
    rows=[]
    for seed in (0,1,42,100,2026):
        coordinates=None
        for topology in ('random','local'):
            c=deepcopy(load_config()); c['graph']['topology']=topology
            if topology=='random': c['graph']['nearest_neighbor_count']=None
            started=perf_counter(); s=make_state(seed,c); generation=perf_counter()-started
            points=[(n.id,n.x,n.y) for n in s.graph.nodes]
            if coordinates is None: coordinates=points
            else: assert coordinates==points
            pairs={}; degree={n.id:0 for n in s.graph.nodes}; lengths=[]
            for e in s.graph.edges:
                if e.metadata['road_id'] not in pairs:
                    pairs[e.metadata['road_id']]=e; degree[e.source_id]+=1; degree[e.target_id]+=1
                    a=s.graph.get_node(e.source_id); b=s.graph.get_node(e.target_id); lengths.append(math.hypot(a.x-b.x,a.y-b.y))
            report=validate_road_network(s.graph,GeneratorConfig(**c['graph'])).to_dict()
            plans=[]
            for objective in ('distance','cost'):
                session=Session(make_state(seed,c)); begin=perf_counter(); p=session.prepare(objective); runtime=perf_counter()-begin
                if p.report.safe_to_apply:
                    session.apply(p); session.depart()
                    while session.running: session.step()
                plans.append({'objective':objective,'planning_seconds':runtime,'plan':p.to_dict(),'executed_valid':session.audit().valid,'executed_complete':session.audit().complete_all})
            rows.append({'seed':seed,'topology':topology,'coordinates':points,'road_report':report,'degrees':degree,
                         'mean_geometric_road_length':sum(lengths)/len(lengths),'generation_seconds':generation,'plans':plans})
    target.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in rows:
        r=row['road_report']; print(row['seed'],row['topology'],r['physical_road_count'],r['directed_edge_count'],round(row['mean_geometric_road_length'],3),max(row['degrees'].values()),[p['executed_complete'] for p in row['plans']])


if __name__=='__main__': main()
