"""Operational parameters and pressure windows; immutable prior sessions."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal,InvalidOperation
import json
from pathlib import Path
from typing import Any
from logiroute.core import Edge
from logiroute.dispatch.scenario import State,make_state
from logiroute.dispatch.models import RANK
from logiroute.dispatch.real_map import map_config
from logiroute.dispatch.session import Session,ConflictError
from logiroute.dispatch.time_windows import calibrate_windows,load_window_policy
from logiroute.algorithms.ordering import ordered_strings
from logiroute.scenario_generator.random_source import RandomSource


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
    hubs=parameters['hub_ids'];caps=parameters['capacities']
    single = state.config.get('single_vehicle', False)
    if single:
        if hubs != []:
            raise ValueError('single vehicle does not use transfer hubs')
        known = {v['id'] for v in base['vehicles'] if v['role'] == 'trunk'}
    else:
        known = {v['id'] for v in base['vehicles']}
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
                            'available_hubs':[] if single else [{'id':h,'name':trial.graph.get_node(h).name} for h in base['hub_ids']]}
    trial.graph.validate();return trial


def studio_state(seed: int,parameters: dict[str,Any],window_mode: str = 'strict',operational: bool = False,
                 *,single_vehicle: bool = False) -> State:
    """Explicit opt-in profile. Time bounded window construction; space O(state+plans)."""
    c=map_config('bjut-campus')
    if operational:
        c.update(json.loads((Path(__file__).resolve().parents[3]/'config/dispatch_bjut_operational.json').read_text(encoding='utf-8')))
    initial = make_state(seed, c)
    if single_vehicle:
        initial.config['single_vehicle'] = True
        warehouse_car = next(v for v in initial.vehicles.values() if v.role == 'trunk')
        parameters = {**parameters, 'hub_ids': [],
                      'capacities': {key: value for key, value in parameters['capacities'].items()
                                     if key == warehouse_car.id}}
    s=configure(initial,parameters)
    if operational:
        schedule=s.config['simulated_traffic']
        if (not isinstance(schedule,dict) or set(schedule)!={'interval_seconds','seed'}
                or isinstance(schedule['interval_seconds'],bool) or not isinstance(schedule['interval_seconds'],int)
                or not 1<=schedule['interval_seconds']<=3600
                or isinstance(schedule['seed'],bool) or not isinstance(schedule['seed'],int)):
            raise ValueError('invalid simulated traffic schedule')
    if window_mode in ('pressure','rush'):
        if not operational:raise ValueError('pressure windows require operational campus profile')
        rng=RandomSource(seed)
        if window_mode=='pressure':
            bounds=s.config['pressure_windows']
            for priority in ('critical','urgent','normal'):
                due=bounds[priority]
                if (not isinstance(due,list) or len(due)!=2 or any(isinstance(x,bool) or not isinstance(x,int) for x in due)
                        or due[0]<=0 or due[1]<due[0]):raise ValueError('invalid pressure window bounds')
        else:
            lengths=s.config['rush_window_lengths_minutes'];starts=s.config['rush_earliest_offsets_minutes']
            if not isinstance(s.config['rush_direct_critical_delivery'],bool):raise ValueError('invalid rush direct critical delivery setting')
            s.config['direct_critical_delivery']=s.config['rush_direct_critical_delivery']
            if not isinstance(lengths,dict) or not isinstance(starts,dict) or set(lengths)!=set(RANK) or set(starts)!=set(RANK):raise ValueError('invalid rush priority windows')
            for priority in ('critical','urgent','normal'):
                length=lengths[priority];start=starts[priority]
                if (not isinstance(length,list) or len(length)!=2 or any(isinstance(x,bool) or not isinstance(x,int) for x in length)
                        or length[0]<=0 or length[1]<length[0]):raise ValueError('invalid rush window lengths')
                if (not isinstance(start,list) or len(start)!=2 or any(isinstance(x,bool) or not isinstance(x,int) for x in start)
                        or start[0]<0 or start[1]<start[0]
                        or (priority=='critical' and (start[1]>=10 or length[1]>=15))
                        or (priority=='urgent' and (start[1]>=15 or length[1]>=20))):raise ValueError('invalid rush earliest offsets')
        deadline_policy=s.config['pressure_deadline_policy']
        if deadline_policy.get('mode')!='pressure' or deadline_policy.get('hard_priorities')!=['critical']:
            raise ValueError('invalid pressure deadline policy')
        s.config['late_delivery']=deepcopy(deadline_policy)
        s.config['operational_window_mode']=window_mode
        for key in ordered_strings(s.orders):
            order=s.orders[key]
            if window_mode=='pressure':
                width=rng.randint(*bounds[order.priority]);earliest=s.now;deadline=s.now+width
            else:
                start=rng.randint(*starts[order.priority]);length=rng.randint(*lengths[order.priority])
                earliest=s.now+start;deadline=earliest+length
            s.orders[key]=replace(order,earliest=earliest,deadline=deadline,
                                  allow_late=window_mode=='rush' and order.priority=='critical')
        s.config['window_evidence']={'mode':window_mode,'initial_only':True,'initial_time':s.now,
                                     'initial_traffic_version':s.traffic_version,'changed_vehicles':[],
                                     'baseline_late_orders':[],'window_min_minutes':min(o.deadline-o.earliest for o in s.orders.values()),
                                     'window_max_minutes':max(o.deadline-o.earliest for o in s.orders.values())}
        return s
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
    signed={oid:event['action'].end for event in session.events if event['kind']=='action' and event['action'].kind=='deliver'
            for oid in event['action'].ids}
    forecast_current=(plan is not None and not session._pausing and
                      session._planned_order_version==session._order_version and
                      plan.traffic_version==session.state.traffic_version)
    planned={oid:action.end for route in plan.routes for action in route.actions if action.kind=='deliver'
             for oid in action.ids} if forecast_current else {}
    late=[];predicted=[]
    for oid in ordered_strings(session.state.orders):
        order=session.state.orders[oid]
        if oid in signed and signed[oid]>order.deadline:
            late.append({'id':oid,'deadline':order.deadline,'signed_at':signed[oid],
                         'delay_minutes':signed[oid]-order.deadline,'status':'delivered','penalty':late_penalty})
        elif oid not in signed and order.status not in ('cancelled','expired') and session.state.now>order.deadline:
            late.append({'id':oid,'deadline':order.deadline,'signed_at':None,
                         'delay_minutes':session.state.now-order.deadline,'status':order.status,'penalty':late_penalty})
        if oid in planned and oid not in signed and order.status not in ('cancelled','expired') and planned[oid]>order.deadline:
            predicted.append({'id':oid,'deadline':order.deadline,'signoff':planned[oid],
                              'delay_minutes':planned[oid]-order.deadline,'priority':order.priority,'penalty':late_penalty})
    return {**p,'presets':settings['presets'],'planned':summary([a for r in plan.routes for a in r.actions]) if plan else None,
            'executed':summary([e['action'] for e in session.events if e['kind']=='action']),
            'late_orders':late,'planned_late_orders':predicted,
            'late_penalty_total':sum(row['penalty'] for row in late),
            'planned_late_penalty_total':sum(row['penalty'] for row in predicted),
            'auto_replan':getattr(session,'_studio_auto_replan_status',None),
            'trial':session.state.config.get('studio_trial')}
