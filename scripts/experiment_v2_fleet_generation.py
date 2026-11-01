"""Measured Phase 4 acceptance/rejection evidence; refuses to overwrite artifacts."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from logiroute.scenario_generator import (
    FleetGeneratorConfig, FleetGenerationError, generate_fleet_scenario, load_fleet_generator_config,
)
from logiroute.scenario_generator.fleet_generator import _scenario_dict
from logiroute.scenario_generator.fleet_witness import construct_candidate
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.scheduling import plan_fleet
from logiroute.scheduling.fleet_validator import validate_fleet


def settings() -> dict[str, Any]:
    return json.loads((ROOT/'config/fleet_generation_experiments.json').read_text(encoding='utf-8'))


def profile_config(config: FleetGeneratorConfig, profile: dict[str, Any]) -> FleetGeneratorConfig:
    values = {k: v for k, v in profile.items()
              if k not in ('name', 'seed', 'vehicle_count', 'capacity')}
    vehicles = config.vehicles[:profile['vehicle_count']]
    if 'capacity' in profile:
        vehicles = tuple(replace(v, capacity=Decimal(str(profile['capacity']))) for v in vehicles)
    if 'demand_choices' in values:
        values['demand_choices'] = tuple(Decimal(str(v)) for v in values['demand_choices'])
    return replace(config, vehicles=vehicles, **values)


def replay_payload() -> list[dict[str, Any]]:
    """Full deterministic snapshots, including a real multi-attempt acceptance."""
    cfg = load_fleet_generator_config(ROOT/'config/fleet_generator.json')
    spec = settings()
    rows = [generate_fleet_scenario(cfg, seed=seed).to_dict(include_timing=False)
            for seed in spec['seeds']]
    tight = spec['profiles'][0]
    rows.append(generate_fleet_scenario(profile_config(cfg, tight), seed=tight['seed'])
                .to_dict(include_timing=False))
    return rows


def cross_process_replay() -> dict[str, Any]:
    digests = []
    start = perf_counter()
    for value in settings()['hash_seeds']:
        env = dict(os.environ, PYTHONHASHSEED=value, PYTHONPATH=str(ROOT/'src'),
                   PYTHONDONTWRITEBYTECODE='1')
        command = [sys.executable, '-B', '-c',
                   'import json; from scripts.experiment_v2_fleet_generation import replay_payload; '
                   'print(json.dumps(replay_payload(),ensure_ascii=True,separators=(",",":"),allow_nan=False))']
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                   text=True, encoding='utf-8', timeout=180, check=True)
        rows = json.loads(completed.stdout)
        if len(rows) != len(settings()['seeds'])+1:
            raise AssertionError('missing cross-process scenarios')
        digests.append(hashlib.sha256(completed.stdout.encode('utf-8')).hexdigest())
    if len(set(digests)) != 1:
        raise AssertionError('cross-process scenario/route/history mismatch')
    return dict(hash_seeds=settings()['hash_seeds'], sha256=digests, identical=True,
                scenarios_per_process=len(settings()['seeds'])+1,
                runtime_seconds=perf_counter()-start)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refusing to overwrite experiment evidence; choose a new path')
    cfg = load_fleet_generator_config(ROOT/'config/fleet_generator.json')
    spec = settings()
    matrix = []
    start = perf_counter()
    for seed in spec['seeds']:
        for count in spec['order_counts']:
            for fleet in spec['vehicle_counts']:
                case = replace(cfg, orders_count=count, vehicles=cfg.vehicles[:fleet])
                try:
                    result = generate_fleet_scenario(case, seed=seed)
                    matrix.append(dict(seed=seed, orders=count, vehicles=fleet, accepted=True,
                                       evidence=result.to_dict()))
                except FleetGenerationError as error:
                    matrix.append(dict(seed=seed, orders=count, vehicles=fleet, accepted=False,
                                       evidence=error.to_dict()))
    profiles = []
    for profile in spec['profiles']:
        case = profile_config(cfg, profile)
        try:
            result = generate_fleet_scenario(case, seed=profile['seed'])
            profiles.append(dict(name=profile['name'], accepted=True,
                                 config=case.to_dict(), evidence=result.to_dict()))
        except FleetGenerationError as error:
            profiles.append(dict(name=profile['name'], accepted=False,
                                 config=case.to_dict(), evidence=error.to_dict()))
    # Replay every failed tight-window candidate and keep its real partial routes.
    tight = spec['profiles'][0]
    case = profile_config(cfg, tight)
    rng = RandomSource(tight['seed'])
    candidate_replays = []
    accepted_attempt = len(profiles[0]['evidence']['attempts'])
    for number in range(1, accepted_attempt+1):
        bundle, witnesses, stage, reasons = construct_candidate(case, rng, tight['seed'], number)
        row = dict(number=number, stage=stage, reasons=list(reasons))
        if witnesses:
            row['scenario'] = _scenario_dict(bundle)
            row['witness_reports'] = [validate_fleet(bundle, w).to_dict() for w in witnesses]
            answers = [plan_fleet(bundle, objective) for objective in ('distance', 'cost')]
            row['actual_plans'] = [a.to_dict() for a in answers]
            row['independent_reports'] = [validate_fleet(bundle, a).to_dict() for a in answers]
        candidate_replays.append(row)
    attempts = [a for row in matrix for a in row['evidence']['attempts']]
    reasons: dict[str, int] = {}
    for attempt in attempts:
        reasons[attempt['stage']] = reasons.get(attempt['stage'], 0)+1
    names = ['src/logiroute/scenario_generator/fleet_config.py',
             'src/logiroute/scenario_generator/fleet_generator.py',
             'src/logiroute/scenario_generator/fleet_witness.py',
             'src/logiroute/scenario_generator/graph_sampler.py',
             'src/logiroute/scenario_generator/config_spec.py',
             'src/logiroute/scheduling/fleet_planner.py',
             'src/logiroute/scheduling/fleet_validator.py',
             'src/logiroute/scheduling/algorithms/fleet_greedy.py',
             'src/logiroute/scheduling/algorithms/fleet_insertion.py',
             'config/fleet_generator.json', 'config/fleet_generation_experiments.json',
             'scripts/experiment_v2_fleet_generation.py']
    evidence = dict(config=cfg.to_dict(), matrix=matrix, profiles=profiles,
                    tight_candidate_replays=candidate_replays,
                    cross_process=cross_process_replay(),
                    summary=dict(requested=len(matrix), accepted=sum(r['accepted'] for r in matrix),
                                 rejected=sum(not r['accepted'] for r in matrix),
                                 attempts=len(attempts), stages=reasons),
                    runtime_seconds=perf_counter()-start,
                    source_sha256={n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(summary=evidence['summary'], cross_process=evidence['cross_process'],
                          runtime_seconds=evidence['runtime_seconds']), ensure_ascii=True))


if __name__ == '__main__':
    main()
