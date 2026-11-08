"""Private physical state for the opt-in completion-deadline workflow."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass,field
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any
from logiroute.algorithms.ordering import ordered_strings
from logiroute.core.enums import NodeType
from logiroute.graph import LogisticsGraph
from logiroute.scenario_generator.config_spec import GeneratorConfig
from logiroute.scenario_generator.graph_sampler import sample_logistics_graph
from logiroute.scenario_generator.random_source import RandomSource
from logiroute.dispatch.models import SCHEMA,RANK,Parcel,VehicleSpec,json_value


def load_config() -> dict[str,Any]:
    """Read exact original quantities. Time/Space O(config bytes)."""
    return json.loads((Path(__file__).resolve().parents[3]/'config/dispatch_v2.json').read_text(encoding='utf-8'),parse_float=Decimal)


@dataclass
class State:
    graph: LogisticsGraph
    config: dict[str,Any]
    orders: dict[str,Parcel]
    locations: dict[str,tuple[str,str]]
    vehicles: dict[str,VehicleSpec]
    positions: dict[str,str]
    now: float
    revision: int = 0
    traffic_version: int = 0
    protected: set[str] = field(default_factory=set)

    def fingerprint(self) -> str:
        """Canonical complete physical input digest; O(V²+E²+N²) manual ordering."""
        edges={e.source_id+'\0'+e.target_id:e for e in self.graph.edges}
        data=[json_value(self.config),self.now,self.revision,self.traffic_version,
              [[n.id,n.node_type.value,n.x,n.y] for n in (self.graph.get_node(k) for k in ordered_strings(n.id for n in self.graph.nodes))],
              [[e.source_id,e.target_id,e.distance,e.travel_time,e.cost,e.traffic_status.value] for e in (edges[k] for k in ordered_strings(edges))],
              [[k,json_value(self.orders[k]),self.locations[k]] for k in ordered_strings(self.orders)],
              [[k,json_value(self.vehicles[k]),self.positions[k]] for k in ordered_strings(self.vehicles)],ordered_strings(self.protected)]
        return hashlib.sha256(json.dumps(data,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def make_state(seed: int,config: dict[str,Any] | None = None) -> State:
    """Generate candidate input, not a promise of feasibility. Time/Space O(V²+E+N)."""
    c=deepcopy(load_config() if config is None else config)
    if isinstance(seed,bool) or not isinstance(seed,int): raise ValueError('seed must be integer')
    if c['schema_version']!=SCHEMA or c['time_window_rule']!='service_end': raise ValueError('unsupported contract')
    if c['cluster_metric']!='travel_time' or set(c['priority_weights'])!=set(RANK): raise ValueError('invalid priority/cluster configuration')
    if any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in c['priority_weights'].values()) or sum(c['priority_weights'].values())<=0:
        raise ValueError('invalid priority weights')
    if isinstance(c['orders_count'],bool) or not isinstance(c['orders_count'],int) or c['orders_count']<1: raise ValueError('invalid order count')
    for key,value in c['timing'].items():
        from logiroute.scheduling.fleet_paths import finite_time
        if isinstance(value,bool) or not isinstance(value,(int,float,Decimal)): raise ValueError('invalid timing scalar')
        finite_time(float(value),key,nonnegative=True); c['timing'][key]=float(value)
    if c.get('road_dataset'):
        from logiroute.dispatch.real_map import load_road_graph
        graph=load_road_graph(c)
    else:
        graph=sample_logistics_graph(GeneratorConfig(**c['graph']),RandomSource(seed))
    for field,expected in (('warehouse_ids',NodeType.WAREHOUSE),('hub_ids',NodeType.TRANSFER)):
        if not c[field] or len(c[field])!=len(set(c[field])): raise ValueError('duplicate/empty configured bases')
        if any(k not in graph.node_ids or graph.get_node(k).node_type is not expected for k in c[field]): raise ValueError('invalid configured base references')
    vehicles={}
    for row in c['vehicles']:
        car=VehicleSpec(**row)
        if car.id in vehicles or any(v.courier_id==car.courier_id for v in vehicles.values()): raise ValueError('duplicate vehicle/courier')
        expected=NodeType.WAREHOUSE if car.role=='trunk' else NodeType.TRANSFER
        if graph.get_node(car.base).node_type is not expected: raise ValueError('invalid vehicle base')
        vehicles[car.id]=car
    if len([v for v in vehicles.values() if v.role=='trunk'])!=1: raise ValueError('one trunk required')
    if len(set(c['hub_ids']))!=len(c['hub_ids']) or {v.base for v in vehicles.values() if v.role=='delivery'}!=set(c['hub_ids']): raise ValueError('hub bindings required')
    if len([v for v in vehicles.values() if v.role=='delivery'])!=len(c['hub_ids']): raise ValueError('one vehicle per hub required')
    if any(v.base not in c['warehouse_ids'] for v in vehicles.values() if v.role=='trunk'): raise ValueError('warehouse binding required')
    rng=RandomSource(seed); customers=ordered_strings(c.get('candidate_ids',[n.id for n in graph.nodes if n.node_type is NodeType.CUSTOMER]))
    if c.get('sample_unique_destinations') and c['orders_count']>len(customers): raise ValueError('order count exceeds unique candidate pool')
    orders={}; locations={}; t=c['timing']
    for i in range(c['orders_count']):
        draw=rng.randint(1,sum(c['priority_weights'].values())); priority='normal'
        for p in RANK:
            draw-=c['priority_weights'][p]
            if draw<=0: priority=p; break
        key=c['order_prefix']+str(i+1)
        destination=rng.choice(customers)
        if c.get('sample_unique_destinations'): customers.remove(destination)
        orders[key]=Parcel(key,destination,rng.choice(c['demand_choices']),t['window_start'],t['window_end'],priority)
        locations[key]=('warehouse',c['warehouse_ids'][0])
    return State(graph,c,orders,locations,vehicles,{k:v.base for k,v in vehicles.items()},t['initial'])
