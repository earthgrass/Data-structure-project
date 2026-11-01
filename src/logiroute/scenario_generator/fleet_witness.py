"""Constructive per-car witnesses; never supplied to the greedy planner as hints.

Uses existing route assessment for construction only. Certification is performed
separately by fleet_validator, which does not import that assessment function.
No shortest-path algorithm or graph container is reimplemented here.
"""
from __future__ import annotations

from decimal import Decimal
import math

from logiroute.algorithms.ordering import ordered_strings
from logiroute.config.loader import ScenarioBundle
from logiroute.core import Vehicle, Courier, Order
from logiroute.core.enums import NodeType, OrderPriority
from logiroute.core.quantities import exact_sum
from logiroute.scenario_generator.fleet_config import FleetGeneratorConfig
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.scenario_generator.road_validator import validate_road_network
from logiroute.scheduling.algorithms.fleet_insertion import assess_route, EvaluationCounters
from logiroute.scheduling.fleet_paths import freeze_scenario, PathClosure, finite_time
from logiroute.scheduling.fleet_types import FleetScheduleResult, FleetStats, FleetVisit


def _witness(bundle: ScenarioBundle, allocation: dict[str, list[str]], objective: str
             ) -> tuple[FleetScheduleResult | None, tuple[str, ...]]:
    """Construct full routes with current windows. Cost: one closure + O(MD+K)."""
    data = freeze_scenario(bundle)
    paths = PathClosure(data, objective)
    routes = []
    for key in ordered_strings(data.vehicles):
        home = data.vehicles[key].current_node_id
        visits = (FleetVisit(home),) + tuple(
            FleetVisit(data.orders[oid].destination_id, (oid,)) for oid in allocation[key]
        ) + (FleetVisit(home),)
        route, reasons = assess_route(data, paths, key, visits, EvaluationCounters())
        if route is None:
            return None, reasons
        routes.append(route)
    return FleetScheduleResult(bundle.name, objective, tuple(routes), (), (), FleetStats(),
                               input_fingerprint=data.fingerprint), ()


def construct_candidate(config: FleetGeneratorConfig, rng: RandomSource, seed: int,
                        attempt: int
                        ) -> tuple[ScenarioBundle | None, tuple[FleetScheduleResult, ...], str,
                                   tuple[str, ...]]:
    """Sample roads, exact per-car packing, independent IDs and witness-derived windows.

    Packing scans K cars/order using exact_sum (O(MKD)); no total-fleet capacity
    is used as a feasibility proof. Customers are sampled WITH replacement.
    Four witness builds (two provisional, two final) each reuse existing closure
    and replay: O(F + U*G*log V + U²*(G+V) + MD + K). Road generation cost is
    additional; Space O(G+U²V+M+K+D), excluding immutable returned records.
    """
    graph = sample_logistics_graph(config.network, rng)
    road_report = validate_road_network(graph, config.network)
    if not road_report.valid:
        raise ValueError('road generator returned an invalid network')
    customers = ordered_strings(n.id for n in graph.nodes if n.node_type is NodeType.CUSTOMER)
    by_id = {v.id: v for v in config.vehicles}
    vehicle_ids = ordered_strings(by_id)
    loads = {key: Decimal(0) for key in vehicle_ids}
    allocation: dict[str, list[str]] = {key: [] for key in vehicle_ids}
    orders = []
    for index in range(config.orders_count):
        quantity = rng.choice(config.demand_choices)
        available = [key for key in vehicle_ids
                     if exact_sum((loads[key], quantity)) <= by_id[key].capacity]
        if not available:
            return None, (), 'capacity', (f'order_{index+1}:no_vehicle_fits:{quantity}',)
        chosen = rng.choice(available)
        oid = f'{config.order_id_prefix}{index+1}'
        destination = rng.choice(customers)
        priority = (OrderPriority.URGENT if rng.uniform(0.0, 1.0) < config.urgent_fraction
                    else OrderPriority.NORMAL)
        orders.append(Order(oid, destination, quantity, config.initial_time,
                            config.witness_horizon, priority))
        loads[chosen] = exact_sum((loads[chosen], quantity))
        allocation[chosen].append(oid)
    for key in vehicle_ids:
        rng.shuffle(allocation[key])
    bundle = ScenarioBundle(
        f'{config.name}.seed{seed}.attempt{attempt}', 'fixed', seed, graph,
        [Vehicle(key, by_id[key].capacity, current_node_id=by_id[key].depot_id)
         for key in vehicle_ids],
        [Courier(by_id[key].courier_id, by_id[key].courier_id, key) for key in vehicle_ids],
        orders, {'initial_time': config.initial_time, 'service_time': config.service_time},
        metadata={'generator': 'v2.phase4', 'base_seed': seed, 'attempt': attempt,
                  'config_fingerprint': config.fingerprint, 'road_network': road_report.to_dict()})
    provisional = []
    for objective in ('distance', 'cost'):
        answer, reasons = _witness(bundle, allocation, objective)
        if answer is None:
            return bundle, (), 'witness_route', (objective, *reasons)
        provisional.append(answer)
    starts = [{s.order_id: s.service_start for r in p.routes for s in r.services}
              for p in provisional]
    # A window covers each order's service in both primary-path witnesses.
    # There is no rounding or epsilon expansion of a configured constraint.
    final_orders = []
    for order in orders:
        lower = max(config.initial_time,
                    min(times[order.id] for times in starts)-config.window_early_slack)
        upper = max(times[order.id] for times in starts)+config.window_late_slack
        if not math.isfinite(upper) or lower >= upper:
            return bundle, (), 'witness_window', (order.id, 'nonfinite_or_collapsed_window')
        final_orders.append(Order(order.id, order.destination_id, order.demand_decimal,
                                  lower, upper, order.priority))
    bundle.orders = final_orders
    final = []
    for objective in ('distance', 'cost'):
        answer, reasons = _witness(bundle, allocation, objective)
        if answer is None:
            return bundle, (), 'witness_route', (objective, *reasons)
        final.append(answer)
    return bundle, tuple(final), 'constructed', ()
