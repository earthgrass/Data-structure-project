"""Bounded deterministic candidate generation with real dual-objective acceptance."""
from __future__ import annotations
from time import perf_counter
from typing import Any
from logiroute.dispatch.scenario import State,load_config,make_state
from logiroute.dispatch.planner import plan_dispatch


class GenerationError(ValueError):
    def __init__(self,attempts: list[dict[str,Any]]) -> None:
        super().__init__('bounded generation exhausted; no dual-objective complete plan found')
        self.attempts=attempts


def generate_state(seed: int,config: dict[str,Any] | None = None,*,window_mode: str | None = None) -> tuple[State,list[dict[str,Any]]]:
    """Return only after both real plans independently pass. O(attempts*planner)."""
    if isinstance(seed,bool) or not isinstance(seed,int): raise ValueError('integer seed required')
    c=load_config() if config is None else config; attempts=[]
    if window_mode is not None and not c.get('time_window_policy_file'): raise ValueError('window modes require an explicit policy')
    limit=c['max_generation_attempts']
    if isinstance(limit,bool) or not isinstance(limit,int) or limit<1: raise ValueError('positive attempt limit required')
    for index in range(limit):
        started=perf_counter(); state=make_state(seed+index,c); rows=[]
        if c.get('time_window_policy_file'):
            from logiroute.dispatch.time_windows import calibrate_windows,load_window_policy,WindowGenerationError
            policy=load_window_policy(c)
            try: state=calibrate_windows(state,policy,policy['default_mode'] if window_mode is None else window_mode)
            except WindowGenerationError as exc:
                attempts.append({'base_seed':seed,'seed':seed+index,'attempt':index+1,'window_attempts':exc.attempts,'runtime_seconds':perf_counter()-started})
                # Keep orders/seed fixed; never silently resample to make the comparison pass.
                raise GenerationError(attempts) from exc
        for objective in ('distance','cost'):
            plan=plan_dispatch(state,objective)
            rows.append({'objective':objective,'report':plan.to_dict()['report'],'accepted':len(plan.accepted),
                         'deferred':plan.to_dict()['deferred'],'distance':sum(r.total_distance for r in plan.routes),'cost':sum(r.total_cost for r in plan.routes)})
        attempts.append({'base_seed':seed,'seed':seed+index,'attempt':index+1,'fingerprint':state.fingerprint(),'plans':rows,'runtime_seconds':perf_counter()-started})
        if all(r['report']['complete_all'] for r in rows): return state,attempts
    raise GenerationError(attempts)
