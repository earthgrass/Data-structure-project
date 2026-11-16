"""Real HTTP acceptance for planning explanations, impact and signoff timelines.

Usage: python -B scripts/check_planning_insights_live.py [base_url] [new_output.json.gz]
Uses isolated sessions; existing evidence is never overwritten.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.request import Request, urlopen


def run(base: str, output: Path) -> None:
    """Exercise actual API plans and events; O(requests * snapshot size) evidence."""
    if output.exists():
        raise FileExistsError('existing evidence preserved; choose a new filename')
    began = time.perf_counter()
    evidence: dict[str, Any] = {'scope': 'real HTTP; original planner; no mocked responses', 'attempts': []}
    assertions = 0

    def check(value: bool, description: str) -> None:
        nonlocal assertions
        assertions += 1
        if not value:
            raise AssertionError(description)

    def metric(actions: list[dict]) -> dict[str, float]:
        return {key: sum(a[key] for a in actions) for key in ('distance', 'cost', 'travel_time')}

    try:
        for mode in ('strict', 'relaxed'):
            attempt: dict[str, Any] = {'mode': mode, 'requests': [], 'outcome': 'running'}
            evidence['attempts'].append(attempt)

            def post(path: str, body: dict) -> dict:
                start = time.perf_counter()
                entry = {'path': path, 'request': body}
                attempt['requests'].append(entry)
                request = Request(base + path, json.dumps(body).encode(), {'Content-Type': 'application/json'})
                with urlopen(request, timeout=180) as response:
                    result = json.load(response)
                    entry['status'] = response.status
                entry['runtime_seconds'] = time.perf_counter() - start
                entry['snapshot'] = {k: v for k, v in result.items() if k not in ('nodes', 'edges', 'map', 'time_windows')}
                check(entry['status'] == 200, 'successful HTTP response')
                check(result['audit']['valid'], 'independent execution audit valid')
                return result

            snapshot = post('/sessions', {'profile': 'bjut-studio', 'seed': 42, 'window_mode': mode, 'auto_replan': True})

            def command(kind: str, **fields: Any) -> dict:
                nonlocal snapshot
                snapshot = post('/sessions/' + snapshot['id'] + '/commands',
                                {'revision': snapshot['revision'], 'command': kind, **fields})
                return snapshot

            command('plan', objective='distance')
            check(snapshot['planning_insights']['impact'] is None, 'initial plan has no fabricated baseline')
            original = snapshot['plan']
            command('depart')
            command('step')
            check(any(v['current'] and v['current']['kind'] == 'drive' for v in snapshot['vehicles']), 'actually entered a road')
            cargo = [(v['id'], v['load'], v['cargo']) for v in snapshot['vehicles']]
            command('add', id='INSIGHT_URGENT', destination='P27', demand='1', priority='urgent',
                    earliest=snapshot['now'], deadline=snapshot['now'] + 2000)
            check(snapshot['planning_insights']['timeline']['stale'], 'old timeline invalidated during checkpoint drain')
            check(all(r['expected'] is None for r in snapshot['planning_insights']['timeline']['orders']), 'no stale ETA advertised')
            drain_steps = 0
            while snapshot['running']:
                check(drain_steps < len(snapshot['vehicles']), 'only entered actions drain')
                command('step')
                drain_steps += 1
            check(cargo == [(v['id'], v['load'], v['cargo']) for v in snapshot['vehicles']], 'entered road completion preserves exact cargo')
            info = snapshot['planning_insights']
            impact = info['impact']
            check(impact['at'] == snapshot['now'], 'same checkpoint comparison')
            completed = [e['action'] for e in snapshot['events'] if e['kind'] == 'action']
            old_actions = [a for r in original['routes'] for a in r['actions'] if a not in completed]
            new_actions = [a for r in snapshot['plan']['routes'] for a in r['actions']]
            before, after = metric(old_actions), metric(new_actions)
            for name in before:
                check(abs(impact['before'][name] - before[name]) < 1e-9, 'independently summed old remaining ' + name)
                check(abs(impact['after'][name] - after[name]) < 1e-9, 'independently summed new remaining ' + name)
                check(abs(impact['delta'][name] - (after[name] - before[name])) < 1e-9, 'independent delta ' + name)
            for row in info['timeline']['orders']:
                expected = row['expected']
                if expected is not None:
                    action = next(a for a in new_actions if a['kind'] == 'deliver' and row['order_id'] in a['ids'])
                    check(expected['signoff'] == action['end'], 'predicted signoff from real service action')
                    check(expected['slack'] == row['deadline'] - action['end'], 'exact time slack')
                    check(row['actual'] is None, 'planned is not physically delivered')
            attempt['accepted_urgent'] = 'INSIGHT_URGENT' in snapshot['plan']['accepted']
            attempt['impact_after_add'] = impact
            attempt['explanations_after_add'] = info['explanations']
            if not attempt['accepted_urgent']:
                detail = next(x for x in info['explanations']['items'] if x['order_id'] == 'INSIGHT_URGENT')
                check(detail['scope'] == 'heuristic_candidate' and bool(detail['attempts']), 'real refusal candidate evidence')
                for failure in detail['attempts']:
                    if failure['code'] == 'completion_deadline':
                        check(failure['service_end'] > failure['deadline'], 'witness actually exceeds completion deadline')
                        check(bool(failure['order_ids']), 'blocking order identity is preserved')
            command('cancel', id='INSIGHT_URGENT')
            cancelled = next(r for r in snapshot['planning_insights']['timeline']['orders'] if r['order_id'] == 'INSIGHT_URGENT')
            check(cancelled['status'] == 'cancelled' and cancelled['expected'] is None and cancelled['actual'] is None, 'cancelled identity retained without fabricated timing')
            frozen = snapshot['planning_insights']['impact']
            command('depart')
            steps = 0
            action_bound = sum(len(r['actions']) for r in snapshot['plan']['routes'])
            while not any(r['actual'] for r in snapshot['planning_insights']['timeline']['orders']):
                check(snapshot['running'] and steps < action_bound, 'first real signoff reachable')
                command('step')
                steps += 1
            check(snapshot['planning_insights']['impact'] == frozen, 'normal execution cannot change replan deltas')
            for row in snapshot['planning_insights']['timeline']['orders']:
                if row['actual'] is not None:
                    action = next(e['action'] for e in snapshot['events'] if e['kind'] == 'action'
                                  and e['action']['kind'] == 'deliver' and row['order_id'] in e['action']['ids'])
                    check(row['actual']['signoff'] == action['end'], 'actual signoff is backed by completed event')
            attempt['steps_to_first_actual_signoff'] = steps
            attempt['outcome'] = 'passed'
        evidence['passed'] = True
    except Exception as exc:
        evidence['passed'] = False
        evidence['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        evidence['assertions'] = assertions
        evidence['runtime_seconds'] = time.perf_counter() - began
        raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        payload = gzip.compress(raw, mtime=0) if output.suffix == '.gz' else raw
        with output.open('xb') as stream:
            stream.write(payload)
        print(json.dumps({'output': str(output), 'passed': evidence.get('passed'), 'assertions': assertions,
                          'runtime_seconds': evidence['runtime_seconds']}, ensure_ascii=False))


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    run(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8001/api/v2',
        root / 'docs/experiments' / (sys.argv[2] if len(sys.argv) > 2 else 'planning-insights-live.json.gz'))
