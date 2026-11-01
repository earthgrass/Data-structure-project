"""Phase 6: shared-input matrix and independent small-instance enumeration."""
from __future__ import annotations
from collections.abc import Iterator
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from time import perf_counter
from logiroute.algorithms.dijkstra import shortest_path
from logiroute.algorithms.ordering import ordered_strings
from logiroute.core.quantities import exact_sum
from logiroute.dispatch.models import json_value
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.session import Session
from logiroute.dispatch.planner import plan_dispatch


def permutations(items: list[str]) -> Iterator[list[str]]:
    """Independent handwritten enumeration, Time O(n*n!), Space O(n²)."""
    if not items: yield []; return
    for i,item in enumerate(items):
        for tail in permutations(items[:i]+items[i+1:]): yield [item]+tail


def reference(seed: int,objective: str) -> dict:
    """Enumerate hub assignment, trunk hub order and customer order independently.

    Restricted oracle: same primary-shortest-path closure, one batch/car, three
    normal orders and fixed stations. Does not call insertion or its validator.
    """
    state=make_state(seed); ids=ordered_strings(state.orders)[:3]
    state.orders={k:replace(state.orders[k],priority='normal') for k in ids}; state.locations={k:state.locations[k] for k in ids}
    graph=state.graph; hubs=ordered_strings(state.config['hub_ids']); t=state.config['timing']; cache={}
    def path(a: str,b: str):
        key=(a,b)
        if key not in cache: cache[key]=shortest_path(graph,a,b,objective)
        return cache[key]
    def leg(a: str,b: str,now: float,main: float):
        p=path(a,b)
        if not p.reachable: return None
        for x,y in zip(p.path,p.path[1:]):
            edge=graph.get_edge(x,y); now+=edge.travel_time; main+=edge.weight(objective)
        return now,main
    trunk=next(v for v in state.vehicles.values() if v.role=='trunk'); branches={v.base:v for v in state.vehicles.values() if v.role=='delivery'}
    feasible=0; best=None
    def assignments(i: int,current: dict):
        if i==len(ids): yield dict(current); return
        for hub in hubs:
            current[ids[i]]=hub; yield from assignments(i+1,current)
    for assigned in assignments(0,{}):
        groups={h:[k for k in ids if assigned[k]==h] for h in hubs}
        if exact_sum(state.orders[k].demand for k in ids)>trunk.capacity: continue
        if any(exact_sum(state.orders[k].demand for k in groups[h])>branches[h].capacity for h in hubs): continue
        for sequence in permutations([h for h in hubs if groups[h]]):
            now=state.now+t['loading']; node=trunk.base; main=0.0; released={}; valid=True
            for hub in sequence:
                result=leg(node,hub,now,main)
                if result is None: valid=False; break
                now,main=result; now+=t['unloading']; released[hub]=now; node=hub
            returned=leg(node,trunk.base,now,main) if valid else None
            if returned is None: continue
            trunk_main=returned[1]
            def delivery(index: int,total: float):
                nonlocal feasible,best
                if index==len(hubs):
                    feasible+=1
                    if best is None or total<best: best=total
                    return
                hub=hubs[index]
                if not groups[hub]: delivery(index+1,total); return
                for order in permutations(groups[hub]):
                    clock=released[hub]+t['loading']; current=hub; amount=0.0; ok=True
                    for key in order:
                        o=state.orders[key]; result=leg(current,o.destination,clock,amount)
                        if result is None: ok=False; break
                        clock,amount=result; clock=max(clock,o.earliest)+t['service']; current=o.destination
                        if clock>o.deadline: ok=False; break
                    result=leg(current,hub,clock,amount) if ok else None
                    if result is not None: delivery(index+1,total+result[1])
            delivery(0,trunk_main)
    greedy=plan_dispatch(state,objective); main=sum(r.total_distance if objective=='distance' else r.total_cost for r in greedy.routes)
    return {'seed':seed,'objective':objective,'orders':ids,'feasible_labeled_solutions':feasible,'reference_best':best,
            'greedy_main':main,'greedy_report':json_value(greedy.report),'gap':main-best if best is not None and greedy.report.complete_all else None,
            'scope':'all fixed-hub assignments, trunk permutations, per-hub customer permutations; primary shortest paths; one batch'}


def main() -> None:
    root=Path(__file__).resolve().parents[1]; target=root/'docs/experiments/v2-phase6-dispatch-results.json'
    if target.exists(): raise ValueError('existing experiment preserved; choose a fresh output path')
    records=[]; dynamic=[]; scenarios={}
    for seed in (0,1,42,100,2026):
        for profile in ('clear','congested','blocked'):
            for objective in ('distance','cost'):
                session=Session(make_state(seed)); edge=next(iter(session.state.graph.edges))
                if profile!='clear': session.traffic(*edge.key,profile)
                before=session.snapshot(); fingerprint=session.state.fingerprint(); scenarios.setdefault(str(seed)+':'+profile,before)
                started=perf_counter(); plan=session.prepare(objective); planning=perf_counter()-started
                executed=perf_counter()
                if plan.report.safe_to_apply:
                    session.apply(plan); session.depart()
                    while session.running: session.step()
                records.append({'seed':seed,'profile':profile,'objective':objective,'fingerprint':fingerprint,'plan':plan.to_dict(),
                                'planning_seconds':planning,'execution_seconds':perf_counter()-executed,'audit':json_value(session.audit()),'events':json_value(session.events)})
        session=Session(make_state(seed)); session.apply(session.prepare('distance')); session.depart(); session.step()
        order=next(iter(session.state.orders.values())); new_id=session.state.config['dynamic_prefix']+'-experiment'
        session.add_order(new_id,order.destination,Decimal('0.1'),session.state.now,session.state.now+float(session.state.config['automatic_window_width']),'critical')
        session.pause()
        while session.running: session.step()
        before=session.snapshot(); started=perf_counter(); plan=session.prepare('cost'); elapsed=perf_counter()-started
        if plan.report.safe_to_apply:
            session.apply(plan); session.depart()
            while session.running: session.step()
        dynamic.append({'seed':seed,'checkpoint':before,'plan':plan.to_dict(),'planning_seconds':elapsed,'audit':json_value(session.audit()),'events':json_value(session.events)})
    evidence={'scenarios':scenarios,'matrix':records,'dynamic':dynamic,'reference':[reference(42,m) for m in ('distance','cost')]}
    target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'matrix_runs':len(records),'complete_plans':sum(r['plan']['report']['complete_all'] for r in records),
                      'valid_execution_histories':sum(r['audit']['valid'] for r in records),'dynamic_complete':sum(r['audit']['complete_all'] for r in dynamic),
                      'reference':evidence['reference']},ensure_ascii=False),flush=True)


if __name__=='__main__': main()
