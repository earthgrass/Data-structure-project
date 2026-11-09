"""A-G completion-window cases, measured independently; existing evidence untouched."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
import sys
from pathlib import Path
from typing import Any
from logiroute.dispatch.controlled_demo import demo_state
from logiroute.dispatch.models import Parcel,json_value
from logiroute.dispatch.real_map import map_config
from logiroute.dispatch.generation import generate_state
from logiroute.dispatch.session import Session
from logiroute.dispatch.validation import validate_plan

ROOT=Path(__file__).resolve().parents[1]


def record(state: Any,label: str,initial_session: Session | None = None) -> dict[str,Any]:
    """Real plan and execution, O(planner+event audit), storage O(state+events)."""
    session=deepcopy(initial_session) if initial_session is not None else Session(deepcopy(state))
    p=session.prepare('distance');services={k:a for r in p.routes for a in r.actions if a.kind=='deliver' for k in a.ids}
    rows=[{'id':k,'earliest':o.earliest,'deadline':o.deadline,'priority':o.priority,
           'completion':services[k].end if k in services else None,'slack':o.deadline-services[k].end if k in services else None,
           'deferred_reason':dict(p.deferred).get(k)} for k,o in state.orders.items()]
    if not p.report.valid:raise ValueError('experimental plan invalid')
    session.apply(p);session.depart()
    while session.running:session.step()
    audit=session.audit()
    if not audit.valid:raise ValueError('experimental history invalid')
    return {'case':label,'input_fingerprint':state.fingerprint(),'planned_served':len(p.accepted),'actually_delivered':sum(o.status=='delivered' for o in session.state.orders.values()),
            'complete_all':audit.complete_all,'orders':rows,'late_orders':[r['id'] for r in rows if r['slack'] is not None and r['slack']<0],
            'distance':sum(r.total_distance for r in p.routes),'cost':sum(r.total_cost for r in p.routes),'travel_time':sum(a.travel_time for r in p.routes for a in r.actions),
            'final_return':session.state.now,'wait_minutes':sum(a.end-a.start for r in p.routes for a in r.actions if a.kind=='wait'),
            'plan':p.to_dict(),'audit':json_value(audit)}


def main() -> None:
    """Preserve all successful and partial cases; never claim arbitrary feasibility."""
    target=ROOT/'docs/experiments'/('phase7-windows.json' if len(sys.argv)==1 else sys.argv[1])
    if target.exists():raise ValueError('existing evidence preserved')
    c=json.loads((ROOT/'config/phase7-experiments.json').read_text(encoding='utf-8'));rows=[]
    for label,mode in [('A-relaxed','relaxed'),('B-strict','strict')]:
        state,_=generate_state(c['seed'],map_config('bjut-campus'),window_mode=mode);rows.append(record(state,label))
    for label in ('C-tiny','D-wait','E-urgent','E-critical','F-same-site','G-traffic'):
        state=demo_state();key=next(iter(state.orders));o=state.orders[key]
        if label=='C-tiny':state.orders[key]=replace(o,deadline=c['tiny_deadline'])
        if label in ('D-wait','F-same-site'):
            state.orders[key]=replace(o,earliest=c['delayed_earliest'],deadline=c['delayed_deadline'])
            if label=='F-same-site':
                state.orders[c['competition_id']]=replace(o,id=c['competition_id'],demand=Decimal(c['competition_demand']),earliest=c['delayed_earliest'],deadline=c['same_site_deadline'])
                state.locations[c['competition_id']]=state.locations[key]
        if label.startswith('E-'):
            state.orders[key]=replace(o,priority=label.split('-')[1])
            state.orders[c['competition_id']]=Parcel(c['competition_id'],o.destination,Decimal(c['competition_demand']),0,c['competition_deadline'])
            state.locations[c['competition_id']]=state.locations[key]
        if label=='G-traffic':
            state.orders[key]=replace(o,deadline=c['competition_deadline']);session=Session(state);old=session.prepare('distance')
            session.traffic('H','A','congested');state=session.state
            old_validation=json_value(validate_plan(state,old))
        row=record(state,label,session if label=='G-traffic' else None)
        if label=='G-traffic':row['old_plan_revalidation']=old_validation
        rows.append(row)
    target.write_text(json.dumps({'scope':'controlled A-G, not population success rate','runs':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    print([(r['case'],r['actually_delivered'],r['complete_all'],r['wait_minutes']) for r in rows])


if __name__=='__main__':main()
