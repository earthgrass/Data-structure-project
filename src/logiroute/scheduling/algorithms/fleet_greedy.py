"""Global feasible insertion; admission priority is not global service-time order.

Enumerate every pending order, available vehicle, new-visit and same-site service
slot. Replay the entire affected route before comparing. Admit exactly one order
per iteration; defer failed orders and rescan them after every admission. Stop only
when no feasible insertion remains. This is a heuristic, never a no-solution proof.

After path closure: O((M^4+K*M²)*(D+1)) worst time, O(M+K+D) trial storage plus
retained routes. Queue setup O(M²). No builtin sort, heap or multi-car wrapper.
"""
from __future__ import annotations
from logiroute.algorithms.order_queue import OrderPriorityQueue, PRIORITY_RANK
from logiroute.algorithms.ordering import ordered_strings
from logiroute.core.enums import OrderStatus
from logiroute.scheduling.fleet_paths import FleetInput, PathClosure, vehicle_reasons
from logiroute.scheduling.fleet_types import FleetVisit, UnservedOrder, VehicleRoutePlan
from logiroute.scheduling.algorithms.fleet_insertion import (
    assess_route, insertions, precedes, CandidateKey, EvaluationCounters,
)


def global_insertion(data: FleetInput, paths: PathClosure
                     ) -> tuple[tuple[VehicleRoutePlan,...],tuple[UnservedOrder,...],
                                tuple[tuple[str,tuple[str,...]],...],
                                tuple[tuple[str,str,int,int,int],...],EvaluationCounters]:
    """One static planning run. Complexity and termination are documented above."""
    counters=EvaluationCounters()
    routes={}; unavailable=[]
    for vehicle_id in ordered_strings(data.vehicles):
        reasons=vehicle_reasons(data,vehicle_id)
        if reasons:
            unavailable.append((vehicle_id,reasons))
            continue
        depot=data.vehicles[vehicle_id].current_node_id
        route,errors=assess_route(data,paths,vehicle_id,(FleetVisit(depot),FleetVisit(depot)),counters)
        if errors:
            raise ValueError(f'empty static route cannot be evaluated: {errors}')
        routes[vehicle_id]=route
    queue=OrderPriorityQueue()
    rejected={}
    for key in ordered_strings(data.orders):
        order=data.orders[key]
        if order.status is OrderStatus.PENDING:
            queue.enqueue(order)
        else:
            rejected[key]=('order_not_pending',)
    ordered=[]
    while not queue.is_empty():
        ordered.append(queue.pop_next())
    active={order.id for order in ordered}
    trace=[]; failures={}
    vehicle_ids=ordered_strings(routes)
    while active:
        best_key: CandidateKey | None=None
        best_route: VehicleRoutePlan | None=None
        failures={key:set() for key in active}
        for order in ordered:
            if order.id not in active: continue
            for vehicle_id in vehicle_ids:
                old=routes[vehicle_id]
                old_main=old.total_distance if paths.objective=='distance' else old.total_cost
                for kind,visit,service,visits in insertions(old.visits,order):
                    counters.candidate_evaluations+=1
                    route,errors=assess_route(data,paths,vehicle_id,visits,counters)
                    if errors:
                        failures[order.id].update(errors)
                        continue
                    main=route.total_distance if paths.objective=='distance' else route.total_cost
                    key=(PRIORITY_RANK[order.priority],order.time_window_end,main-old_main,
                         vehicle_id,order.id,kind,visit,service)
                    if best_key is None or precedes(key,best_key):
                        best_key,best_route=key,route
        if best_key is None:
            break
        vehicle_id,order_id=best_key[3],best_key[4]
        routes[vehicle_id]=best_route
        active.remove(order_id)
        trace.append((order_id,vehicle_id,best_key[5],best_key[6],best_key[7]))
    for order_id in active:
        reasons=tuple(ordered_strings(failures[order_id])) if vehicle_ids else ('no_available_vehicle',)
        if not reasons:
            raise ValueError('unassigned order has no failed-candidate evidence')
        rejected[order_id]=reasons
    return (tuple(routes[key] for key in vehicle_ids),
            tuple(UnservedOrder(key,rejected[key]) for key in ordered_strings(rejected)),
            tuple(unavailable),tuple(trace),counters)
