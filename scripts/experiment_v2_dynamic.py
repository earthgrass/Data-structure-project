"""Real event-driven dynamic experiments, with complete histories and no overwrite."""
from __future__ import annotations
import argparse
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from logiroute.dynamic.config import load_dynamic_config
from logiroute.dynamic.session import DynamicSession
from logiroute.scenario_generator import load_fleet_generator_config,generate_fleet_scenario,FleetGenerationResult
from logiroute.config.loader import ScenarioBundle


def settings() -> dict[str,Any]:
    return json.loads((ROOT/'config/dynamic_experiments.json').read_text(encoding='utf-8'),parse_float=Decimal)


def _record(session: DynamicSession, label: str) -> dict[str,Any]:
    report=session.validate()
    if not report.valid: raise AssertionError(report.violations)
    return dict(label=label,snapshot=session.snapshot().to_dict(),valid=report.valid)


def _drain(session: DynamicSession) -> None:
    while session.step() is not None:
        report=session.validate()
        if not report.valid: raise AssertionError(report.violations)


def run_case(seed: int, objective: str, generated: FleetGenerationResult | None = None) -> dict[str,Any]:
    spec=settings()
    cfg=replace(load_fleet_generator_config(ROOT/'config/fleet_generator.json'),orders_count=spec['orders_count'])
    if generated is None: generated=generate_fleet_scenario(cfg,seed=seed)
    tick=perf_counter()
    dynamic=load_dynamic_config(ROOT/'config/dynamic_orders.json')
    dynamic=replace(dynamic,automatic=replace(dynamic.automatic,
                    window_width_range=tuple(spec['automatic_window_width_range'])))
    session=DynamicSession(generated.scenario,dynamic); frames=[_record(session,'initial')]
    first=session.replan(objective)
    if first.status!='applied': raise AssertionError('initial plan failed')
    frames.append(_record(session,'planned'))
    session.depart(); session.step()
    now=session.snapshot().time
    manual=session.submit_manual(generated.scenario.orders[0].destination_id,
                                  spec['manual_demand'],now,now+spec['manual_window_width'])
    automatic=session.submit_automatic(seed=seed)
    deferred=session.replan(objective)
    if deferred.status!='deferred': raise AssertionError('unsafe replan was not deferred')
    frames.append(_record(session,'queued_while_running'))
    _drain(session); frames.append(_record(session,'first_trip_complete'))
    if session.replan(objective).status!='applied': raise AssertionError('second wave failed')
    second_ids={s.order_id for r in session.snapshot().plan.routes for s in r.services}
    if second_ids!={manual.order_id,automatic.order_id}: raise AssertionError('completed tasks reintroduced')
    frames.append(_record(session,'second_plan'))
    session.depart(); _drain(session); frames.append(_record(session,'complete'))
    final=session.snapshot()
    if any(o.status.value!='delivered' for o in final.orders): raise AssertionError('incomplete dynamic case')
    return dict(seed=seed,objective=objective,config=dynamic.to_dict(),
                initial_scene=generated.to_dict(include_timing=False)['scenario'],frames=frames,
                submitted=len(final.orders),delivered=sum(o.status.value=='delivered' for o in final.orders),
                runtime_seconds=perf_counter()-tick)


def _rollback_source() -> ScenarioBundle:
    spec=settings(); p=spec['rollback']
    cfg=load_fleet_generator_config(ROOT/'config/fleet_generator.json')
    cfg=replace(cfg,orders_count=p['orders_count'],vehicles=(replace(cfg.vehicles[0],capacity=Decimal(p['capacity'])),),
                demand_choices=(Decimal(p['demand']),))
    return generate_fleet_scenario(cfg,seed=p['seed']).scenario


def rollback_case(objective: str, original: ScenarioBundle | None = None) -> dict[str,Any]:
    spec=settings(); p=spec['rollback']
    if original is None: original=_rollback_source()
    tick=perf_counter()
    session=DynamicSession(original,load_dynamic_config(ROOT/'config/dynamic_orders.json'))
    session.replan(objective); old=session.snapshot().plan
    now=session.snapshot().time
    receipt=session.submit_manual(original.orders[0].destination_id,Decimal(p['demand']),
                                   now,now+spec['manual_window_width'])
    failed=session.replan(objective)
    if failed.status!='incomplete' or session.snapshot().plan!=old:
        raise AssertionError('failed replan overwrote the valid plan')
    frames=[_record(session,'incomplete_plan_retained')]
    session.depart(); _drain(session); frames.append(_record(session,'original_delivered'))
    if session.replan(objective).status!='applied': raise AssertionError('pending order lost')
    session.depart(); _drain(session); frames.append(_record(session,'new_order_delivered'))
    return dict(objective=objective,pending_id=receipt.order_id,failed_result=failed.result.to_dict(),
                frames=frames,runtime_seconds=perf_counter()-tick)


def stable(value: Any) -> Any:
    """Only remove measured clock fields from exact full-state replay evidence."""
    if isinstance(value,dict):
        return {k:stable(v) for k,v in value.items() if k not in ('runtime_seconds','validation_seconds')}
    if isinstance(value,list): return [stable(v) for v in value]
    return value


def replay_payload() -> dict[str,Any]:
    matrix,rollback=_shared_inputs()
    return stable(dict(matrix=matrix,rollback=rollback))


def _shared_inputs() -> tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    """Both modes use the SAME initial object; sessions isolate their mutable state."""
    spec=settings(); matrix=[]
    cfg=replace(load_fleet_generator_config(ROOT/'config/fleet_generator.json'),orders_count=spec['orders_count'])
    for seed in spec['seeds']:
        generated=generate_fleet_scenario(cfg,seed=seed)
        for mode in spec['objectives']: matrix.append(run_case(seed,mode,generated))
    original=_rollback_source()
    return matrix,[rollback_case(mode,original) for mode in spec['objectives']]


def cross_process_replay() -> dict[str,Any]:
    digests=[]; tick=perf_counter()
    for seed in settings()['hash_seeds']:
        env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1')
        command=[sys.executable,'-B','-c','import json; from scripts.experiment_v2_dynamic import replay_payload; '
                 'print(json.dumps(replay_payload(),ensure_ascii=True,separators=(",",":"),allow_nan=False))']
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=180,check=True)
        payload=json.loads(result.stdout)
        if len(payload['matrix'])!=len(settings()['seeds'])*len(settings()['objectives']):
            raise AssertionError('missing process cases')
        digests.append(hashlib.sha256(result.stdout.encode()).hexdigest())
    if len(set(digests))!=1: raise AssertionError('dynamic histories differ across hash processes')
    return dict(hash_seeds=settings()['hash_seeds'],sha256=digests,identical=True,runtime_seconds=perf_counter()-tick)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('refusing to overwrite existing evidence')
    tick=perf_counter(); spec=settings()
    matrix,rollback=_shared_inputs()
    names=[str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'src/logiroute/dynamic').glob('*.py')]
    names+=['src/logiroute/scheduling/algorithms/dynamic_execution.py','src/logiroute/algorithms/order_queue.py',
            'config/dynamic_orders.json','config/dynamic_experiments.json','scripts/experiment_v2_dynamic.py']
    data=dict(matrix=matrix,rollback=rollback,cross_process=cross_process_replay(),
              summary=dict(sessions=len(matrix),submitted=sum(r['submitted'] for r in matrix),
                           delivered=sum(r['delivered'] for r in matrix)),
              runtime_seconds=perf_counter()-tick,
              source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps(dict(summary=data['summary'],cross_process=data['cross_process'],runtime_seconds=data['runtime_seconds'])))


if __name__=='__main__': main()
