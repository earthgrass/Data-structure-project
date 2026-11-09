"""Actual campus quota, five-hub execution and cross-process reproducibility."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from logiroute.dispatch.real_map import map_config
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.session import Session


def fingerprint(seed: int) -> str:
    """Hash complete physical input and both full plans. O(two planning runs)."""
    s=make_state(seed,map_config('bjut-campus')); plans=[Session(make_state(seed,map_config('bjut-campus'))).prepare(mode).to_dict() for mode in ('distance','cost')]
    return hashlib.sha256(json.dumps([s.fingerprint(),plans],ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def main() -> None:
    """Measure all plans and execution, persist evidence once. O(seeds*planner)."""
    if len(sys.argv)>1:
        print(fingerprint(int(sys.argv[1]))); return
    root=Path(__file__).resolve().parents[1]; output=root/'docs/experiments/campus-delivery-results.json'
    if output.exists(): raise ValueError('existing evidence preserved')
    rows=[]; fixed=None
    for seed in (0,1,42,100,2026):
        state=make_state(seed,map_config('bjut-campus')); graph_signature=hashlib.sha256(json.dumps([[n.id,n.x,n.y] for n in state.graph.nodes]+[[e.source_id,e.target_id,e.distance,e.metadata] for e in state.graph.edges],separators=(',',':')).encode()).hexdigest()
        if fixed is None: fixed=graph_signature
        if graph_signature!=fixed: raise ValueError('road graph changed across seeds')
        plans=[]
        for mode in ('distance','cost'):
            session=Session(make_state(seed,map_config('bjut-campus'))); started=perf_counter(); plan=session.prepare(mode); duration=perf_counter()-started
            if not plan.report.safe_to_apply or not plan.report.complete_all: raise ValueError(str(plan.report))
            session.apply(plan); session.depart(); started=perf_counter(); steps=0
            while session.running: session.step(); steps+=1
            audit=session.audit()
            if not audit.valid or not audit.complete_all: raise ValueError(str(audit))
            plans.append({'objective':mode,'plan':plan.to_dict(),'planning_seconds':duration,'execution_seconds':perf_counter()-started,'steps':steps,'hub_distribution':{hub:sum(h==hub for _,h in plan.assignments) for hub in session.state.config['hub_ids']},'final_time':session.state.now,'audit':{'valid':audit.valid,'complete_all':audit.complete_all},'final_positions':session.state.positions})
        children=[]
        for hash_seed in ('1','2'):
            environment={**os.environ,'PYTHONHASHSEED':hash_seed,'PYTHONPATH':'src','PYTHONDONTWRITEBYTECODE':'1'}
            child=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),str(seed)],cwd=root,env=environment,text=True,capture_output=True,timeout=180,check=True)
            children.append({'hash_seed':hash_seed,'fingerprint':child.stdout.strip(),'exit_code':child.returncode})
        if children[0]['fingerprint']!=children[1]['fingerprint']: raise ValueError('cross-process fingerprint mismatch')
        rows.append({'seed':seed,'nodes':len(state.graph.nodes),'edges':len(state.graph.edges),'candidate_count':len(state.config['candidate_ids']),'campus_orders':sum(state.graph.get_node(o.destination).metadata['zone']=='campus' for o in state.orders.values()),'regional_quotas':state.config['destination_quotas'],'selected_destinations':[o.destination for o in state.orders.values()],
                     'graph_fingerprint':graph_signature,'processes':children,'plans':plans})
        print(seed,'both objectives complete; process fingerprints match',flush=True)
    output.write_text(json.dumps({'source':map_config('bjut-campus')['map']['source_sha256'],'campus_config_sha256':hashlib.sha256((root/'data/bjut/campus-config.json').read_bytes()).hexdigest(),'dataset_sha256':hashlib.sha256((root/'data/bjut/campus-network.json').read_bytes()).hexdigest(),'runs':rows},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
