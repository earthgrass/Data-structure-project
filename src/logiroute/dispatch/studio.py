"""Explicit parameter experiments; unchanged production planner and immutable old sessions."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal,InvalidOperation
import json
from pathlib import Path
from typing import Any
from logiroute.core import Edge
from logiroute.dispatch.scenario import State,make_state
from logiroute.dispatch.real_map import map_config
from logiroute.dispatch.session import Session,ConflictError
from logiroute.dispatch.time_windows import calibrate_windows,load_window_policy


def policy() -> dict[str,Any]:
    """Time/Space O(JSON bytes)."""
    return json.loads((Path(__file__).resolve().parents[3]/'config/operations_studio.json').read_text(encoding='utf-8'))


def defaults() -> dict[str,Any]:
    """Fresh user editable parameters; Time/Space O(JSON bytes)."""
    return deepcopy(policy()['default'])


def _number(value: Any,limits: list[float]) -> Decimal:
    if isinstance(value,bool) or not isinstance(value,(str,int,float,Decimal)):raise ValueError('numeric parameter required')
    try:q=Decimal(str(value))
    except InvalidOperation as exc:raise ValueError('invalid numeric parameter') from exc
    if not q.is_finite() or q<Decimal(str(limits[0])) or q>Decimal(str(limits[1])):raise ValueError('parameter outside configured range')
    return q


def configure(state: State,parameters: dict[str,Any]) -> State:
    """Copy and reweight from distance/time, never old cost. Time/Space O(V+E+N).

    Capacity uses original Decimal quantities. Road economics are shared fleet
    reference rates, not per-vehicle or load-dependent shortest-path claims.
    """
    p=policy();base=map_config('bjut-campus');expected=set(p['default'])
    if not isinstance(parameters,dict) or set(parameters)!=expected:raise ValueError('complete known parameter fields required')
    hubs=parameters['hub_ids'];caps=parameters['capacities'];known={v['id'] for v in base['vehicles']}
    if not isinstance(hubs,list) or any(not isinstance(h,str) for h in hubs) or len(hubs)!=len(set(hubs)) or len(hubs)<p['minimum_hubs'] or any(h not in base['hub_ids'] for h in hubs):raise ValueError('at least three distinct known hubs required')
    if not isinstance(caps,dict) or set(caps)-known:raise ValueError('unknown vehicle capacities')
    numeric={k:_number(parameters[k],p['bounds'][k]) for k in ('fuel_per_100km','fuel_price','driver_hourly','maintenance_per_km')}
    capacity={k:_number(v,p['bounds']['capacity']) for k,v in caps.items()}
    trial=deepcopy(state);trial.config.pop('window_evidence',None)
    rows=[v for v in base['vehicles'] if v['role']=='trunk' or v['base'] in hubs]
    from logiroute.dispatch.models import VehicleSpec
    trial.vehicles={v['id']:VehicleSpec(**{**v,'capacity':capacity.get(v['id'],Decimal(str(v['capacity'])))}) for v in rows}
    trial.positions={k:v.base for k,v in trial.vehicles.items()};trial.config['vehicles']=[{**v,'capacity':str(trial.vehicles[v['id']].capacity)} for v in rows]
    trial.config['hub_ids']=list(hubs);trial.config['traffic']['cost_per_delay']=float(numeric['driver_hourly']/60)
    factors=trial.config.get('road_fuel_factors',p['road_factors'])
    speeds=trial.config.get('road_speed_kmh',{})
    for e in list(trial.graph.edges):
        kind=e.metadata.get('highway');factor=factors.get(kind,factors['default'])
        base_time=e.metadata.get('base_travel_time',e.travel_time)
        speed=speeds.get(kind)
        travel_time=base_time
        if speed and base_time>0 and abs(e.distance/base_time*60-float(speed['baseline']))<0.000001:
            travel_time=e.distance/float(speed['operational'])*60
        fuel=e.distance*float(numeric['fuel_per_100km'])/100*factor
        cost=fuel*float(numeric['fuel_price'])+travel_time/60*float(numeric['driver_hourly'])+e.distance*float(numeric['maintenance_per_km'])
        metadata={**e.metadata,'fuel_liters':fuel}
        if speeds: metadata['base_travel_time']=base_time
        trial.graph.remove_edge(*e.key);trial.graph.add_edge(Edge(*e.key,e.distance,travel_time,cost,e.traffic_status,metadata))
    normalized={**parameters,**{k:str(v) for k,v in numeric.items()},'capacities':{k:str(v.capacity) for k,v in trial.vehicles.items()}}
    note=p['model_note']+(' '+trial.config['road_model_note'] if 'road_model_note' in trial.config else '')
    trial.config['studio']={'variant':trial.config.get('scenario_variant','legacy'),'parameters':normalized,'model_note':note,'official_map_url':p['official_map_url'],
                            'available_hubs':[{'id':h,'name':trial.graph.get_node(h).name} for h in base['hub_ids']]}
    trial.graph.validate();return trial


def studio_state(seed: int,parameters: dict[str,Any],window_mode: str = 'strict',operational: bool = False) -> State:
    """Explicit opt-in profile. Time bounded window construction; space O(state+plans)."""
    c=map_config('bjut-campus')
    if operational:
        c.update(json.loads((Path(__file__).resolve().parents[3]/'config/dispatch_bjut_operational.json').read_text(encoding='utf-8')))
    s=configure(make_state(seed,c),parameters)
    return calibrate_windows(s,load_window_policy(c),window_mode)


def trial_session(original: Session,parameters: dict[str,Any]) -> Session:
    """New initial session only; never reset entered cargo/history. O(copy+V+E+N)."""
    s=original.state
    if original.running or s.now!=s.config['timing']['initial'] or s.traffic_version or any(e['kind']=='action' for e in original.events) or any(loc[0]!='warehouse' for loc in s.locations.values()) or any(o.status not in ('pending','planned') for o in s.orders.values()):
        raise ConflictError('parameter experiments require a fresh unexecuted warehouse scene; create a new scene')
    state=configure(s,parameters);state.protected.clear();state.revision=0
    state.orders={k:replace(o,status='pending' if o.status=='planned' else o.status,hub='') for k,o in state.orders.items()}
    return Session(state)


def metrics(session: Session) -> dict[str,Any]:
    """JSON-only indicators from actual plan/actions, O(A+N); no scheduling."""
    p=session.state.config['studio'];rates=p['parameters'];plan=session.plan;settings=policy();late_penalty=settings['late_penalty_per_order']
    def summary(actions: list[Any]) -> dict[str,float]:
        drives=[a for a in actions if a.kind=='drive'];distance=sum(a.distance for a in drives);time=sum(a.travel_time for a in drives)
        fuel=sum(session.state.graph.get_edge(a.source,a.target).metadata['fuel_liters'] for a in drives)
        return {'distance':distance,'fuel_liters':fuel,'fuel_cost':fuel*float(rates['fuel_price']),
                'labor_cost':time/60*float(rates['driver_hourly']),'maintenance_cost':distance*float(rates['maintenance_per_km']),
                'total_cost':sum(a.cost for a in drives),'travel_time':time}
    return {**p,'presets':settings['presets'],'planned':summary([a for r in plan.routes for a in r.actions]) if plan else None,
            'executed':summary([e['action'] for e in session.events if e['kind']=='action']),
            'late_orders':[{'id':o.id,'deadline':o.deadline,'penalty':late_penalty} for o in session.state.orders.values() if o.status not in ('delivered','cancelled','expired') and session.state.now>o.deadline],
            'auto_replan':getattr(session,'_studio_auto_replan_status',None),
            'trial':session.state.config.get('studio_trial')}
