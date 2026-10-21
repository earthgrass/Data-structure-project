"""Independent tiny exhaustive reference; never used by production planning.

Enumerates ordered lists assigned to labelled vehicles. For M tasks/K vehicles,
M! * choose(M+K-1,K-1) route combinations; O(combinations*(M*D+K)) time after
canonical Dijkstra paths, O(M+K+U²V) space. No greedy selection/replay imports.
The proof domain is canonical primary-metric paths, not arbitrary road walks.
"""
from __future__ import annotations
from collections.abc import Iterator
import json
from pathlib import Path
from typing import Any

from logiroute.algorithms.dijkstra import shortest_path
from logiroute.algorithms.ordering import ordered_strings
from logiroute.config.loader import ScenarioBundle
from logiroute.core import Node,Edge,Order,Vehicle,Courier,NodeType,OrderStatus,VehicleStatus,CourierStatus
from logiroute.core.quantities import exact_sum
from logiroute.graph import LogisticsGraph


def capacity_counterexample() -> ScenarioBundle:
    """JSON-defined research fixture, outside the production loader scale contract."""
    values=json.loads((Path(__file__).resolve().parents[1]/'config/fleet_experiments.json').read_text(encoding='utf-8'))['counterexample']
    warehouse,customer=values['warehouse'],values['customer']
    graph=LogisticsGraph()
    graph.add_node(Node(warehouse,warehouse,NodeType.WAREHOUSE,0,0))
    graph.add_node(Node(customer,customer,NodeType.CUSTOMER,0,0))
    weight=values['edge_weight']
    graph.add_edge(Edge(warehouse,customer,weight,weight,weight))
    graph.add_edge(Edge(customer,warehouse,weight,weight,weight))
    return ScenarioBundle(values['name'],'fixed',0,graph,
        [Vehicle(key,values['capacity'],current_node_id=warehouse) for key in values['vehicle_ids']],
        [Courier(cid,cid,vid) for cid,vid in zip(values['courier_ids'],values['vehicle_ids'])],
        [Order(key,customer,demand,values['window_start'],values['window_end'])
         for key,demand in zip(values['order_ids'],values['demands'])],
        {'initial_time':values['initial_time'],'service_time':values['service_time']})


def _permutations(items: tuple[str,...]) -> Iterator[tuple[str,...]]:
    """Handwritten recursive permutations. O(n*n!) output time; O(n²) stack data."""
    if not items:
        yield ()
    for index,key in enumerate(items):
        for tail in _permutations(items[:index]+items[index+1:]):
            yield (key,)+tail


def enumerate_fleet(scenario: ScenarioBundle, objective: str) -> dict[str,Any]:
    """Enumerate every full assignment/order independently; <=6 tasks is intentional."""
    if objective not in ('distance','cost'):
        raise ValueError('invalid reference objective')
    if len(scenario.orders)>6 or len(scenario.vehicles)>2:
        raise ValueError('exhaustive reference is restricted to M<=6,K<=2')
    orders={order.id:order for order in scenario.orders}
    if len(orders)!=len(scenario.orders) or any(o.status is not OrderStatus.PENDING for o in orders.values()):
        raise ValueError('reference requires unique pending orders')
    vehicles={v.id:v for v in scenario.vehicles}
    for v in vehicles.values():
        matches=[c for c in scenario.couriers if c.vehicle_id==v.id]
        if (v.status is not VehicleStatus.IDLE or v.current_load_decimal!=0
                or scenario.graph.get_node(v.current_node_id).node_type is not NodeType.WAREHOUSE
                or len(matches)!=1 or matches[0].status is not CourierStatus.IDLE):
            raise ValueError('reference fixture requires available vehicles')
    vehicle_ids=ordered_strings(vehicles)
    terminals={o.destination_id for o in orders.values()}|{v.current_node_id for v in vehicles.values()}
    table={(a,b):shortest_path(scenario.graph,a,b,objective) for a in ordered_strings(terminals)
           for b in ordered_strings(terminals)}
    checked=feasible=0; best=None; best_witness=None
    buckets=[[] for _ in vehicle_ids]
    ids=tuple(ordered_strings(orders))

    def evaluate(sequences: tuple[tuple[str,...],...]) -> None:
        nonlocal checked,feasible,best,best_witness
        checked+=1
        total=0.0
        for index,sequence in enumerate(sequences):
            vehicle=vehicles[vehicle_ids[index]]
            load=exact_sum(orders[key].demand_decimal for key in sequence)
            if load>vehicle.capacity_decimal: return
            current=vehicle.current_node_id
            clock=scenario.simulation['initial_time']
            for key in sequence:
                order=orders[key]
                path=table[current,order.destination_id]
                if not path.reachable: return
                total+=path.total_weight
                clock=max(clock+path.cross_metrics['travel_time'],order.time_window_start)
                if clock>order.time_window_end: return
                clock+=scenario.simulation['service_time']
                current=order.destination_id
            back=table[current,vehicle.current_node_id]
            if not back.reachable: return
            total+=back.total_weight
        feasible+=1
        if best is None or total<best:
            best=total
            best_witness=[{'vehicle_id':vehicle_ids[i],'order_ids':list(sequence)}
                          for i,sequence in enumerate(sequences)]

    def order_buckets(index: int, sequences: tuple[tuple[str,...],...]) -> None:
        if index==len(buckets):
            evaluate(sequences); return
        for permutation in _permutations(tuple(buckets[index])):
            order_buckets(index+1,sequences+(permutation,))

    def assign(index: int) -> None:
        if index==len(ids):
            order_buckets(0,()); return
        for bucket in buckets:
            bucket.append(ids[index]); assign(index+1); bucket.pop()

    assign(0)
    return {'combinations_checked':checked,'full_feasible_combinations':feasible,
            'best_objective':best,'witness':best_witness,
            'proof_domain':'canonical primary-metric Dijkstra closure'}
