"""Independent physical replay. Never imports insertion, planner or session replay."""
from __future__ import annotations
import math
from logiroute.core.quantities import exact_sum
from logiroute.core.enums import NodeType,TrafficStatus
from logiroute.graph.logistics_graph import GraphError
from logiroute.dispatch.models import Plan,Report,RANK
from logiroute.dispatch.scenario import State


def validate_plan(state: State,plan: Plan) -> Report:
    """Replay original roads and inventory by event completion. Time O(A²+AN), Space O(A+N).

    Floating tolerance applies only to reported metrics; never capacity or deadlines.
    The caller-supplied report is ignored. Action lists retain per-car causal order.
    """
    errors=[]; active={k for k,o in state.orders.items() if o.status not in ('delivered','cancelled','expired')}
    if any(k!=o.id for k,o in state.orders.items()) or len({o.id for o in state.orders.values()})!=len(state.orders): errors.append('input_order_identity')
    if set(state.locations)!=set(state.orders): errors.append('input_inventory_partition')
    assigned=dict(plan.assignments); accepted=set(plan.accepted); deferred=dict(plan.deferred)
    if plan.objective not in ('distance','cost'): errors.append('objective')
    if (plan.revision,plan.traffic_version,plan.fingerprint)!=(state.revision,state.traffic_version,state.fingerprint()): errors.append('stale_input')
    if len(accepted)!=len(plan.accepted) or len(deferred)!=len(plan.deferred) or accepted & deferred.keys() or accepted|deferred.keys()!=active: errors.append('order_partition')
    if set(assigned)!=accepted or len(assigned)!=len(plan.assignments) or any(h not in state.config['hub_ids'] for h in assigned.values()): errors.append('assignments')
    if any(not reason for reason in deferred.values()): errors.append('missing_reason')
    if len({r.vehicle for r in plan.routes})!=len(plan.routes) or {r.vehicle for r in plan.routes}!=set(state.vehicles): errors.append('vehicle_partition')
    if len({v.courier_id for v in state.vehicles.values()})!=len(state.vehicles): errors.append('courier_binding')
    locations=dict(state.locations); release={k:state.now for k in locations}; positions=dict(state.positions)
    clock={k:state.now for k in positions}; lower={k:False for k in positions}; seen=set(); cursors=[0]*len(plan.routes)
    pending=sum(len(r.actions) for r in plan.routes)
    try:
        for r in plan.routes:
            car=state.vehicles[r.vehicle]
            expected=NodeType.WAREHOUSE if car.role=='trunk' else NodeType.TRANSFER
            if state.graph.get_node(car.base).node_type is not expected or r.start_node!=positions[car.id] or r.end_node!=car.base: errors.append('base')
        while pending:
            choices=[(r.actions[cursors[i]].end,i) for i,r in enumerate(plan.routes) if cursors[i]<len(r.actions)]
            earliest=min(x[0] for x in choices); picked=None
            # An unload at the same timestamp may release a zero-duration load.
            for end,i in choices:
                if end!=earliest: continue
                a=plan.routes[i].actions[cursors[i]]; car=state.vehicles[a.vehicle]
                origin=('warehouse' if car.role=='trunk' else 'hub',car.base)
                if a.kind!='load' or all(locations.get(k)==origin and release[k]<=a.start for k in a.ids): picked=i; break
            if picked is None: errors.append('inventory_not_available_at_load_start'); break
            r=plan.routes[picked]; a=r.actions[cursors[picked]]; car=state.vehicles[r.vehicle]; key=car.id
            cursors[picked]+=1; pending-=1
            if a.vehicle!=key or not all(math.isfinite(float(x)) and x>=0 for x in (a.start,a.end,a.distance,a.travel_time,a.cost)) or a.end<a.start or a.start!=clock[key] or a.source!=positions[key]: errors.append('action_time_position')
            if len(set(a.ids))!=len(a.ids) or any(k not in accepted for k in a.ids): errors.append('manifest_ids')
            if a.kind=='drive':
                edge=state.graph.get_edge(a.source,a.target)
                if edge.traffic_status is TrafficStatus.BLOCKED or a.traffic_version!=state.traffic_version: errors.append('blocked_or_stale_edge')
                if (a.distance,a.travel_time,a.cost)!=(edge.distance,edge.travel_time,edge.cost) or a.end!=a.start+edge.travel_time: errors.append('road_metrics')
                if a.ids: errors.append('drive_manifest')
                positions[key]=a.target
            else:
                if a.target!=a.source or a.distance!=0 or a.travel_time!=0 or a.cost!=0: errors.append('nontravel_metrics')
                duration=a.end-a.start; t=state.config['timing']
                def duration_is(expected: float) -> bool:
                    return a.end==a.start+expected
                if a.kind=='load':
                    if positions[key]!=car.base or not duration_is(t['loading']) or not a.ids: errors.append('loading')
                    origin=('warehouse' if car.role=='trunk' else 'hub',car.base)
                    for oid in a.ids:
                        if locations.get(oid)!=origin or release[oid]>a.start: errors.append('load_inventory')
                        if car.role=='delivery' and assigned.get(oid)!=car.base: errors.append('wrong_hub_load')
                        locations[oid]=('vehicle',key)
                    lower[key]=False
                elif a.kind in ('unload','deliver'):
                    if not a.ids: errors.append('empty_service')
                    priority=min((RANK[state.orders[k].priority] for k in a.ids),default=2)
                    if priority==0 and lower[key]: errors.append('critical_precedence')
                    if priority!=0: lower[key]=True
                    for oid in a.ids:
                        order=state.orders[oid]
                        if locations.get(oid)!=('vehicle',key): errors.append('cargo_not_onboard')
                        if a.kind=='unload':
                            if car.role!='trunk' or assigned.get(oid)!=positions[key] or not duration_is(t['unloading']): errors.append('hub_unload')
                            locations[oid]=('hub',positions[key]); release[oid]=a.end
                        else:
                            if car.role!='delivery' or car.base!=assigned.get(oid) or positions[key]!=order.destination or a.start<order.earliest or a.end>order.deadline or not duration_is(t['service']) or len(a.ids)!=1 or oid in seen: errors.append('customer_service')
                            locations[oid]=('delivered',oid); seen.add(oid)
                elif a.kind=='finish':
                    if positions[key]!=car.base or duration!=0 or a.ids or any(loc==('vehicle',key) for loc in locations.values()): errors.append('return_with_cargo')
                elif a.kind=='wait':
                    if a.ids: errors.append('wait_manifest')
                else: errors.append('unknown_action')
            clock[key]=a.end
            if exact_sum(state.orders[k].demand for k,loc in locations.items() if loc==('vehicle',key))>car.capacity: errors.append('capacity')
        if seen!=accepted: errors.append('customer_coverage')
        for r in plan.routes:
            if positions[r.vehicle]!=state.vehicles[r.vehicle].base: errors.append('missing_return')
        for oid in active-accepted:
            if locations[oid]!=state.locations[oid]: errors.append('unaccepted_inventory_changed')
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError,GraphError) as exc:
        errors.append('malformed_plan:'+type(exc).__name__)
    valid=not errors
    return Report(valid,valid and accepted==active,valid and state.protected<=accepted,tuple(errors))
