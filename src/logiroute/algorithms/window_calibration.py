"""Bounded strict-window construction using real plans and independent verification."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import math
from typing import Any
from logiroute.algorithms.ordering import ordered_strings
from logiroute.dispatch.models import Plan,json_value
from logiroute.dispatch.scenario import State
from logiroute.dispatch.planner import plan_dispatch
from logiroute.dispatch.validation import validate_plan


class WindowGenerationError(ValueError):
    """No verified route-changing complete strict instance within the bounded trials."""
    def __init__(self,attempts: list[dict[str,Any]]) -> None:
        super().__init__('strict window trials exhausted; no verified complete route-changing scenario')
        self.attempts=attempts


def route_structure(plan: Plan) -> dict[str,list[tuple[Any,...]]]:
    """Ignore timestamps; compare real driving, service and manifests. O(actions)."""
    return {r.vehicle:[(a.kind,a.source,a.target,a.ids) for a in r.actions if a.kind!='wait'] for r in plan.routes}


def _services(plan: Plan) -> dict[str,Any]:
    return {oid:a for r in plan.routes for a in r.actions if a.kind=='deliver' for oid in a.ids}


def _routes(plan: Plan) -> list[dict[str,Any]]:
    return [{'vehicle':r.vehicle,'edges':[{'source':a.source,'target':a.target} for a in r.actions if a.kind=='drive'],
             'service_order':[oid for a in r.actions if a.kind=='deliver' for oid in a.ids]} for r in plan.routes]


def calibrate_windows(state: State,policy: dict[str,Any],mode: str) -> State:
    """Construct input only, never substitute routes for the production scheduler.

    Time O(N*N+(1+P*(1+2S))*planner+P*S*(state+N)).
    Space O(state+plans+P*S*N); state includes graph cloning.
    P bounded probes, S configured slack levels. No RNG draws or wall-clock semantics.
    Pseudocode: plan relaxed input; tighten a late customer's deadline; require full
    feasibility; fit appointment windows around that real witness; replan both goals;
    require real structural change and independent rejection of the relaxed plan.
    """
    if mode not in policy['modes']: raise ValueError('unknown window mode')
    numeric=('deadline_advance_minutes','max_window_width_minutes','latest_deadline_minutes','automatic_window_width_minutes')
    values=[policy[k] for k in numeric]+list(policy['appointment_slack_minutes'])
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values): raise ValueError('positive finite window policy values required')
    count=policy['max_probe_orders']
    if isinstance(count,bool) or not isinstance(count,int) or count<1 or not policy['appointment_slack_minutes']: raise ValueError('bounded window trials required')
    if state.protected or any(o.status!='pending' or state.locations[k][0]!='warehouse' for k,o in state.orders.items()): raise ValueError('window construction requires untouched initial orders')
    source=deepcopy(state); baseline=plan_dispatch(source,'distance'); attempts=[]
    if not baseline.report.complete_all: raise WindowGenerationError([{'stage':'relaxed_baseline','report':json_value(baseline.report)}])
    old=_services(baseline); baseline_structure=route_structure(baseline)
    if mode=='relaxed':
        source.config['window_evidence']={'mode':'relaxed','initial_only':True,'initial_time':source.now,'initial_traffic_version':source.traffic_version,'changed_vehicles':[],'baseline_late_orders':[],
                                          'window_min_minutes':min(o.deadline-o.earliest for o in source.orders.values()),'window_max_minutes':max(o.deadline-o.earliest for o in source.orders.values()),'attempts':[]}
        return source
    candidates=ordered_strings(old)
    # Hand insertion by decreasing completion, then explicit ID tie break.
    for i in range(1,len(candidates)):
        key=candidates[i];j=i-1
        while j>=0 and (old[key].end>old[candidates[j]].end or (old[key].end==old[candidates[j]].end and key<candidates[j])):
            candidates[j+1]=candidates[j];j-=1
        candidates[j+1]=key
    for key in candidates[:count]:
        cutoff=old[key].end-policy['deadline_advance_minutes']
        if cutoff<=source.orders[key].earliest:
            attempts.append({'stage':'deadline_probe','order_id':key,'deadline':cutoff,'reason':'nonpositive_window'});continue
        probe=deepcopy(source);probe.orders[key]=replace(probe.orders[key],deadline=cutoff)
        witness=plan_dispatch(probe,'distance')
        attempts.append({'stage':'deadline_probe','order_id':key,'deadline':cutoff,'report':json_value(witness.report),'deferred':list(witness.deferred)})
        if not witness.report.complete_all: continue
        slots=_services(witness)
        for slack in policy['appointment_slack_minutes']:
            trial=deepcopy(probe)
            for oid,a in slots.items():
                earliest=max(source.now,source.orders[oid].earliest,a.start-slack)
                deadline=min(source.orders[oid].deadline,a.end+slack,source.now+policy['latest_deadline_minutes'],cutoff if oid==key else math.inf)
                if deadline<=earliest: break
                trial.orders[oid]=replace(trial.orders[oid],earliest=earliest,deadline=deadline)
            else:
                if any(o.deadline-o.earliest>policy['max_window_width_minutes'] for o in trial.orders.values()):
                    attempts.append({'stage':'appointments','slack':slack,'reason':'window_width_budget'});continue
                strict=plan_dispatch(trial,'distance'); cost=plan_dispatch(trial,'cost')
                attempts.append({'stage':'appointments','slack':slack,'distance_report':json_value(strict.report),'cost_report':json_value(cost.report)})
                if not strict.report.complete_all or not cost.report.complete_all: continue
                new=route_structure(strict);changed=[v for v in ordered_strings(new) if new[v]!=baseline_structure[v]]
                late=[{'order_id':oid,'baseline_end':a.end,'deadline':trial.orders[oid].deadline} for oid,a in old.items() if a.end>trial.orders[oid].deadline]
                baseline_report=validate_plan(trial,replace(baseline,fingerprint=trial.fingerprint()))
                if not changed or not late or baseline_report.valid:
                    attempts.append({'stage':'proof','reason':'no_verified_hard_route_effect'});continue
                actual=_services(strict)
                trial.config['automatic_window_width']=policy['automatic_window_width_minutes']
                trial.config['window_evidence']={
                    'mode':'strict','initial_only':True,'initial_time':source.now,'initial_traffic_version':source.traffic_version,'comparison_objective':'distance',
                    'changed_vehicles':changed,'baseline_late_orders':late,'relaxed_routes':_routes(baseline),
                    'window_min_minutes':min(o.deadline-o.earliest for o in trial.orders.values()),
                    'window_max_minutes':max(o.deadline-o.earliest for o in trial.orders.values()),
                    'minimum_completion_slack_minutes':min(trial.orders[k].deadline-a.end for k,a in actual.items()),
                    'probe_order_id':key,'probe_old_end':old[key].end,'probe_deadline':cutoff,
                    'baseline_replay':json_value(baseline_report),'attempts':deepcopy(attempts),
                    'orders':[{'id':k,'destination':trial.orders[k].destination,'demand':str(trial.orders[k].demand),'priority':trial.orders[k].priority,'earliest':trial.orders[k].earliest,'deadline':trial.orders[k].deadline,
                               'baseline_end':old[k].end,'strict_end':actual[k].end} for k in ordered_strings(trial.orders)]}
                return trial
            attempts.append({'stage':'appointments','slack':slack,'reason':'empty_window'})
    raise WindowGenerationError(attempts)
