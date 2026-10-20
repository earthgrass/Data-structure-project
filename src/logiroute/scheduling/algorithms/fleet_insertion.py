"""Candidate positions and full static route replay, never a shortest-path solver."""
from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass
import math

from logiroute.core import Order
from logiroute.core.enums import OrderStatus
from logiroute.core.delivery_load import check_delivery_load, DeliveryLoadState
from logiroute.scheduling.fleet_paths import FleetInput, PathClosure
from logiroute.scheduling.fleet_types import FleetVisit, FleetLeg, FleetService, VehicleRoutePlan

CandidateKey = tuple[int,float,float,str,str,int,int,int]
MERGE_VISIT = 0
NEW_VISIT = 1


@dataclass
class EvaluationCounters:
    candidate_evaluations: int = 0
    feasibility_checks: int = 0
    time_window_checks: int = 0


def precedes(left: CandidateKey, right: CandidateKey) -> bool:
    """Approved lexicographic order, explicit field comparison. Time/Space O(1).

    rank, deadline, primary delta, vehicle ID, order ID, kind, visit, service.
    String IDs are explicit final tie breakers, never business priority ranks.
    """
    for index in range(8):
        if left[index] != right[index]:
            return left[index] < right[index]
    return False


def insertions(visits: tuple[FleetVisit,...], order: Order
               ) -> Iterator[tuple[int,int,int,tuple[FleetVisit,...]]]:
    """New visits and all service slots at existing same-site visits.

    O(r) variants, O(r) materialization per yield; Space O(r) excluding consumer.
    A visit may serve multiple distinct IDs; nonadjacent revisits remain possible.
    """
    for index in range(1,len(visits)-1):
        visit = visits[index]
        if visit.node_id == order.destination_id:
            for service in range(len(visit.order_ids)+1):
                ids = visit.order_ids[:service] + (order.id,) + visit.order_ids[service:]
                trial = visits[:index] + (FleetVisit(visit.node_id,ids),) + visits[index+1:]
                yield MERGE_VISIT,index,service,trial
    for index in range(1,len(visits)):
        trial = visits[:index] + (FleetVisit(order.destination_id,(order.id,)),) + visits[index:]
        yield NEW_VISIT,index,0,trial


def assess_route(data: FleetInput, paths: PathClosure, vehicle_id: str,
                 visits: tuple[FleetVisit,...], counters: EvaluationCounters
                 ) -> tuple[VehicleRoutePlan | None, tuple[str,...]]:
    """Replay every affected visit/order and the final directed return.

    Time O((r+1)*(D+1)); Space O(r+D). No float load subtotal or epsilon.
    Window end limits service START. Priority controls admission, not service order.
    """
    counters.feasibility_checks += 1
    vehicle = data.vehicles[vehicle_id]
    home = vehicle.current_node_id
    if len(visits)<2 or visits[0] != FleetVisit(home) or visits[-1] != FleetVisit(home):
        raise ValueError('candidate route must start/end at its own depot without depot tasks')
    ids = [key for visit in visits for key in visit.order_ids]
    if len(ids) != len(set(ids)) or any(key not in data.orders for key in ids):
        raise ValueError('candidate order identities are invalid')
    orders = [data.orders[key] for key in ids]
    if any(order.status is not OrderStatus.PENDING for order in orders):
        raise ValueError('static candidate contains a nonpending order')
    for visit in visits[1:-1]:
        if not visit.order_ids or any(data.orders[key].destination_id != visit.node_id for key in visit.order_ids):
            raise ValueError('candidate visit has no task or a wrong service destination')
    report = check_delivery_load(vehicle.capacity_decimal,orders)
    if not report.feasible:
        return None,('capacity',)
    cargo = DeliveryLoadState(vehicle.capacity_decimal,orders)
    now = data.initial_time
    services: list[FleetService] = []
    legs: list[FleetLeg] = []
    distance = travel = cost = 0.0
    for index in range(1,len(visits)):
        source,target = visits[index-1].node_id,visits[index].node_id
        leg = paths.leg(source,target)
        if leg is None:
            reason = paths.failure(source,target)
            if reason == 'unreachable_leg' and index == len(visits)-1:
                reason = 'return_unreachable'
            return None,(reason,)
        legs.append(leg)
        distance += leg.distance
        travel += leg.travel_time
        cost += leg.cost
        now += leg.travel_time
        arrival = now
        if not all(math.isfinite(value) for value in (now,distance,travel,cost)):
            return None,('nonfinite_time',)
        for service_index,key in enumerate(visits[index].order_ids):
            order = data.orders[key]
            counters.time_window_checks += 1
            start = max(now,order.time_window_start)
            if start > order.time_window_end:
                return None,('time_window',)
            end = start + data.service_time
            if not math.isfinite(end):
                return None,('nonfinite_time',)
            cargo.deliver(key)
            services.append(FleetService(key,index,service_index,arrival,start-now,start,end,cargo.current_load))
            now = end
    return VehicleRoutePlan(vehicle_id,data.couriers[vehicle_id].id,home,visits,tuple(legs),
        tuple(services),vehicle.capacity_decimal,report.initial_load,data.initial_time,now,
        distance,travel,cost),()
