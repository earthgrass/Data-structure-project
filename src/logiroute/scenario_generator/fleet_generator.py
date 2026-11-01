"""V2 production acceptance: witness + independent validation + BOTH real objectives.

A finite, deterministic rejection sampler. Success is a certificate for the
returned input, not a theorem that greedy can solve every feasible instance.
Legacy generate_scenario and the Web interface are deliberately unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from copy import deepcopy
from time import perf_counter
from typing import Any

from logiroute.algorithms.ordering import ordered_strings
from logiroute.config.loader import ScenarioBundle
from logiroute.scenario_generator.fleet_config import FleetGeneratorConfig
from logiroute.scenario_generator.fleet_witness import construct_candidate
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.scheduling import plan_fleet
from logiroute.scheduling.fleet_paths import fingerprint_scenario
from logiroute.scheduling.fleet_types import FleetScheduleResult
from logiroute.scheduling.fleet_validator import validate_fleet


def _scenario_dict(bundle: ScenarioBundle) -> dict[str, Any]:
    """Independent JSON snapshot with full metadata and exact load text.

    Manual ID ordering costs O(V²+M²+K²+sum(degree²)); linear output space.
    The ScenarioBundle remains mutable by its owner; exported dictionaries do
    not alias its metadata. Certification applies to the returned fingerprint.
    """
    graph = bundle.graph
    nodes = [graph.get_node(key) for key in ordered_strings(graph.node_ids)]
    edges = []
    for node in nodes:
        outgoing = {e.target_id: e for e in graph.get_neighbors(node.id)}
        for target in ordered_strings(outgoing):
            e = outgoing[target]
            edges.append(dict(source_id=e.source_id, target_id=e.target_id,
                              distance=e.distance, travel_time=e.travel_time, cost=e.cost,
                              traffic_status=e.traffic_status.value, metadata=deepcopy(e.metadata)))
    orders = {o.id: o for o in bundle.orders}
    vehicles = {v.id: v for v in bundle.vehicles}
    couriers = {c.id: c for c in bundle.couriers}
    return dict(name=bundle.name, mode=bundle.mode, random_seed=bundle.random_seed,
                nodes=[dict(id=n.id, name=n.name, node_type=n.node_type.value,
                            x=n.x, y=n.y, metadata=deepcopy(n.metadata)) for n in nodes],
                edges=edges,
                orders=[dict(id=o.id, destination_id=o.destination_id, demand=str(o.demand_decimal),
                             time_window_start=o.time_window_start, time_window_end=o.time_window_end,
                             priority=o.priority.value, status=o.status.value)
                        for o in (orders[k] for k in ordered_strings(orders))],
                vehicles=[dict(id=v.id, capacity=str(v.capacity_decimal),
                               current_load=str(v.current_load_decimal),
                               current_node_id=v.current_node_id, status=v.status.value)
                          for v in (vehicles[k] for k in ordered_strings(vehicles))],
                couriers=[dict(id=c.id, name=c.name, vehicle_id=c.vehicle_id, status=c.status.value)
                          for c in (couriers[k] for k in ordered_strings(couriers))],
                simulation=deepcopy(bundle.simulation), optimization=deepcopy(bundle.optimization),
                metadata=deepcopy(bundle.metadata))


@dataclass(frozen=True, slots=True)
class GenerationAttempt:
    number: int
    candidate_id: str
    stage: str
    reasons: tuple[str, ...]
    input_fingerprint: str
    outcomes: tuple[tuple[str, bool, bool, int], ...]
    runtime_seconds: float

    def to_dict(self, *, include_timing: bool = True) -> dict[str, Any]:
        """Explicit evidence boundary. Time/Space O(reasons + outcomes)."""
        result = dict(number=self.number, candidate_id=self.candidate_id, stage=self.stage,
                      reasons=list(self.reasons), input_fingerprint=self.input_fingerprint,
                      outcomes=[dict(objective=m, valid=v, complete=c, served=n)
                                for m, v, c, n in self.outcomes])
        if include_timing:
            result['runtime_seconds'] = self.runtime_seconds
        return result


class FleetGenerationError(RuntimeError):
    """No scenario is published; failed attempts remain inspectable and reproducible."""
    def __init__(self, seed: int, config_fingerprint: str,
                 attempts: tuple[GenerationAttempt, ...]) -> None:
        self.seed = seed
        self.config_fingerprint = config_fingerprint
        self.attempts = attempts
        super().__init__(f'fleet generation rejected after {len(attempts)} attempts; '
                         f'seed={seed}; last stage={attempts[-1].stage}')

    def to_dict(self, *, include_timing: bool = True) -> dict[str, Any]:
        """Serialize every rejection, not only the final one. Time/Space O(attempts)."""
        return dict(seed=self.seed, config_fingerprint=self.config_fingerprint,
                    attempts=[a.to_dict(include_timing=include_timing) for a in self.attempts])


@dataclass(frozen=True, slots=True)
class FleetGenerationResult:
    scenario: ScenarioBundle
    witnesses: tuple[FleetScheduleResult, ...]
    plans: tuple[FleetScheduleResult, ...]
    attempts: tuple[GenerationAttempt, ...]
    seed: int
    config_fingerprint: str
    scenario_fingerprint: str
    runtime_seconds: float

    def to_dict(self, *, include_timing: bool = True) -> dict[str, Any]:
        """Full scene/routes; includes manual snapshot ordering and linear output space."""
        if fingerprint_scenario(self.scenario) != self.scenario_fingerprint:
            raise ValueError('scenario changed after certification; regenerate or revalidate')
        def plan(answer: FleetScheduleResult) -> dict[str, Any]:
            value = answer.to_dict()
            if not include_timing:
                value['planning_stats'].pop('runtime_seconds')
                value['planning_stats'].pop('validation_seconds')
            return value
        result = dict(seed=self.seed, config_fingerprint=self.config_fingerprint,
                      scenario_fingerprint=self.scenario_fingerprint,
                      scenario_id=self.scenario.name,
                      scenario=_scenario_dict(self.scenario),
                      witnesses=[plan(p) for p in self.witnesses],
                      plans=[plan(p) for p in self.plans],
                      attempts=[a.to_dict(include_timing=include_timing) for a in self.attempts])
        if include_timing:
            result['runtime_seconds'] = self.runtime_seconds
        if fingerprint_scenario(self.scenario) != self.scenario_fingerprint:
            raise ValueError('scenario changed during certificate export')
        return result


def generate_fleet_scenario(config: FleetGeneratorConfig, *, seed: int) -> FleetGenerationResult:
    """Return only a doubly certified full scenario, or an explicit finite failure.

    One local PRNG continues across attempts; base seed/config/version/attempt
    identify replay. No process hash, sleeps, retries of arbitrary exceptions or
    relaxation of demand/windows/capacity. Invalid plan claims stop immediately;
    valid incomplete heuristics can reject and regenerate the WHOLE candidate.
    Time O(A*(construct + 2*planner + 4*independent_validator)), A<=max_attempts.
    Peak Space O(one candidate + returned witnesses/plans + A*failure evidence).
    """
    if not isinstance(config, FleetGeneratorConfig):
        raise ValueError('expected FleetGeneratorConfig')
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed must be an explicit integer')
    config_id = config.fingerprint
    rng = RandomSource(seed)
    history = []
    start = perf_counter()
    for attempt in range(1, config.max_attempts + 1):
        tick = perf_counter()
        bundle, witnesses, stage, reasons = construct_candidate(config, rng, seed, attempt)
        if witnesses and (bundle is None
                or tuple(w.objective for w in witnesses) != ('distance', 'cost')):
            raise ValueError('candidate must carry distinct distance and cost witnesses')
        fingerprint = fingerprint_scenario(bundle) if bundle is not None else ''
        accepted_witnesses = []
        plans = []
        outcomes = []
        fatal = False
        if witnesses:
            for witness in witnesses:
                report = validate_fleet(bundle, witness)
                accepted_witnesses.append(replace(witness, validation=report))
                if not report.valid or not report.complete:
                    stage, reasons, fatal = 'invalid_witness', report.violations, True
                    break
            if not fatal:
                for objective in ('distance', 'cost'):
                    answer = plan_fleet(bundle, objective)  # ordinary input; NO witness hint
                    report = validate_fleet(bundle, answer, objective=objective)
                    plans.append(replace(answer, validation=report))
                    served = sum(len(route.services) for route in answer.routes)
                    outcomes.append((objective, report.valid, report.complete, served))
                    if not report.valid:
                        stage, reasons, fatal = 'invalid_plan', report.violations, True
                        break
                if not fatal:
                    if all(p.is_feasible for p in plans):
                        stage, reasons = 'accepted', ()
                    else:
                        stage = 'heuristic_incomplete'
                        reasons = tuple(f'{p.objective}:{o.order_id}:{reason}'
                                        for p in plans for o in p.unserved_orders for reason in o.reasons)
        if config.fingerprint != config_id or (bundle is not None
                and fingerprint_scenario(bundle) != fingerprint):
            raise ValueError('generation input changed during certification')
        history.append(GenerationAttempt(attempt, f'{config.name}.seed{seed}.attempt{attempt}',
                                         stage, reasons, fingerprint, tuple(outcomes),
                                         perf_counter()-tick))
        if stage == 'accepted':
            return FleetGenerationResult(bundle, tuple(accepted_witnesses), tuple(plans),
                                         tuple(history), seed, config_id, fingerprint,
                                         perf_counter()-start)
        if fatal:
            break
    raise FleetGenerationError(seed, config_id, tuple(history))
