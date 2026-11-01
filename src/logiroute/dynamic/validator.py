"""Independent event/manifest replay, never imports the session or event compiler.

The static independent fleet validator certifies each proposal before loading;
this auditor separately checks the resulting lifecycle, actual graph travel,
time windows, exact manifests and cargo against an immutable observation.
"""
from __future__ import annotations
from decimal import Decimal
import math
from logiroute.core.enums import OrderStatus,OrderPriority,VehicleStatus,CourierStatus,NodeType
from logiroute.core.quantities import exact_sum,exact_difference
from logiroute.dynamic.models import DynamicSnapshot,DynamicValidationReport
from logiroute.graph import LogisticsGraph


def validate_dynamic_snapshot(graph: LogisticsGraph, snapshot: DynamicSnapshot) -> DynamicValidationReport:
    """Reconstruct events independently; no constant-cost history replay claim.

    With N orders, K cars, H events, J manifest IDs, L traversed edges and D
    decimal alignment digits, Time O(N+K+H*N+K*J+(H+J)*D+L), Space O(N+K+D).
    Plan/withdrawal events scan states; each departure checks other manifests.
    No load epsilon or rounded totals. In-flight position is the last confirmed
    node plus an explicit whole-leg path, not an invented reset to a depot.
    """
    errors=[]
    def issue(message: str) -> None: errors.append(message)
    orders={o.id:o for o in snapshot.orders}; vehicles={v.id:v for v in snapshot.vehicles}
    if len(orders)!=len(snapshot.orders) or len(vehicles)!=len(snapshot.vehicles): issue('duplicate identities')
    if len({v.courier_id for v in snapshot.vehicles})!=len(vehicles): issue('duplicate courier bindings')
    if not math.isfinite(snapshot.time) or snapshot.time<0: issue('invalid clock')
    if not math.isfinite(snapshot.service_time) or snapshot.service_time<0: issue('invalid service duration')
    for o in orders.values():
        if (not isinstance(o.demand,Decimal) or not o.demand.is_finite() or o.demand<0
                or not isinstance(o.status,OrderStatus) or not isinstance(o.priority,OrderPriority)
                or o.time_window_start>=o.time_window_end
                or not math.isfinite(o.time_window_start) or not math.isfinite(o.time_window_end)):
            issue('invalid order observation')
        node=graph.try_get_node(o.destination_id)
        if node is None or node.node_type is not NodeType.CUSTOMER: issue('invalid order destination')
    for v in vehicles.values():
        if (not isinstance(v.capacity,Decimal) or not isinstance(v.current_load,Decimal)
                or not v.capacity.is_finite() or not v.current_load.is_finite()
                or not 0<=v.current_load<=v.capacity): issue('invalid observed load')
    if errors: return DynamicValidationReport(False,tuple(errors))
    statuses={}; cargo={k:set() for k in vehicles}; loads={k:Decimal(0) for k in vehicles}
    positions={k:v.home_node_id for k,v in vehicles.items()}; ready={}; active=set(); delivered=set()
    last=-math.inf
    for index,event in enumerate(snapshot.events,1):
        if event.sequence!=index or not math.isfinite(event.time) or not last<=event.time<=snapshot.time:
            issue('invalid event sequence/time')
        last=event.time; kind=event.kind; oid=event.order_id; key=event.vehicle_id
        if kind=='accepted':
            if oid not in orders or oid in statuses: issue('duplicate/unknown accepted ID')
            else:
                if (event.quantity!=orders[oid].demand or event.detail!=orders[oid].source
                        or (event.detail=='automatic' and (isinstance(event.seed,bool) or not isinstance(event.seed,int)))
                        or (event.detail!='automatic' and event.seed is not None)):
                    issue('admission quantity/source/seed mismatch')
                statuses[oid]=OrderStatus.PENDING
        elif kind=='plan_applied':
            expected={k for k,s in statuses.items() if s in (OrderStatus.PENDING,OrderStatus.PLANNED)}
            if (active or len(event.order_ids)!=len(set(event.order_ids))
                    or set(event.order_ids)!=expected): issue('invalid planned coverage/checkpoint')
            for k in event.order_ids:
                if k in statuses: statuses[k]=OrderStatus.PLANNED
        elif kind in ('cancelled','expired'):
            if statuses.get(oid) not in (OrderStatus.PENDING,OrderStatus.PLANNED): issue('illegal terminal transition')
            if kind=='expired' and (oid not in orders or event.time<=orders[oid].time_window_end):
                issue('premature expiry')
            statuses[oid]=OrderStatus.CANCELLED if kind=='cancelled' else OrderStatus.EXPIRED
            if event.detail=='plan_withdrawn':
                for k in statuses:
                    if statuses[k] is OrderStatus.PLANNED: statuses[k]=OrderStatus.PENDING
        elif kind=='updated':
            if statuses.get(oid) is not OrderStatus.PENDING: issue('updated nonpending order')
        elif kind=='depart':
            if key not in vehicles: issue('unknown departure vehicle'); continue
            if key in active or loads[key]!=0 or positions[key]!=vehicles[key].home_node_id:
                issue('illegal departure checkpoint')
            ids=event.order_ids
            if len(ids)!=len(set(ids)) or any(statuses.get(k) is not OrderStatus.PLANNED for k in ids):
                issue('invalid departure manifest')
            if any(k not in orders for k in ids): issue('unknown manifest order'); continue
            total=exact_sum(orders[k].demand for k in ids)
            if event.quantity!=total or total>vehicles[key].capacity: issue('invalid departure load')
            if any(set(ids)&cargo[v] for v in vehicles if v!=key): issue('duplicate vehicle ownership')
            cargo[key]=set(ids); loads[key]=total; active.add(key); ready[key]=event.time
            for k in ids: statuses[k]=OrderStatus.IN_TRANSIT
        elif kind in ('travel','wait','service','finish'):
            if key not in active: issue('execution without departure'); continue
            if event.start_time!=ready[key] or event.source_node!=positions[key]:
                issue('broken execution prefix/time')
            if kind=='travel':
                path=event.path
                if not path or path[0]!=positions[key] or path[-1]!=event.target_node:
                    issue('invalid travel endpoints')
                distance=travel=cost=0.0
                for source,target in zip(path,path[1:]):
                    if not graph.has_edge(source,target): issue('missing/wrong-direction travel edge'); continue
                    edge=graph.get_edge(source,target)
                    distance+=edge.distance; travel+=edge.travel_time; cost+=edge.cost
                if ((event.distance,event.travel_time,event.cost)!=(distance,travel,cost)
                        or event.time!=event.start_time+travel): issue('incorrect actual travel metrics/time')
                positions[key]=event.target_node
            elif kind=='wait':
                if event.target_node!=positions[key] or event.time<event.start_time: issue('invalid wait')
            elif kind=='service':
                if oid not in orders: issue('unknown service order'); continue
                order=orders[oid]
                if (oid in delivered or oid not in cargo[key] or statuses.get(oid) is not OrderStatus.IN_TRANSIT
                        or positions[key]!=order.destination_id or event.quantity!=order.demand):
                    issue('invalid/duplicate service identity or cargo')
                if (not order.time_window_start<=event.start_time<=order.time_window_end
                        or event.time!=event.start_time+snapshot.service_time): issue('invalid service window/duration')
                cargo[key].discard(oid); loads[key]=exact_difference(loads[key],order.demand)
                statuses[oid]=OrderStatus.DELIVERED; delivered.add(oid)
            elif kind=='finish':
                if (cargo[key] or loads[key]!=0 or positions[key]!=vehicles[key].home_node_id
                        or event.time!=event.start_time): issue('invalid return')
                active.discard(key)
            ready[key]=event.time
        elif kind not in ('clock_advanced','replan_deferred','replan_incomplete'):
            issue('unknown execution event')
    if set(statuses)!=set(orders): issue('accepted order coverage mismatch')
    for key,order in orders.items():
        if statuses.get(key)!=order.status: issue('order lifecycle mismatch')
    observed_onboard=set()
    for key,v in vehicles.items():
        home=graph.try_get_node(v.home_node_id)
        if home is None or home.node_type is not NodeType.WAREHOUSE: issue('invalid home warehouse')
        if (not isinstance(v.capacity,Decimal) or not isinstance(v.current_load,Decimal)
                or not v.capacity.is_finite() or not v.current_load.is_finite()
                or not 0<=v.current_load<=v.capacity): issue('invalid observed load')
        ids=v.onboard_order_ids
        if len(ids)!=len(set(ids)) or set(ids)!=cargo[key] or observed_onboard.intersection(ids):
            issue('observed onboard ownership mismatch')
        observed_onboard.update(ids)
        if v.current_load!=loads[key] or v.current_node_id!=positions[key]: issue('observed position/load mismatch')
        if key in active:
            expected=VehicleStatus.DELIVERING if ids else VehicleStatus.RETURNING
            if v.status is not expected or v.courier_status is not CourierStatus.DELIVERING:
                issue('active vehicle/courier status mismatch')
            if (not v.action_kind or v.action_end<snapshot.time or v.action_start!=ready[key]):
                issue('invalid remaining execution cursor')
            if v.action_kind=='travel' and (not v.in_flight_path or v.in_flight_path[0]!=v.current_node_id):
                issue('missing in-flight path')
        elif (v.status not in (VehicleStatus.IDLE,VehicleStatus.MAINTENANCE)
                or v.action_kind or v.current_load!=0 or v.current_node_id!=v.home_node_id
                or v.courier_status is CourierStatus.DELIVERING):
            issue('idle checkpoint mismatch')
    if observed_onboard!={o.id for o in orders.values() if o.status is OrderStatus.IN_TRANSIT}:
        issue('in-transit order coverage mismatch')
    pending=snapshot.pending_ids
    if len(pending)!=len(set(pending)) or set(pending)!={o.id for o in orders.values() if o.status is OrderStatus.PENDING}:
        issue('queue partition mismatch')
    ranks={OrderPriority.URGENT:0,OrderPriority.NORMAL:1}; previous=None
    for key in pending:
        if key not in orders: continue
        o=orders[key]; current=(ranks.get(o.priority,2),o.time_window_end,o.id)
        if previous is not None and current<previous: issue('queue ordering mismatch')
        previous=current
    planned={o.id for o in orders.values() if o.status is OrderStatus.PLANNED}
    reported=[] if snapshot.plan is None else [s.order_id for r in snapshot.plan.routes for s in r.services]
    if len(reported)!=len(set(reported)) or set(reported)!=planned: issue('committed plan partition mismatch')
    stale_plan=(snapshot.plan is not None and any(r.departure_time!=snapshot.time for r in snapshot.plan.routes))
    if snapshot.needs_replan!=(bool(pending) or stale_plan): issue('replan flag disagrees with queue/schedule')
    return DynamicValidationReport(not errors,tuple(errors))
