"""Explicit discrete events from validated closed routes; no new routing algorithm."""
from __future__ import annotations
from logiroute.dynamic.models import ExecutionAction
from logiroute.scheduling.fleet_types import VehicleRoutePlan


def compile_actions(route: VehicleRoutePlan) -> tuple[ExecutionAction,...]:
    """Expand arrivals/waits/services/return. Time/Space O(visits+services).

    Every drive keeps the actual path; current_node means last confirmed node
    while that leg is in flight. Service end can exceed the window end, since
    the existing contract bounds service start. The caller independently validates
    the route before departure. Idle vehicles get no fictitious tasks.
    """
    if not route.services: return ()
    services={}
    for service in route.services:
        services.setdefault(service.visit_index,[]).append(service)
    now=route.departure_time
    actions=[]
    for index,leg in enumerate(route.legs,1):
        arrival=now+leg.travel_time
        if len(leg.path)>1:
            actions.append(ExecutionAction('travel',now,arrival,leg.source,leg.target,
                                           leg.path,distance=leg.distance,
                                           travel_time=leg.travel_time,cost=leg.cost))
        now=arrival
        for service in services.get(index,()):
            if service.service_start>now:
                actions.append(ExecutionAction('wait',now,service.service_start,leg.target,leg.target))
            actions.append(ExecutionAction('service',service.service_start,service.service_end,
                                           leg.target,leg.target,order_id=service.order_id))
            now=service.service_end
    actions.append(ExecutionAction('finish',now,now,route.depot_id,route.depot_id))
    return tuple(actions)


def next_action(programs: dict[str,tuple[ExecutionAction,...]], cursors: dict[str,int]
                ) -> tuple[str,ExecutionAction] | None:
    """Handwritten minimum scan by (time,vehicle ID,index). Time O(K), Space O(1)."""
    best=None; best_key=None
    for key,program in programs.items():
        cursor=cursors[key]
        if cursor>=len(program): continue
        candidate=(program[cursor].time,key,cursor)
        better=best_key is None
        if best_key is not None:
            for index in range(3):
                if candidate[index]!=best_key[index]:
                    better=candidate[index]<best_key[index]
                    break
        if better:
            best_key=candidate; best=(key,program[cursor])
    return best
