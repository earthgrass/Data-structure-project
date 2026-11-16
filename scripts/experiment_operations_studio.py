"""Real immutable parameter comparisons, original campus roads/orders/windows retained."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter
from logiroute.dispatch.studio import studio_state,defaults,trial_session,policy
from logiroute.dispatch.session import Session
from logiroute.dispatch.models import json_value
from logiroute.algorithms.window_calibration import route_structure


def main() -> None:
    """Time O(variants*two real planners+execution); preserve original evidence."""
    target=Path(__file__).resolve().parents[1]/'docs/experiments/operations-studio.json'
    if target.exists():raise ValueError('existing evidence preserved')
    source=Session(studio_state(42,defaults(),'relaxed'));spec=policy();variants=[]
    for label in ('reference','fuel_price_stress','capacity_20kg','insufficient_capacity'):
        c=defaults()
        if label=='fuel_price_stress':c['fuel_price']=spec['presets']['fuel_price_stress']
        if label=='capacity_20kg':c['capacities']={k:('150' if v.role=='trunk' else spec['presets']['delivery_capacity_kg']) for k,v in source.state.vehicles.items()}
        if label=='insufficient_capacity':c['capacities']={k:str(spec['bounds']['capacity'][0]) for k in source.state.vehicles}
        for mode in ('distance','cost'):
            session=trial_session(source,c);before=source.state.fingerprint();started=perf_counter();p=session.prepare(mode);runtime=perf_counter()-started
            assert p.report.valid and p.report.safe_to_apply
            assert [(o.id,o.destination,o.demand,o.earliest,o.deadline) for o in session.state.orders.values()]==[(o.id,o.destination,o.demand,o.earliest,o.deadline) for o in source.state.orders.values()]
            baseline=source.prepare(mode);changed=route_structure(p)!=route_structure(baseline)
            session.apply(p);session.depart()
            while session.running:session.step()
            audit=session.audit();assert audit.valid
            assert source.state.fingerprint()==before
            if label in ('reference','fuel_price_stress','capacity_20kg'):assert audit.complete_all
            else:assert not audit.complete_all
            variants.append({'variant':label,'objective':mode,'parameters':c,'plan':p.to_dict(),'route_structure_changed':changed,
                             'runtime_seconds':runtime,'final_time':session.state.now,'audit':json_value(audit),'metrics':session.snapshot()['studio']})
    strict=Session(studio_state(42,defaults(),'strict'));strict_runs=[]
    for mode in ('distance','cost'):
        s=deepcopy(strict);p=s.prepare(mode);assert p.report.valid and p.report.complete_all;s.apply(p);s.depart()
        while s.running:s.step()
        assert s.audit().complete_all
        strict_runs.append({'objective':mode,'plan':p.to_dict(),'audit':json_value(s.audit()),'metrics':s.snapshot()['studio']})
    target.write_text(json.dumps({'note':'controlled parameter sensitivity, simulated rates; relaxed comparisons preserve same windows; original five-hub profile unchanged','variants':variants,'strict_default':strict_runs},ensure_ascii=False,indent=2),encoding='utf-8')
    print([(r['variant'],r['objective'],r['plan']['total_distance'],r['plan']['total_cost'],len(r['plan']['accepted']),r['route_structure_changed']) for r in variants])


if __name__=='__main__':main()
