"""Measured wide/strict counterfactuals: only windows vary, actual executions audited."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from logiroute.dispatch.real_map import map_config
from logiroute.dispatch.generation import generate_state
from logiroute.dispatch.session import Session
from logiroute.dispatch.validation import validate_plan
from logiroute.dispatch.models import json_value
from logiroute.algorithms.window_calibration import route_structure


def fingerprint(seed: int) -> str:
    """Full strict input and two complete route plans, excluding measured runtimes."""
    state,_=generate_state(seed,map_config('bjut-campus'),window_mode='strict')
    return hashlib.sha256(json.dumps([state.fingerprint(),[Session(deepcopy(state)).prepare(m).to_dict() for m in ('distance','cost')]],separators=(',',':')).encode()).hexdigest()


def main() -> None:
    """Preserve real measurements and never overwrite previous evidence."""
    if len(sys.argv)>1: print(fingerprint(int(sys.argv[1]))); return
    root=Path(__file__).resolve().parents[1];target=root/'docs/experiments/strict-windows-results.json'
    if target.exists(): raise ValueError('existing evidence preserved')
    rows=[]
    for seed in (0,1,42,100,2026):
        created=perf_counter();strict,attempts=generate_state(seed,map_config('bjut-campus'),window_mode='strict');generation=perf_counter()-created
        wide,_=generate_state(seed,map_config('bjut-campus'),window_mode='relaxed')
        identity=lambda s:[(o.id,o.destination,str(o.demand),o.priority) for o in s.orders.values()]
        graph=lambda s:[(e.source_id,e.target_id,e.distance,e.travel_time,e.cost) for e in s.graph.edges]
        assert identity(strict)==identity(wide) and graph(strict)==graph(wide) and strict.vehicles==wide.vehicles
        plans=[]; baseline={}
        for label,state in (('relaxed',wide),('strict',strict)):
            for mode in ('distance','cost'):
                session=Session(deepcopy(state));started=perf_counter();p=session.prepare(mode);runtime=perf_counter()-started
                assert p.report.valid and p.report.complete_all,p.report
                if label=='relaxed':baseline[mode]=p
                else:
                    old=baseline[mode];replay=validate_plan(state,replace(old,fingerprint=state.fingerprint()))
                    assert not replay.valid and 'customer_service' in replay.violations
                    changed=[k for k,v in route_structure(p).items() if v!=route_structure(old)[k]]
                    assert changed
                session.apply(p);session.depart();steps=0
                while session.running:session.step();steps+=1
                audit=session.audit();assert audit.valid and audit.complete_all
                services={oid:a for r in p.routes for a in r.actions if a.kind=='deliver' for oid in a.ids}
                assert all(a.end<=state.orders[k].deadline and a.start>=state.orders[k].earliest for k,a in services.items())
                plans.append({'window_mode':label,'objective':mode,'plan':p.to_dict(),'planning_seconds':runtime,'steps':steps,'final_time':session.state.now,
                              'audit':json_value(audit),'changed_vehicles':[] if label=='relaxed' else changed,
                              'minimum_completion_slack':min(state.orders[k].deadline-a.end for k,a in services.items())})
        processes=[]
        for value in ('1','2'):
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),str(seed)],cwd=root,env={**os.environ,'PYTHONPATH':'src','PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':value},capture_output=True,text=True,timeout=180,check=True)
            processes.append({'hash_seed':value,'exit_code':result.returncode,'fingerprint':result.stdout.strip()})
        assert processes[0]['fingerprint']==processes[1]['fingerprint']
        rows.append({'seed':seed,'unchanged_order_identity':identity(strict),'same_roads_vehicles_demands_priorities':True,'strict_generation_seconds':generation,
                     'generation_attempts':attempts,'window_evidence':strict.config['window_evidence'],'plans':plans,'processes':processes})
        print(seed,'four actual executions valid/complete; wide route rejected under strict windows; processes match',flush=True)
    state,_=generate_state(42,map_config('bjut-campus'),window_mode='strict');session=Session(state)
    session.add_order('IMPOSSIBLE-WINDOW',next(iter(state.orders.values())).destination,Decimal('0.1'),0,1,'urgent')
    p=session.prepare('distance');assert p.report.valid and not p.report.complete_all
    assert dict(p.deferred)['IMPOSSIBLE-WINDOW']=='completion_deadline' and len(p.accepted)==24
    target.write_text(json.dumps({'runs':rows,'infeasible_order':{'id':'IMPOSSIBLE-WINDOW','deadline':1,'service_minutes':state.config['timing']['service'],'plan':p.to_dict(),'report':json_value(p.report)}},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
