"""Isolated, JSON-driven teaching experiment; never modifies campus sessions."""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from logiroute.core import Node,Edge
from logiroute.core.enums import NodeType
from logiroute.graph import LogisticsGraph
from logiroute.dispatch.models import Parcel,VehicleSpec,json_value
from logiroute.dispatch.scenario import State,load_config
from logiroute.dispatch.session import Session
from logiroute.algorithms.demo_reference import enumerate_demo

ROOT=Path(__file__).resolve().parents[3]


def demo_state() -> State:
    """Load fixed original quantities. Time/Space O(JSON+V+E+N)."""
    data=json.loads((ROOT/'config/phase7-objective-demo.json').read_text(encoding='utf-8'))
    g=LogisticsGraph()
    for key,kind in data['nodes']:g.add_node(Node(key,key,NodeType(kind),0,0))
    for a,b,d,t,c in data['roads']:g.add_edge(Edge(a,b,d,t,c))
    g.validate();c=load_config();c.update(warehouse_ids=[data['warehouse']],hub_ids=[data['hub']])
    cars={v['id']:VehicleSpec(**{**v,'capacity':Decimal(v['capacity'])}) for v in data['vehicles']}
    orders={o['id']:Parcel(**{**o,'demand':Decimal(o['demand'])}) for o in data['orders']}
    return State(g,c,orders,{k:('warehouse',data['warehouse']) for k in orders},cars,{k:v.base for k,v in cars.items()},c['timing']['initial'])


def objective_demo() -> dict[str,Any]:
    """Real production plans, independent validation and full physical execution.

    Time two production plans + execution/audit + tiny exponential reference.
    Space O(state+plans+reference output); no persistent session mutation.
    """
    state=demo_state();data=json.loads((ROOT/'config/phase7-objective-demo.json').read_text(encoding='utf-8'));runs=[]
    for objective in ('distance','cost'):
        session=Session(deepcopy(state));started=perf_counter();plan=session.prepare(objective);elapsed=perf_counter()-started
        if not plan.report.valid or not plan.report.complete_all:raise ValueError('controlled demo must have two verified complete plans')
        session.apply(plan);session.depart()
        while session.running:session.step()
        audit=session.audit()
        if not audit.valid or not audit.complete_all:raise ValueError('controlled execution audit failed')
        runs.append({'objective':objective,'input_fingerprint':state.fingerprint(),'plan':plan.to_dict(),'distance':sum(r.total_distance for r in plan.routes),
                     'cost':sum(r.total_cost for r in plan.routes),'travel_time':sum(a.travel_time for r in plan.routes for a in r.actions),
                     'final_return':session.state.now,'planning_seconds':elapsed,'audit':json_value(audit)})
    return {'title':data['title'],'simulated_costs':True,'cost_note':data['cost_note'],'runs':runs,
            'reference':enumerate_demo(state.graph,data['warehouse'],data['hub'],data['orders'][0]['destination'])}
