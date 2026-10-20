"""Static fleet entry; isolated from the existing single-car API and execution.

plan_fleet does not advance time or mutate order/courier/vehicle lifecycle state.
It always invokes an independently implemented verifier before returning. Primary
paths are canonical shortest distance/cost paths, not all possible road paths.
"""
from __future__ import annotations
from dataclasses import replace
from time import perf_counter

from logiroute.config.loader import ScenarioBundle
from logiroute.scheduling.fleet_paths import freeze_scenario, build_closure, fingerprint_scenario
from logiroute.scheduling.fleet_types import FleetScheduleResult, FleetStats
from logiroute.scheduling.fleet_validator import validate_fleet
from logiroute.scheduling.algorithms.fleet_greedy import global_insertion


def plan_fleet(scenario: ScenarioBundle, objective: str = 'distance') -> FleetScheduleResult:
    """Plan all vehicles together for distance or cost, then independently verify.

    O(U*G*log V+U²*(G+V)+(M^4+K*M²)*(D+1)) plus input ordering/fingerprinting
    and independent verification. Space O(G+U²V+(M+K)V+(M+K)D+MK).
    No epsilon/floating cargo arithmetic, implicit state change or no-solution claim.
    """
    start=perf_counter()
    if objective not in ('distance','cost'):
        raise ValueError('fleet objective must be distance or cost')
    data=freeze_scenario(scenario)
    paths=build_closure(data,objective)
    routes,unserved,unavailable,trace,counters=global_insertion(data,paths)
    if fingerprint_scenario(scenario)!=data.fingerprint:
        raise ValueError('input changed during fleet planning')
    stats=FleetStats(paths.dijkstra_calls,paths.cache_hits,paths.cache_misses,paths.path_table_hits,
        counters.candidate_evaluations,counters.feasibility_checks,counters.time_window_checks,
        len(trace),perf_counter()-start)
    result=FleetScheduleResult(scenario.name,objective,routes,unserved,unavailable,stats,
        selection_trace=trace,input_fingerprint=data.fingerprint)
    verification_start=perf_counter()
    report=validate_fleet(scenario,result,objective=objective)
    return replace(result,validation=report,
                   planning_stats=replace(stats,validation_seconds=perf_counter()-verification_start))
