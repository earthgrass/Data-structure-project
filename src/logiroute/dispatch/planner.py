"""Deterministic nearest-feasible-hub admission and two-echelon insertion."""
from __future__ import annotations
from dataclasses import replace
from logiroute.algorithms.ordering import ordered_strings
from logiroute.core.quantities import exact_sum
from logiroute.dispatch.models import Action,Job,Plan,Route,RANK
from logiroute.dispatch.algorithms import Paths,build_route,RouteUnavailableError
from logiroute.dispatch.scenario import State
from logiroute.dispatch.validation import validate_plan


def _jobs(state: State,ids: list[str],assign: dict[str,str],kind: str) -> list[Job]:
    t=state.config['timing']; groups={}
    for oid in ids:
        node=assign[oid] if kind=='unload' else state.orders[oid].destination
        group=node if kind=='unload' else oid
        groups.setdefault(group,[]).append(oid)
    result=[]
    for key in ordered_strings(groups):
        items=groups[key]; orders=[state.orders[k] for k in items]
        priority=min(orders,key=lambda o:RANK[o.priority]).priority
        result.append(Job(kind+':'+key,assign[items[0]] if kind=='unload' else orders[0].destination,
                          kind,tuple(items),exact_sum(o.demand for o in orders),priority,
                          0.0 if kind=='unload' else orders[0].earliest,min(o.deadline for o in orders),
                          t['unloading' if kind=='unload' else 'service']))
    return result


def _schedule(state: State,assign: dict[str,str],objective: str,paths: Paths) -> tuple[tuple[Route,...] | None,str]:
    t=state.config['timing']; programs={k:[] for k in state.vehicles}; ready={k:state.now for k in state.vehicles}
    release={k:state.now for k in assign if state.locations[k][0]=='hub'}
    def append_trip(car_id: str,ids: list[str],start: str,begin: float,batch: int,load: bool) -> str:
        car=state.vehicles[car_id]; actions=programs[car_id]
        if load:
            if exact_sum(state.orders[k].demand for k in ids)>car.capacity: return 'capacity'
            if begin>ready[car_id]: actions.append(Action(car_id,'wait',ready[car_id],begin,start,start,batch=batch))
            end=begin+t['loading']; actions.append(Action(car_id,'load',begin,end,start,start,tuple(ids),batch=batch)); begin=end
        kind='unload' if car.role=='trunk' else 'deliver'
        try: route,failed=build_route(paths,car,_jobs(state,ids,assign,kind),begin,start_node=start,objective=objective,batch=batch)
        except RouteUnavailableError: return 'return_unreachable'
        if failed: return next(iter(failed.values()))
        actions.extend(route.actions); ready[car_id]=route.end_time
        for a in route.actions:
            if a.kind=='unload':
                for oid in a.ids: release[oid]=a.end
        return ''
    # Existing cargo first: it cannot be re-created at the warehouse or reassigned.
    for key in ordered_strings(state.vehicles):
        ids=[k for k in ordered_strings(assign) if state.locations[k]==('vehicle',key)]
        if ids or state.positions[key]!=state.vehicles[key].base:
            error=append_trip(key,ids,state.positions[key],state.now,0,False)
            if error: return None,error
    trunk=next(v for v in state.vehicles.values() if v.role=='trunk')
    warehouse=[k for k in ordered_strings(assign) if state.locations[k][0]=='warehouse']
    if any(state.locations[k][1]!=trunk.base for k in warehouse): return None,'unsupported_warehouse'
    if warehouse:
        error=append_trip(trunk.id,warehouse,trunk.base,ready[trunk.id],1,True)
        if error: return None,error
    for key in ordered_strings(state.vehicles):
        car=state.vehicles[key]
        if car.role!='delivery': continue
        ids=[k for k in ordered_strings(assign) if assign[k]==car.base and state.locations[k]!=('vehicle',key)]
        if ids:
            if any(k not in release for k in ids): return None,'inventory_not_released'
            error=append_trip(key,ids,car.base,max(ready[key],max(release[k] for k in ids)),1,True)
            if error: return None,error
    return tuple(Route(key,state.positions[key],state.vehicles[key].base,tuple(programs[key])) for key in ordered_strings(state.vehicles)),''


def plan_dispatch(state: State,objective: str = 'distance') -> Plan:
    """Greedy admission, exact full downstream replay for every trial.

    Hand insertion orders admissions by priority/deadline/ID; hubs by travel-time/ID.
    Each trial uses hand feasible insertion and shared original Dijkstra closure.
    Time O(N*H*N⁴*D + closure); Space O(ND+U²V). No optimality claim.
    """
    if objective not in ('distance','cost'): raise ValueError('invalid objective')
    paths=Paths(state.graph,state.traffic_version); active=[k for k in ordered_strings(state.orders) if state.orders[k].status not in ('delivered','cancelled','expired')]
    required={k for k in active if k in state.protected or state.locations[k][0]!='warehouse'}
    assign={k:state.orders[k].hub for k in active if k in required}; deferred={}
    for key in required:
        if not assign[key] and state.locations[key][0]=='hub': assign[key]=state.locations[key][1]
    routes,error=_schedule(state,assign,objective,paths) if all(assign.values()) else (None,'missing_protected_hub')
    if routes is None:
        assign={}; routes=tuple(Route(k,state.positions[k],v.base,()) for k,v in state.vehicles.items())
        deferred={k:'protected_continuation:'+error for k in active}
    else:
        pending=[k for k in active if k not in required]
        for i in range(1,len(pending)):
            key=pending[i]; j=i-1
            def rank(k: str) -> tuple[int,float,str]:
                o=state.orders[k]; return RANK[o.priority],o.deadline,k
            while j>=0 and rank(key)<rank(pending[j]): pending[j+1]=pending[j]; j-=1
            pending[j+1]=key
        for key in pending:
            hubs=[]
            for hub in ordered_strings(state.config['hub_ids']):
                path=paths.get(hub,state.orders[key].destination,'travel_time')
                if path.reachable: hubs.append((path.total_weight,hub))
            for i in range(1,len(hubs)):
                item=hubs[i]; j=i-1
                while j>=0 and item<hubs[j]: hubs[j+1]=hubs[j]; j-=1
                hubs[j+1]=item
            reason='unreachable'
            for _,hub in hubs:
                trial={**assign,key:hub}; proposed,reason=_schedule(state,trial,objective,paths)
                if proposed is not None: assign=trial; routes=proposed; break
            else: deferred[key]=reason or 'heuristic_incomplete'
    plan=Plan(objective,state.revision,state.traffic_version,tuple((k,assign[k]) for k in ordered_strings(assign)),routes,
              tuple(ordered_strings(assign)),tuple((k,deferred[k]) for k in ordered_strings(deferred)),fingerprint=state.fingerprint())
    return replace(plan,report=validate_plan(state,plan))
