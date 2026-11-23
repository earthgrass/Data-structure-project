"""Deterministic nearest-feasible-hub admission and two-echelon insertion."""
from __future__ import annotations
from dataclasses import replace
from logiroute.algorithms.ordering import ordered_strings
from logiroute.core.quantities import exact_sum
from logiroute.dispatch.models import Action,Job,Plan,Route,RANK,FailureEvidence
from logiroute.dispatch.explanations import explain_order
from logiroute.dispatch.algorithms import Paths,build_route,RouteUnavailableError
from logiroute.dispatch.scenario import State
from logiroute.dispatch.validation import validate_plan
from logiroute.dispatch.deadlines import hard_deadline,fleet_lateness_score


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
        deadlines=[o.deadline for o in orders if hard_deadline(state.config,o.priority,o.allow_late)] if kind=='unload' else []
        hard=bool(deadlines) if kind=='unload' else hard_deadline(state.config,orders[0].priority,orders[0].allow_late)
        result.append(Job(kind+':'+key,assign[items[0]] if kind=='unload' else orders[0].destination,
                          kind,tuple(items),exact_sum(o.demand for o in orders),priority,
                          0.0 if kind=='unload' else orders[0].earliest,min(deadlines) if deadlines else min(o.deadline for o in orders),
                          t['unloading' if kind=='unload' else 'service'],hard))
    return result


def _schedule(state: State,assign: dict[str,str],objective: str,paths: Paths,
              details: list[FailureEvidence] | None = None) -> tuple[tuple[Route,...] | None,str]:
    """Replay original candidates, optionally recording its first failure.

    Time is unchanged from the route builder; evidence retains O(N) identity data
    for the first rejected trip. Diagnostic output never affects route selection.
    """
    t=state.config['timing']; programs={k:[] for k in state.vehicles}; ready={k:state.now for k in state.vehicles}
    trunk=next(v for v in state.vehicles.values() if v.role=='trunk')
    direct={k for k in assign if state.config.get('direct_critical_delivery')
            and state.orders[k].priority=='critical'
            and (state.locations[k][0]=='warehouse' or state.locations[k]==('vehicle',trunk.id))}
    release={k:state.now for k in assign if state.locations[k][0]=='hub'}
    def append_trip(car_id: str,ids: list[str],start: str,begin: float,batch: int,load: bool) -> str:
        car=state.vehicles[car_id]; actions=programs[car_id]
        returned=[k for k in ordered_strings(state.orders)
                  if state.locations[k]==('vehicle',car_id) and state.orders[k].status in ('cancelled','expired')] if batch==0 else []
        if load:
            demand=exact_sum(state.orders[k].demand for k in ids)
            if demand>car.capacity:
                if details is not None:details.append(FailureEvidence('capacity','load',vehicle=car_id,order_ids=tuple(ids),load=demand,capacity=car.capacity,source=start,target=start))
                return 'capacity'
            if begin>ready[car_id]: actions.append(Action(car_id,'wait',ready[car_id],begin,start,start,batch=batch))
            end=begin+t['loading']; actions.append(Action(car_id,'load',begin,end,start,start,tuple(ids),batch=batch)); begin=end
        kind='unload' if car.role=='trunk' else 'deliver'
        jobs=(_jobs(state,[k for k in ids if k not in direct],assign,'unload')+
              _jobs(state,[k for k in ids if k in direct],assign,'deliver')) if car.role=='trunk' else _jobs(state,ids,assign,kind)
        failures={} if details is not None else None
        try:route,failed=build_route(paths,car,jobs,begin,start_node=start,objective=objective,batch=batch,failure_details=failures,
                                     soft_lower='late_delivery' in state.config)
        except RouteUnavailableError as exc:
            if details is not None:details.append(exc.detail or FailureEvidence('return_unreachable','return',vehicle=car_id,source=start,target=car.base))
            return 'return_unreachable'
        if failed:
            first=next(iter(failed))
            if details is not None:
                detail=failures.get(first,FailureEvidence(failed[first],kind,vehicle=car_id))
                # Hub jobs group several parcels under their earliest deadline.
                # Name only actual identities whose deadline is exceeded.
                if detail.code=='completion_deadline' and detail.stage=='unload':
                    detail=replace(detail,order_ids=tuple(k for k in detail.order_ids if state.orders[k].deadline<detail.service_end))
                details.append(detail)
            return failed[first]
        if returned:
            actions.extend(route.actions[:-1])
            back=route.actions[-1]
            end=back.end+t['unloading']
            actions.append(Action(car_id,'return_cancelled',back.start,end,car.base,car.base,tuple(returned),batch=batch))
            actions.append(Action(car_id,'finish',end,end,car.base,car.base,batch=batch))
            ready[car_id]=end
        else:
            actions.extend(route.actions);ready[car_id]=route.end_time
        for a in route.actions:
            if a.kind=='unload':
                for oid in a.ids: release[oid]=a.end
        return ''
    # Existing cargo first: it cannot be re-created at the warehouse or reassigned.
    for key in ordered_strings(state.vehicles):
        ids=[k for k in ordered_strings(assign) if state.locations[k]==('vehicle',key)]
        returned=any(state.locations[k]==('vehicle',key) and state.orders[k].status in ('cancelled','expired') for k in state.orders)
        if ids or returned or state.positions[key]!=state.vehicles[key].base:
            error=append_trip(key,ids,state.positions[key],state.now,0,False)
            if error: return None,error
    warehouse=[k for k in ordered_strings(assign) if state.locations[k][0]=='warehouse']
    if any(state.locations[k][1]!=trunk.base for k in warehouse):
        if details is not None:details.append(FailureEvidence('unsupported_warehouse','load',vehicle=trunk.id,order_ids=tuple(k for k in warehouse if state.locations[k][1]!=trunk.base),target=trunk.base))
        return None,'unsupported_warehouse'
    if warehouse:
        error=append_trip(trunk.id,warehouse,trunk.base,ready[trunk.id],1,True)
        if error: return None,error
    for key in ordered_strings(state.vehicles):
        car=state.vehicles[key]
        if car.role!='delivery': continue
        ids=[k for k in ordered_strings(assign) if k not in direct and assign[k]==car.base and state.locations[k]!=('vehicle',key)]
        if ids:
            if any(k not in release for k in ids):
                if details is not None:details.append(FailureEvidence('inventory_not_released','inventory',vehicle=key,order_ids=tuple(k for k in ids if k not in release),target=car.base))
                return None,'inventory_not_released'
            error=append_trip(key,ids,car.base,max(ready[key],max(release[k] for k in ids)),1,True)
            if error: return None,error
    return tuple(Route(key,state.positions[key],state.vehicles[key].base,tuple(programs[key])) for key in ordered_strings(state.vehicles)),''


def plan_dispatch(state: State,objective: str = 'distance') -> Plan:
    """Greedy admission, exact full downstream replay for every trial.

    Hand insertion orders admissions by priority/deadline/ID. Historical hubs use
    travel-time/ID; pressure mode compares feasible whole-fleet lateness before
    distance or cost and hub ID.
    Each trial uses hand feasible insertion and shared original Dijkstra closure.
    Time O(N*H*N⁴*D + closure); Space O(ND+U²V+HN²), including failure IDs.
    Each rejected hub keeps one representative candidate, not every attempted
    permutation. No optimality or global-infeasibility claim.
    """
    if objective not in ('distance','cost'): raise ValueError('invalid objective')
    paths=Paths(state.graph,state.traffic_version); active=[k for k in ordered_strings(state.orders) if state.orders[k].status not in ('delivered','cancelled','expired')]
    required={k for k in active if k in state.protected or state.locations[k][0]!='warehouse'}
    assign={k:state.orders[k].hub for k in active if k in required}; deferred={}; explanations={}
    for key in required:
        if not assign[key] and state.locations[key][0]=='hub': assign[key]=state.locations[key][1]
    protected_details=[]
    if all(assign.values()):routes,error=_schedule(state,assign,objective,paths,protected_details)
    else:
        routes,error=None,'missing_protected_hub'
        protected_details.append(FailureEvidence(error,'assignment',order_ids=tuple(k for k in active if k in assign and not assign[k])))
    if routes is None:
        assign={}; routes=tuple(Route(k,state.positions[k],v.base,()) for k,v in state.vehicles.items())
        deferred={k:'protected_continuation:'+error for k in active}
        explanations={k:explain_order(k,deferred[k],tuple(protected_details)) for k in active}
    else:
        pending=[k for k in active if k not in required]
        for i in range(1,len(pending)):
            key=pending[i]; j=i-1
            def rank(k: str) -> tuple[int,float,str]:
                o=state.orders[k]; return RANK[o.priority],o.deadline,k
            while j>=0 and rank(key)<rank(pending[j]): pending[j+1]=pending[j]; j-=1
            pending[j+1]=key
        for key in pending:
            hubs=[]; attempts=[]
            for hub in ordered_strings(state.config['hub_ids']):
                path=paths.get(hub,state.orders[key].destination,'travel_time')
                if path.reachable:hubs.append((path.total_weight,hub))
                else:
                    car=next((v.id for v in state.vehicles.values() if v.role=='delivery' and v.base==hub),None)
                    attempts.append(FailureEvidence('unreachable','travel',hub=hub,vehicle=car,order_ids=(key,),source=hub,target=state.orders[key].destination))
            for i in range(1,len(hubs)):
                item=hubs[i]; j=i-1
                while j>=0 and item<hubs[j]: hubs[j+1]=hubs[j]; j-=1
                hubs[j+1]=item
            reason='unreachable';best_choice=None
            for _,hub in hubs:
                details=[];trial={**assign,key:hub}; proposed,reason=_schedule(state,trial,objective,paths,details)
                if proposed is not None:
                    expedite=state.orders[key].priority=='critical' and state.orders[key].allow_late
                    if 'late_delivery' not in state.config and not expedite:
                        assign=trial;routes=proposed;break
                    main=sum(r.total_distance if objective=='distance' else r.total_cost for r in proposed)
                    if expedite:
                        signoff=next(a.end for r in proposed for a in r.actions
                                     if a.kind=='deliver' and key in a.ids)
                        choice=(signoff,*fleet_lateness_score(proposed,state.orders),main,hub)
                    else:choice=(*fleet_lateness_score(proposed,state.orders),main,hub)
                    if best_choice is None or choice<best_choice[0]:best_choice=(choice,trial,proposed)
                    continue
                attempts.extend(replace(item,hub=hub) for item in details)
            else:
                if best_choice is not None:assign=best_choice[1];routes=best_choice[2]
                else:
                    deferred[key]=reason or 'heuristic_incomplete'
                    explanations[key]=explain_order(key,deferred[key],tuple(attempts))
    plan=Plan(objective,state.revision,state.traffic_version,tuple((k,assign[k]) for k in ordered_strings(assign)),routes,
              tuple(ordered_strings(assign)),tuple((k,deferred[k]) for k in ordered_strings(deferred)),fingerprint=state.fingerprint(),
              explanations=tuple(explanations[k] for k in ordered_strings(explanations)))
    return replace(plan,report=validate_plan(state,plan))
