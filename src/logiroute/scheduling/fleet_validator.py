"""Independent fleet witness verification, including final unserved evidence.

Does not import candidate insertion, greedy selection or their route replay.
Shares only core identity/Decimal tools, input normalization and the existing
Dijkstra PathProvider. Recomputes actual edge metrics and service schedules.
Partial witnesses claiming no insertion are independently checked for that claim.
"""
from __future__ import annotations
from decimal import Decimal
import math

from logiroute.algorithms.ordering import ordered_strings
from logiroute.config.loader import ScenarioBundle
from logiroute.core.enums import NodeType, OrderStatus, VehicleStatus, CourierStatus
from logiroute.core.order_identity import validate_order_coverage
from logiroute.core.delivery_load import check_delivery_load
from logiroute.core.quantities import exact_difference
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.fleet_paths import FleetInput, freeze_scenario, fingerprint_scenario
from logiroute.scheduling.fleet_types import (
    FleetVisit,FleetLeg,FleetService,VehicleRoutePlan,FleetScheduleResult,FleetValidationReport,
)


def _close(a: float, b: float) -> bool:
    # Reporting consistency only; never used to relax capacity or time windows.
    return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)


def _recompute(data: FleetInput, table: dict, vehicle_id: str, visits: tuple[FleetVisit,...],
               actual_legs: tuple[FleetLeg,...] | None = None
               ) -> tuple[VehicleRoutePlan | None,str | None]:
    """Validator-owned replay. O((r+1)(D+1)); Space O(r+D).

    For a supplied witness use its real, independently summed roads; for checking
    an unserved claim use freshly computed canonical primary-metric paths.
    """
    vehicle=data.vehicles[vehicle_id]
    home=vehicle.current_node_id
    if len(visits)<2 or visits[0]!=FleetVisit(home) or visits[-1]!=FleetVisit(home):
        return None,'depot_mismatch'
    ids=[key for visit in visits for key in visit.order_ids]
    if len(set(ids))!=len(ids) or any(key not in data.orders for key in ids):
        return None,'order_identity'
    for visit in visits[1:-1]:
        if not visit.order_ids or any(data.orders[key].destination_id!=visit.node_id for key in visit.order_ids):
            return None,'service_location'
    if any(data.orders[key].status is not OrderStatus.PENDING for key in ids):
        return None,'order_not_pending'
    load_report=check_delivery_load(vehicle.capacity_decimal,[data.orders[key] for key in ids])
    if not load_report.feasible:
        return None,'capacity'
    load=load_report.initial_load
    clock=data.initial_time
    events=[]; legs=[]
    totals=[0.0,0.0,0.0]
    for index in range(1,len(visits)):
        if actual_legs is None:
            path=table[visits[index-1].node_id,visits[index].node_id]
            if not path.reachable:
                return None,'return_unreachable' if index==len(visits)-1 else 'unreachable_leg'
            metrics=tuple(path.cross_metrics[m] for m in ('distance','travel_time','cost'))
            if not all(math.isfinite(x) for x in metrics):
                return None,'nonfinite_path'
            leg=FleetLeg(path.source,path.target,path.path,*metrics)
        else:
            leg=actual_legs[index-1]
        legs.append(leg)
        for metric,value in enumerate((leg.distance,leg.travel_time,leg.cost)):
            totals[metric]+=value
        clock+=leg.travel_time
        arrival=clock
        if not all(math.isfinite(x) for x in (*totals,clock)):
            return None,'nonfinite_time'
        for slot,key in enumerate(visits[index].order_ids):
            order=data.orders[key]
            begin=max(clock,order.time_window_start)
            if begin>order.time_window_end:
                return None,'time_window'
            finish=begin+data.service_time
            if not math.isfinite(finish):
                return None,'nonfinite_time'
            load=exact_difference(load,order.demand_decimal)
            events.append(FleetService(key,index,slot,arrival,begin-clock,begin,finish,load))
            clock=finish
    return VehicleRoutePlan(vehicle_id,data.couriers[vehicle_id].id,home,visits,tuple(legs),
        tuple(events),vehicle.capacity_decimal,load_report.initial_load,data.initial_time,
        clock,*totals),None


def validate_fleet(scenario: ScenarioBundle, result: FleetScheduleResult, *,
                   objective: str | None = None) -> FleetValidationReport:
    """Recheck a witness from original inputs, ignoring its validation flag.

    Path closure uses fresh single-source Dijkstra. Full witness checking is
    O(U*G*log V + U²*(G+V) + L + MD). For partial results, independently checking
    all claimed failed insertions adds O(M³*(D+1)+KM*(D+1)) worst case.
    Space O(G+U²V+(M+K)V+(M+K)D), streaming trial insertions. G=V+E.
    Invalid original inputs raise ValueError; invalid result claims are reported.
    """
    if not isinstance(result,FleetScheduleResult):
        raise ValueError('expected FleetScheduleResult')
    data=freeze_scenario(scenario)
    mode=result.objective if objective is None else objective
    if mode not in ('distance','cost'):
        raise ValueError('fleet objective must be distance or cost')
    errors=[]
    if mode!=result.objective:
        errors.append('objective_mismatch')
    if result.scenario_name!=scenario.name:
        errors.append('scenario_mismatch')
    if result.input_fingerprint and result.input_fingerprint!=data.fingerprint:
        errors.append('input_fingerprint_mismatch')
    # Eligibility is independently derived, not imported from planner selection.
    available={}; unavailable={}
    for key in ordered_strings(data.vehicles):
        vehicle=data.vehicles[key]; reasons=[]
        if vehicle.status is not VehicleStatus.IDLE: reasons.append('vehicle_not_idle')
        if vehicle.current_load_decimal!=0: reasons.append('vehicle_not_empty')
        node=data.bundle.graph.try_get_node(vehicle.current_node_id)
        if node is None or node.node_type is not NodeType.WAREHOUSE: reasons.append('invalid_depot')
        if data.couriers[key].status is not CourierStatus.IDLE: reasons.append('courier_not_idle')
        if reasons: unavailable[key]=tuple(reasons)
        else: available[key]=vehicle
    claimed=dict(result.unavailable_vehicles)
    if len(claimed)!=len(result.unavailable_vehicles) or claimed!=unavailable:
        errors.append('unavailable_vehicle_evidence_mismatch')
    routes={}
    for route in result.routes:
        if route.vehicle_id in routes: errors.append('duplicate_vehicle_route')
        routes[route.vehicle_id]=route
        if route.vehicle_id not in available: errors.append('route_vehicle_unavailable_or_unknown')
    if set(routes)!=set(available): errors.append('vehicle_route_partition_mismatch')
    served=[event.order_id for route in result.routes for event in route.services]
    partition=validate_order_coverage(data.orders.values(),served,(o.order_id for o in result.unserved_orders))
    errors.extend(partition.violations)
    provider=PathProvider(data.bundle.graph)
    terminals={order.destination_id for order in data.orders.values()}
    terminals.update(vehicle.current_node_id for vehicle in available.values())
    terminal_ids=tuple(ordered_strings(terminals))
    table={}
    for source in terminal_ids:
        batch=provider.shortest_paths_from(source,terminal_ids,mode)
        for target in terminal_ids: table[source,target]=batch[target]
    global_actual=[0.0,0.0,0.0]
    for route in result.routes:
        key=route.vehicle_id
        if key not in available: continue
        expected_ids=tuple(oid for visit in route.visits for oid in visit.order_ids)
        if expected_ids!=route.served_order_ids: errors.append(f'service_visit_mapping:{key}')
        if len(route.legs)!=len(route.visits)-1:
            errors.append(f'leg_count:{key}'); continue
        checked=[]; path_bad=False
        for index,leg in enumerate(route.legs):
            source,target=route.visits[index].node_id,route.visits[index+1].node_id
            if (leg.source!=source or leg.target!=target or not leg.path
                    or leg.path[0]!=source or leg.path[-1]!=target
                    or any(not data.bundle.graph.has_node(n) for n in leg.path)):
                errors.append(f'path_endpoints:{key}'); path_bad=True; continue
            weights=[0.0,0.0,0.0]; missing=False
            for pos in range(len(leg.path)-1):
                edge=data.bundle.graph.try_get_edge(leg.path[pos],leg.path[pos+1])
                if edge is None:
                    errors.append(f'road_missing_or_wrong_direction:{key}')
                    missing=True; break
                for metric,value in enumerate((edge.distance,edge.travel_time,edge.cost)):
                    weights[metric]+=value
            if missing or not all(math.isfinite(x) for x in weights):
                path_bad=True; continue
            for expected,reported in zip(weights,(leg.distance,leg.travel_time,leg.cost)):
                if not _close(expected,reported): errors.append(f'leg_metric:{key}')
            optimal=table.get((source,target))
            main=weights[0 if mode=='distance' else 2]
            if optimal is None or not optimal.reachable or not _close(main,optimal.total_weight):
                errors.append(f'not_primary_shortest_path:{key}')
            checked.append(FleetLeg(source,target,leg.path,*weights))
        if path_bad: continue
        expected,reason=_recompute(data,table,key,route.visits,tuple(checked))
        if reason is not None:
            errors.append(f'{reason}:{key}'); continue
        if route.courier_id!=expected.courier_id or route.depot_id!=expected.depot_id:
            errors.append(f'vehicle_binding_or_depot:{key}')
        if route.capacity!=expected.capacity or route.initial_load!=expected.initial_load:
            errors.append(f'exact_load:{key}')
        for actual,reported in zip((expected.departure_time,expected.return_time,expected.total_distance,
                                   expected.total_travel_time,expected.total_cost),
                                  (route.departure_time,route.return_time,route.total_distance,
                                   route.total_travel_time,route.total_cost)):
            if not _close(actual,reported): errors.append(f'route_time_or_metric:{key}')
        if len(route.services)!=len(expected.services): errors.append(f'service_count:{key}')
        for actual,reported in zip(expected.services,route.services):
            if ((actual.order_id,actual.visit_index,actual.service_index,actual.load_after)
                    !=(reported.order_id,reported.visit_index,reported.service_index,reported.load_after)):
                errors.append(f'service_identity_or_exact_load:{key}')
            for name in ('arrival_time','waiting_time','service_start','service_end'):
                if not _close(getattr(actual,name),getattr(reported,name)):
                    errors.append(f'service_time:{key}')
            order=data.orders[actual.order_id]
            if not order.time_window_start<=reported.service_start<=order.time_window_end:
                errors.append(f'reported_service_outside_window:{key}')
        for index,value in enumerate((expected.total_distance,expected.total_travel_time,expected.total_cost)):
            global_actual[index]+=value
    for actual,reported in zip(global_actual,(result.total_distance,result.total_travel_time,result.total_cost)):
        if not _close(actual,reported): errors.append('global_metric_mismatch')
    # Independently check final failed-insertion explanations, without greedy code.
    if not errors:
        for item in result.unserved_orders:
            order=data.orders[item.order_id]
            observed=set()
            if order.status is not OrderStatus.PENDING: observed.add('order_not_pending')
            elif not available: observed.add('no_available_vehicle')
            else:
                for key in ordered_strings(routes):
                    visits=routes[key].visits
                    for position in range(1,len(visits)):
                        trial=visits[:position]+(FleetVisit(order.destination_id,(order.id,)),)+visits[position:]
                        _,reason=_recompute(data,table,key,trial)
                        if reason is None: errors.append(f'unserved_has_feasible_insertion:{order.id}')
                        else: observed.add(reason)
                    for position in range(1,len(visits)-1):
                        visit=visits[position]
                        if visit.node_id!=order.destination_id: continue
                        for slot in range(len(visit.order_ids)+1):
                            ids=visit.order_ids[:slot]+(order.id,)+visit.order_ids[slot:]
                            trial=visits[:position]+(FleetVisit(visit.node_id,ids),)+visits[position+1:]
                            _,reason=_recompute(data,table,key,trial)
                            if reason is None: errors.append(f'unserved_has_feasible_insertion:{order.id}')
                            else: observed.add(reason)
            if set(item.reasons)!=observed or len(set(item.reasons))!=len(item.reasons):
                errors.append(f'unserved_reason_mismatch:{item.order_id}')
    if fingerprint_scenario(scenario)!=data.fingerprint:
        errors.append('input_changed_during_validation')
    valid=not errors
    return FleetValidationReport(valid,valid and partition.all_orders_served,tuple(errors))
