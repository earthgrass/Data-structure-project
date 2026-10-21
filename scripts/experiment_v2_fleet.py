"""Measured Phase 3 research experiments; does not alter production generation."""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from logiroute.config import load_scenario
from logiroute.config.loader import ScenarioBundle
from logiroute.core import Vehicle,Courier
from logiroute.scenario_generator import generate_scenario,GeneratorConfig
from logiroute.scheduling import plan_fleet
from logiroute.scheduling.fleet_paths import fingerprint_scenario
from scripts.fleet_reference import capacity_counterexample,enumerate_fleet


def load_settings() -> dict[str,Any]:
    return json.loads((ROOT/'config/fleet_experiments.json').read_text(encoding='utf-8'))


def experiment_input(settings: dict[str,Any], seed: int, orders: int, vehicles: int) -> ScenarioBundle:
    """Derived research fixture: original generator stays strictly single-car."""
    original,_=generate_scenario(GeneratorConfig(**settings['generator'],orders_count=orders),seed=seed)
    rows=settings['vehicles'][:vehicles]
    return replace(original,
        vehicles=[Vehicle(row['id'],row['capacity'],current_node_id=row['current_node_id']) for row in rows],
        couriers=[Courier(row['courier_id'],row['courier_id'],row['id']) for row in rows],
        metadata={**original.metadata,'derived_fleet_research_fixture':True})


def cross_process_replay() -> dict[str,Any]:
    """Five seeds × both modes in each of three distinct Python hash processes."""
    child='''
import json
from scripts.experiment_v2_fleet import load_settings,experiment_input
from logiroute.scheduling import plan_fleet
s=load_settings(); rows=[]
for seed in s['seeds']:
 raw=experiment_input(s,seed,5,2)
 for objective in s['objectives']:
  result=plan_fleet(raw,objective).to_dict()
  result['planning_stats'].pop('runtime_seconds')
  result['planning_stats'].pop('validation_seconds')
  rows.append(result)
print(json.dumps(rows,ensure_ascii=True,separators=(',',':'),allow_nan=False))
'''
    digests=[]
    hash_seeds=('1','2','73')
    start=perf_counter()
    for value in hash_seeds:
        env=dict(os.environ)
        env.update(PYTHONHASHSEED=value,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT))
        completed=subprocess.run([sys.executable,'-B','-c',child],cwd=ROOT,env=env,
                                  capture_output=True,text=True,encoding='utf-8',timeout=120,check=True)
        payload=json.loads(completed.stdout)
        if len(payload)!=10 or any(row['status']=='invalid' for row in payload):
            raise AssertionError('cross-process experiment returned invalid/incomplete evidence')
        encoded=json.dumps(payload,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        digests.append(hashlib.sha256(encoded).hexdigest())
    identical=len(set(digests))==1
    if not identical: raise AssertionError('fleet results changed across Python hash processes')
    return {'hash_seeds':hash_seeds,'sha256':digests,'identical':identical,
            'scenarios_per_process':10,'runtime_seconds':perf_counter()-start}


def _measured(raw: ScenarioBundle, objective: str) -> dict[str,Any]:
    before=fingerprint_scenario(raw)
    start=perf_counter(); result=plan_fleet(raw,objective); elapsed=perf_counter()-start
    if fingerprint_scenario(raw)!=before or result.input_fingerprint!=before:
        raise AssertionError('comparison inputs changed')
    if not result.validation.valid: raise AssertionError(result.validation.violations)
    return {'input_fingerprint':before,'served_orders':sum(len(r.services) for r in result.routes),
            'unserved_orders':len(result.unserved_orders),'total_call_seconds':elapsed,
            'result':result.to_dict()}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    settings=load_settings(); matrix=[]
    for seed in settings['seeds']:
        for orders in settings['order_counts']:
            for vehicles in settings['vehicle_counts']:
                raw=experiment_input(settings,seed,orders,vehicles)
                for objective in settings['objectives']:
                    measured=_measured(raw,objective)
                    matrix.append({'seed':seed,'orders':orders,'vehicles':vehicles,'objective':objective,
                        'nodes':raw.graph.node_count,'directed_edges':raw.graph.edge_count,
                        'physical_roads':raw.metadata['road_network']['physical_road_count'],
                        'bidirectional_ratio':raw.metadata['road_network']['bidirectional_ratio'],**measured})
    fixed=load_scenario(ROOT/'config/scenario_fleet.json')
    fixed_results={objective:_measured(fixed,objective) for objective in settings['objectives']}
    counter=capacity_counterexample(); counter_results={}
    for objective in settings['objectives']:
        start=perf_counter(); exact=enumerate_fleet(counter,objective); elapsed=perf_counter()-start
        counter_results[objective]={'exhaustive':exact,'exhaustive_seconds':elapsed,
                                    'greedy':_measured(counter,objective)}
    summary={}
    for objective in settings['objectives']:
        rows=[row for row in matrix if row['objective']==objective]
        summary[objective]={'runs':len(rows),
            'complete':sum(row['result']['status']=='complete' for row in rows),
            'partial':sum(row['result']['status']=='partial' for row in rows),
            'valid':sum(row['result']['validation']['valid'] for row in rows),
            'served':sum(row['served_orders'] for row in rows),
            'submitted':sum(row['orders'] for row in rows),
            'planning_seconds':sum(row['result']['planning_stats']['runtime_seconds'] for row in rows),
            'validation_seconds':sum(row['result']['planning_stats']['validation_seconds'] for row in rows)}
    names=[str(path.relative_to(ROOT)).replace('\\','/') for path in (ROOT/'src/logiroute/scheduling').glob('fleet_*.py')]
    names.extend(['src/logiroute/scheduling/algorithms/fleet_insertion.py',
                  'src/logiroute/scheduling/algorithms/fleet_greedy.py',
                  'src/logiroute/scheduling/planner.py','scripts/fleet_reference.py',
                  'scripts/experiment_v2_fleet.py','config/fleet_experiments.json'])
    evidence={'matrix':matrix,'summary':summary,'fixed_fleet':fixed_results,
              'capacity_counterexample':counter_results,'cross_process':cross_process_replay(),
              'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names},
              'limitations':['derived research fixtures, not production multi-car generation',
                             'canonical primary paths; heuristic incomplete is not proof of infeasibility']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'summary':summary,'cross_process':evidence['cross_process'],
                      'output_bytes':args.output.stat().st_size},ensure_ascii=True))


if __name__=='__main__':
    main()
