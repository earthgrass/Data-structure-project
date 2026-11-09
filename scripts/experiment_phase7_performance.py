"""Real current-system measurements; invalid scales explicitly refused."""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from time import perf_counter
from typing import Any,Callable
from logiroute.dispatch.real_map import map_config
from logiroute.dispatch.scenario import make_state
from logiroute.dispatch.generation import generate_state,GenerationError
from logiroute.dispatch.time_windows import calibrate_windows,load_window_policy
from logiroute.dispatch.session import Session
from logiroute.dispatch.validation import validate_plan
from logiroute.dispatch.models import json_value


def measure(fn: Callable[[],Any]) -> tuple[Any,float]:
    """Monotonic measurement, no synthetic delays or retries."""
    start=perf_counter();value=fn();return value,perf_counter()-start


def main() -> None:
    """Time dominated by real planners. Space O(states+raw plans+events)."""
    root=Path(__file__).resolve().parents[1];target=root/'docs/experiments/phase7-performance.json'
    if target.exists():raise ValueError('existing evidence preserved')
    policy=json.loads((root/'config/phase7-experiments.json').read_text(encoding='utf-8'));rows=[]
    for count in policy['performance_counts']:
        c=map_config('bjut-campus');c['orders_count']=count;c['destination_quotas']={'campus':count*5//6,'surrounding':count//6}
        start=perf_counter()
        try:(state,attempts),elapsed=measure(lambda:generate_state(policy['seed'],c))
        except (ValueError,GenerationError) as exc:
            rows.append({'orders':count,'accepted_scale':False,'runtime_seconds':perf_counter()-start,'reason':str(exc),'attempts':getattr(exc,'attempts',[])});continue
        session=Session(state);plans=[]
        for mode in ('distance','cost'):
            p,seconds=measure(lambda:session.prepare(mode));validation,vtime=measure(lambda:validate_plan(state,p))
            assert validation.valid and validation.complete_all
            plans.append({'objective':mode,'planning_seconds':seconds,'validation_seconds':vtime,'report':json_value(validation),'plan':p.to_dict()})
        snapshot,stime=measure(session.snapshot);encoded,etime=measure(lambda:json.dumps(snapshot,ensure_ascii=False,separators=(',',':')).encode())
        p=session.prepare('distance');session.apply(p);session.depart();session.pause()
        steps=[]
        while session.running:_,seconds=measure(session.step);steps.append(seconds)
        preserved={k:list(loc) for k,loc in session.state.locations.items()}
        _,addtime=measure(lambda:session.add_order(policy['dynamic_id'],next(iter(state.orders.values())).destination,Decimal(policy['dynamic_demand']),session.state.now,session.state.now+policy['dynamic_window_minutes'],'critical'))
        proposal,replan_time=measure(lambda:session.prepare('distance'))
        if proposal.report.safe_to_apply:
            session.apply(proposal);session.depart()
            while session.running:session.step()
        audit,atime=measure(session.audit)
        rows.append({'orders':count,'accepted_scale':True,'generation_seconds':elapsed,'generation_attempts':attempts,'plans':plans,'snapshot_seconds':stime,'json_encoding_seconds':etime,'json_bytes':len(encoded),
                     'checkpoint_steps_seconds':steps,'add_seconds':addtime,'replan_seconds':replan_time,'cargo_at_checkpoint':preserved,'replan_report':json_value(proposal.report),'replan_deferred':list(proposal.deferred),
                     'audit_seconds':atime,'audit':json_value(audit)})
    c=map_config('bjut-campus');raw,_=measure(lambda:make_state(policy['seed'],c));strict,construction=measure(lambda:calibrate_windows(raw,load_window_policy(c),'strict'))
    data={'measurement':'one real run per scale; wall seconds; no general performance guarantee','runs':rows,'strict_window_construction_seconds':construction,'strict_input_fingerprint':strict.fingerprint()}
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print([(r['orders'],r['accepted_scale'],r.get('generation_seconds'),r.get('reason'),r.get('replan_report')) for r in rows]);print('strict construction',construction)


if __name__=='__main__':main()
