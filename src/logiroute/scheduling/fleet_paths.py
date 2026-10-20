"""Private static inputs and one shared primary-metric path closure per call.

Uses existing PathProvider.single-source batches; never implements shortest paths.
The original input must not change during planning. Clone weights and exact
quantities rather than copying legacy float DTOs. Fingerprints exclude object IDs.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math

from logiroute.algorithms.ordering import ordered_strings
from logiroute.config.loader import ScenarioBundle
from logiroute.core import Node, Edge, Order, Vehicle, Courier
from logiroute.core.enums import NodeType, VehicleStatus, CourierStatus
from logiroute.core.order_identity import index_orders
from logiroute.graph import LogisticsGraph
from logiroute.scheduling.path_provider import PathProvider
from logiroute.scheduling.fleet_types import FleetLeg


def finite_time(value: float, name: str, *, nonnegative: bool = False) -> float:
    """Validate a time scalar (no wall clock). Time/Space O(1)."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (nonnegative and value < 0)):
        raise ValueError(f'{name} must be a finite time in its allowed range')
    return float(value)


def fingerprint_scenario(bundle: ScenarioBundle) -> str:
    """Stable relevant input identity; no builtin sorting or process IDs.

    Handwritten ID ordering O(V²+M²+K²+sum(degree²)); Space O(V+E+M+K+D).
    D includes the serialized scalar digit count. Metadata is not a planner input.
    """
    graph = bundle.graph
    nodes = [graph.get_node(key) for key in ordered_strings(graph.node_ids)]
    edges = []
    for node in nodes:
        outgoing = {e.target_id: e for e in graph.get_neighbors(node.id)}
        for target in ordered_strings(outgoing):
            e = outgoing[target]
            edges.append((e.source_id,e.target_id,e.distance,e.travel_time,e.cost,e.traffic_status.value))
    orders = index_orders(bundle.orders)
    vehicles = {v.id:v for v in bundle.vehicles}
    couriers = {c.id:c for c in bundle.couriers}
    content = (bundle.name, bundle.mode, bundle.random_seed,
        [(n.id,n.node_type.value,n.x,n.y) for n in nodes], edges,
        [(o.id,o.destination_id,str(o.demand_decimal),o.time_window_start,o.time_window_end,
          o.priority.value,o.status.value) for o in (orders[k] for k in ordered_strings(orders))],
        [(v.id,str(v.capacity_decimal),str(v.current_load_decimal),v.current_node_id,v.status.value)
         for v in (vehicles[k] for k in ordered_strings(vehicles))],
        [(c.id,c.vehicle_id,c.status.value) for c in (couriers[k] for k in ordered_strings(couriers))],
        bundle.simulation.get('initial_time'),bundle.simulation.get('service_time'))
    return hashlib.sha256(json.dumps(content,ensure_ascii=True,allow_nan=False).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class FleetInput:
    bundle: ScenarioBundle
    orders: dict[str, Order]
    vehicles: dict[str, Vehicle]
    couriers: dict[str, Courier]
    initial_time: float
    service_time: float
    fingerprint: str


def freeze_scenario(source: ScenarioBundle) -> FleetInput:
    """Validate and isolate static business data using existing core models.

    Time includes fingerprint ordering plus O(V+E+MD+KD); same linear space.
    No source state is changed. A changed input raises instead of mixing versions.
    """
    if not isinstance(source, ScenarioBundle):
        raise ValueError('fleet planning requires a ScenarioBundle')
    source.graph.validate()
    original_orders = index_orders(source.orders)
    initial = finite_time(source.simulation.get('initial_time'), 'initial_time')
    service = finite_time(source.simulation.get('service_time'), 'service_time', nonnegative=True)
    vehicles: dict[str, Vehicle] = {}
    for v in source.vehicles:
        if not isinstance(v, Vehicle):
            raise ValueError('invalid vehicle')
        v.__post_init__()
        if v.id in vehicles:
            raise ValueError('duplicate vehicle id')
        if v.current_node_id and not source.graph.has_node(v.current_node_id):
            raise ValueError('unknown vehicle location')
        vehicles[v.id] = v
    if not vehicles:
        raise ValueError('fleet must contain at least one vehicle')
    couriers: dict[str, Courier] = {}
    seen_couriers: set[str] = set()
    for c in source.couriers:
        if not isinstance(c, Courier):
            raise ValueError('invalid courier')
        c.__post_init__()
        if c.id in seen_couriers or c.vehicle_id in couriers or c.vehicle_id not in vehicles:
            raise ValueError('invalid or duplicate courier binding')
        seen_couriers.add(c.id)
        couriers[c.vehicle_id] = c
    if len(couriers) != len(vehicles):
        raise ValueError('every vehicle requires exactly one courier')
    for order in original_orders.values():
        if not source.graph.has_node(order.destination_id):
            raise ValueError('unknown order destination')
        finite_time(order.time_window_start,'time_window_start')
        finite_time(order.time_window_end,'time_window_end')
    before = fingerprint_scenario(source)
    vehicles = {key:Vehicle(v.id,v.capacity_decimal,v.current_load_decimal,v.current_node_id,v.status)
                for key,v in vehicles.items()}
    couriers = {key:Courier(c.id,c.name,c.vehicle_id,c.status) for key,c in couriers.items()}
    graph = LogisticsGraph()
    for n in source.graph.get_all_nodes():
        graph.add_node(Node(n.id,n.name,n.node_type,n.x,n.y))
    for e in source.graph.get_all_edges():
        for value in (e.distance,e.travel_time,e.cost):
            finite_time(value,'edge weight',nonnegative=True)
        graph.add_edge(Edge(e.source_id,e.target_id,e.distance,e.travel_time,e.cost,e.traffic_status))
    orders = {key:Order(o.id,o.destination_id,o.demand_decimal,o.time_window_start,o.time_window_end,
                        o.priority,o.status) for key,o in original_orders.items()}
    bundle = ScenarioBundle(source.name,source.mode,source.random_seed,graph,
        list(vehicles.values()),list(couriers.values()),list(orders.values()),
        {'initial_time':initial,'service_time':service})
    if fingerprint_scenario(source) != before:
        raise ValueError('input changed while taking planning snapshot')
    return FleetInput(bundle,orders,vehicles,couriers,initial,service,before)


def vehicle_reasons(data: FleetInput, vehicle_id: str) -> tuple[str, ...]:
    """Static eligibility only. Time/Space O(1). Does not mutate status/load."""
    vehicle = data.vehicles[vehicle_id]
    reasons = []
    if vehicle.status is not VehicleStatus.IDLE:
        reasons.append('vehicle_not_idle')
    if vehicle.current_load_decimal != 0:
        reasons.append('vehicle_not_empty')
    node = data.bundle.graph.try_get_node(vehicle.current_node_id)
    if node is None or node.node_type is not NodeType.WAREHOUSE:
        reasons.append('invalid_depot')
    if data.couriers[vehicle_id].status is not CourierStatus.IDLE:
        reasons.append('courier_not_idle')
    return tuple(reasons)


class PathClosure:
    """Local O(1)-average pair lookup, including unreachable static pairs.

    Build O(U*(V+E)log V + P*(V+E+V)), including existing fingerprint-key hashing
    and path reconstruction; storage O(PV+V+E). No cross-call cache sharing.
    """
    __slots__ = ('_table','_failures','dijkstra_calls','cache_hits','cache_misses','path_table_hits','objective')

    def __init__(self, data: FleetInput, objective: str) -> None:
        if objective not in ('distance','cost'):
            raise ValueError('fleet objective must be distance or cost')
        self.objective = objective
        self._table: dict[tuple[str,str], FleetLeg | None] = {}
        self._failures: dict[tuple[str,str], str] = {}
        self.path_table_hits = 0
        terminals = {o.destination_id for o in data.orders.values()}
        for vehicle_id, vehicle in data.vehicles.items():
            if not vehicle_reasons(data,vehicle_id):
                terminals.add(vehicle.current_node_id)
        ids = tuple(ordered_strings(terminals))
        provider = PathProvider(data.bundle.graph)
        for source in ids:
            batch = provider.shortest_paths_from(source,ids,objective)
            for target in ids:
                result = batch[target]
                key = (source,target)
                if not result.reachable:
                    self._table[key] = None
                    self._failures[key] = 'unreachable_leg'
                    continue
                metrics = tuple(result.cross_metrics[name] for name in ('distance','travel_time','cost'))
                if any(not math.isfinite(value) or value < 0 for value in metrics):
                    self._table[key] = None
                    self._failures[key] = 'nonfinite_path'
                else:
                    self._table[key] = FleetLeg(source,target,result.path,*metrics)
        self.dijkstra_calls = provider.dijkstra_calls
        self.cache_hits = provider.cache_hits
        self.cache_misses = provider.cache_misses

    def leg(self, source: str, target: str) -> FleetLeg | None:
        """Known pair lookup; never accepts unknown same-node shortcuts. Time/Space O(1)."""
        if (source,target) not in self._table:
            raise ValueError('node pair is outside this planning snapshot')
        self.path_table_hits += 1
        return self._table[source,target]

    def failure(self, source: str, target: str) -> str:
        """Reason for a failed pair. Time/Space O(1)."""
        return self._failures[source,target]


def build_closure(data: FleetInput, objective: str) -> PathClosure:
    """Build one primary-metric closure shared by every vehicle in this call."""
    return PathClosure(data,objective)
